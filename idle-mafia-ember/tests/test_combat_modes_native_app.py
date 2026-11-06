"""Actual Combat policy/native-owner composition; no live RPC or source bypass."""
import unittest
import test_player_combat_planner_app as planner_fixture
import test_native_combat_app as native_fixture
import test_runtime_host as host_fixture
from engine_harness import lua_table


class CombatModesNativeAppTests(unittest.TestCase):
    def setUp(self):
        self.p = planner_fixture.PlayerCombatPlannerAppTests()
        self.p.setUp()
        self.f, self.h, self.app = self.p.f, self.p.h, self.p.app
        self.native = native_fixture.NativeCombatAppTests()
        self.native.h = self.h
        self.native.attach(self.f)
        self.port, self.owner = self.native.port, self.native.owner

    def allowance(self):
        return self.f.runtime.checkpoint.Allowance(self.f.runtime.checkpoint, 'combat')[0]

    def test_cautious_and_balanced_each_dispatch_settle_and_preserve_separate_caps(self):
        for policy in ('Cautious', 'Balanced'):
            with self.subTest(policy=policy):
                if policy == 'Balanced':
                    self.tearDown()
                    self.setUp()
                self.assertTrue(self.app.Set(self.app, 'combat.policy', policy)[0])
                self.f.begin()
                self.f.send()
                self.assertEqual(self.h.lua.eval('type')(self.port.attackBusy), 'table')
                self.f.result.after.native.stats = lua_table(self.h.lua, {'maxHealth': 100})
                self.f.settle()
                self.assertEqual(self.f.runtime.Status(self.f.runtime).outcomes.combat, 'confirmed')
                self.assertEqual((self.allowance().attackAttempted, self.allowance().attackSpent), (1, 5))
                self.assertEqual((self.allowance().scoutAttempted, self.allowance().scoutSpent), (0, 0))
                self.assertEqual(self.f.ledger.Summary(self.f.ledger).fights, 1)
                self.assertFalse(self.port.attackBusy)
                self.assertEqual(self.f.executor.calls, 1)

    def test_cautious_floor_remains_stricter_than_balanced_explicit_chance(self):
        self.f.tab.playerProfiles.cache['42'].defense = 180
        self.app.Set(self.app, 'combat.custom.minWinChance', 60)
        self.app.Set(self.app, 'combat.custom.minWinRate', 0)
        self.app.Set(self.app, 'combat.policy', 'Cautious')
        self.app.Set(self.app, 'combat.enabled', True)
        self.app.Resume(self.app)
        self.f.step()
        self.assertEqual(len(self.f.executor.queued), 0)
        self.assertEqual(self.port.writes, 0)
        self.app.Set(self.app, 'combat.policy', 'Balanced')
        self.f.step()
        self.assertEqual(len(self.f.executor.queued), 1)
        self.f.send()
        self.assertEqual(self.allowance().attackSpent, 5)
        self.assertEqual(self.allowance().scoutSpent, 0)

    def test_policy_change_to_cautious_cancels_a_queued_balanced_attack(self):
        self.f.tab.playerProfiles.cache['42'].defense = 180
        self.app.Set(self.app, 'combat.custom.minWinChance', 60)
        self.app.Set(self.app, 'combat.policy', 'Balanced')
        self.f.begin()
        self.app.Set(self.app, 'combat.policy', 'Cautious')
        self.f.executor.queued[1]()
        self.assertEqual(self.f.executor.calls, 0)
        self.assertEqual(self.port.writes, 0)
        self.assertEqual(self.allowance().attackSpent, 0)
        self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)), 0)

    def test_native_challenge_winning_queue_race_is_preserved_without_charge(self):
        self.f.begin()
        self.port.confirmation = True
        self.f.executor.queued[1]()
        self.assertEqual(self.f.executor.calls, 0)
        self.assertTrue(self.port.confirmation)
        self.assertEqual(self.port.writes, 0)
        self.assertEqual(self.allowance().attackSpent, 0)
        self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)), 0)
        self.app.Destroy(self.app)
        self.assertTrue(self.port.confirmation)
        self.assertTrue(self.port.restored)

    def test_source_retirement_before_dispatch_refunds_only_unsent_work(self):
        self.f.begin()
        self.port.valid = False
        self.f.source.Current = self.h.lua.eval('function() return false end')
        self.f.executor.queued[1]()
        self.assertEqual(self.f.executor.calls, 0)
        self.assertEqual(self.allowance().attackSpent, 0)
        self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)), 0)
        self.assertFalse(self.owner.Status(self.owner).active)
        self.assertTrue(self.owner.Status(self.owner).closed)
        self.assertFalse(self.port.attackBusy)

    def test_source_retirement_while_rpc_yields_retains_sent_custody_no_replay(self):
        self.f.executor.InvokeOwned = self.h.lua.eval('''function(self)
            self.calls=self.calls+1;coroutine.yield('combat-native-wait');return fixtureFightReply
        end''')
        self.f.begin()
        self.h.lua.globals().combatQueuedCall = self.f.executor.queued[1]
        thread = self.h.lua.eval('coroutine.create(combatQueuedCall)').coroutine()
        self.assertEqual(next(thread), 'combat-native-wait')
        self.assertTrue(self.owner.Status(self.owner).physical)
        self.port.valid = False
        self.f.source.Current = self.h.lua.eval('function() return false end')
        self.assertTrue(self.owner.Status(self.owner).closed)
        self.assertTrue(self.owner.Status(self.owner).physical)
        self.assertFalse(self.port.attackBusy)
        self.assertRaises(StopIteration, next, thread)
        self.assertFalse(self.owner.Status(self.owner).physical)
        self.h.at(45)
        raw = self.f.result.after
        raw.capturedAt = 45
        raw.native.stats = lua_table(self.h.lua, {'maxHealth': 100})
        self.f.step(raw)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).outcomes.combat, 'skipped_unconfirmed')
        self.assertEqual((self.allowance().attackAttempted, self.allowance().attackSpent), (1, 5))
        self.assertEqual(self.allowance().scoutSpent, 0)
        self.assertEqual(self.f.ledger.Summary(self.f.ledger).fights, 0)
        self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)), 1)
        self.assertEqual(self.f.executor.calls, 1)
        self.assertEqual(len(self.f.executor.queued), 1)

    def test_native_presence_reply_keeps_manual_prompt_and_sent_allowance(self):
        self.h.lua.globals().challengePort = self.port
        self.f.source.HandleReply = self.h.lua.eval('''function(self,reply)
            if reply.code=='presence' then self.challengeObserved=true;challengePort.confirmation=true end
            return true
        end''')
        self.h.lua.globals().fixtureFightReply = lua_table(self.h.lua, {'ok': False, 'code': 'presence'})
        self.f.begin()
        self.f.send()
        self.assertTrue(self.f.source.challengeObserved)
        self.assertTrue(self.port.confirmation)
        self.h.at(45)
        raw = self.f.result.before
        raw.revision += 1
        raw.capturedAt = 45
        raw.native.serverNow += 45
        self.f.step(raw)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).outcomes.combat, 'skipped_unconfirmed')
        self.assertEqual(self.allowance().attackSpent, 5)
        self.assertEqual(self.f.ledger.Summary(self.f.ledger).fights, 0)
        self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)), 1)
        self.assertTrue(self.port.confirmation)
        self.assertFalse(self.port.attackBusy)
        self.assertEqual(self.f.executor.calls, 1)

    def transfer_host(self):
        host = host_fixture.RuntimeHostTests()
        host.provided_h = self.h
        host.setUp()
        signal = host.teleport_signal()
        self.h.lua.globals().transferActualApp = self.app
        host.deps.App.start = self.h.lua.eval('function() return transferActualApp end')
        owner, why = host.host_module.start(host.deps)
        self.assertIsNotNone(owner, why)
        self.addCleanup(lambda: owner.Destroy(owner))
        return owner, signal

    def test_automatic_server_movement_closes_actual_combat_before_queued_send(self):
        self.f.begin()
        host, signal = self.transfer_host()
        signal.callback(lua_table(self.h.lua, {'Name': 'Started'}))
        self.f.executor.queued[1]()
        self.assertFalse(host.active)
        self.assertFalse(self.app.alive)
        self.assertTrue(self.owner.Status(self.owner).closed)
        self.assertTrue(self.port.restored)
        self.assertFalse(self.port.attackBusy)
        self.assertEqual(self.f.executor.calls, 0)

    def test_automatic_server_movement_fences_inflight_reply_and_retains_uncertainty(self):
        self.f.executor.InvokeOwned = self.h.lua.eval('''function(self)
            self.calls=self.calls+1;coroutine.yield('combat-native-wait');return fixtureFightReply
        end''')
        self.f.begin()
        host, signal = self.transfer_host()
        self.h.lua.globals().combatQueuedCall = self.f.executor.queued[1]
        thread = self.h.lua.eval('coroutine.create(combatQueuedCall)').coroutine()
        self.assertEqual(next(thread), 'combat-native-wait')
        callback = self.f.source.callback
        signal.callback(lua_table(self.h.lua, {'Name': 'InProgress'}))
        self.assertFalse(host.active)
        self.assertFalse(self.app.alive)
        self.assertTrue(self.owner.Status(self.owner).physical)
        self.assertFalse(self.port.attackBusy)
        callback('fightcash', '', lua_table(self.h.lua, self.f.result.final))
        self.assertRaises(StopIteration, next, thread)
        self.assertFalse(self.owner.Status(self.owner).physical)
        self.assertEqual(self.allowance().attackSpent, 5)
        self.assertEqual(self.f.ledger.Summary(self.f.ledger).fights, 0)
        self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)), 1)
        self.assertEqual(self.f.executor.calls, 1)
        self.assertEqual(len(self.f.executor.queued), 1)

    def tearDown(self):
        self.p.tearDown()
