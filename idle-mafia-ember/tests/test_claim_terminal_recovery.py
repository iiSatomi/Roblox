"""Original terminal receipts reconcile through real Rewards/Contracts descriptors."""
import unittest

from engine_harness import lua_table
from runtime_entry_fixture import native_catalog
import test_automation_runtime as runtime_fixture
import test_claim_callback_custody as claim_fixture


KINDS = ('groupBonus', 'contracts', 'bonuses')


class ClaimTerminalRecoveryTests(unittest.TestCase):
    def prepare(self, kind, returned=None, weekly=False):
        f = runtime_fixture.AutomationRuntimeTests(); f.setUp()
        source = claim_fixture.CASES[kind](); source.setUp(); source.h = f.h
        f.runtime.Close(f.runtime)
        config = native_catalog()['config']; config['GROUP']['incomeBonus'] = .15
        self.config = lua_table(f.h.lua, config)
        self.f, self.source, self.kind = f, source, kind
        self.weekly = weekly
        self.executor = f.install_native_adapter()
        self.executor.reply = lua_table(f.h.lua, returned or {'ok': True})
        self.app = None
        self.start()
        self.app.Set(self.app, kind + '.enabled', True); self.app.Resume(self.app)
        self.before = self.raw()
        self.app.Step(self.app, self.before); self.executor.Drain(self.executor)
        self.assertEqual(len(self.executor.calls), 1, dict(f.runtime.Status(f.runtime).reasons.items()))
        records = f.runtime.checkpoint.Records(f.runtime.checkpoint)
        self.assertEqual(len(records), 1)
        self.action_key = records[1].actionKey
        self.saved = f.runtime.checkpoint.Recovery(f.runtime.checkpoint, self.action_key)[0]
        self.assertIsNotNone(self.saved.reply)

    def start(self):
        f, h = self.f, self.f.h
        deps = {k: v for k, v in f.runtime.modules.items()}
        required = ('groupBonus', 'playtime', 'monthlyRewards') if self.kind == 'groupBonus' else ('contracts', 'bonuses')
        for row in h.load('src/engine/FeatureRegistry.luau').requirements().values():
            if row.id in required:
                for field, directory in (('reader', 'game'), ('planner', 'features'), ('evidence', 'features')):
                    deps[row[field]] = h.load('src/' + directory + '/' + row[field] + '.luau')
        deps.update(config=self.config, fingerprint='a' * 64, release=h.session['release'], rewardsSource=f.rewards_source)
        if self.kind == 'groupBonus':
            folder, names = 'rewards', ('NativeRewardsCatalog', 'RewardEffects')
        else:
            folder, names = 'contracts', ('NativeContractCatalog', 'ContractGoalState', 'ContractGoalBlocked', 'ContractCashQuote')
        for name in names: deps[name] = h.load('src/tabs/' + folder + '/' + name + '.luau')
        self.tab = h.load('src/tabs/' + folder + '/Module.luau').new(lua_table(h.lua, deps))
        self.tabs = lua_table(h.lua, [self.tab])
        descriptors = self.tab.Descriptors(self.tab)
        f.runtime = h.load('src/engine/AutomationRuntime.luau').new(lua_table(h.lua, {
            'clock': h.clock, 'transport': h.load('src/transport/NativeDispatchAdapter.luau').new(
                h.load('src/transport/NativeCallPlan.luau'), self.executor),
            'storage': f.storage, 'identity': h.session, 'modules': f.runtime.modules,
            'features': descriptors,
            'featurePages': {row.id: folder for row in descriptors.values()}, 'tabInstances': self.tabs,
            'snapshotAssembler': h.load('src/tabs/TabSnapshotAssembler.luau').new(self.tabs)}))
        self.app = f.start_test_app()

    def raw(self, revision=1, awarded=False, clock_delta=0):
        raw = claim_fixture.frame(self.source, self.kind, revision, awarded)
        raw.catalogKey = 'a' * 64
        for field in ('groupConfig', 'contractConfig', 'contractBonusConfig'):
            raw[field] = None  # Only the real tab may attach its native catalog.
        raw.native.serverNow += clock_delta
        if self.weekly:
            for row in raw.native.contracts.daily.values():
                row.done, row.claimed = True, True
            if self.kind == 'contracts':
                raw.native.contracts.weekly = lua_table(self.f.h.lua, {
                    'id': 'w_legacy', 'done': True, 'claimed': awarded})
            else:
                raw.native.contracts.bonusClaimed = True
                raw.native.contracts.weekly = lua_table(self.f.h.lua, {'id': 'w_legacy', 'claimed': True})
                raw.native.contracts.weeklyBonusClaimed = awarded
        return raw

    def restart(self):
        self.app.Destroy(self.app)
        self.f.h.session['session'] = 'restarted-owned-run'
        self.start()
        self.app.Resume(self.app)

    def tearDown(self):
        if getattr(self, 'app', None): self.app.Destroy(self.app)

    def test_normal_tabs_reconcile_saved_terminal_positive_without_a_second_send(self):
        for kind in KINDS:
            with self.subTest(kind=kind):
                self.prepare(kind)
                from test_legacy_completion_receipts import plain
                immutable = plain(self.saved)
                self.restart(); self.f.h.at(1)
                after = self.raw(0, True, 1)
                self.app.Step(self.app, after); self.executor.Drain(self.executor)
                self.assertEqual(self.f.runtime.Status(self.f.runtime).recoveries[kind], 'confirmed')
                self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)), 0)
                self.assertEqual(len(self.executor.calls), 1)
                self.assertEqual(plain(self.saved), immutable)
                self.app.Destroy(self.app)

    def test_negative_exact_unchanged_recovery_requires_strict_native_clock(self):
        for kind in KINDS:
            with self.subTest(kind=kind):
                self.prepare(kind, {'ok': False}); self.restart(); self.f.h.at(1)
                self.app.Step(self.app, self.raw(0))
                self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)), 1)
                self.f.h.at(2); self.app.Step(self.app, self.raw(1, False, 1))
                self.assertEqual(self.f.runtime.Status(self.f.runtime).recoveries[kind], 'rejected')
                self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)), 0)
                self.assertEqual(len(self.executor.calls), 1)
                self.app.Destroy(self.app)

    def test_transient_terminal_markers_remain_held_after_real_tab_restart(self):
        for kind in KINDS:
            for returned in ({'ok': True, 'pending': True}, {'ok': True, 'code': 'busy'},
                             {'ok': False, 'code': 'presence'}):
                with self.subTest(kind=kind, reply=returned):
                    self.prepare(kind, returned); self.restart(); self.f.h.at(46)
                    self.app.Step(self.app, self.raw(0, True, 46)); self.executor.Drain(self.executor)
                    self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)), 1)
                    self.assertEqual(len(self.executor.calls), 1)
                    self.app.Destroy(self.app)

    def test_contract_other_row_reset_or_selected_identity_changes_cannot_settle(self):
        for kind in ('contracts', 'bonuses'):
            for ok in (False, True):
                for change in ('other-row', 'reset', 'selected-id'):
                    with self.subTest(kind=kind, ok=ok, change=change):
                        self.prepare(kind, {'ok': ok}); self.restart(); self.f.h.at(1)
                        after = self.raw(0, ok, 1)
                        if change == 'other-row': after.native.contracts.daily[2].id = 'replacement-row'
                        elif change == 'reset': after.native.derived.contractDayReset += 86400
                        else: after.native.contracts.daily[1].id = 'replacement-selected'
                        self.app.Step(self.app, after)
                        self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)), 1)
                        self.assertEqual(len(self.executor.calls), 1)
                        self.app.Destroy(self.app)

    def test_group_changed_source_effect_and_forged_saved_baseline_stay_held(self):
        for change in ('effect', 'method', 'saved-baseline'):
            with self.subTest(change=change):
                self.prepare('groupBonus')
                self.restart(); self.f.h.at(1)
                after = self.raw(0, True, 1)
                if change == 'effect': self.tab.catalog.groupIncomeBonus = .2
                elif change == 'method':
                    self.f.h.lua.globals().originalGroupEffect = self.tab.catalog.GroupEffect
                    self.tab.catalog.GroupEffect = self.f.h.lua.eval('function(s,r)return originalGroupEffect(s,r)end')
                else:
                    # Exercise the descriptor's real adapter against a detached,
                    # altered baseline; never edit the checkpoint or its scope.
                    from test_legacy_completion_receipts import plain
                    changed = lua_table(self.f.h.lua, plain(self.saved))
                    changed.baseline.effect.incomeBonus = .2
                    enriched = self.tab.Enrich(self.tab, after)[0]
                    spec = self.f.runtime.features.groupBonus
                    self.assertIsNotNone(spec.recoverSaved)
                    self.assertIsNone(spec.recoverSaved(changed, enriched))
                    self.app.Destroy(self.app); continue
                self.app.Step(self.app, after)
                self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)), 1)
                self.app.Destroy(self.app)

    def test_legacy_single_weekly_rows_keep_the_original_index_and_reset(self):
        for kind in ('contracts', 'bonuses'):
            for ok in (False, True):
                with self.subTest(kind=kind, ok=ok):
                    self.prepare(kind, {'ok': ok}, weekly=True)
                    self.assertEqual(self.saved.baseline.period, 'weekly')
                    self.restart(); self.f.h.at(1)
                    self.app.Step(self.app, self.raw(0, ok, 1))
                    self.assertEqual(self.f.runtime.Status(self.f.runtime).recoveries[kind], 'confirmed' if ok else 'rejected')
                    self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)), 0)
                    self.assertEqual(len(self.executor.calls), 1)
                    self.app.Destroy(self.app)

    def test_contract_saved_baseline_and_command_identity_cannot_be_changed(self):
        from test_legacy_completion_receipts import plain
        for kind in ('contracts', 'bonuses'):
            for change in ('baseline', 'action', 'resources'):
                with self.subTest(kind=kind, change=change):
                    self.prepare(kind); self.restart(); self.f.h.at(1)
                    after = self.tab.Enrich(self.tab, self.raw(0, True, 1))[0]
                    detached = lua_table(self.f.h.lua, plain(self.saved))
                    if change == 'baseline': detached.baseline.reset += 1
                    elif change == 'action': detached.proposal.actionKey += ':other'
                    else: detached.proposal.resources.cash = 1
                    self.assertIsNone(self.f.runtime.features[kind].recoverSaved(detached, after))
                    self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)), 1)
                    self.app.Destroy(self.app)


if __name__ == '__main__': unittest.main()
