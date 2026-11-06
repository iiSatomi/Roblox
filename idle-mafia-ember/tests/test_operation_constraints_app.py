"""Legacy Operation constraints through actual App, broker and native adapter."""
import unittest
import test_trophy_goal_runtime as fixture
from engine_harness import lua_table

class OperationConstraintsAppTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.TrophyGoalRuntimeTests();self.f.setUp()
        self.h=self.f.h;self.app=self.f.app;self.runtime=self.f.runtime;self.executor=self.f.executor
    def tearDown(self):self.f.tearDown()
    def set(self,key,value):
        result=self.app.Set(self.app,'operations.custom.'+key,value);self.assertTrue(result[0],result[1])
    def raw(self,revision=1):
        raw=self.f.raw(revision)
        raw.native.cash=10000
        raw.operationCatalog=lua_table(self.h.lua,[
            {'id':'op_fence','level':1,'duration':600,'cost':200,'cash':1500,'xp':20,'crate':'crate_low','crateChance':.1},
            {'id':'op_truck','level':8,'duration':3600,'cost':4000,'cash':18000,'xp':180,'crate':'crate_high','crateChance':.2}])
        raw.crateCatalog=lua_table(self.h.lua,{'crate_low':{'buckets':[{'weight':1,'rarity':1}]},'crate_high':{'buckets':[{'weight':1,'rarity':5}]}})
        raw.operationCrateRarities=lua_table(self.h.lua,{'crate_low':2,'crate_high':4})
        return raw
    def run_op(self,raw=None,policy='Highest tier'):
        self.assertTrue(self.app.Set(self.app,'operations.policy',policy)[0])
        self.app.Set(self.app,'operations.enabled',True);self.app.Resume(self.app)
        self.app.Step(self.app,raw or self.raw())
    def target(self):
        self.assertIsNotNone(self.executor.callback)
        self.executor.callback();self.assertEqual(len(self.executor.calls),1)
        self.assertEqual(self.executor.calls[1].remote,'StartOperation')
        return self.executor.calls[1].args[1]
    def test_profit_goal_uses_net_cash_per_duration(self):
        self.run_op(policy='Profit / hour');self.assertEqual(self.target(),'op_truck')
    def test_xp_goal_uses_current_xp_per_duration(self):
        self.run_op(policy='XP / hour');self.assertEqual(self.target(),'op_truck')
    def test_shortest_goal_uses_catalog_duration(self):
        self.run_op(policy='Shortest duration');self.assertEqual(self.target(),'op_fence')
    def test_enabled_level_bounds_filter_before_ranking(self):
        self.set('limitsEnabled',True);self.set('maxLevel',1);self.run_op()
        self.assertEqual(self.target(),'op_fence')
    def test_duration_and_level_boundaries_are_inclusive(self):
        for key,value in [('limitsEnabled',True),('minLevel',8),('maxLevel',8),('minHours',1),('maxHours',1)]:self.set(key,value)
        self.run_op();self.assertEqual(self.target(),'op_truck')
    def test_inverted_bounds_hold_instead_of_ignoring_constraint(self):
        self.set('limitsEnabled',True);self.set('minHours',2);self.set('maxHours',1)
        self.run_op();self.assertIsNone(self.executor.callback)
    def test_disabled_bounds_retain_values_without_restricting_start(self):
        self.set('maxLevel',1);self.set('maxHours',.1);self.set('minCrateRarity',9)
        self.run_op();self.assertEqual(self.target(),'op_truck')
    def test_rarity_filter_uses_primary_crate_item_rarity_not_drop_bucket_mean(self):
        self.set('limitsEnabled',True);self.set('minCrateRarity',5);self.run_op()
        self.assertIsNone(self.executor.callback)
    def test_missing_primary_crate_rarity_cannot_satisfy_positive_floor(self):
        self.set('limitsEnabled',True);self.set('minCrateRarity',1)
        raw=self.raw();raw.operationCrateRarities=None;self.run_op(raw)
        self.assertIsNone(self.executor.callback)
    def test_selected_list_restricts_even_when_optional_bounds_are_disabled(self):
        self.set('selection','Only selected');self.set('selectedIds','op_fence')
        self.run_op();self.assertEqual(self.target(),'op_fence')
    def test_empty_or_unknown_selected_list_holds_instead_of_falling_back(self):
        self.set('selection','Only selected');self.run_op();self.assertIsNone(self.executor.callback)
        self.set('selectedIds','removed_op');self.app.Step(self.app,self.raw());self.assertIsNone(self.executor.callback)
    def test_tightening_bound_before_dispatch_prevents_native_call(self):
        self.run_op();self.set('limitsEnabled',True);self.set('maxLevel',1)
        self.executor.callback();self.assertEqual(len(self.executor.calls),0)
    def test_reselecting_before_dispatch_prevents_native_call(self):
        self.run_op();self.set('selection','Only selected');self.set('selectedIds','op_fence')
        self.executor.callback();self.assertEqual(len(self.executor.calls),0)
    def test_sent_start_still_requires_exact_slot_and_cash_after_limit_change(self):
        self.run_op();self.target();self.set('limitsEnabled',True);self.set('maxLevel',1)
        after=self.raw(2);after.native.cash=6000
        after.native.operations.active=lua_table(self.h.lua,[{'opId':'op_truck','remaining':3599,'slot':1}])
        self.h.at(1);self.app.Step(self.app,after)
        self.assertEqual(self.runtime.Status(self.runtime).outcomes.operations,'confirmed')
    def test_disable_queued_start_does_not_invoke(self):
        self.run_op();self.app.Set(self.app,'operations.enabled',False);self.executor.callback()
        self.assertEqual(len(self.executor.calls),0)
    def test_unload_queued_start_does_not_invoke(self):
        self.run_op();self.app.Destroy(self.app);self.executor.callback();self.assertEqual(len(self.executor.calls),0)
    def test_invalid_numeric_bounds_and_bad_selection_text_refuse_without_coercion(self):
        for key,value in [('minLevel',1.5),('maxLevel',0),('minHours',-1),('maxHours',float('nan')),('minCrateRarity',2.5),('selectedIds','a,,b')]:
            self.assertFalse(self.app.Set(self.app,'operations.custom.'+key,value)[0])

    def test_unknown_member_in_otherwise_valid_selection_still_holds(self):
        self.set('selection','Only selected');self.set('selectedIds','op_fence,removed_op')
        self.run_op();self.assertIsNone(self.executor.callback)
    def test_no_crate_and_unknown_contents_still_allow_non_chest_goals(self):
        raw=self.raw();raw.crateCatalog=None
        self.run_op(raw,policy='Profit / hour');self.assertEqual(self.target(),'op_truck')
    def test_rejected_start_is_not_a_confirmed_run(self):
        self.executor.reply=lua_table(self.h.lua,{'ok':False})
        self.run_op(policy='Profit / hour');self.target();self.h.at(1)
        self.app.Step(self.app,self.raw(2))
        self.assertEqual(self.runtime.Status(self.runtime).outcomes.operations,'rejected')
    def test_wrong_cash_or_slot_cannot_confirm_sent_start(self):
        self.run_op(policy='XP / hour');self.target();after=self.raw(2)
        after.native.operations.active=lua_table(self.h.lua,[{'opId':'op_truck','remaining':3599,'slot':1}])
        self.h.at(1);self.app.Step(self.app,after)
        self.assertNotEqual(self.runtime.Status(self.runtime).outcomes.operations,'confirmed')
    def restart(self):
        self.app.Destroy(self.app);self.h.session['session']='ops-reloaded';self.f.start_app()
        self.app=self.f.app;self.runtime=self.f.runtime;self.executor=self.f.executor
    def test_saved_sent_rate_goal_recovers_exact_effect_without_replay(self):
        self.run_op(policy='Profit / hour');self.target();self.restart()
        after=self.raw(0);after.capturedAt=1;after.native.cash=6000
        after.native.operations.active=lua_table(self.h.lua,[{'opId':'op_truck','remaining':3599,'slot':1}])
        self.h.at(1);self.app.Step(self.app,after)
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.operations,'confirmed')
        self.assertEqual(len(self.executor.calls),0);self.assertFalse(self.app.model['values']['operations.enabled'])
    def test_unknown_saved_start_remains_held_without_replay(self):
        self.run_op(policy='Shortest duration');self.target();self.restart()
        self.h.at(1);self.app.Step(self.app,self.raw(2))
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),1)
        self.assertEqual(len(self.executor.calls),0)
    def test_actual_tab_numeric_and_selection_inputs_keep_typed_values(self):
        import test_ui_prototype as ui
        f=ui.PrototypeTests();f.setUp();app,ember=f.app()
        try:
            control=app.ui.handles['operations.custom.minHours'];control.Set(control,'0.5');ember.Flush()
            self.assertEqual(app.model['values']['operations.custom.minHours'],.5)
            control=app.ui.handles['operations.custom.selectedIds'];control.Set(control,'op_fence, op_truck');ember.Flush()
            self.assertEqual(app.model['values']['operations.custom.selectedIds'],'op_fence, op_truck')
            self.assertFalse(app.model['values']['operations.enabled'])
        finally:app.Destroy(app)

    def saved_start(self,reply=None):
        self.executor.reply=lua_table(self.h.lua,reply or {'ok':True})
        self.run_op(policy='Profit / hour');self.target()
        record=self.runtime.checkpoint.Records(self.runtime.checkpoint)[1]
        return self.runtime.checkpoint.Recovery(self.runtime.checkpoint,record.actionKey)[0]
    def settled(self):
        after=self.raw(0);after.session='ops-reloaded';after.native.cash=6000
        after.native.operations.active=lua_table(self.h.lua,[{'opId':'op_truck','remaining':3599,'slot':1}])
        return after
    def test_saved_recovery_refuses_forged_baseline_and_cash_exposure(self):
        data=self.saved_start();evidence=self.h.load('src/features/OperationsEvidence.luau');after=self.settled()
        self.assertEqual(evidence.recoverSaved(data,after),'confirmed')
        data.baseline.cost=1;self.assertIsNone(evidence.recoverSaved(data,after));data.baseline.cost=4000
        data.baseline.slots[2]='unrelated';self.assertIsNone(evidence.recoverSaved(data,after));data.baseline.slots[2]=None
        data.proposal.resources.cash=1;self.assertIsNone(evidence.recoverSaved(data,after))
    def test_saved_recovery_refuses_wrong_scope_old_clock_and_incomplete_sync(self):
        data=self.saved_start();evidence=self.h.load('src/features/OperationsEvidence.luau')
        for field in ('account','place','release'):
            after=self.settled();after[field]='other';self.assertIsNone(evidence.recoverSaved(data,after))
        after=self.settled();after.native.serverNow-=1;self.assertIsNone(evidence.recoverSaved(data,after))
        after=self.settled();after.native.fullSync=False;self.assertIsNone(evidence.recoverSaved(data,after))
    def test_saved_reply_is_required_and_rejection_cannot_override_exact_effect(self):
        data=self.saved_start();evidence=self.h.load('src/features/OperationsEvidence.luau');after=self.settled()
        data.reply=None;self.assertIsNone(evidence.recoverSaved(data,after))
        data.reply=lua_table(self.h.lua,{'ok':False});self.assertIsNone(evidence.recoverSaved(data,after))
    def test_saved_rejected_start_recovers_without_replaying(self):
        self.saved_start({'ok':False});self.restart();self.h.at(1)
        self.app.Step(self.app,self.raw(2))
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.operations,'rejected')
        self.assertEqual(len(self.executor.calls),0)
    def test_failed_recovery_cleanup_retains_record_until_later_success(self):
        self.saved_start();self.restart();after=self.settled();after.session=self.h.session['session'];after.capturedAt=1
        storage=self.f.base.storage;write=storage.Write;storage.Write=self.h.lua.eval('function() return false end')
        self.h.at(1);self.app.Step(self.app,after)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),1)
        self.assertEqual(len(self.executor.calls),0);storage.Write=write
        self.restart();after=self.settled();after.session=self.h.session['session'];after.capturedAt=2
        self.h.at(2);self.app.Step(self.app,after)
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.operations,'confirmed')
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),0)

    def test_balanced_goal_normalizes_eligible_net_xp_and_primary_crate_quotes(self):
        raw=self.raw();raw.operationCatalog[1].cash=60200
        self.run_op(raw,policy='Balanced');self.assertEqual(self.target(),'op_fence')
    def test_balanced_goal_respects_constraints_before_normalization(self):
        raw=self.raw();raw.operationCatalog[1].cash=60200
        self.set('limitsEnabled',True);self.set('minLevel',8)
        self.run_op(raw,policy='Balanced');self.assertEqual(self.target(),'op_truck')
    def test_balanced_goal_does_not_infer_missing_primary_crate_rarity(self):
        raw=self.raw();raw.operationCrateRarities=None
        self.run_op(raw,policy='Balanced');self.assertIsNone(self.executor.callback)

if __name__=='__main__':unittest.main()
