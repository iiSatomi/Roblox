"""Native War preflight retains exact family/build/manual-warning ownership."""
import unittest
import test_native_client_bindings as fixture
from engine_harness import lua_table

class WarNativeBindingsTests(unittest.TestCase):
    def make(self,scout=False):
        f=fixture.NativeClientBindingsTests()
        self.h,self.game,self.state,self.probe,self.source,self.p=f.scout_client() if scout else f.fight_client()
        self.p.feature='warCombat'
        for key,value in {'familyId':'enemy-family','ownFamilyId':'own-family','warFamilyId':'enemy-family',
                          'serverNow':1000,'warStatusServerNow':1000,'warDay':0,'attackQuote':2}.items():self.p.intent[key]=value
        self.state.data.family=lua_table(self.h.lua,{'id':'own-family'})
        self.state.data.derived=lua_table(self.h.lua,{'war':{'state':'active','enemyId':'enemy-family'}})
    def test_exact_war_attack_and_opted_scout_can_use_existing_native_safeguards(self):
        for scout in (False,True):
            self.make(scout);guard=self.source.CanScout if scout else self.source.CanAttack
            self.assertTrue(guard(self.source,self.p,99)[0])
            self.assertFalse(self.probe.busy);self.assertEqual(self.probe.remaining,5)
    def test_mismatched_current_enemy_own_family_or_day_never_authorizes_war(self):
        for scout in (False,True):
            for field,value in (('warFamilyId','other'),('ownFamilyId','other'),('warDay',1),('warStatusServerNow',980)):
                self.make(scout);self.p.intent[field]=value
                guard=self.source.CanScout if scout else self.source.CanAttack
                self.assertFalse(guard(self.source,self.p,99)[0])
            self.make(scout);self.state.data.derived.war.enemyId='changed'
            guard=self.source.CanScout if scout else self.source.CanAttack
            self.assertFalse(guard(self.source,self.p,99)[0])
    def test_native_shield_family_and_no_points_warning_still_require_manual_handling(self):
        for scout in (False,True):
            for field,value in (('warning','NO WAR POINTS'),('family',True),('shield',9999999999),('remaining',0),('cooldown',1),('busy',True)):
                self.make(scout);self.probe[field]=value
                guard=self.source.CanScout if scout else self.source.CanAttack
                self.assertFalse(guard(self.source,self.p,99)[0])
    def test_native_build_context_or_config_replacement_fences_war(self):
        self.make();self.game.PlaceVersion=649;self.assertFalse(self.source.CanAttack(self.source,self.p,99)[0])
        self.make();self.state.data.family.id='enemy-family';self.assertFalse(self.source.CanAttack(self.source,self.p,99)[0])

    def test_exact_numeric_family_identity_uses_native_family_guard_without_string_coercion(self):
        self.make()
        self.p.intent.familyId=22;self.p.intent.warFamilyId=22;self.p.intent.ownFamilyId=21
        self.state.data.family.id=21;self.state.data.derived.war.enemyId=22
        self.assertTrue(self.source.CanAttack(self.source,self.p,99)[0])
        self.state.data.derived.war.enemyId='22'
        self.assertFalse(self.source.CanAttack(self.source,self.p,99)[0])
