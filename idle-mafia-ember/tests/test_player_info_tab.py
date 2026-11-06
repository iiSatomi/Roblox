"""Read-only Ember Player tab renders known, collecting, unavailable and stale states."""
import unittest
from engine_harness import Harness,lua_table
import test_player_info_state as facts_fixture

class PlayerInfoTabTests(unittest.TestCase):
    def setUp(self):
        self.h=Harness();self.module=self.h.load('src/tabs/player/Module.luau')
        ember=self.h.load('tests/ember_double.lua')();self.window=ember.new(lua_table(self.h.lua,{}))
        self.tab=self.module.new(self.window.Section(self.window,'Player'))
    def test_unavailable_trust_and_rates_do_not_show_fake_zero_and_render_changes_are_detached(self):
        self.tab.Render(self.tab,lua_table(self.h.lua,{}))
        self.assertIn('Unavailable',self.tab.fields.attack.Get(self.tab.fields.attack))
        self.assertIn('Not exposed',self.tab.fields.trust.Get(self.tab.fields.trust))
        f=facts_fixture.PlayerInfoStateTests();f.provided_h=self.h;f.setUp();r=f.observe()
        model=lua_table(self.h.lua,{'automationRuntime':{'playerInfo':r}});self.tab.Render(self.tab,model)
        self.assertIn('150',self.tab.fields.attack.Get(self.tab.fields.attack));self.assertIn('3,000',self.tab.fields.propertyIncome.Get(self.tab.fields.propertyIncome))
        self.assertIn('Collecting',self.tab.fields.mugIncome.Get(self.tab.fields.mugIncome))
        r.status='stale';self.tab.Render(self.tab,model);self.assertIn('Stale',self.tab.fields.state.Get(self.tab.fields.state))

    def test_property_and_power_rows_keep_stable_identity_when_earlier_rows_disappear(self):
        f=facts_fixture.PlayerInfoStateTests();f.provided_h=self.h;f.setUp();v=f.observe()
        model=lua_table(self.h.lua,{'automationRuntime':{'playerInfo':v}});self.tab.Render(self.tab,model)
        self.assertEqual(self.tab.propertyRows['p_a'].handle.options.Text,'Laundromat')
        v.properties=lua_table(self.h.lua,[{'id':'p_b','name':'Diner','owned':1,'active':1,'activeBasePerHour':300}])
        v.powerBreakdown=lua_table(self.h.lua,[{'id':'gear','attack':20,'defense':10}])
        self.tab.Render(self.tab,model)
        self.assertFalse(self.tab.propertyRows['p_a'].handle.visible)
        self.assertTrue(self.tab.propertyRows['p_b'].handle.visible)
        self.assertEqual(self.tab.propertyRows['p_b'].handle.options.Text,'Diner')
        self.assertEqual(self.tab.powerRows['gear'].handle.options.Text,'Gear')
