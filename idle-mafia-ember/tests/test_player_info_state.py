"""Read-only player facts and confirmed session mug rates; no balance-delta inference."""
import unittest
from engine_harness import Harness,lua_table

class PlayerInfoStateTests(unittest.TestCase):
    def setUp(self):
        self.h=getattr(self,"provided_h",None) or Harness();self.owner=self.h.load('src/game/PlayerInfoState.luau').new(lua_table(self.h.lua,self.h.session))
        self.raw=self.h.snapshot(native={'fullSync':True,'serverNow':1000,'userId':42,'level':20,'maxLevel':25,'prestige':2,
            'respect':400,'cash':1000,'banked':5000,'xp':250,'skillPoints':3,'fightWins':4,'defWins':2,'crewSize':6,
            'pools':{'health':80,'energy':30,'stamina':20},'stats':{'atkBase':50,'defBase':40,'maxHealth':100,'maxEnergy':100,'maxStamina':40},
            'derived':{'incomePerHour':2000,'goldPerDay':2,'gearAtk':20,'gearDef':10,'familyName':'Family',
                'statBreakdown':{'atk':{'total':150,'base':50,'gear':20},'def':{'total':120,'base':40,'gear':10}}},
            'properties':{'p_a':{'owned':2},'p_b':{'owned':1}},'lots':['p_a','p_b'],'trustScore':999})
        self.facts=lua_table(self.h.lua,{'userId':42,'name':'LocalUser','displayName':'Local Display','propertyMultiplier':1.5,
            'properties':[{'id':'p_a','name':'Laundromat','incomePerHour':100},{'id':'p_b','name':'Diner','incomePerHour':300}]})
        self.ledger=lua_table(self.h.lua,{'fights':0,'lastRequestId':0,'recent':[]})
    def observe(self,at=0):
        self.raw.capturedAt=at;self.raw.revision+=1;self.raw.native.serverNow=1000+at
        return self.owner.Observe(self.owner,self.raw,at,self.facts,self.ledger)
    def row(self,request,feature,cash):
        return {'requestId':request,'feature':feature,'receipt':{'cashConfirmed':cash,'won':cash>0}}
    def test_native_totals_effective_property_rate_and_owned_active_breakdown(self):
        view=self.observe();self.assertEqual((view.attack,view.defense,view.propertyBasePerHour,view.propertyPerHour),(150,120,2000,3000))
        self.assertEqual((view.ownedProperties,view.activeProperties,view.inactiveProperties),(3,2,1))
        self.assertEqual((view.properties[1].name,view.properties[1].owned,view.properties[1].active),('Laundromat',2,1))
        self.assertIsNone(view.trustScore);self.assertEqual(view.trustStatus,'Not exposed by the observed client')
        self.assertIsNone(view.mugPerHour);self.assertIsNone(view.combinedPerHour)
    def test_cash_balance_changes_do_not_become_mug_income_and_rates_include_idle_time(self):
        self.observe();self.raw.native.cash=9999999;view=self.observe(60)
        self.assertEqual(view.mugCash,0);self.assertEqual(view.mugPerHour,0);self.assertEqual(view.combinedPerHour,3000)
    def test_owned_confirmed_payouts_separate_war_and_deduplicate_across_refreshes(self):
        self.observe();self.ledger.fights=2;self.ledger.lastRequestId=9
        self.ledger.recent=lua_table(self.h.lua,[self.row(7,'combat',100),self.row(9,'warCombat',9999)])
        v=self.observe(60);self.assertEqual((v.mugCash,v.mugFights,v.mugPerHour,v.combinedPerHour),(100,1,6000,9000))
        v=self.observe(120);self.assertEqual((v.mugCash,v.mugPerHour),(100,3000))
    def test_existing_history_before_observation_is_not_new_session_income(self):
        self.ledger.fights=1;self.ledger.lastRequestId=10;self.ledger.recent=lua_table(self.h.lua,[self.row(10,'combat',9999)])
        self.observe();self.assertEqual(self.observe(60).mugCash,0)
    def test_missing_receipts_or_counter_regression_make_the_rate_unknown(self):
        self.observe();self.ledger.fights=2;self.ledger.lastRequestId=10
        self.ledger.recent=lua_table(self.h.lua,[self.row(10,'combat',100)])
        v=self.observe(60);self.assertIsNone(v.mugPerHour);self.assertIn('incomplete',v.mugStatus.lower())
        self.assertIsNone(self.observe(120).mugPerHour)
    def test_wrong_scope_identity_stale_or_closed_owner_never_publishes_fresh_facts(self):
        self.raw.account='other';self.assertIsNone(self.observe())
        self.setUp();self.facts.userId=43;v=self.observe();self.assertIsNone(v.name);self.assertIsNone(v.propertyPerHour)
        self.setUp();self.observe();self.assertEqual(self.owner.Read(self.owner,3).status,'stale')
        self.owner.Close(self.owner);self.assertIsNone(self.owner.Read(self.owner,3));self.assertIsNone(self.observe(3))
    def test_unknown_multiplier_missing_stats_or_catalog_never_invents_zero_or_total(self):
        self.facts=None;self.raw.native.derived.statBreakdown=None;v=self.observe()
        self.assertIsNone(v.attack);self.assertEqual(v.attackBase,50);self.assertIsNone(v.propertyPerHour)
        self.assertEqual(v.propertyBasePerHour,2000);self.assertIsNone(v.properties)
    def test_empty_owned_properties_is_known_zero_and_results_are_detached(self):
        self.raw.native.properties=lua_table(self.h.lua,{});self.raw.native.lots=lua_table(self.h.lua,[])
        v=self.observe();self.assertEqual(v.ownedProperties,0);self.assertEqual(v.activeProperties,0)
        v.cash=0;self.assertEqual(self.owner.Read(self.owner,0).cash,1000)

    def test_scope_change_retires_previous_identity_instead_of_displaying_cached_personal_data(self):
        self.observe();self.raw.account='other'
        self.assertIsNone(self.observe(.25));self.assertIsNone(self.owner.Read(self.owner,.25))

    def test_changed_native_user_id_cannot_relabel_previous_current_player_under_same_header(self):
        self.observe();self.raw.native.userId=99
        self.assertIsNone(self.observe(.25));self.assertIsNone(self.owner.Read(self.owner,.25))
