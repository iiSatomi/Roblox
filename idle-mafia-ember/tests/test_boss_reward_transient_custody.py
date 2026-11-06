"""Current boss and source-wrapped monthly callbacks must be terminal to settle."""
import unittest
import test_bosses_runtime as boss_fixture
import test_boss_shop_runtime as shop_fixture
import test_global_boss_attack_runtime as global_fixture
import test_automation_runtime as runtime_fixture
import test_monthly_rewards as monthly_fixture
from engine_harness import lua_table
from runtime_entry_fixture import native_catalog


class BossRewardTransientCustodyTests(unittest.TestCase):
    def case(self, kind, returned):
        if kind == 'bosses':
            f = boss_fixture.BossesRuntimeTests(); f.setUp(); owner = f
            after = lambda revision, applied, delta: f.raw(revision, hp=150 if applied else 200,
                stamina=11 if applied else 12, server_now=2000000 + delta)
        elif kind == 'bossShop':
            f = shop_fixture.BossShopRuntimeTests(); f.setUp(); owner = f.f
            def after(revision, applied, delta):
                raw = f.raw(revision, tokens=2986 if applied else 3000, owned=3 if applied else 2)
                raw.native.serverNow += delta
                return raw
        else:
            f = global_fixture.GlobalBossAttackRuntimeTests(); f.setUp(); owner = f.f
            after = lambda revision, applied, delta: f.raw(revision, hits=3 if applied else 2,
                damage=125 if applied else 50, stamina=9 if applied else 10, now=2000100 + delta)
        self.addCleanup(f.tearDown)
        owner.executor.reply = lua_table(owner.h.lua, {'dmg': 75, **returned})
        f.begin()
        return f, owner, after

    def test_real_boss_callbacks_hold_original_charge_and_never_replay_after_timeout_or_restart(self):
        for kind in ('bosses', 'bossShop', 'globalBossAttack'):
            for code in ('busy', 'pending'):
                for ok in (False, True):
                    with self.subTest(kind=kind, code=code, ok=ok):
                        f, owner, after = self.case(kind, {'ok': ok, 'code': code})
                        key = owner.runtime.checkpoint.Records(owner.runtime.checkpoint)[1].actionKey
                        owner.h.at(1); owner.app.Step(owner.app, after(2, ok, 1))
                        records = owner.runtime.checkpoint.Records(owner.runtime.checkpoint)
                        self.assertEqual(len(records), 1)
                        self.assertEqual(records[1].actionKey, key)
                        owner.h.at(46); owner.app.Step(owner.app, after(3, ok, 46))
                        owner.restart(); owner.h.at(1); owner.app.Step(owner.app, after(0, ok, 47))
                        owner.drain()
                        records = owner.runtime.checkpoint.Records(owner.runtime.checkpoint)
                        self.assertEqual(len(records), 1)
                        self.assertEqual(records[1].actionKey, key)
                        saved = owner.runtime.checkpoint.Recovery(owner.runtime.checkpoint, key)[0]
                        self.assertEqual((saved.reply.ok, saved.reply.code), (ok, code))
                        self.assertEqual(len(owner.executor.calls), 1)


