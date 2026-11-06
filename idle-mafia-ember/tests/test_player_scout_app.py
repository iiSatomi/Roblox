"""Actual App Scout lifecycle with frozen planner; production dispatch stays blocked."""
import unittest
import test_player_fight_app as app_fixture
import test_player_scout_evidence as scout_fixture
from engine_harness import lua_table

class PlayerScoutAppTests(unittest.TestCase):
    def setUp(self):
        self.f=app_fixture.PlayerFightAppTests();self.f.setUp();self.h=self.f.h
        self.f.app.Destroy(self.f.app)
        self.scout=scout_fixture.PlayerScoutEvidenceTests();self.scout.provided_h=self.h;self.scout.setUp()
        self.f.result=self.scout;self.start()
    def start(self):
        f,h=self.f,self.h;self.scout.initial={};f.start()
        f.source.CanScout=h.lua.eval('function(self) return self.allowScout~=false end')
        f.source.Friendship=h.lua.eval('function() return false end')
        f.tab.scoutEvidence=self.scout.e
        f.tab.playerProfiles=h.load('src/tabs/combat/PlayerProfileQuery.luau').new(lua_table(h.lua,h.session),'a'*64,f.tab.hitListQuery,f.source,self.scout.e)
        self.profiles=f.tab.playerProfiles
        descriptor=next(row for row in f.tab.Descriptors(f.tab).values() if row.id=='combat')
        f.spec.evidence=descriptor.evidence;f.spec.recoverSaved=descriptor.recoverSaved;f.spec.recordOutcome=descriptor.recordOutcome
        f.executor.InvokeOwned=h.lua.eval("function(self,token,remote,method,target) self.calls=self.calls+1;assert(remote=='ScoutPlayer' and target==42);if self.interrupt then error('interrupted') end;return fixtureScoutReply end")
        h.lua.globals().fixtureScoutReply=self.scout.reply
        f.transport.plan=h.lua.execute("return {describe=function(p) return {remote='ScoutPlayer',method='InvokeServer',arity=1,args={p.intent.target}} end}")
        if h.session['session']==self.scout.before.session:
            request=f.tab.hitListQuery.Prepare(f.tab.hitListQuery,self.scout.before)[0]
            reply=lua_table(h.lua,{'ok':True,'list':[{'userId':42,'name':'Target','level':128,'stamina':2,'familyId':'other','shielded':False}]})
            staged=f.tab.hitListQuery.Accept(f.tab.hitListQuery,self.scout.before,request,reply)[0]
            self.assertTrue(f.tab.hitListQuery.Commit(f.tab.hitListQuery,staged))
            request=self.profiles.Prepare(self.profiles,self.scout.before)[0]
            reply=lua_table(h.lua,{'ok':True,'profile':{'userId':42,'name':'Target','level':128,'maxLevel':128,'familyId':'other','scoutCost':1,'statsHidden':True}})
            staged=self.profiles.Accept(self.profiles,self.scout.before,request,reply)[0]
            self.assertTrue(self.profiles.Commit(self.profiles,staged))
    def settle(self,stamina=19):
        self.h.at(.25);self.scout.after.capturedAt=.25;self.scout.after.native.pools.stamina=stamina
        self.f.step(self.scout.after)
    def usage(self):return self.f.runtime.checkpoint.Allowance(self.f.runtime.checkpoint,'combat')[0]
    def test_exact_scout_commits_hidden_target_cache_and_only_scout_allowance(self):
        self.f.begin();self.f.send();self.settle()
        self.assertEqual(self.f.runtime.Status(self.f.runtime).outcomes.combat,'confirmed')
        self.assertEqual((self.usage().scoutSpent,self.usage().attackSpent),(5,0))
        self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)),0)
        row=self.profiles.Read(self.profiles,self.scout.after)['42']
        self.assertTrue(row.statsHidden);self.assertEqual(row.scout.defense,100)
        self.assertIsNone(self.f.source.callback);self.assertEqual(self.f.ledger.Summary(self.f.ledger).fights,0)
    def test_disabled_queued_scout_refunds_only_the_unsent_scout_charge(self):
        self.f.begin();self.f.app.Set(self.f.app,'combat.enabled',False);self.f.step();self.f.executor.queued[1]()
        self.assertEqual(self.f.executor.calls,0);self.assertEqual(self.usage().scoutSpent,0)
    def test_native_guard_rejection_before_invoke_refunds_unsent_scout(self):
        self.f.begin();self.f.source.allowScout=False;self.f.executor.queued[1]()
        self.assertEqual(self.f.executor.calls,0);self.assertEqual(self.usage().scoutSpent,0)
    def test_native_rejection_requires_no_effect_and_retains_conservative_attempt_charge(self):
        self.h.lua.globals().fixtureScoutReply=lua_table(self.h.lua,{'ok':False,'code':'target_unavailable'})
        self.f.begin();self.f.send();self.settle(20)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).outcomes.combat,'rejected')
        self.assertEqual(self.usage().scoutSpent,5);self.assertIsNone(self.profiles.Read(self.profiles,self.scout.after)['42'].scout)
    def test_sent_disable_can_settle_without_another_scout(self):
        self.f.begin();self.f.send();self.f.app.Set(self.f.app,'combat.enabled',False);self.settle()
        self.assertEqual(self.f.runtime.Status(self.f.runtime).outcomes.combat,'confirmed');self.assertEqual(self.f.executor.calls,1)
    def test_interrupted_scout_expires_unconfirmed_without_refund_or_cache(self):
        self.f.begin();self.f.executor.interrupt=True;self.f.send()
        self.h.at(45);raw=self.scout.after;raw.capturedAt=45;self.f.step(raw)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).outcomes.combat,'skipped_unconfirmed')
        self.assertEqual(self.usage().scoutSpent,5);self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)),1)
    def test_saved_reply_after_unload_recovers_exact_effect_all_off_without_replay(self):
        self.f.begin();self.f.send();old=self.f.executor;self.f.app.Destroy(self.f.app)
        self.h.session['session']='fresh-session';self.start()
        raw=self.scout.after;raw.session='fresh-session';raw.revision=3;raw.capturedAt=.25;self.h.at(.25);self.f.step(raw)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).recoveries.combat,'confirmed')
        self.assertEqual(self.f.executor.calls,0);self.assertEqual(old.calls,1);self.assertEqual(self.usage().scoutSpent,5)
    def test_unload_before_send_recovers_known_unsent_and_never_invokes(self):
        self.f.begin();old=self.f.executor;self.f.app.Destroy(self.f.app);old.queued[1]()
        self.h.session['session']='fresh-session';self.start()
        raw=self.scout.after;raw.session='fresh-session';raw.revision=3;raw.capturedAt=.25;self.h.at(.25);self.f.step(raw)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).recoveries.combat,'known_unsent')
        self.assertEqual(old.calls,0);self.assertEqual(self.usage().scoutSpent,0)
    def tearDown(self):self.f.tearDown()
