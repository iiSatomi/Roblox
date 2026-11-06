"""Current native own-power/resources and target guards; no request or private writes."""
import unittest
import test_native_client_bindings as fixture
from engine_harness import lua_table

class PlayerCombatFactsTests(unittest.TestCase):
    def setUp(self):
        self.h,self.game,self.state,self.probe,_,_=fixture.NativeClientBindingsTests().fight_client()
        cfg=self.game.GetService(self.game,'ReplicatedStorage').children.MW.children.Config.Value
        cfg.prestigeMult=self.h.lua.eval('function(data) return data.powerPrestige end')
        cfg.skillPowerMult=self.h.lua.eval('function(data,kind) assert(kind=="attack");return data.powerSkill end')
        for key,value in {'hospitalHealth':20,'staminaCost':2,'scoutStaminaCost':1,'dailyTargetCap':5,
            'fightVariance':.2,'fightVarianceCap':5000,'bullyMaxStamina':5,'targetCooldown':30}.items():cfg.COMBAT[key]=value
        self.config=cfg
        bindings=self.h.load('src/transport/NativeClientBindings.luau')
        self.source=bindings.read(self.game,self.h.lua.eval('function(m) return m.Value end'),self.probe.upvalues)[0].currentFightNotifications
        self.native=lua_table(self.h.lua,{'fullSync':True,'serverNow':1000,'shieldUntil':0,'family':{'id':'own-family'},
            'stats':{'atkBase':100,'maxHealth':100},'derived':{'gearAtk':20,'crewBonus':.5},
            'powerPrestige':3,'powerSkill':2,'pools':{'health':80.5,'stamina':10.25}})
        self.targets=lua_table(self.h.lua,[{'userId':99,'familyId':'foreign-family'}])
    def read(self):return self.source.CombatFrame(self.source,self.native,self.targets)
    def test_exact_current_native_power_formula_preserves_fractional_pools(self):
        frame=self.read();self.assertEqual(frame.attack,1080)
        self.assertEqual((frame.ownUserId,frame.ownFamilyId,frame.health,frame.stamina),(42,'own-family',80.5,10.25))
        self.assertEqual((frame.hospitalHealth,frame.scoutCost,frame.maxStaminaCost),(20,1,5))
        self.assertEqual(frame.targets['99'].remainingDaily,5);self.assertFalse(frame.targets['99'].manualWarning)
        self.assertFalse(frame.targets['99'].sameFamily)
    def test_native_busy_shield_and_target_cooldown_are_exposed_without_changing_them(self):
        self.probe.busy=True;self.probe.cooldown=10;self.native.shieldUntil=1001
        frame=self.read();self.assertTrue(frame.busy);self.assertTrue(frame.shielded)
        self.assertEqual(frame.targets['99'].cooldownLeft,10);self.assertTrue(self.probe.busy)
    def test_family_and_native_war_warning_remain_explicit_exclusions(self):
        self.probe.family=True;self.probe.warning='Native confirmation needed'
        frame=self.read();self.assertTrue(frame.targets['99'].sameFamily);self.assertTrue(frame.targets['99'].manualWarning)
    def test_missing_or_changed_rules_functions_and_nonfinite_values_are_unknown(self):
        for field,value in [('powerPrestige',None),('powerSkill',float('nan'))]:
            self.setUp();self.native[field]=value;self.assertIsNone(self.read())
        self.setUp();self.config.prestigeMult=self.h.lua.eval('function() return 100 end');self.assertIsNone(self.read())
    def test_native_context_replacement_or_changed_version_cannot_publish_facts(self):
        self.game.PlaceVersion=649;self.assertIsNone(self.read())
        self.game.PlaceVersion=648;self.game.GetService(self.game,'Players').LocalPlayer=None;self.assertIsNone(self.read())
    def test_duplicate_or_unbounded_target_rows_are_refused(self):
        self.targets[2]=self.targets[1];self.assertIsNone(self.read())

    def test_missing_derived_uses_the_native_zero_bonus_default(self):
        self.native.derived=None;self.assertEqual(self.read().attack,600)
    def test_native_scope_or_functions_changed_during_calculation_cannot_escape_postcheck(self):
        self.h.lua.globals().factGame=self.game
        self.config.prestigeMult=self.h.lua.eval('function(data) factGame.PlaceVersion=649;return data.powerPrestige end')
        bindings=self.h.load('src/transport/NativeClientBindings.luau')
        self.source=bindings.read(self.game,self.h.lua.eval('function(m) return m.Value end'),self.probe.upvalues)[0].currentFightNotifications
        self.assertIsNone(self.read())
