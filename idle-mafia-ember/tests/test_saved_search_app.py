"""Owned saved lookup travels through the actual App/shared lane/profile path."""
import unittest
import test_player_combat_planner_app as fixture
from engine_harness import lua_table

class SavedSearchAppTests(unittest.TestCase):
    def setUp(self):
        self.b=fixture.PlayerCombatPlannerAppTests();self.b.setUp();self.f=self.b.f;self.h=self.b.h
        self.f.begin();self.f.send();self.f.result.after.native.stats=lua_table(self.h.lua,{'maxHealth':100});self.f.settle()
        self.b.app.Destroy(self.b.app);self.h.session['session']='saved-search-session'
        raw=self.f.result.before;raw.session=self.h.session['session'];raw.revision=1;raw.capturedAt=1
        raw.native.serverNow+=86400;raw.native.attackDaily.day+=1;raw.native.attackDaily.counts=self.h.lua.table();self.h.at(1)
        self.f.start();self.app=self.f.app;self.raw=raw
        self.empty=lua_table(self.h.lua,{'ok':True,'list':[],'warStatus':{'day':raw.native.attackDaily.day,'serverNow':raw.native.serverNow,'targets':[]}})
        q=self.f.tab.hitListQuery;request=q.Prepare(q,raw)[0]
        self.assertTrue(q.Commit(q,q.Accept(q,raw,request,self.empty)[0]))
        self.reply=lua_table(self.h.lua,{'ok':True,'search':'Target B','list':[{'userId':42,'name':'Target B','level':128,'stamina':1,'shielded':False,'familyId':'other-family'}]})
        self.h.lua.globals().savedSearchReply=self.reply;self.h.lua.globals().savedSearchRaw=raw;self.h.lua.globals().savedEmptyList=self.empty
        self.f.executor.log=self.h.lua.table()
        self.f.executor.InvokeOwned=self.h.lua.eval("""function(self,token,remote,method,arg)
            self.calls=self.calls+1;self.log[#self.log+1]={remote=remote,arg=arg}
            if self.yieldReply then coroutine.yield('lookup-return') end
            if remote=='SearchTarget' then assert(arg=='Target B');return savedSearchReply end
            if remote=='GetHitList' then savedEmptyList.warStatus.serverNow=savedSearchRaw.native.serverNow;return savedEmptyList end
            if remote=='Attack' and self.allowAttack then assert(arg==42);return {ok=false,code='requirements'} end
            if remote=='PlayerProfile' then assert(arg==42);return {ok=true,profile={userId=42,name='Target B',level=128,maxLevel=128,
                familyId='other-family',scoutCost=1,statsHidden=false,atk=100,def=1,crew=1}} end
            error('Lookup cannot authorize gameplay')
        end""")
        sources=self.f.tab.ReadSources(self.f.tab,self.f.f.reader)
        budget=self.h.load('src/engine/ReadBudget.luau').new(self.h.clock,lua_table(self.h.lua,[{'id':s.id,'interval':s.interval} for s in sources.values()]),5,60)
        reads=self.h.load('src/transport/ReadCoordinator.luau').new(lua_table(self.h.lua,{'clock':self.h.clock,'lane':self.f.lane,
            'budget':budget,'executor':self.f.executor,'sources':sources,'currentSnapshot':self.h.lua.eval('function() return savedSearchRaw end')}))
        self.f.runtime.readSources=sources;self.f.runtime.readCoordinator=reads
        for key,value in [('minimumPayout',0),('minSamples',1)]:self.app.Set(self.app,'combat.custom.'+key,value)
    def enable(self):
        self.assertTrue(self.app.Set(self.app,'combat.custom.targetSource','Saved and new + lookup')[0])
        self.app.Set(self.app,'combat.enabled',True);self.app.Resume(self.app);self.f.step()
        self.assertEqual(len(self.f.executor.queued),1,str(dict(self.f.runtime.Status(self.f.runtime).reasons.items())))
    def tick(self,at):
        delta=at-self.raw.capturedAt;self.raw.capturedAt=at;self.raw.revision+=1;self.raw.native.serverNow+=delta;self.h.at(at);self.f.step()
    def test_saved_lookup_uses_current_day_when_native_bucket_is_from_yesterday(self):
        before=self.f.runtime.checkpoint.Allowance(self.f.runtime.checkpoint,'combat')[0]
        self.raw.native.attackDaily.day-=1;self.raw.native.attackDaily.counts['42']=5
        self.enable();self.f.executor.queued[1]()
        self.assertEqual(len(self.f.executor.log),1)
        self.assertEqual(self.f.executor.log[1].remote,'SearchTarget')
        self.assertEqual(self.raw.native.attackDaily.counts['42'],5)
        allowance=self.f.runtime.checkpoint.Allowance(self.f.runtime.checkpoint,'combat')[0]
        self.assertEqual(allowance.attackSpent,before.attackSpent);self.assertEqual(allowance.scoutSpent,before.scoutSpent)

    def test_default_off_and_unopted_combat_do_not_issue_saved_search(self):
        self.assertEqual(self.app.model['values']['combat.custom.targetSource'],'Saved and new')
        self.f.step();self.app.Set(self.app,'combat.enabled',True);self.app.Resume(self.app);self.f.step()
        self.assertEqual(len(self.f.executor.queued),0);self.assertEqual(len(self.f.executor.log),0)
    def test_exact_lookup_and_profile_share_lane_and_never_spend_attack_or_scout(self):
        self.enable();self.f.executor.queued[1]();self.assertEqual(self.f.executor.log[1].remote,'SearchTarget')
        self.tick(2);self.assertEqual(len(self.f.executor.queued),2);self.f.executor.queued[2]()
        self.assertEqual(self.f.executor.log[2].remote,'PlayerProfile');self.tick(3)
        rows=self.f.runtime.allowanceSnapshot.hitListProof.rows;self.assertEqual(rows[1].userId,42)
        self.assertEqual(len(self.f.executor.log),2);self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)),0)
        self.assertEqual(self.f.runtime.checkpoint.Allowance(self.f.runtime.checkpoint,'combat')[0].attackSpent,5)
        self.assertFalse(self.app.model['values']['combat.custom.allowScout']);self.assertEqual(self.app.model['values']['combat.custom.maxAttackSpend'],0)
    def test_same_name_wrong_identity_does_not_schedule_profile_or_activate_target(self):
        self.reply.list[1].userId=43;self.enable();self.f.executor.queued[1]();self.tick(2)
        self.assertEqual(len(self.f.runtime.allowanceSnapshot.hitListProof.rows),0)
        self.assertEqual(len(self.f.executor.queued),1);self.assertEqual(len(self.f.executor.log),1)
    def test_later_normal_roster_update_overrides_cached_searched_family(self):
        self.raw.native.family=lua_table(self.h.lua,{'id':'own-family'})
        self.raw.native.derived=lua_table(self.h.lua,{'war':{'state':'active','enemyId':'enemy-family'}})
        self.empty.warStatus.summary=lua_table(self.h.lua,{'enemyId':'enemy-family'})
        self.empty.warStatus.targets=lua_table(self.h.lua,[{'userId':99,'name':'Enemy','level':128,'familyId':'enemy-family'}])
        q=self.f.tab.hitListQuery;call=q.Prepare(q,self.raw)[0]
        self.assertTrue(q.Commit(q,q.Accept(q,self.raw,call,self.empty)[0]))
        self.assertIs(q.Read(q,self.raw).war.enemyTargets['99'],True)
        self.app.Set(self.app,'combat.custom.maxAttackSpend',10)
        self.enable();self.f.executor.queued[1]();self.tick(2)
        if len(self.f.executor.queued)>1:self.f.executor.queued[2]()
        self.empty.warStatus.targets[1].userId=42
        call=q.Prepare(q,self.raw)[0];self.assertTrue(q.Commit(q,q.Accept(q,self.raw,call,self.empty)[0]))
        self.tick(3)
        self.assertLessEqual(len(self.f.executor.queued),2,'Contradictory searched enemy must never queue ordinary Attack')
        self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)),0)
    def test_lookup_can_reach_ordinary_adapter_only_after_explicit_attempt_budget(self):
        self.enable();self.f.executor.queued[1]();self.tick(2);self.f.executor.queued[2]();self.tick(3)
        self.assertEqual(len(self.f.executor.queued),2)
        self.app.Set(self.app,'combat.custom.maxAttackSpend',10);self.tick(4)
        self.assertEqual(len(self.f.executor.queued),3)
        self.f.executor.allowAttack=True;self.f.executor.queued[3]();self.tick(5)
        self.assertEqual((self.f.executor.log[3].remote,self.f.executor.log[3].arg),('Attack',42))
        self.assertEqual(self.f.runtime.Status(self.f.runtime).outcomes.combat,'rejected')
        self.assertEqual(self.f.runtime.checkpoint.Allowance(self.f.runtime.checkpoint,'combat')[0].attackSpent,10)
    def test_fresh_profile_friend_or_shield_blocks_lookup_from_becoming_attack(self):
        for change in ('friend','shield'):
            self.tearDown();self.setUp();self.enable();self.f.executor.queued[1]();self.tick(2);self.f.executor.queued[2]()
            profile=self.f.tab.playerProfiles.cache['42']
            if change=='friend':profile.friend=True
            else:profile.shieldUntil=self.raw.native.serverNow+20
            self.app.Set(self.app,'combat.custom.maxAttackSpend',10);self.tick(3)
            self.assertEqual(len(self.f.executor.queued),2);self.assertEqual(len(self.f.executor.log),2)
    def test_known_enemy_roster_member_is_skipped_before_a_saved_lookup(self):
        self.raw.native.family=lua_table(self.h.lua,{'id':'own-family'})
        self.raw.native.derived=lua_table(self.h.lua,{'war':{'state':'active','enemyId':'enemy-family'}})
        self.empty.warStatus.summary=lua_table(self.h.lua,{'enemyId':'enemy-family'})
        self.empty.warStatus.targets=lua_table(self.h.lua,[{'userId':42,'name':'Target B','level':128,'familyId':'enemy-family'}])
        q=self.f.tab.hitListQuery;call=q.Prepare(q,self.raw)[0];q.Commit(q,q.Accept(q,self.raw,call,self.empty)[0])
        self.app.Set(self.app,'combat.custom.targetSource','Saved and new + lookup');self.app.Set(self.app,'combat.enabled',True)
        self.app.Resume(self.app);self.f.step()
        self.assertEqual(len(self.f.executor.queued),0);self.assertEqual(len(self.f.executor.log),0)
    def test_unknown_active_enemy_identity_does_not_spend_lookup_reads(self):
        self.raw.native.family=lua_table(self.h.lua,{'id':'own-family'})
        self.raw.native.derived=lua_table(self.h.lua,{'war':{'state':'active','enemyId':'enemy-family'}})
        self.empty.warStatus.summary=self.h.lua.table()
        q=self.f.tab.hitListQuery;call=q.Prepare(q,self.raw)[0];q.Commit(q,q.Accept(q,self.raw,call,self.empty)[0])
        self.app.Set(self.app,'combat.custom.targetSource','Saved and new + lookup');self.app.Set(self.app,'combat.enabled',True)
        self.app.Resume(self.app);self.f.step()
        self.assertEqual(len(self.f.executor.queued),0);self.assertEqual(len(self.f.executor.log),0)
    def test_disable_or_unload_before_queued_lookup_sends_nothing(self):
        for change in ('feature','permission','unload'):
            self.tearDown();self.setUp();self.enable()
            if change=='unload':self.app.Destroy(self.app)
            else:self.app.Set(self.app,'combat.enabled' if change=='feature' else 'combat.custom.targetSource',False if change=='feature' else 'Saved and new');self.f.step()
            self.f.executor.queued[1]();self.assertEqual(len(self.f.executor.log),0)
    def test_negative_challenge_pending_and_rate_reply_do_not_populate_targets_or_spin(self):
        for reply in ({'ok':False},{'ok':False,'code':'presence'},{'ok':True,'pending':True},{'ok':False,'code':'rate_limited'}):
            self.tearDown();self.setUp();self.h.lua.globals().savedSearchReply=lua_table(self.h.lua,reply)
            self.enable();self.f.executor.queued[1]();self.tick(2);self.tick(3)
            self.assertEqual(len(self.f.executor.log),1);self.assertEqual(len(self.f.executor.queued),1)
            self.assertEqual(len(self.f.runtime.allowanceSnapshot.hitListProof.rows),0)
    def test_unload_while_lookup_reply_yields_cannot_commit(self):
        self.enable();self.f.executor.yieldReply=True;self.h.lua.globals().savedLookupCallback=self.f.executor.queued[1]
        value=self.h.lua.execute('savedLookupThread=coroutine.create(savedLookupCallback);local ok,value=coroutine.resume(savedLookupThread);assert(ok);return value')
        self.assertEqual(value,'lookup-return');self.app.Destroy(self.app);self.h.lua.execute('assert(coroutine.resume(savedLookupThread))')
        self.assertIsNone(self.f.tab.hitListQuery.Read(self.f.tab.hitListQuery,self.raw))
    def tearDown(self):
        if hasattr(self,'f'):self.f.tearDown()
