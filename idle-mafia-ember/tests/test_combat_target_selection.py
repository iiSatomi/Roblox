"""Bounded player target policy; no executor, transport or native effects."""
import unittest
from engine_harness import Harness,lua_table

class CombatTargetSelectionTests(unittest.TestCase):
    def setUp(self):
        self.h=Harness();self.module=self.h.load('src/tabs/combat/TargetSelection.luau')
    def view(self):
        return lua_table(self.h.lua,{'status':'known','serverNow':1000,'ownUserId':1,'ownFamilyId':9,
            'health':100,'maxHealth':100,'stamina':20,'attack':200,
            'hospitalHealth':20,'scoutCost':1,'fightVariance':.2,'fightVarianceCap':5000,
            'war':{'active':True,'enemyFamilyId':10,'statusServerNow':1000,'canScore':True,'eligibleAt':0,'ownRemaining':8,'ownCap':20},
            'targets':[{'userId':2,'name':'Target','level':10,'staminaCost':2,'familyId':11,
                'friend':False,'shieldUntil':0,'remainingDaily':5,'cooldownUntil':0,
                'warStatus':{'day':0,'remaining':3,'cap':5,'attacksRemaining':2,'attacksCap':8,'pairRemaining':1,'canScore':True},
                'history':[{'at':900,'cash':1000,'won':True}],
                'stats':{'at':990,'defense':100,'kind':'scout','level':10}}]})
    def settings(self,**kw):
        v={'enabled':True,'policy':'Balanced','minimumPayout':100,'healthFloor':50,'staminaReserve':1,
            'targetSource':'Saved and new','allowScout':False,'maxStaminaCost':5,'minTargetLevel':1,
            'maxTargetLevel':10000,'minSamples':1,'minWinRate':70,'minWinChance':60,'minPowerRatio':1,
            'scoutMaxAge':30,'maxScoutSpend':0,'maxAttackSpend':20}
        v.update(kw);return lua_table(self.h.lua,v)
    def choose(self,view=None,settings=None,mode='combat',held=None):
        return self.module.choose(view or self.view(),settings or self.settings(),
            lua_table(self.h.lua,held or {'stamina':0,'health':0,'attackSpent':0,'scoutSpent':0}),mode)
    def test_minimum_attack_quote_is_inclusive_and_not_reserved_maximum_exposure(self):
        view=self.view();view.maxNativeStaminaCost=5
        self.assertIsNotNone(self.choose(view,self.settings(minStaminaCost=2))[0])
        self.assertIsNone(self.choose(view,self.settings(minStaminaCost=3))[0])
        view.targets[1].familyId=10;view.targets[1].warFamilyId=10
        self.assertIsNotNone(self.choose(view,self.settings(minStaminaCost=2),mode='warCombat')[0])
        self.assertIsNone(self.choose(view,self.settings(minStaminaCost=3),mode='warCombat')[0])
        view.targets[1].familyId=11;view.targets[1].warFamilyId=None;view.targets[1].stats=None
        selected=self.choose(view,self.settings(minStaminaCost=2,allowScout=True,maxScoutSpend=5))[0]
        self.assertEqual((selected.kind,selected.cost),('scout',1))
        self.assertIsNone(self.choose(view,self.settings(minStaminaCost=3,allowScout=True,maxScoutSpend=5))[0])
    def test_invalid_or_inverted_attack_quote_range_refuses(self):
        for low in (0,6,1.5,True,'2'):
            self.assertIsNone(self.choose(settings=self.settings(minStaminaCost=low))[0])
        self.assertIsNone(self.choose(settings=self.settings(minStaminaCost=3,maxStaminaCost=2))[0])
    def test_daily_only_uses_known_native_count_and_keeps_repeat_permission_separate(self):
        view=self.view();view.targets[1].attacksToday=1
        self.assertIsNone(self.choose(view,self.settings(dailyOnly=True))[0])
        self.assertIsNotNone(self.choose(view,self.settings(dailyOnly=False))[0])
        view.targets[1].attacksToday=0
        self.assertIsNotNone(self.choose(view,self.settings(dailyOnly=True))[0])
    def test_daily_only_missing_malformed_count_or_setting_never_becomes_zero(self):
        for value in (None,-1,1.5,True,'0'):
            view=self.view();view.targets[1].attacksToday=value
            self.assertIsNone(self.choose(view,self.settings(dailyOnly=True))[0])
        self.assertIsNone(self.choose(settings=self.settings(dailyOnly='false'))[0])
    def test_ordinary_daily_only_prevents_unneeded_scout_but_does_not_cap_war_scoring(self):
        view=self.view();view.targets[1].attacksToday=1;view.targets[1].stats=None
        self.assertIsNone(self.choose(view,self.settings(dailyOnly=True,allowScout=True,maxScoutSpend=5))[0])
        row=view.targets[1];row.familyId=10;row.warFamilyId=10
        self.assertIsNotNone(self.choose(view,self.settings(dailyOnly=True,allowScout=True,maxScoutSpend=5),mode='warCombat')[0])
    def test_saved_and_new_prefers_eligible_history_then_falls_back_to_unknown(self):
        view=self.view();saved=view.targets[1];saved.userId=3;saved.history[1].cash=0
        new=self.view().targets[1];new.userId=2;new.history=self.h.lua.table();view.targets[2]=new
        settings=self.settings(minSamples=0,minimumPayout=0)
        self.assertEqual(self.choose(view,settings)[0].userId,3)
        saved.shieldUntil=2000
        self.assertEqual(self.choose(view,settings)[0].userId,2)
        settings.targetSource='Saved only';self.assertIsNone(self.choose(view,settings)[0])
    def test_value_per_stamina_uses_native_quote_instead_of_maximum_exposure(self):
        view=self.view();view.maxNativeStaminaCost=5;other=self.view().targets[1];other.userId=3
        other.staminaCost=1;other.history[1].cash=800;view.targets[2]=other
        self.assertEqual(self.choose(view,self.settings(targetPriority='Risk-adjusted value'))[0].userId,2)
        self.assertEqual(self.choose(view,self.settings(targetPriority='Value / stamina'))[0].userId,3)
    def test_recent_payout_and_risk_adjusted_priorities_are_distinct_after_safety_filters(self):
        view=self.view();view.targets[1].stats.defense=180;view.targets[1].history[1].cash=2000
        other=self.view().targets[1];other.userId=3;other.history[1].cash=1500;view.targets[2]=other
        self.assertEqual(self.choose(view,self.settings(targetPriority='Risk-adjusted value'))[0].userId,3)
        self.assertEqual(self.choose(view,self.settings(targetPriority='Recent payout'))[0].userId,2)
        view.targets[1].shieldUntil=2000
        self.assertEqual(self.choose(view,self.settings(targetPriority='Recent payout'))[0].userId,3)
    def test_safest_and_highest_level_are_lexicographic_without_magic_cash_weights(self):
        view=self.view();view.targets[1].stats.defense=180;view.targets[1].history[1].cash=9007199254740991
        other=self.view().targets[1];other.userId=3;other.history[1].cash=1;view.targets[2]=other
        self.assertEqual(self.choose(view,self.settings(targetPriority='Safest history',minimumPayout=0))[0].userId,3)
        view.targets[1].stats.defense=100;other.level=11;other.stats.level=11
        self.assertEqual(self.choose(view,self.settings(targetPriority='Highest eligible level',minimumPayout=0))[0].userId,3)
    def test_priority_ties_remain_stable_and_invalid_labels_refuse(self):
        view=self.view();other=self.view().targets[1];other.userId=3;view.targets[2]=other
        for priority in ('Risk-adjusted value','Value / stamina','Recent payout','Safest history','Highest eligible level'):
            self.assertEqual(self.choose(view,self.settings(targetPriority=priority))[0].userId,2)
        for priority in ('Unknown',False,2):self.assertIsNone(self.choose(view,self.settings(targetPriority=priority))[0])
    def test_explicit_lookup_source_options_preserve_base_phase_and_all_fight_filters(self):
        view=self.view();view.targets[1].history=self.h.lua.table()
        settings=self.settings(targetSource='Saved only + lookup',minSamples=0,minimumPayout=0)
        self.assertIsNone(self.choose(view,settings)[0])
        settings.targetSource='Saved and new + lookup'
        self.assertIsNotNone(self.choose(view,settings)[0])
        view.targets[1].friend=True;self.assertIsNone(self.choose(view,settings)[0])
    def test_known_history_and_scout_select_exact_target_cost(self):
        selected,why=self.choose();self.assertIsNone(why)
        self.assertEqual(selected.userId,2);self.assertEqual(selected.kind,'attack');self.assertEqual(selected.cost,2)
    def test_each_exclusion_is_independent_and_unknown_friend_is_not_false(self):
        for field,value in [('userId',1),('familyId',9),('friend',True),('friend',None),
                ('shieldUntil',1001),('remainingDaily',0),('cooldownUntil',1001),('staminaCost',6)]:
            with self.subTest(field=field,value=value):
                view=self.view();view.targets[1][field]=value;self.assertIsNone(self.choose(view)[0])
    def test_health_stamina_and_other_holds_preserve_reserves(self):
        self.assertIsNone(self.choose(held={'stamina':18,'health':0,'attackSpent':0,'scoutSpent':0})[0])
        self.assertIsNone(self.choose(held={'stamina':0,'health':51,'attackSpent':0,'scoutSpent':0})[0])
        view=self.view();view.health=49;self.assertIsNone(self.choose(view)[0])
    def test_fresh_scout_has_independent_opt_in_and_spend_cap(self):
        view=self.view();view.targets[1].stats=None
        self.assertIsNone(self.choose(view)[0])
        settings=self.settings(allowScout=True,maxScoutSpend=1)
        selected,why=self.choose(view,settings);self.assertIsNone(why);self.assertEqual(selected.kind,'scout')
        self.assertEqual(selected.cost,1)
        self.assertIsNone(self.choose(view,settings,held={'stamina':0,'health':0,'attackSpent':0,'scoutSpent':1})[0])
    def test_scout_keeps_followup_attack_and_stamina_reserve(self):
        view=self.view();view.targets[1].stats=None;view.stamina=3
        self.assertIsNone(self.choose(view,self.settings(allowScout=True,maxScoutSpend=1))[0])
    def test_old_or_changed_level_stats_need_new_scout(self):
        for at,level in ((969,10),(1001,10),(990,11)):
            view=self.view();view.targets[1].stats.at=at;view.targets[1].stats.level=level
            self.assertIsNone(self.choose(view)[0])
    def test_saved_only_and_minimum_payout_never_treat_unknown_as_known(self):
        view=self.view();view.targets[1].history=self.h.lua.table()
        self.assertIsNone(self.choose(view,self.settings(targetSource='Saved only'))[0])
        self.assertIsNone(self.choose(view)[0])
        self.assertIsNotNone(self.choose(view,self.settings(minimumPayout=0,minSamples=0))[0])
    def test_war_targets_require_separate_verified_enemy_identity_and_scout(self):
        view=self.view();view.targets[1].warFamilyId=10
        self.assertIsNone(self.choose(view,mode='warCombat')[0])
        view.targets[1].familyId=10
        self.assertIsNotNone(self.choose(view,mode='warCombat')[0])
        view.targets[1].stats.kind='public'
        self.assertIsNone(self.choose(view,mode='warCombat')[0])
    def test_regular_hit_list_is_never_war_proof(self):
        view=self.view();view.targets[1].familyId=10
        self.assertIsNone(self.choose(view,mode='warCombat')[0])
        view.targets[1].warFamilyId=10;view.war.active=False
        self.assertIsNone(self.choose(view,mode='warCombat')[0])
    def test_rank_saved_targets_before_new_and_use_recent_payout(self):
        view=self.view();row=self.view().targets[1];row.userId=3
        row.history=lua_table(self.h.lua,[{'at':999,'cash':2000,'won':True}]);view.targets[2]=row
        selected=self.choose(view)[0];self.assertEqual(selected.userId,3)
    def test_minimum_win_rate_samples_level_cost_and_attempt_exposure(self):
        for kw in ({'minSamples':2},{'minTargetLevel':11},{'maxTargetLevel':9},{'maxStaminaCost':1},{'maxAttackSpend':1}):
            with self.subTest(kw=kw):self.assertIsNone(self.choose(settings=self.settings(**kw))[0])
        view=self.view();view.targets[1].history[1].won=False
        self.assertIsNone(self.choose(view)[0])
    def test_missing_identity_or_nonfinite_values_fail_closed(self):
        for field,value in [('serverNow',float('nan')),('maxHealth',0),('ownUserId',None),('ownFamilyId',None)]:
            view=self.view();view[field]=value;self.assertIsNone(self.choose(view)[0])
    def test_duplicate_ids_are_not_selected(self):
        view=self.view();view.targets[2]=self.view().targets[1]
        self.assertIsNone(self.choose(view)[0])

    def test_string_family_ids_keep_friendly_and_war_exclusions(self):
        view=self.view();view.ownFamilyId='family-own';view.war.enemyFamilyId='family-enemy'
        row=view.targets[1];row.familyId='family-other'
        self.assertIsNotNone(self.choose(view)[0])
        row.familyId='family-own';self.assertIsNone(self.choose(view)[0])
        row.familyId='family-enemy';self.assertIsNone(self.choose(view)[0])
        self.assertIsNone(self.choose(view,mode='warCombat')[0])
        row.warFamilyId='family-enemy'
        self.assertIsNotNone(self.choose(view,mode='warCombat')[0])
        row.warFamilyId='family-other';self.assertIsNone(self.choose(view,mode='warCombat')[0])

    def test_invalid_string_family_identity_is_not_an_unknown_no_family(self):
        for value in ('', 'x'*121, 'family\nother', 'family\x00other'):
            with self.subTest(value=repr(value)):
                view=self.view();view.ownFamilyId=value
                self.assertIsNone(self.choose(view)[0])
                view=self.view();view.targets[1].familyId=value
                self.assertIsNone(self.choose(view)[0])

    def test_mixed_nonzero_family_id_types_do_not_make_a_safe_foreign_target(self):
        view=self.view();view.ownFamilyId='9';view.war.active=False
        self.assertIsNone(self.choose(view)[0])
        view=self.view();view.war.enemyFamilyId='10'
        self.assertIsNone(self.choose(view)[0])
        self.assertIsNone(self.choose(view,mode='warCombat')[0])

    def test_target_specific_scout_quote_uses_its_own_cap_and_followup_reserve(self):
        view=self.view();view.targets[1].stats=None;view.targets[1].scoutCost=3
        self.assertIsNone(self.choose(view,self.settings(allowScout=True,maxScoutSpend=2))[0])
        selected=self.choose(view,self.settings(allowScout=True,maxScoutSpend=3))[0]
        self.assertEqual((selected.kind,selected.cost),('scout',3))
        view.stamina=5;self.assertIsNone(self.choose(view,self.settings(allowScout=True,maxScoutSpend=3))[0])

    def test_old_public_stats_request_free_refresh_instead_of_paid_scout(self):
        view=self.view();view.targets[1].stats.kind='public';view.targets[1].stats.at=900
        self.assertIsNone(self.choose(view,self.settings(allowScout=True,maxScoutSpend=10))[0])

    def test_war_policy_still_requires_paid_scout_evidence_even_when_public_stats_exist(self):
        view=self.view();row=view.targets[1];row.familyId=10;row.warFamilyId=10;row.stats.kind='public'
        selected=self.choose(view,self.settings(allowScout=True,maxScoutSpend=1),mode='warCombat')[0]
        self.assertEqual(selected.kind,'scout')

    def test_configured_max_exposure_must_fit_attack_cap_and_physical_reserve(self):
        view=self.view();view.maxNativeStaminaCost=5
        self.assertIsNone(self.choose(view,self.settings(maxAttackSpend=2))[0])
        view.stamina=4;self.assertIsNone(self.choose(view,self.settings(maxAttackSpend=5))[0])
        view.stamina=20;selected=self.choose(view,self.settings(maxAttackSpend=5))[0]
        self.assertEqual((selected.cost,selected.exposure),(2,5))
    def test_scout_max_exposure_keeps_both_budgets_and_followup_reserve(self):
        view=self.view();view.maxNativeStaminaCost=5;view.targets[1].stats=None
        self.assertIsNone(self.choose(view,self.settings(allowScout=True,maxScoutSpend=1))[0])
        view.stamina=10;self.assertIsNone(self.choose(view,self.settings(allowScout=True,maxScoutSpend=5))[0])
        view.stamina=20;selected=self.choose(view,self.settings(allowScout=True,maxScoutSpend=5))[0]
        self.assertEqual((selected.kind,selected.cost,selected.exposure),('scout',1,5))

    def war_view(self):
        view=self.view();view.targets[1].familyId=10;view.targets[1].warFamilyId=10;return view
    def test_war_policy_requires_native_current_scoring_and_valid_own_defeat_counts(self):
        for field,value in [('canScore',False),('canScore',None),('eligibleAt',1001),('statusServerNow',989),
                            ('statusServerNow',1011),('ownRemaining',21),('ownRemaining',None),('ownCap',None)]:
            with self.subTest(field=field,value=value):
                view=self.war_view();view.war[field]=value
                self.assertIsNone(self.choose(view,mode='warCombat')[0])
    def test_war_policy_rejects_each_native_scoring_cap_before_attack_or_paid_scout(self):
        for field,value in [('remaining',0),('remaining',6),('attacksRemaining',0),('attacksRemaining',9),
                            ('pairRemaining',0),('canScore',False),('canScore',None),('day',1),('cap',None)]:
            for scout in (False,True):
                with self.subTest(field=field,value=value,scout=scout):
                    view=self.war_view();view.targets[1].warStatus[field]=value
                    if scout:view.targets[1].stats=None
                    self.assertIsNone(self.choose(view,self.settings(allowScout=scout,maxScoutSpend=5),mode='warCombat')[0])
    def test_missing_native_war_allowance_never_falls_back_to_ordinary_daily_count(self):
        view=self.war_view();view.targets[1].warStatus=None
        self.assertIsNone(self.choose(view,mode='warCombat')[0])
    def test_own_defeat_allowance_zero_does_not_invent_an_attack_ban(self):
        view=self.war_view();view.war.ownRemaining=0
        self.assertIsNotNone(self.choose(view,mode='warCombat')[0])
    def test_capped_first_enemy_does_not_hide_a_second_eligible_enemy(self):
        view=self.war_view();second=self.war_view().targets[1];second.userId=3
        view.targets[2]=second;view.targets[1].warStatus.pairRemaining=0
        self.assertEqual(self.choose(view,mode='warCombat')[0].userId,3)
    def test_ordinary_mode_does_not_require_or_consume_war_scoring_allowances(self):
        view=self.view();view.war.canScore=False;view.war.ownRemaining=None;view.targets[1].warStatus=None
        self.assertIsNotNone(self.choose(view)[0])
