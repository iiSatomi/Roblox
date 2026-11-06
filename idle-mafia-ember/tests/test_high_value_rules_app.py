"""Custom rules run through actual model/profile, App, proposal, queue and recovery."""
import unittest
import test_high_value_app as fixture
import test_ui_prototype as ui_fixture
import test_legacy_profile_preview as legacy_fixture
from engine_harness import lua_table

class HighValueRulesAppTests(unittest.TestCase):
    def setUp(self):
        self.b=fixture.HighValueAppTests();self.b.setUp();self.f=self.b.f;self.app=self.b.app;self.h=self.b.h
    def rules(self,promote=500,below=100,hits=3):
        for key,value in [('promoteCash',promote),('demoteBelow',below),('demoteHits',hits)]:
            self.assertTrue(self.app.Set(self.app,'combat.memory.'+key,value)[0],key)
    def test_custom_owned_promotion_survives_actual_graceful_unload_and_reload(self):
        self.rules();self.b.promote(close=True,cash=500);self.app=self.b.app;self.f.step()
        self.assertEqual(self.f.runtime.Status(self.f.runtime).recoveries.combat,'confirmed')
        memory=self.f.ledger.Summary(self.f.ledger)
        self.assertEqual((memory.highValue.count,memory.recent[1].highPromoteCash),(1,500))
        self.assertEqual(self.app.model['values']['combat.memory.promoteCash'],1000000000)
    def test_rule_change_before_queued_send_refuses_without_spending(self):
        self.rules();self.f.begin();self.app.Set(self.app,'combat.memory.demoteHits',2);self.f.step()
        self.f.executor.queued[1]();self.assertEqual(self.f.executor.calls,0)
        self.assertEqual(self.f.runtime.checkpoint.Allowance(self.f.runtime.checkpoint,'combat')[0].attackSpent,0)
    def test_rule_change_after_send_cannot_reinterpret_the_settled_fight(self):
        self.rules()
        for packet in (self.f.result.initial,self.f.result.final):packet['cashEstimate']=500
        self.f.result.final.update(cashConfirmed=500,stolen=500)
        self.h.lua.globals().fixtureFightReply=lua_table(self.h.lua,self.f.result.initial)
        self.f.begin();self.f.send();self.app.Set(self.app,'combat.memory.promoteCash',1000);self.f.settle()
        row=self.f.ledger.Summary(self.f.ledger)
        self.assertEqual((row.highValue.count,row.recent[1].highPromoteCash),(1,500))
    def test_rule_bounds_are_atomic_and_never_enable_or_resume_combat(self):
        paused=self.app.model.paused
        self.rules(below=0,hits=100)
        for key,value in [('promoteCash',0),('promoteCash',1000000000000001),('demoteBelow',-1),('demoteHits',101),('demoteHits',1.5)]:
            before=self.app.model['values']['combat.memory.'+key]
            self.assertFalse(self.app.Set(self.app,'combat.memory.'+key,value)[0]);self.assertEqual(self.app.model['values']['combat.memory.'+key],before)
        self.assertFalse(self.app.model['values']['combat.enabled']);self.assertEqual(self.app.model.paused,paused)
    def test_rules_have_owned_collapsed_combat_controls_outside_the_18_custom_limits(self):
        f=ui_fixture.PrototypeTests();f.setUp();app,ember=f.app()
        try:
            self.assertEqual(len(app.ui.features.combat.feature.custom),18)
            for key,value in [('promoteCash','500'),('demoteBelow','0'),('demoteHits','100')]:
                handle=app.ui.handles['combat.memory.'+key];self.assertIsNotNone(handle)
                handle.Set(handle,value);ember.Flush()
                self.assertEqual(app.model['values']['combat.memory.'+key],int(value))
            self.assertFalse(app.model['values']['combat.enabled'])
        finally:app.Destroy(app)
    def test_legacy_custom_rule_preview_preserves_intent_without_activation(self):
        f=legacy_fixture.LegacyProfilePreviewTests();f.setUp()
        try:
            accepted,why=f.preview({'version':17,'combatHighPromoteCash':500,'combatHighDemoteBelow':0,'combatHighDemoteHits':100})
            self.assertTrue(accepted,why)
            for key,value in [('promoteCash',500),('demoteBelow',0),('demoteHits',100)]:self.assertEqual(f.app.staged['values']['combat.memory.'+key],value)
            self.assertFalse(f.app.model['values']['combat.enabled']);self.assertEqual(f.app.model['values']['combat.custom.targetSource'],'Saved and new')
        finally:f.tearDown()
    def tearDown(self):
        if hasattr(self,'b'):self.b.tearDown()
