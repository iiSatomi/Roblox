"""Independent ordinary/war caps and Scout consent are explicit and default inert."""
import unittest
from engine_harness import Harness,lua_table

class PlayerCombatSettingsTests(unittest.TestCase):
    def setUp(self):
        self.h=Harness();self.catalog=self.h.load('src/ui/Catalog.luau')
        self.model=self.h.load('src/storage/Settings.luau').new(self.catalog)
    def test_both_modes_have_independent_zero_caps_and_scout_off(self):
        for feature in ('combat','warCombat'):
            self.assertIs(self.model["values"][ feature+'.custom.allowScout'],False)
            self.assertEqual(self.model["values"][ feature+'.custom.maxScoutSpend'],0)
            self.assertEqual(self.model["values"][ feature+'.custom.maxAttackSpend'],0)
        self.assertTrue(self.model.Set(self.model,'combat.custom.allowScout',True)[0])
        self.assertIs(self.model["values"][ 'warCombat.custom.allowScout'],False)
        self.assertFalse(self.model.Set(self.model,'combat.custom.maxScoutSpend',1.5)[0])
        self.assertFalse(self.model.Set(self.model,'combat.custom.scoutMaxAge',1801)[0])
        self.assertFalse(self.model.Set(self.model,'combat.custom.minWinChance',101)[0])
    def test_actual_combat_ui_builds_scout_as_boolean_and_keeps_limits_visible_for_all_policies(self):
        ember=self.h.load('tests/ember_double.lua')();window=ember.new(lua_table(self.h.lua,{}));section=window.Section(window,'Combat')
        feature=next(f for f in self.catalog.features.values() if f.id=='combat')
        self.h.lua.globals().settingsHandles=self.h.lua.table()
        bind=self.h.lua.eval('function(group,kind,key,opts) local handle=group[kind](group,opts);settingsHandles[key]=handle;return handle end')
        row=self.h.load('src/tabs/combat/Module.luau').BuildUI(section,feature,bind,self.h.lua.table())
        self.assertIsNone(row.blockedReason)
        self.assertTrue(row.alwaysShowCustom)
        self.assertEqual(self.h.lua.globals().settingsHandles['combat.custom.allowScout'].kind,'Toggle')
        self.assertEqual(self.h.lua.globals().settingsHandles['combat.custom.dailyOnly'].kind,'Toggle')
        self.assertIs(self.h.lua.globals().settingsHandles['combat.custom.dailyOnly'].value,True)
