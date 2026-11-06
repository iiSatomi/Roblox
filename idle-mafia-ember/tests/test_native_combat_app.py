"""Actual App lifecycle keeps native manual controls inside owned dispatch."""
import unittest
import test_player_fight_app as fight_fixture
import test_player_scout_app as scout_fixture
from engine_harness import lua_table

class NativeCombatAppTests(unittest.TestCase):
    def setUp(self):
        self.f=fight_fixture.PlayerFightAppTests();self.f.setUp();self.h=self.f.h;self.attach(self.f)
    def attach(self,f):
        h=self.h
        self.port=h.lua.execute("""return {nonYielding=true,attackBusy=false,calls=0,writes=0,valid=true,
            Current=function(s) return s.valid end,
            Read=function(s) return {attackBusy=s.attackBusy,scoutGeneration=0,scoutBusy=false,confirmationPending=s.confirmation==true,modalOpen=false} end,
            CompareAttackBusy=function(s,a,b) if s.attackBusy~=a then return false end;s.attackBusy=b;s.writes=s.writes+1;return true end,
            Install=function(s,gate) s.gateway=gate;return {} end,
            Restore=function(s) s.restored=true;return true end}""")
        self.owner,why=h.load('src/tabs/combat/NativeCombatLease.luau').new(self.port,h.clock,lua_table(h.lua,h.session),h.lua.table());self.assertIsNotNone(self.owner,why)
        f.transport.combatLease=self.owner;f.transport.requireCombatLease=True;f.tab.nativeCombatLease=self.owner
        h.lua.globals().nativeControlPort=self.port
        f.source.CanAttack=h.lua.eval('function() return nativeControlPort.attackBusy==false end')
        if f.source.CanScout is not None:f.source.CanScout=h.lua.eval('function() return nativeControlPort.attackBusy==false end')
    def test_owned_attack_blocks_native_competitor_and_settles_with_busy_guard_held(self):
        f=self.f;f.begin();f.send();self.assertEqual(self.h.lua.eval('type')(self.port.attackBusy),'table')
        self.assertIsNone(self.port.gateway('Attack',self.h.lua.eval('function() error("Native competitor must not send") end'),42))
        f.settle();self.assertEqual(f.runtime.Status(f.runtime).outcomes.combat,'confirmed');self.assertFalse(self.port.attackBusy)
        self.assertEqual(f.ledger.Summary(f.ledger).fights,1);self.assertEqual(f.executor.calls,1)
    def test_native_confirmation_winning_final_dispatch_race_is_unsent_and_refunded(self):
        f=self.f;f.begin();self.port.confirmation=True;f.executor.queued[1]()
        self.assertEqual(f.executor.calls,0);self.assertFalse(self.port.attackBusy);self.assertTrue(self.port.confirmation)
        self.assertEqual(f.runtime.checkpoint.Allowance(f.runtime.checkpoint,'combat')[0].attackSpent,0)
    def test_queued_disable_or_unload_never_acquires_native_guard_or_invokes(self):
        f=self.f;f.begin();f.app.Set(f.app,'combat.enabled',False);f.executor.queued[1]()
        self.assertEqual(self.port.writes,0);self.assertEqual(f.executor.calls,0)
        f.app.Destroy(f.app);self.assertTrue(self.port.restored)
    def test_expiry_releases_guard_keeps_custody_and_never_counts_native_rpc_as_outcome(self):
        f=self.f;f.begin();f.send();self.h.at(45);f.result.after.capturedAt=45;f.step(f.result.after)
        self.assertFalse(self.port.attackBusy);self.assertEqual(f.runtime.Status(f.runtime).outcomes.combat,'skipped_unconfirmed')
        self.assertEqual(len(f.runtime.checkpoint.Records(f.runtime.checkpoint)),1);self.assertEqual(f.ledger.Summary(f.ledger).fights,0)
    def test_owner_denial_before_executor_callback_is_definitely_unsent(self):
        f=self.f;self.owner.Invoke=self.h.lua.eval('function() return false,"owner retired" end');f.begin();f.executor.queued[1]()
        self.assertEqual(f.executor.calls,0);self.assertFalse(self.port.attackBusy)
        self.assertEqual(len(f.runtime.checkpoint.Records(f.runtime.checkpoint)),0)
        self.assertEqual(f.runtime.checkpoint.Allowance(f.runtime.checkpoint,'combat')[0].attackSpent,0)
    def test_native_scout_uses_same_owned_dispatch_and_independent_cache_acceptance(self):
        self.f.tearDown();s=scout_fixture.PlayerScoutAppTests();s.setUp();self.f=s.f;self.h=s.h;self.attach(self.f)
        self.f.begin();self.f.send();self.assertEqual(self.h.lua.eval('type')(self.port.attackBusy),'table')
        s.settle();self.assertEqual(self.f.runtime.Status(self.f.runtime).outcomes.combat,'confirmed');self.assertFalse(self.port.attackBusy)
        self.assertEqual(s.usage().scoutSpent,5);self.assertEqual(s.usage().attackSpent,0)
    def tearDown(self):self.f.tearDown()
