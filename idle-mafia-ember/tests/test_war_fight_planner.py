"""Independent owned War selection; ordinary catalog is never a target authority."""
import unittest
import test_war_profile_query as profile_fixture
from engine_harness import lua_table

class WarTargetViewTests(unittest.TestCase):
    def setUp(self):
        self.f=profile_fixture.WarProfileQueryTests();self.f.setUp();self.h=self.f.h
        self.f.f.reply.warStatus.targets[1].stamina=2;self.f.f.commit()
        self.f.reply.profile.shieldLeft=0;self.f.accept();self.raw=self.f.raw
        self.raw.native.userId=1;self.raw.native.pools=lua_table(self.h.lua,{'health':100,'stamina':20})
        self.raw.native.stats=lua_table(self.h.lua,{'maxHealth':100})
        self.raw.native.attackDaily=lua_table(self.h.lua,{'day':0,'counts':{}})
        self.context=lua_table(self.h.lua,{**self.h.session,'revision':1,'capturedAt':0,'serverNow':1000})
        self.raw.warRosterProof=self.f.targets.Read(self.f.targets,self.raw)
        self.raw.warRosterProof.profiles=self.f.q.Read(self.f.q,self.raw)
        self.profile=self.raw.warRosterProof.profiles['42']
        self.profile.scout=lua_table(self.h.lua,{'kind':'scout','level':128,'defense':100,'at':999})
        self.header={**self.h.session,'revision':1,'capturedAt':0,'serverNow':1000}
        frame={'sourceKey':'a'*64,'header':self.header,'ownUserId':1,'ownFamilyId':'own-family','attack':200,
            'health':100,'maxHealth':100,'stamina':20,'hospitalHealth':20,'staminaCost':1,'scoutCost':1,
            'maxStaminaCost':5,'dailyTargetCap':5,'targetCooldown':30,'fightVariance':.2,'fightVarianceCap':5000,
            'busy':False,'shielded':False,'globalCooldown':0,
            'targets':{'42':{'remainingDaily':5,'cooldownLeft':0,'sameFamily':False,'manualWarning':False}}}
        self.raw.warRosterProof.nativeFrame=lua_table(self.h.lua,frame)
        usage=self.h.load('src/tabs/combat/PlayerFightUsage.luau').copy(None)
        usage.lanes.combat.attack.attempted=1;usage.lanes.combat.attack.spent=5
        self.raw.playerFightUsageProof=lua_table(self.h.lua,{'account':'user-a','capturedAt':0,'usage':usage})
        self.raw.playerFightHistoryProof=lua_table(self.h.lua,{**self.header,'recent':[]})
        self.reader=self.h.load('src/tabs/combat/PlayerTargetState.luau')
    def read(self):
        self.assertIsNotNone(self.reader.readWarSelection,'Owned War selection reader is missing')
        return self.reader.readWarSelection(self.raw,self.context)
    def test_exact_roster_profile_frame_scout_and_independent_usage_produce_war_target(self):
        view,why=self.read();self.assertIsNotNone(view,why)
        self.assertEqual((view.status,view.ownUserId,view.ownFamilyId,view.attackSpent),('known',1,'own-family',0))
        row=view.targets[1]
        self.assertEqual((row.userId,row.familyId,row.warFamilyId,row.staminaCost,row.friend),(42,'enemy-family','enemy-family',2,False))
        self.assertEqual((row.stats.kind,row.stats.defense,row.warStatus.pairRemaining),('scout',100,1))
        self.assertEqual((view.war.canScore,view.war.ownRemaining,view.war.canFeed),(True,8,False))
    def test_ordinary_hit_list_cannot_supply_war_target_quote_or_profile(self):
        self.raw.hitListProof=lua_table(self.h.lua,{'rows':[{'userId':99,'name':'Other','stamina':1}],
            'profiles':{'42':{'defense':1,'friend':False}}})
        view,why=self.read();self.assertIsNotNone(view,why);self.assertEqual(view.targets[1].userId,42)
        self.raw.warRosterProof.rows[1].stamina=None
        self.assertEqual(len(self.read()[0].targets),0)
    def test_current_native_frame_target_quote_supports_war_rows_without_a_quote(self):
        self.raw.warRosterProof.rows[1].stamina=None
        self.raw.warRosterProof.nativeFrame.targets['42'].staminaCost=3
        self.assertEqual(self.read()[0].targets[1].staminaCost,3)
        self.raw.warRosterProof.rows[1].stamina=2
        self.assertEqual(len(self.read()[0].targets),0)
    def test_missing_or_malformed_own_frame_daily_usage_and_history_refuse_selection(self):
        for field in ('nativeFrame',):
            self.setUp();self.raw.warRosterProof[field]=None;self.assertIsNone(self.read()[0])
        for field in ('playerFightUsageProof','playerFightHistoryProof'):
            self.setUp();self.raw[field]=None;self.assertIsNone(self.read()[0])
        self.setUp();self.raw.native.attackDaily.day=1;self.assertIsNone(self.read()[0])
        self.setUp();self.raw.warRosterProof.nativeFrame.ownUserId=2;self.assertIsNone(self.read()[0])
    def test_missing_profile_shield_or_friendship_is_never_invented_as_clear(self):
        self.profile.shieldStatus='unknown';self.assertEqual(len(self.read()[0].targets),0)
        self.setUp();self.profile.friend=None;self.profile.friendshipStatus='unknown'
        self.assertIsNone(self.read()[0].targets[1].friend)
        self.setUp();self.profile.shieldStatus='shielded';self.profile.shieldUntil=1010
        self.assertEqual(len(self.read()[0].targets),0)
    def test_native_manual_same_family_busy_or_shield_proof_cannot_be_bypassed(self):
        for key in ('manualWarning','sameFamily'):
            self.setUp();self.raw.warRosterProof.nativeFrame.targets['42'][key]=True
            self.assertEqual(len(self.read()[0].targets),0)
        for key,value in (('busy',True),('shielded',True),('globalCooldown',.1)):
            self.setUp();self.raw.warRosterProof.nativeFrame[key]=value;self.assertIsNone(self.read()[0])
    def test_public_stats_never_replace_fresh_scout_required_by_war(self):
        self.profile.statsHidden=False;self.profile.attack=300;self.profile.defense=1;self.profile.crew=1
        self.assertEqual(self.read()[0].targets[1].stats.kind,'scout')
        self.profile.scout=None
        self.assertEqual(self.read()[0].targets[1].stats.kind,'public')
    def test_bad_scout_identity_time_or_power_is_not_promoted(self):
        for field,value in (('kind','public'),('level',129),('defense',0),('at',1001),('at',-1)):
            self.setUp();self.profile.scout[field]=value;self.assertIsNone(self.read()[0].targets[1].stats)
    def test_war_history_samples_are_separate_while_all_fights_keep_shared_cooldown(self):
        self.raw.playerFightHistoryProof.recent=lua_table(self.h.lua,[{'requestId':1,'feature':'combat','target':42,
            'serverNow':980,'initial':{'targetDaily':{'serverNow':980}},'receipt':{'won':True,'cashConfirmed':1000}},
            {'requestId':2,'feature':'warCombat','target':42,'serverNow':900,'initial':{'targetDaily':{'serverNow':900}},
             'receipt':{'won':False,'cashConfirmed':0}}])
        row=self.read()[0].targets[1]
        self.assertEqual((len(row.history),row.history[1].cash,row.history[1].won),(1,0,False))
        self.assertEqual((row.attacksToday,row.cooldownUntil),(2,1011))
    def test_war_target_daily_allowance_takes_the_lowest_native_or_replicated_remaining(self):
        self.raw.native.attackDaily.counts['42']=4
        self.raw.warRosterProof.nativeFrame.targets['42'].remainingDaily=3
        self.assertEqual(self.read()[0].targets[1].remainingDaily,1)
    def test_read_is_detached_and_existing_observed_view_contract_is_preserved(self):
        view=self.read()[0];view.targets[1].warStatus.remaining=999
        self.assertEqual(self.raw.warRosterProof.rows[1].warStatus.remaining,3)
        observed,why=self.reader.readWar(self.raw,self.context)
        self.assertIsNotNone(observed,why);self.assertEqual(observed.status,'observed')
        self.assertIsNone(observed.targets[1].stats)

