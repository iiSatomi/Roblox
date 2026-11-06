"""War Scout capture, exact result, cache admission and restart recovery."""
import unittest
import test_war_fight_evidence as attack_fixture
from engine_harness import lua_table

class WarScoutEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.f=attack_fixture.WarFightEvidenceTests();self.f.setUp();self.h=self.f.h
        self.before=self.f.before;self.after=self.f.after;self.reader=self.f.reader
        self.before.warRosterProof.profiles['42'].scout=None
        view,why=self.reader.readWarSelection(self.before,self.f.f.context);self.assertIsNotNone(view,why)
        self.f.settings.allowScout=True;self.f.settings.maxScoutSpend=5
        self.p,why=self.f.planner.propose(view,self.f.settings,lua_table(self.h.lua,{'stamina':0,'uncertainStamina':0}))
        self.assertIsNotNone(self.p,why);self.p.requestId=2
        self.module=self.h.load('src/tabs/combat/PlayerScoutEvidence.luau')
        self.e=self.module.new(self.reader) if self.module.new else self.module
        self.baseline=self.e.capture(self.p,self.before)[0]
        self.reply=lua_table(self.h.lua,{'ok':True,'atk':300,'def':100,'crew':4})
        self.after.playerFightProof=None;self.after.native.attackDaily.counts['42']=None
    def data(self):return lua_table(self.h.lua,{'proposal':self.p,'before':self.before,'baseline':self.baseline,'reply':self.reply})
    def evaluate(self):return self.e.evaluate(self.p,self.before,self.after,self.reply,self.baseline)
    def test_exact_war_scout_baseline_binds_enemy_identity_and_own_allowance(self):
        self.assertIsNotNone(self.baseline,'Owned War Scout baseline is missing')
        self.assertEqual((self.p.intent.kind,self.baseline.warFamilyId,self.baseline.ownFamilyId,self.baseline.familyId),
                         ('playerScout','enemy-family','own-family','enemy-family'))
        self.assertEqual((self.baseline.staminaCost,self.baseline.staminaExposure),(1,5))
    def test_exact_success_and_native_cost_yield_target_bound_scout_without_claiming_attack(self):
        self.assertIsNotNone(self.baseline,'Owned War Scout baseline is missing')
        self.assertEqual(self.evaluate(),'confirmed');row=self.e.outcome(self.data(),self.after)
        self.assertEqual((row.target,row.familyId,row.level,row.defense,row.requestId),(42,'enemy-family',128,100,2))
        self.assertIsNone(row.won);self.assertIsNone(row.warPoints)
    def test_native_scoring_cap_or_changed_enemy_prevents_paid_scout_capture(self):
        self.assertIsNotNone(self.baseline,'Owned War Scout baseline is missing')
        self.before.warRosterProof.rows[1].warStatus.pairRemaining=0
        self.assertIsNone(self.e.capture(self.p,self.before)[0])
        self.setUp();self.p.intent.warFamilyId='other';self.assertIsNone(self.e.capture(self.p,self.before)[0])
    def test_missing_war_source_cannot_use_matching_ordinary_source(self):
        self.assertIsNotNone(self.baseline,'Owned War Scout baseline is missing')
        self.before.hitListProof=self.before.warRosterProof;self.before.warRosterProof=None
        self.assertIsNone(self.e.capture(self.p,self.before)[0])
    def test_separate_optin_allowance_and_unknown_profile_remain_required(self):
        self.assertIsNotNone(self.baseline,'Owned War Scout baseline is missing')
        for change in ('consent','allowance','shield','friend'):
            self.setUp()
            if change=='consent':self.p.intent.allowScout=False
            elif change=='allowance':self.before.playerFightUsageProof.usage.lanes.warCombat.scout.spent=1
            elif change=='shield':self.before.warRosterProof.profiles['42'].shieldStatus='unknown'
            else:self.before.warRosterProof.profiles['42'].friend=None
            self.assertIsNone(self.e.capture(self.p,self.before)[0])
    def test_reply_alone_or_pool_delta_alone_never_confirms_war_scout(self):
        self.assertIsNotNone(self.baseline,'Owned War Scout baseline is missing')
        self.after.native.pools.stamina=20;self.assertEqual(self.evaluate(),'pending')
        self.after.native.pools.stamina=19;self.reply=lua_table(self.h.lua,{'ok':True})
        self.assertEqual(self.evaluate(),'pending')
    def test_saved_exact_scout_recovers_without_current_war_or_replay(self):
        self.assertIsNotNone(self.baseline,'Owned War Scout baseline is missing')
        self.after.session='new-session';self.assertEqual(self.e.recoverSaved(self.data(),self.after),'confirmed')
        data=self.data();data.baseline.warFamilyId='other';self.assertIsNone(self.e.recoverSaved(data,self.after))
    def test_changed_war_intent_cannot_confirm_using_captured_header_only_baseline(self):
        self.assertIsNotNone(self.baseline,'Owned War Scout baseline is missing')
        self.p.intent.warFamilyId='other';self.assertEqual(self.evaluate(),'pending')
    def test_manual_presence_unknown_and_wrong_target_results_stay_pending(self):
        self.assertIsNotNone(self.baseline,'Owned War Scout baseline is missing')
        for reply in ({'ok':False,'code':'presence'},{'ok':False,'code':'rate_limited'},{'ok':True,'pending':True},
                      {'ok':True,'atk':300,'def':100,'crew':4,'target':43}):
            self.reply=lua_table(self.h.lua,reply);self.assertEqual(self.evaluate(),'pending')
    def test_exact_confirmed_result_populates_only_matching_war_profile_cache(self):
        self.assertIsNotNone(self.baseline,'Owned War Scout baseline is missing')
        # Exercise the actual profile owner with the same original owned roster.
        q=self.f.f.f.q
        q.scoutEvidence=self.e;q.scoutOutcome=self.e.outcome
        self.assertTrue(q.RecordScout(q,self.data(),self.after)[0])
        # Current after has no active roster, so an outcome cannot create target authority.
        self.assertIsNone(q.scoutCache['42'])

    def test_exact_scout_receipt_enters_real_war_cache_and_selects_followup_attack(self):
        self.assertIsNotNone(self.baseline,'Owned War Scout baseline is missing')
        profile_fixture=self.f.f.f;roster=profile_fixture.f;q=profile_fixture.q
        after=self.after;after.native.family=lua_table(self.h.lua,{'id':'own-family'})
        after.native.derived=lua_table(self.h.lua,{'war':{'state':'active','enemyId':'enemy-family'}})
        after.native.stats=lua_table(self.h.lua,{'maxHealth':100});after.native.userId=1
        roster.reply.warStatus.serverNow=after.native.serverNow;roster.reply.warStatus.day=self.f.day
        native_target=roster.reply.warStatus.targets[1]
        native_target.warStatus.day=self.f.day;native_target.name='Target B';native_target.stamina=1
        call,why=roster.q.Prepare(roster.q,after);self.assertIsNotNone(call,why)
        staged,why=roster.q.Accept(roster.q,after,call,roster.reply);self.assertIsNotNone(staged,why)
        self.assertTrue(roster.q.Commit(roster.q,staged))
        profile_fixture.reply.profile.name='Target B'
        request,why=q.Prepare(q,after);self.assertIsNotNone(request,why)
        staged,why=q.Accept(q,after,request,profile_fixture.reply);self.assertIsNotNone(staged,why)
        self.assertTrue(q.Commit(q,staged));q.scoutEvidence=self.e;q.scoutOutcome=self.e.outcome
        self.assertTrue(q.RecordScout(q,self.data(),after)[0])
        cache=q.Read(q,after)['42'].scout
        self.assertEqual((cache.kind,cache.defense,cache.at),('scout',100,self.f.now))
        after.warRosterProof=roster.q.Read(roster.q,after);after.warRosterProof.profiles=q.Read(q,after)
        clone=self.h.lua.eval('function(value) local function c(v) if type(v)~="table" then return v end local o={} for k,x in pairs(v) do o[k]=c(x) end return o end return c(value) end')
        frame=clone(self.before.warRosterProof.nativeFrame)
        frame.header.revision=2;frame.header.serverNow=after.native.serverNow;frame.stamina=19
        after.warRosterProof.nativeFrame=frame
        usage=self.h.load('src/tabs/combat/PlayerFightUsage.luau')
        after.playerFightUsageProof=lua_table(self.h.lua,{'account':after.account,'capturedAt':after.capturedAt,
            'usage':usage.charge(self.before.playerFightUsageProof.usage,self.p)[0]})
        after.playerFightHistoryProof=lua_table(self.h.lua,{**self.h.session,'revision':2,'capturedAt':0,
            'serverNow':after.native.serverNow,'recent':[]})
        context=lua_table(self.h.lua,{**self.h.session,'revision':2,'capturedAt':0,'serverNow':after.native.serverNow})
        view,why=self.reader.readWarSelection(after,context);self.assertIsNotNone(view,why)
        attack,why=self.f.planner.propose(view,self.f.settings,lua_table(self.h.lua,{'stamina':0,'uncertainStamina':0}))
        self.assertIsNotNone(attack,why)
        self.assertEqual((attack.feature,attack.intent.kind,attack.intent.statsAt,view.scoutSpent,view.attackSpent),
                         ('warCombat','playerAttack',self.f.now,5,0))
