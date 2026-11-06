"""Property constraints use actual App/descriptor/native-adapter custody paths."""
import unittest
import test_trophy_goal_runtime as fixture
from engine_harness import lua_table

class PropertyConstraintsAppTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.TrophyGoalRuntimeTests();self.f.setUp();self.f.targets()
        self.h=self.f.h;self.app=self.f.app;self.runtime=self.f.runtime;self.executor=self.f.executor
        data={'PROPERTIES':[{'id':'p_owned','level':1,'baseCost':10,'incomePerHour':20},
            {'id':'p_city','level':8,'baseCost':100,'incomePerHour':10},
            {'id':'p_other','level':1,'baseCost':1,'incomePerHour':100}]}
        self.f.native_properties=self.h.load('src/tabs/property/NativePropertyCatalog.luau').new(lua_table(self.h.lua,data),lua_table(self.h.lua,{'PROPERTY':{'costGrowth':1.18,'maxOwned':20}}),'a'*64,'release-a')
        for key,value in [('cashReserve',0),('purchaseCap',1000),('ownedLimit',10)]:self.set(key,value)
    def tearDown(self):self.f.tearDown()
    def set(self,key,value):
        result=self.app.Set(self.app,'properties.custom.'+key,value);self.assertTrue(result[0],result[1])
    def raw(self,revision=1):return self.f.target_raw(revision)
    def run_build(self,policy='Best value'):
        self.assertTrue(self.app.Set(self.app,'properties.policy',policy)[0]);self.app.Set(self.app,'properties.enabled',True)
        self.app.Resume(self.app);self.app.Step(self.app,self.raw())
    def target(self):
        self.assertIsNotNone(self.executor.callback);self.executor.callback()
        self.assertEqual(len(self.executor.calls),1);self.assertEqual(self.executor.calls[1].remote,'BuyProperty')
        return self.executor.calls[1].args[1]
    def test_highest_tier_goal_uses_required_level(self):
        self.run_build('Highest tier');self.assertEqual(self.target(),'p_city')
    def test_selected_property_restricts_before_value_ranking(self):
        self.set('selection','Only selected');self.set('selectedIds','p_city')
        self.run_build();self.assertEqual(self.target(),'p_city')
    def test_selection_is_independent_of_optional_level_bounds(self):
        self.set('selection','Only selected');self.set('selectedIds','p_city');self.set('maxLevel',1)
        self.run_build();self.assertEqual(self.target(),'p_city')
    def test_enabled_bounds_filter_highest_tier_before_ranking(self):
        self.set('limitsEnabled',True);self.set('maxLevel',1)
        self.run_build('Highest tier');self.assertEqual(self.target(),'p_other')
    def test_enabled_level_boundaries_are_inclusive(self):
        self.set('limitsEnabled',True);self.set('minLevel',8);self.set('maxLevel',8)
        self.run_build();self.assertEqual(self.target(),'p_city')
    def test_inverted_bounds_hold(self):
        self.set('limitsEnabled',True);self.set('minLevel',9);self.set('maxLevel',8)
        self.run_build();self.assertIsNone(self.executor.callback)
    def test_empty_or_unknown_selection_holds_without_fallback(self):
        self.set('selection','Only selected');self.run_build();self.assertIsNone(self.executor.callback)
        self.set('selectedIds','p_city,removed_property');self.app.Step(self.app,self.raw())
        self.assertIsNone(self.executor.callback)
    def test_tightening_bound_before_dispatch_prevents_purchase(self):
        self.run_build('Highest tier');self.set('limitsEnabled',True);self.set('maxLevel',1)
        self.executor.callback();self.assertEqual(len(self.executor.calls),0)
    def test_reselecting_before_dispatch_prevents_purchase(self):
        self.run_build();self.set('selection','Only selected');self.set('selectedIds','p_city')
        self.executor.callback();self.assertEqual(len(self.executor.calls),0)
    def test_sent_selected_purchase_confirms_exact_cost_and_other_ownership(self):
        self.set('selection','Only selected');self.set('selectedIds','p_city');self.run_build();self.target()
        self.set('limitsEnabled',True);self.set('maxLevel',1)
        after=self.raw(2);after.native.cash=900;after.native.properties.p_city=lua_table(self.h.lua,{'owned':1})
        self.h.at(1);self.app.Step(self.app,after)
        self.assertEqual(self.runtime.Status(self.runtime).outcomes.properties,'confirmed')
    def test_disable_queued_purchase_does_not_invoke(self):
        self.run_build();self.app.Set(self.app,'properties.enabled',False);self.executor.callback()
        self.assertEqual(len(self.executor.calls),0)
    def test_unload_queued_purchase_does_not_invoke(self):
        self.run_build();self.app.Destroy(self.app);self.executor.callback();self.assertEqual(len(self.executor.calls),0)
    def test_unknown_reply_or_unrelated_ownership_never_confirms_purchase(self):
        self.run_build();self.target();after=self.raw(2);after.native.cash=999
        after.native.properties.p_city=lua_table(self.h.lua,{'owned':1})
        self.h.at(1);self.app.Step(self.app,after)
        self.assertNotEqual(self.runtime.Status(self.runtime).outcomes.properties,'confirmed')
    def test_selected_trophy_route_does_not_override_property_bounds(self):
        self.set('limitsEnabled',True);self.set('maxLevel',1)
        self.f.select('t_brasskeys',jobs=False);self.app.Set(self.app,'properties.enabled',True)
        self.app.Set(self.app,'trophyFocus.custom.borrowProperties',True);self.app.Step(self.app,self.raw())
        active=self.runtime.session.broker.active
        self.assertTrue(active is None or active.proposal.intent.propId!='p_city')
    def test_invalid_numeric_and_selected_text_inputs_are_rejected(self):
        for key,value in [('minLevel',1.5),('maxLevel',0),('selectedIds','bad,,id')]:
            self.assertFalse(self.app.Set(self.app,'properties.custom.'+key,value)[0])

    def restart(self):
        self.app.Destroy(self.app);self.h.session['session']='property-reloaded';self.f.start_app()
        self.app=self.f.app;self.runtime=self.f.runtime;self.executor=self.f.executor
    def test_saved_selected_build_recovers_exact_effect_without_replay(self):
        self.set('selection','Only selected');self.set('selectedIds','p_city');self.run_build();self.target();self.restart()
        after=self.raw(0);after.capturedAt=1;after.native.cash=900
        after.native.properties.p_city=lua_table(self.h.lua,{'owned':1})
        self.h.at(1);self.app.Step(self.app,after)
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.properties,'confirmed')
        self.assertEqual(len(self.executor.calls),0);self.assertFalse(self.app.model['values']['properties.enabled'])
    def test_unknown_saved_purchase_preserves_cash_exposure_without_replay(self):
        self.run_build();self.target();self.restart();self.h.at(1);self.app.Step(self.app,self.raw(2))
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),1)
        self.assertEqual(len(self.executor.calls),0)
    def test_actual_property_tab_inputs_preserve_types_and_all_off_state(self):
        import test_ui_prototype as ui
        f=ui.PrototypeTests();f.setUp();app,ember=f.app()
        try:
            c=app.ui.handles['properties.custom.minLevel'];c.Set(c,'8');ember.Flush()
            self.assertEqual(app.model['values']['properties.custom.minLevel'],8)
            c=app.ui.handles['properties.custom.selectedIds'];c.Set(c,'p_city, p_other');ember.Flush()
            self.assertEqual(app.model['values']['properties.custom.selectedIds'],'p_city, p_other')
            self.assertFalse(app.model['values']['properties.enabled'])
        finally:app.Destroy(app)

    def saved_build(self,reply=None):
        self.executor.reply=lua_table(self.h.lua,reply or {'ok':True})
        self.set('selection','Only selected');self.set('selectedIds','p_city');self.run_build();self.target()
        record=self.runtime.checkpoint.Records(self.runtime.checkpoint)[1]
        return self.runtime.checkpoint.Recovery(self.runtime.checkpoint,record.actionKey)[0]
    def settled(self):
        after=self.raw(0);after.session='property-reloaded';after.native.cash=900
        after.native.properties.p_city=lua_table(self.h.lua,{'owned':1})
        return after
    def test_saved_recovery_rechecks_all_other_property_custody(self):
        data=self.saved_build();evidence=self.h.load('src/features/PropertiesEvidence.luau');after=self.settled()
        self.assertEqual(evidence.recoverSaved(data,after),'confirmed')
        after.native.properties.p_owned.owned=2;self.assertIsNone(evidence.recoverSaved(data,after))
        after.native.properties.p_owned.owned=1;after.native.properties.unknown=lua_table(self.h.lua,{'owned':1})
        self.assertIsNone(evidence.recoverSaved(data,after))
    def test_saved_recovery_refuses_forged_quote_or_other_owned_baseline(self):
        data=self.saved_build();evidence=self.h.load('src/features/PropertiesEvidence.luau');after=self.settled()
        data.baseline.expectedCost=1;self.assertIsNone(evidence.recoverSaved(data,after));data.baseline.expectedCost=100
        data.baseline.otherOwned.p_owned=2;self.assertIsNone(evidence.recoverSaved(data,after))
    def test_saved_recovery_needs_matching_scope_nonolder_clock_and_saved_reply(self):
        data=self.saved_build();evidence=self.h.load('src/features/PropertiesEvidence.luau')
        for field in ('account','place','release'):
            after=self.settled();after[field]='other';self.assertIsNone(evidence.recoverSaved(data,after))
        after=self.settled();after.native.serverNow-=1;self.assertIsNone(evidence.recoverSaved(data,after))
        after=self.settled();data.reply=None;self.assertIsNone(evidence.recoverSaved(data,after))
    def test_saved_rejected_build_recovers_without_new_purchase(self):
        self.saved_build({'ok':False});self.restart();self.h.at(1);self.app.Step(self.app,self.raw(2))
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.properties,'rejected')
        self.assertEqual(len(self.executor.calls),0)
    def test_equal_level_highest_goal_prefers_income_before_cost(self):
        data={'PROPERTIES':[{'id':'p_owned','level':1,'baseCost':10,'incomePerHour':20},
            {'id':'p_city','level':8,'baseCost':1,'incomePerHour':10},
            {'id':'p_other','level':8,'baseCost':100,'incomePerHour':100}]}
        self.f.native_properties=self.h.load('src/tabs/property/NativePropertyCatalog.luau').new(lua_table(self.h.lua,data),lua_table(self.h.lua,{'PROPERTY':{'costGrowth':1.18,'maxOwned':20}}),'a'*64,'release-a')
        self.run_build('Highest tier');self.assertEqual(self.target(),'p_other')

if __name__=='__main__':unittest.main()