class WarFightPlannerTests(unittest.TestCase):
    def setUp(self):
        self.f=WarTargetViewTests();self.f.setUp();self.h=self.f.h
        self.view=self.f.read()[0]
        import test_combat_target_selection as policy_fixture
        policy=policy_fixture.CombatTargetSelectionTests();policy.h=self.h
        self.settings=policy.settings(minimumPayout=0,minSamples=0,maxAttackSpend=20,minPowerRatio=1.25)
        self.held=lua_table(self.h.lua,{'stamina':0,'uncertainStamina':0})
    def propose(self):
        from pathlib import Path
        self.assertTrue((Path(__file__).resolve().parents[1]/'src/tabs/combat/WarFightPlanner.luau').is_file(),
                        'War fight planner is missing')
        planner=self.h.load('src/tabs/combat/WarFightPlanner.luau').new(self.h.load('src/tabs/combat/TargetSelection.luau'))
        return planner.propose(self.view,self.settings,self.held)
    def test_exact_scouted_enemy_attack_uses_war_identity_quote_and_war_counters(self):
        p,why=self.propose();self.assertIsNotNone(p,why)
        self.assertEqual((p.feature,p.intent.kind,p.intent.target,p.intent.expectedStaminaCost,p.resources.stamina),
                         ('warCombat','playerAttack',42,2,5))
        self.assertEqual((p.actionKey,p.intent.warFamilyId,p.intent.ownFamilyId,p.intent.warDay),
                         ('warCombat:attack:42:0','enemy-family','own-family',0))
        self.assertEqual((p.intent.attemptedBefore,p.intent.spentBefore,p.intent.statsAt,p.intent.defense),(0,0,999,100))
    def test_war_enable_attack_and_scout_caps_are_separate_explicit_optins(self):
        self.settings.enabled=False;self.assertIsNone(self.propose()[0])
        self.settings.enabled=True;self.settings.maxAttackSpend=0;self.assertIsNone(self.propose()[0])
        self.settings.maxAttackSpend=5;self.view.targets[1].stats=None;self.assertIsNone(self.propose()[0])
        self.settings.allowScout=True;self.assertIsNone(self.propose()[0])
        self.settings.maxScoutSpend=5;p,why=self.propose();self.assertIsNotNone(p,why)
        self.assertEqual((p.intent.kind,p.intent.expectedStaminaCost,p.resources.stamina,p.intent.attackExposure),('playerScout',1,5,5))
        self.view.scoutSpent=5;self.assertIsNone(self.propose()[0])
    def test_public_or_expired_scout_requires_new_paid_scout_optin_without_attacking(self):
        for change in ('public','stale'):
            self.setUp()
            if change=='public':self.view.targets[1].stats.kind='public'
            else:self.view.targets[1].stats.at=969
            self.assertIsNone(self.propose()[0]);self.settings.allowScout=True;self.settings.maxScoutSpend=5
            self.assertEqual(self.propose()[0].intent.kind,'playerScout')
    def test_missing_or_capped_native_scoring_never_proposes_attack_or_paid_scout(self):
        for key,value in (('remaining',0),('pairRemaining',0),('attacksRemaining',0),('day',1),('canScore',False)):
            for scouting in (False,True):
                self.setUp();self.view.targets[1].warStatus[key]=value
                if scouting:self.view.targets[1].stats=None;self.settings.allowScout=True;self.settings.maxScoutSpend=5
                self.assertIsNone(self.propose()[0])
        for key,value in (('canScore',False),('canScore',None),('eligibleAt',1001),('statusServerNow',989)):
            self.setUp();self.view.war[key]=value;self.assertIsNone(self.propose()[0])
    def test_own_defeats_zero_does_not_invent_an_attack_cap(self):
        self.view.war.ownRemaining=0;self.assertIsNotNone(self.propose()[0])
    def test_current_enemy_identity_allies_friends_and_unknown_friendship_exclude(self):
        for field,value in (('warFamilyId','other'),('familyId','other'),('friend',True),('friend',None)):
            self.setUp();self.view.targets[1][field]=value;self.assertIsNone(self.propose()[0])
        self.setUp();self.settings.relationAllies='enemy-family';self.assertIsNone(self.propose()[0])
    def test_known_and_uncertain_shared_holds_keep_attack_and_followup_stamina_reserved(self):
        self.held.uncertainStamina=15;self.assertIsNone(self.propose()[0])
        self.held.uncertainStamina=2;p,why=self.propose();self.assertIsNotNone(p,why);self.assertEqual(p.intent.uncertainStamina,2)
        self.view.targets[1].stats=None;self.settings.allowScout=True;self.settings.maxScoutSpend=5
        self.view.stamina=12;self.assertIsNone(self.propose()[0])
    def test_corrupt_usage_counter_pairs_cannot_produce_a_durable_charge(self):
        for attempted,spent in ((0,1),(1,0),(1,6)):
            self.setUp();self.view.attackAttempted=attempted;self.view.attackSpent=spent
            self.assertIsNone(self.propose()[0])
    def test_attempted_allowance_charge_is_durable_separate_and_only_unsent_can_refund(self):
        p,why=self.propose();self.assertIsNotNone(p,why)
        usage=self.h.load('src/tabs/combat/PlayerFightUsage.luau')
        charged,charge,why=usage.charge(self.f.raw.playerFightUsageProof.usage,p);self.assertIsNotNone(charged,why)
        self.assertEqual((charged.lanes.combat.attack.spent,charged.lanes.warCombat.attack.spent,
                          charged.lanes.warCombat.attack.attempted,charged.lanes.warCombat.scout.spent),(5,5,1,0))
        persisted=usage.copy(charged);self.assertTrue(usage.holds(persisted,charge))
        self.view.attackAttempted=1;self.view.attackSpent=5;self.settings.maxAttackSpend=5
        self.assertIsNone(self.propose()[0]);self.assertEqual(usage.rollback(persisted,charge).lanes.warCombat.attack.spent,0)

    def test_native_warstatus_classification_agrees_with_supported_scoring_cap_gates(self):
        from pathlib import Path
        if not (Path(__file__).resolve().parents[1]/'docs/native-source/2026-11-01/WarStatus.lua.txt').is_file():
            self.skipTest('Private native contract capture is intentionally excluded from this package')
        native_source=(Path(__file__).resolve().parents[1]/'docs/native-source/2026-11-01/WarStatus.lua.txt').read_text(encoding='utf-8')
        for field,value,code in (('remaining',3,'WAR TARGET'),('remaining',0,'WAR CAPPED'),
                                  ('pairRemaining',0,'WAR LIMIT'),('attacksRemaining',0,'DAILY LIMIT'),
                                  ('canScore',False,'SCORING LOCKED'),('day',1,'CHECKING')):
            self.setUp();native=self.h.lua.execute(native_source);allowance=self.view.targets[1].warStatus;allowance[field]=value
            native_state=native.classify(allowance,self.view.serverNow,self.view.targets[1].remainingDaily)
            self.assertEqual(native_state.code,code)
            self.assertEqual(self.propose()[0] is not None,code=='WAR TARGET')
