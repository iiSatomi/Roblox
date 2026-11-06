"""War execution uses exact staged native receipts and independent source baselines."""
import copy
import unittest
import test_war_fight_planner as war_fixture
from engine_harness import lua_table
from test_fight_receipts import LIVE

class WarFightEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.f=war_fixture.WarTargetViewTests();self.f.setUp();self.h=self.f.h
        self.reader=self.f.reader;self.before=self.f.raw
        self.initial=copy.deepcopy(LIVE['second']['initial']);self.final=copy.deepcopy(LIVE['second']['final'])
        self.now=self.initial['targetDaily']['serverNow'];self.day=self.initial['targetDaily']['day']
        self.before.native.serverNow=self.now;self.before.native.attackDaily.day=self.day
        self.before.playerFightHistoryProof.serverNow=self.now
        proof=self.before.warRosterProof;proof.observedServerNow=self.now;proof.header.serverNow=self.now;proof.readHeader.serverNow=self.now
        proof.war.statusServerNow=self.now;proof.rows[1].warStatus.day=self.day;proof.rows[1].name='Target B';proof.rows[1].stamina=1
        proof.nativeFrame.header.serverNow=self.now
        profile=proof.profiles['42'];profile.name='Target B';profile.observedServerNow=self.now;profile.friendshipObservedAt=self.now
        profile.scout.at=self.now-1
        self.f.context.serverNow=self.now
        view,why=self.reader.readWarSelection(self.before,self.f.context);self.assertIsNotNone(view,why)
        import test_combat_target_selection as policy_fixture
        policy=policy_fixture.CombatTargetSelectionTests();policy.h=self.h
        self.settings=policy.settings(minimumPayout=0,minSamples=0,maxAttackSpend=10,minPowerRatio=1.25)
        self.planner=self.h.load('src/tabs/combat/WarFightPlanner.luau').new(self.h.load('src/tabs/combat/TargetSelection.luau'))
        self.p,why=self.planner.propose(view,self.settings,lua_table(self.h.lua,{'stamina':0,'uncertainStamina':0}))
        self.assertIsNotNone(self.p,why);self.p.requestId=1
        self.before.playerFightProof=lua_table(self.h.lua,{**self.h.session,'revision':1,'capturedAt':0,'sourceKey':'a'*64,'attempts':[]})
        self.e=self.h.load('src/tabs/combat/PlayerFightEvidence.luau').new(self.h.load('src/tabs/combat/FightReceipts.luau'),self.reader)
        self.baseline=self.e.capture(self.p,self.before)[0]
        self.after=self.h.snapshot(revision=2,native={'fullSync':True,'serverNow':self.now+1,
            'pools':{'stamina':19,'health':100},'attackDaily':{'day':self.day,'counts':{'42':1}}})
        self.after.playerFightProof=lua_table(self.h.lua,{**self.h.session,'revision':2,'capturedAt':0,'sourceKey':'a'*64,
            'attempts':[{'actionKey':self.p.actionKey,'feature':'warCombat','target':42,'status':'settled','initial':self.initial,'receipt':self.final}]})
    def data(self):return lua_table(self.h.lua,{'proposal':self.p,'before':self.before,'baseline':self.baseline,'reply':self.initial})
    def evaluate(self):return self.e.evaluate(self.p,self.before,self.after,lua_table(self.h.lua,self.initial),self.baseline)
    def test_war_baseline_uses_only_its_roster_and_separate_attack_usage(self):
        self.assertIsNotNone(self.baseline,'Exact War baseline is missing')
        self.assertEqual((self.baseline.familyId,self.baseline.warFamilyId,self.baseline.ownFamilyId,self.baseline.warDay),
                         ('enemy-family','enemy-family','own-family',self.day))
        self.assertEqual((self.baseline.staminaCost,self.baseline.staminaExposure),(1,5))
    def test_exact_live_receipt_shapes_confirm_war_execution_without_claiming_points(self):
        self.assertIsNotNone(self.baseline,'Exact War baseline is missing')
        self.assertEqual(self.evaluate(),'confirmed')
        row=self.e.outcome(self.data(),self.after)
        self.assertEqual((row.feature,row.target,row.receipt.cashConfirmed),('warCombat',42,36274716))
        self.assertIsNone(row.warPoints);self.assertIsNone(row.scored)
    def test_balance_and_war_points_changes_cannot_replace_owned_receipts(self):
        self.assertIsNotNone(self.baseline,'Exact War baseline is missing')
        self.after.playerFightProof=None;self.after.native.cash=999999999
        self.after.native.derived=lua_table(self.h.lua,{'war':{'pointsToday':99999}})
        self.assertEqual(self.evaluate(),'pending')
    def test_changed_enemy_roster_scoring_or_scout_proof_refuses_capture(self):
        for field,value in (('familyId','changed'),('warFamilyId','changed'),('ownFamilyId','changed'),('warDay',self.day+1)):
            self.setUp();self.p.intent[field]=value;self.assertIsNone(self.e.capture(self.p,self.before)[0])
        for field,value in (('canScore',False),('pairRemaining',0),('remaining',0),('attacksRemaining',0)):
            self.setUp();self.before.warRosterProof.rows[1].warStatus[field]=value
            self.assertIsNone(self.e.capture(self.p,self.before)[0])
        self.setUp();self.before.warRosterProof.profiles['42'].scout=None
        self.assertIsNone(self.e.capture(self.p,self.before)[0])
    def test_missing_war_source_cannot_fall_back_to_matching_ordinary_target(self):
        self.before.hitListProof=self.before.warRosterProof;self.before.warRosterProof=None
        self.assertIsNone(self.e.capture(self.p,self.before)[0])
    def test_independent_attack_allowance_change_or_other_lane_cannot_authorize_war(self):
        self.before.playerFightUsageProof.usage.lanes.warCombat.attack.spent=1
        self.assertIsNone(self.e.capture(self.p,self.before)[0])
    def test_changed_staged_target_feature_cost_or_action_never_confirms(self):
        for key,value in (('target',43),('feature','combat'),('actionKey','combat:42')):
            self.setUp();self.assertIsNotNone(self.baseline,'Exact War baseline is missing')
            self.after.playerFightProof.attempts[1][key]=value;self.assertEqual(self.evaluate(),'pending')
    def test_war_saved_exact_outcome_recovers_from_ledger_without_current_roster_or_replay(self):
        self.assertIsNotNone(self.baseline,'Exact War baseline is missing')
        row=self.e.outcome(self.data(),self.after);self.assertIsNotNone(row)
        self.after.session='new-session';self.after.playerFightProof=None
        self.after.playerFightHistoryProof=lua_table(self.h.lua,{**self.h.session,'session':'new-session','revision':2,'capturedAt':0,'recent':[row]})
        self.assertEqual(self.e.recoverSaved(self.data(),self.after),'confirmed')
        self.after.playerFightHistoryProof.recent[1].target=43
        self.assertIsNone(self.e.recoverSaved(self.data(),self.after))
    def test_saved_enemy_identity_tamper_cannot_recover_a_matching_receipt(self):
        self.assertIsNotNone(self.baseline,'Exact War baseline is missing')
        data=self.data();data.baseline.warFamilyId='other';self.assertIsNone(self.e.recoverSaved(data,self.after))
        self.setUp();self.assertIsNotNone(self.baseline,'Exact War baseline is missing')
        self.p.intent.warFamilyId='other';self.assertEqual(self.evaluate(),'pending')
    def test_exact_negative_is_rejected_but_manual_challenge_and_unknown_stay_pending(self):
        self.assertIsNotNone(self.baseline,'Exact War baseline is missing')
        self.after.native.pools.stamina=20;self.after.native.attackDaily.counts['42']=None
        self.assertEqual(self.e.evaluate(self.p,self.before,self.after,lua_table(self.h.lua,{'ok':False,'code':'war_capped'}),self.baseline),'rejected')
        for reply in ({'ok':False,'code':'presence'},{'ok':False,'code':'busy'},{'ok':False,'code':'rate_limited'},
                      {'ok':True,'pending':True},{'ok':False,'fightId':'unknown'}):
            self.assertEqual(self.e.evaluate(self.p,self.before,self.after,lua_table(self.h.lua,reply),self.baseline),'pending')

    def test_expected_own_power_is_bound_before_a_queued_war_attempt(self):
        self.assertEqual(self.p.intent.attack,200)
        self.before.warRosterProof.nativeFrame.attack=100
        self.assertIsNone(self.e.capture(self.p,self.before)[0])
