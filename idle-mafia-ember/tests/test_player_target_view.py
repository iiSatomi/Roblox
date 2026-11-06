"""Owned sources/usage/history compose an ordinary target view; no transport."""
import unittest
from engine_harness import Harness,lua_table

class PlayerTargetViewTests(unittest.TestCase):
    def setUp(self):
        self.h=Harness();self.module=self.h.load('src/tabs/combat/PlayerTargetState.luau')
        self.raw=self.h.snapshot(native={'fullSync':True,'serverNow':1000,'pools':{'health':100,'stamina':20},
            'stats':{'maxHealth':100},'family':{'id':'own-family'},'attackDaily':{'day':0,'counts':{}}})
        self.context=lua_table(self.h.lua,{**self.h.session,'revision':1,'capturedAt':0,'serverNow':1000})
        header={**self.h.session,'revision':1,'capturedAt':0,'serverNow':1000}
        frame={'sourceKey':'a'*64,'header':header,'ownUserId':1,'ownFamilyId':'own-family','attack':200,
            'health':100,'maxHealth':100,'stamina':20,'hospitalHealth':20,'staminaCost':1,'scoutCost':1,
            'maxStaminaCost':5,'dailyTargetCap':5,'targetCooldown':30,'fightVariance':.2,'fightVarianceCap':5000,
            'busy':False,'shielded':False,'globalCooldown':0,
            'targets':{'2':{'remainingDaily':5,'cooldownLeft':0,'sameFamily':False,'manualWarning':False}}}
        profile={'userId':2,'name':'Target','level':10,'maxLevel':10,'familyId':'other-family','scoutCost':1,
            'statsHidden':False,'defense':100,'friend':False,'friendshipStatus':'reported','friendshipObservedAt':990,'observedServerNow':990,'observedAt':0}
        self.raw.hitListProof=lua_table(self.h.lua,{'account':'user-a','capturedAt':0,'sourceKey':'a'*64,'header':header,
            'readHeader':header,'observedAt':0,'observedServerNow':1000,'nativeFrame':frame,
            'rows':[{'userId':2,'name':'Target','level':10,'stamina':2,'shielded':False,'familyId':'other-family'}],
            'profiles':{'2':profile},'war':{'active':False,'statusServerNow':1000}})
        usage=self.h.load('src/tabs/combat/PlayerFightUsage.luau').copy(None)
        self.raw.playerFightUsageProof=lua_table(self.h.lua,{'account':'user-a','capturedAt':0,'usage':usage})
        self.raw.playerFightHistoryProof=lua_table(self.h.lua,{**header,'recent':[{'requestId':1,'feature':'combat','target':2,
            'serverNow':900,'initial':{'targetDaily':{'serverNow':900}},'receipt':{'won':True,'cashConfirmed':1000}}]})
    def read(self):return self.module.readSelection(self.raw,self.context)
    def test_attacks_today_takes_maximum_of_replicated_native_and_owned_history(self):
        self.assertEqual(self.read()[0].targets[1].attacksToday,1)
        self.raw.native.attackDaily.counts['2']=3
        self.assertEqual(self.read()[0].targets[1].attacksToday,3)
        self.raw.native.attackDaily.counts['2']=0;self.raw.hitListProof.nativeFrame.targets['2'].remainingDaily=3
        self.assertEqual(self.read()[0].targets[1].attacksToday,2)
    def test_empty_history_is_zero_and_impossible_native_remaining_is_unknown(self):
        self.raw.playerFightHistoryProof.recent=self.h.lua.table()
        self.assertEqual(self.read()[0].targets[1].attacksToday,0)
        self.raw.hitListProof.nativeFrame.targets['2'].remainingDaily=6
        self.assertEqual(len(self.read()[0].targets),0)
    def test_new_native_utc_day_does_not_reuse_yesterdays_saved_count(self):
        now=87400;self.raw.native.serverNow=now;self.raw.native.attackDaily.day=1;self.context.serverNow=now
        proof=self.raw.hitListProof;proof.observedServerNow=now;proof.war.statusServerNow=now
        for header in (proof.header,proof.readHeader,proof.nativeFrame.header,self.raw.playerFightHistoryProof):header.serverNow=now
        profile=proof.profiles['2'];profile.observedServerNow=now-10;profile.friendshipObservedAt=now-10
        view,why=self.read();self.assertIsNotNone(view,why);self.assertEqual(view.targets[1].attacksToday,0)
    def test_current_sources_compose_exact_target_quote_history_stats_and_independent_usage(self):
        view,why=self.read();self.assertIsNotNone(view,why);row=view.targets[1]
        self.assertEqual((view.attack,view.ownFamilyId,row.staminaCost,row.scoutCost,row.familyId),(200,'own-family',2,1,'other-family'))
        self.assertEqual((row.stats.defense,row.stats.kind,row.history[1].cash),(100,'public',1000))
        self.assertEqual((view.attackSpent,view.scoutSpent),(0,0));self.assertFalse(row.friend)
    def test_hidden_stats_stay_absent_and_unknown_friendship_is_not_false(self):
        p=self.raw.hitListProof.profiles['2'];p.statsHidden=True;p.defense=999;p.friend=None;p.friendshipStatus='unknown'
        view,why=self.read();self.assertIsNotNone(view,why);self.assertIsNone(view.targets[1].stats)
        self.assertIsNone(view.targets[1].friend)
    def test_missing_or_changed_owned_source_headers_usage_and_history_are_unknown(self):
        for field in ('nativeFrame','profiles'):
            self.setUp();self.raw.hitListProof[field]=None;self.assertIsNone(self.read()[0])
        self.setUp();self.raw.hitListProof.nativeFrame.header.revision=2;self.assertIsNone(self.read()[0])
        self.setUp();self.raw.playerFightUsageProof.usage.lanes.combat=None;self.assertIsNone(self.read()[0])
        self.setUp();self.raw.playerFightHistoryProof=None;self.assertIsNone(self.read()[0])
    def test_busy_own_shield_and_native_manual_warning_do_not_become_attackable(self):
        for field,value in [('busy',True),('shielded',True),('globalCooldown',1)]:
            self.setUp();self.raw.hitListProof.nativeFrame[field]=value;self.assertIsNone(self.read()[0])
        self.setUp();self.raw.hitListProof.nativeFrame.targets['2'].manualWarning=True
        self.assertEqual(len(self.read()[0].targets),0)
    def test_native_family_exclusion_and_profile_identity_change_never_become_foreign_targets(self):
        self.raw.hitListProof.nativeFrame.targets['2'].sameFamily=True;self.assertEqual(len(self.read()[0].targets),0)
        self.setUp();self.raw.hitListProof.profiles['2'].familyId='different';self.assertEqual(len(self.read()[0].targets),0)
    def test_daily_limits_use_lower_native_or_snapshot_remaining_and_cooldown_uses_owned_reply_time(self):
        self.raw.native.attackDaily.counts['2']=3;self.raw.hitListProof.nativeFrame.targets['2'].remainingDaily=4
        self.raw.playerFightHistoryProof.recent[1].serverNow=970
        self.raw.playerFightHistoryProof.recent[1].initial.targetDaily.serverNow=980
        row=self.read()[0].targets[1];self.assertEqual(row.remainingDaily,2);self.assertEqual(row.cooldownUntil,1011)
    def test_war_attack_history_affects_shared_target_cooldown_but_not_ordinary_payout_samples(self):
        r=self.raw.playerFightHistoryProof.recent[1];r.feature='warCombat';r.serverNow=980;r.initial.targetDaily.serverNow=990
        row=self.read()[0].targets[1];self.assertEqual(len(row.history),0);self.assertEqual(row.cooldownUntil,1021)
    def test_stale_profile_does_not_supply_stats_or_friendship(self):
        self.raw.hitListProof.profiles['2'].observedServerNow=969
        self.assertEqual(len(self.read()[0].targets),0)
    def test_missing_saved_server_time_does_not_invent_a_repeat_cooldown(self):
        self.raw.playerFightHistoryProof.recent[1].initial.targetDaily.serverNow=None
        self.assertEqual(len(self.read()[0].targets),0)

    def test_missing_or_changed_observation_headers_return_unknown_without_raising(self):
        self.raw.capturedAt=None;self.assertIsNone(self.read()[0])
        self.setUp();self.raw.native.serverNow=None;self.assertIsNone(self.read()[0])
        self.setUp();self.raw.hitListProof.readHeader.account='other';self.assertIsNone(self.read()[0])
        self.setUp();self.raw.hitListProof.nativeFrame.header.serverNow=None;self.assertIsNone(self.read()[0])
    def test_malformed_visible_stats_do_not_become_permission_to_scout(self):
        self.raw.hitListProof.profiles['2'].defense=float('nan');self.assertEqual(len(self.read()[0].targets),0)
    def test_reported_friendship_without_observation_time_remains_unknown(self):
        self.raw.hitListProof.profiles['2'].friendshipObservedAt=None
        self.assertIsNone(self.read()[0].targets[1].friend)

    def test_missing_war_status_never_becomes_an_explicit_inactive_war(self):
        self.raw.hitListProof.war=None;self.assertIsNone(self.read()[0])
    def test_active_war_requires_verified_enemy_identity_and_preserves_ordinary_exclusions(self):
        self.raw.hitListProof.war=lua_table(self.h.lua,{'active':True,'statusServerNow':1000});self.assertIsNone(self.read()[0])
        self.raw.hitListProof.war.enemyFamilyId='other-family'
        view=self.read()[0];self.assertTrue(view.war.active);self.assertEqual(view.war.enemyFamilyId,'other-family')

    def test_floored_native_reply_time_does_not_invalidate_fractional_snapshot_time(self):
        row=self.raw.playerFightHistoryProof.recent[1];row.serverNow=980.5;row.initial.targetDaily.serverNow=980
        view=self.read()[0];self.assertEqual(len(view.targets),1);self.assertEqual(view.targets[1].cooldownUntil,1011)

    def test_owned_scout_stats_fill_hidden_profile_and_expire_without_becoming_public(self):
        p=self.raw.hitListProof.profiles['2'];p.statsHidden=True;p.defense=None
        p.scout=lua_table(self.h.lua,{'at':995,'defense':80,'level':10,'kind':'scout'})
        view,why=self.read();self.assertIsNotNone(view,why)
        self.assertEqual((view.targets[1].stats.kind,view.targets[1].stats.defense),('scout',80))
        for field,value in [('at',1001),('level',11),('defense',0),('kind','public')]:
            old=p.scout[field];p.scout[field]=value
            self.assertIsNone(self.read()[0].targets[1].stats);p.scout[field]=old
    def test_newer_public_stats_replace_older_scout_and_newer_scout_is_kept_distinct(self):
        p=self.raw.hitListProof.profiles['2']
        p.scout=lua_table(self.h.lua,{'at':989,'defense':80,'level':10,'kind':'scout'})
        self.assertEqual(self.read()[0].targets[1].stats.kind,'public')
        p.scout.at=995;self.assertEqual(self.read()[0].targets[1].stats.kind,'scout')

    def test_profile_native_shield_excludes_a_target_even_when_hitlist_was_unshielded(self):
        self.raw.hitListProof.profiles['2'].shieldUntil=1010
        self.assertEqual(len(self.read()[0].targets),0)

    def test_native_own_user_id_must_match_the_pinned_combat_frame_when_present(self):
        self.raw.native.userId=2
        self.assertIsNone(self.read()[0])
        self.raw.native.userId=1;self.assertIsNotNone(self.read()[0])