class MonthlyRewardTransientAppTests(unittest.TestCase):
    def prepare(self, returned, feature='monthlyRewards'):
        f = runtime_fixture.AutomationRuntimeTests(); f.setUp(); f.runtime.Close(f.runtime)
        self.f, self.h = f, f.h
        self.feature = feature
        self.executor = f.install_native_adapter(); self.executor.reply = lua_table(f.h.lua, returned)
        self.start()
        self.app.Set(self.app, feature + '.enabled', True); self.app.Resume(self.app)
        self.app.Step(self.app, self.raw()); self.executor.Drain(self.executor)
        self.assertEqual(len(self.executor.calls), 1, dict(f.runtime.Status(f.runtime).reasons.items()))

    def start(self):
        f, h = self.f, self.h
        config = native_catalog()['config']
        config['MONTHLY_CALENDAR'] = {'enabled': True, 'days': {1: {'kind': 'gold', 'amount': 2}}}
        deps = {'config': config, 'fingerprint': 'a' * 64, 'release': h.session['release'], 'rewardsSource': f.rewards_source}
        for row in h.load('src/engine/FeatureRegistry.luau').requirements().values():
            if row.id in ('groupBonus', 'playtime', 'monthlyRewards'):
                for field, directory in (('reader', 'game'), ('planner', 'features'), ('evidence', 'features')):
                    deps[row[field]] = h.load('src/' + directory + '/' + row[field] + '.luau')
        for name in ('NativeRewardsCatalog', 'RewardEffects'): deps[name] = h.load('src/tabs/rewards/' + name + '.luau')
        self.tab = h.load('src/tabs/rewards/Module.luau').new(lua_table(h.lua, deps))
        descriptors = self.tab.Descriptors(self.tab)
        f.runtime = h.load('src/engine/AutomationRuntime.luau').new(lua_table(h.lua, {
            'clock': h.clock, 'transport': h.load('src/transport/NativeDispatchAdapter.luau').new(
                h.load('src/transport/NativeCallPlan.luau'), self.executor), 'storage': f.storage,
            'identity': h.session, 'modules': f.runtime.modules, 'features': descriptors,
            'featurePages': {row.id: 'rewards' for row in descriptors.values()}, 'tabInstances': [self.tab],
            'snapshotAssembler': h.load('src/tabs/TabSnapshotAssembler.luau').new(lua_table(h.lua, [self.tab]))}))
        self.app = f.start_test_app()

    def raw(self, revision=1, awarded=False, delta=0):
        raw = self.h.snapshot(revision=revision, native={'fullSync': True,
            'serverNow': monthly_fixture.utc(2026, 10, 20) + delta,
            'inventory': {'gold_bar': 2 if awarded else 0}, 'inventoryBound': {},
            'monthly': {'month': '2026-10', 'claimed': 1, 'lastDay': 2026293} if awarded else None})
        if self.feature == 'playtime':
            raw.native.monthly = None
            raw.native.level, raw.native.maxLevel = 1, 1
            raw.native.derived = lua_table(self.h.lua, {'effMaxEnergy': 40})
            raw.native.pools = lua_table(self.h.lua, {'energy': 40 if awarded else 20})
            raw.native.playtime = lua_table(self.h.lua, {'todaySeconds': 20000,
                'laddersClaimed': {'1': 1} if awarded else {}})
        return raw

    def tearDown(self):
        if getattr(self, 'app', None): self.app.Destroy(self.app)

    def test_source_wrapped_monthly_busy_and_pending_preserve_receipt_after_timeout_and_reload(self):
        for code in ('busy', 'pending'):
            for ok in (False, True):
                with self.subTest(code=code, ok=ok):
                    self.prepare({'ok': ok, 'code': code})
                    key = self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)[1].actionKey
                    self.h.at(1); self.app.Step(self.app, self.raw(2, ok, 1))
                    self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)), 1)
                    self.h.at(46); self.app.Step(self.app, self.raw(3, ok, 46))
                    self.app.Destroy(self.app); self.h.session['session'] = 'restarted-monthly'; self.start()
                    self.h.at(47); self.app.Step(self.app, self.raw(0, ok, 47)); self.executor.Drain(self.executor)
                    records = self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)
                    self.assertEqual(len(records), 1)
                    self.assertEqual(records[1].actionKey, key)
                    self.assertEqual(len(self.executor.calls), 1)
                    self.app.Destroy(self.app)

    def test_source_wrapped_playtime_busy_and_pending_hold_exact_marker_and_refill(self):
        for code in ('busy', 'pending'):
            for ok in (False, True):
                with self.subTest(code=code, ok=ok):
                    self.prepare({'ok': ok, 'code': code}, feature='playtime')
                    key = self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)[1].actionKey
                    self.h.at(1); self.app.Step(self.app, self.raw(2, ok, 1))
                    records = self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)
                    self.assertEqual(len(records), 1)
                    self.assertEqual(records[1].actionKey, key)
                    self.h.at(46); self.app.Step(self.app, self.raw(3, ok, 46))
                    self.app.Destroy(self.app); self.h.session['session'] = 'restarted-playtime'; self.start()
                    self.h.at(47); self.app.Step(self.app, self.raw(0, ok, 47)); self.executor.Drain(self.executor)
                    records = self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)
                    self.assertEqual(len(records), 1)
                    self.assertEqual(records[1].actionKey, key)
                    self.assertEqual(len(self.executor.calls), 1)
                    self.app.Destroy(self.app)


if __name__ == '__main__': unittest.main()
