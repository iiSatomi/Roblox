"""Selected Skill points stay held until exact terminal allocation or rejection."""
import unittest
import test_skills as fixture
import test_automation_runtime as runtime_fixture
from engine_harness import lua_table
from runtime_entry_fixture import native_catalog
from test_legacy_completion_receipts import plain


class SkillsEvidenceLifecycleTests(unittest.TestCase):
    def prepare(self, returned=None, count=1):
        f = runtime_fixture.AutomationRuntimeTests(); f.setUp(); f.runtime.Close(f.runtime)
        source = fixture.SkillsTests(); source.setUp(); source.h = f.h
        self.f, self.h, self.source, self.count = f, f.h, source, count
        self.executor = f.install_native_adapter(); self.executor.reply = lua_table(f.h.lua, returned or {'ok': True})
        self.app = None; self.start()
        for key, value in (('skills.enabled', True), ('skills.custom.stat', 'energy'),
                           ('skills.custom.maxAllocations', 4 + count), ('skills.custom.batchSize', count)):
            self.assertTrue(self.app.Set(self.app, key, value)[0])
        self.app.Resume(self.app); self.before = self.raw()
        self.app.Step(self.app, self.before); self.executor.Drain(self.executor)
        self.assertEqual(len(self.executor.calls), 1, dict(self.f.runtime.Status(self.f.runtime).reasons.items()))
        record = self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)[1]
        self.action_key = record.actionKey
        self.saved = self.f.runtime.checkpoint.Recovery(self.f.runtime.checkpoint, self.action_key)[0]
        self.cost = self.saved.baseline.cost

    def start(self):
        h, f = self.h, self.f
        deps = {'config': native_catalog()['config'], 'fingerprint': 'a' * 64, 'release': h.session['release']}
        for name, directory in (('SkillsState', 'game'), ('Skills', 'features'),
                                ('SkillsEvidence', 'features'), ('NativeSkillCatalog', 'tabs/skills')):
            deps[name] = h.load('src/' + directory + '/' + name + '.luau')
        self.tab = h.load('src/tabs/skills/Module.luau').new(lua_table(h.lua, deps))
        f.runtime = h.load('src/engine/AutomationRuntime.luau').new(lua_table(h.lua, {
            'clock': h.clock, 'transport': h.load('src/transport/NativeDispatchAdapter.luau').new(
                h.load('src/transport/NativeCallPlan.luau'), self.executor), 'storage': f.storage,
            'identity': h.session, 'modules': f.runtime.modules, 'features': self.tab.Descriptors(self.tab),
            'featurePages': {'skills': 'skills'}, 'tabInstances': [self.tab],
            'snapshotAssembler': h.load('src/tabs/TabSnapshotAssembler.luau').new(lua_table(h.lua, [self.tab]))}))
        self.app = f.start_test_app()

    def raw(self, revision=1, points=12, allocated=4, other=0, clock_delta=None):
        raw = self.source.raw(revision, points=points, allocs={'energy': allocated, 'attack': other})
        raw.skillRules = None; raw.catalogKey = 'a' * 64
        raw.native.serverNow = 1000 + (self.h.lua.globals().testNow if clock_delta is None else clock_delta)
        return raw

    def restart(self, enable=False):
        self.app.Destroy(self.app); self.h.session['session'] = 'restarted-skill-owner'; self.start()
        self.app.Set(self.app, 'skills.enabled', enable)
        self.app.Set(self.app, 'skills.custom.maxAllocations', 4 + self.count)
        self.app.Set(self.app, 'skills.custom.batchSize', self.count)
        self.app.Resume(self.app)

    def tearDown(self):
        if getattr(self, 'app', None): self.app.Destroy(self.app)

    def test_transient_exact_effects_or_unchanged_negative_hold_across_timeout_and_restart(self):
        for transient in ({'pending': True}, {'code': 'pending'}, {'code': 'busy'},
                          {'code': 'presence'}, {'code': 'rate_limited'}):
            for ok in (False, True):
                with self.subTest(transient=transient, ok=ok):
                    self.prepare({'ok': ok, **transient}); immutable = plain(self.saved)
                    self.h.at(1)
                    current = self.raw(2, 12 - self.cost if ok else 12, 5 if ok else 4)
                    self.app.Step(self.app, current)
                    self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)), 1)
                    self.h.at(46); self.app.Step(self.app, self.raw(3, 12 - self.cost if ok else 12, 5 if ok else 4))
                    self.assertEqual(self.f.runtime.reservationOwner.Held(self.f.runtime.reservationOwner, current)[0].funds.skillPoints, self.cost)
                    self.restart(enable=True); self.h.at(47)
                    self.app.Step(self.app, self.raw(0, 12 - self.cost if ok else 12, 5 if ok else 4))
                    self.executor.Drain(self.executor)
                    records = self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)
                    self.assertEqual(len(records), 1)
                    self.assertEqual(records[1].actionKey, self.action_key)
                    self.assertEqual(len(self.executor.calls), 1)
                    self.assertEqual(plain(self.saved), immutable)
                    self.app.Destroy(self.app)

    def test_partial_negative_and_changed_other_stat_never_release_point_custody(self):
        for points, allocated, other in ((11, 4, 0), (12, 5, 0), (11, 5, 0), (12, 4, 1)):
            with self.subTest(points=points, allocated=allocated, other=other):
                self.prepare({'ok': False}, count=2); self.h.at(1)
                self.app.Step(self.app, self.raw(2, points, allocated, other))
                records = self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)
                self.assertEqual(len(records), 1)
                self.assertEqual(records[1].actionKey, self.action_key)
                self.assertEqual(len(self.executor.calls), 1)
                self.app.Destroy(self.app)

    def test_terminal_unchanged_rejection_requires_new_sync_and_keeps_normal_success(self):
        for ok in (False, True):
            with self.subTest(ok=ok):
                self.prepare({'ok': ok}); self.app.Step(self.app, self.raw())
                self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)), 1)
                self.h.at(1); self.app.Step(self.app, self.raw(2, 12 - self.cost if ok else 12, 5 if ok else 4))
                self.assertEqual(self.f.runtime.Status(self.f.runtime).outcomes.skills, 'confirmed' if ok else 'rejected')
                self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)), 0)
                self.assertEqual(len(self.executor.calls), 1)
                self.app.Destroy(self.app)

    def test_real_skill_tab_recovers_only_exact_terminal_saved_cost_and_allocation(self):
        for ok in (False, True):
            with self.subTest(ok=ok):
                self.prepare({'ok': ok}); immutable = plain(self.saved)
                self.restart(); self.h.at(1)
                self.app.Step(self.app, self.raw(0, 12 - self.cost if ok else 12, 5 if ok else 4, clock_delta=0))
                self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)), 1)
                self.h.at(2); self.app.Step(self.app, self.raw(1, 12 - self.cost if ok else 12, 5 if ok else 4))
                self.assertEqual(self.f.runtime.Status(self.f.runtime).recoveries.skills, 'confirmed' if ok else 'rejected')
                self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)), 0)
                self.assertEqual(len(self.executor.calls), 1)
                self.assertEqual(plain(self.saved), immutable)
                self.app.Destroy(self.app)


if __name__ == '__main__': unittest.main()
