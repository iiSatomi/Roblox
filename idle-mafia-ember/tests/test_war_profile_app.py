"""War roster -> native profile -> friendship through the actual App read scheduler."""
import unittest
import test_owned_war_roster_app as app_fixture
from engine_harness import lua_table

class WarProfileAppTests(unittest.TestCase):
    def setUp(self):
        self.base=app_fixture.OwnedWarRosterAppTests();self.base.setUp();self.f=self.base.f;self.h=self.base.h
        self.source=self.base.current
        self.source.Friendship=self.h.lua.eval('function(self) self.friendCalls=(self.friendCalls or 0)+1;return false end')
        self.profiles=self.h.load('src/tabs/combat/PlayerProfileQuery.luau').new(lua_table(self.h.lua,self.h.session),'a'*64,self.base.q,self.source)
        self.f.tab.warProfiles=self.profiles
        raw=self.f.result.before;raw.native.family=lua_table(self.h.lua,{'id':'own-family'})
        raw.native.derived=lua_table(self.h.lua,{'war':{'state':'active','enemyId':'enemy-family'}})
        self.h.lua.globals().warReply=lua_table(self.h.lua,{'ok':True,'warStatus':{'day':self.f.result.day,'serverNow':self.f.result.now,
            'summary':{'enemyId':'enemy-family','canScore':True,'ownRemaining':8,'ownCap':20},
            'targets':[{'userId':42,'name':'Enemy','level':128,'familyId':'enemy-family',
                'warStatus':{'day':self.f.result.day,'remaining':3,'cap':5,'attacksRemaining':2,'attacksCap':8,'pairRemaining':1,'canScore':True}}]}})
        self.h.lua.globals().warProfileReply=lua_table(self.h.lua,{'ok':True,'profile':{'userId':42,'name':'Enemy','level':128,
            'maxLevel':150,'familyId':'enemy-family','scoutCost':1,'statsHidden':True}})
        self.f.executor.InvokeOwned=self.h.lua.eval("""function(self,token,remote,method,arg)
            self.calls=self.calls+1
            if remote=='GetHitList' then assert(arg=='warStatus');return warReply end
            assert(remote=='PlayerProfile' and arg==42);return warProfileReply end""")
        self.f.runtime.readCoordinator.Close(self.f.runtime.readCoordinator)
        sources=self.f.tab.ReadSources(self.f.tab,self.f.f.reader)
        budget=self.h.load('src/engine/ReadBudget.luau').new(self.h.clock,lua_table(self.h.lua,[
            {'id':'combatWarRoster','interval':1},{'id':'combatWarProfile','interval':1}]),5,60)
        self.f.runtime.readSources=sources
        self.f.runtime.readCoordinator=self.h.load('src/transport/ReadCoordinator.luau').new(lua_table(self.h.lua,{
            'clock':self.h.clock,'lane':self.f.lane,'budget':budget,'executor':self.f.executor,'sources':sources,
            'currentSnapshot':self.h.lua.eval('function() return warRaw end')}))
    def begin_profile(self):
        self.base.start();self.f.executor.queued[1]();self.h.at(.25);self.f.step()
        self.assertEqual(len(self.f.executor.queued),2)
    def test_profile_and_friendship_reach_only_owned_war_proof_without_any_gameplay(self):
        self.begin_profile();self.f.executor.queued[2]();self.h.at(.5);self.f.step()
        raw=self.f.runtime.allowanceSnapshot;row=raw.warRosterProof.profiles['42']
        self.assertFalse(row.friend);self.assertTrue(row.statsHidden);self.assertIsNone(row.defense)
        self.assertIsNone(raw.hitListProof);self.assertEqual(self.f.executor.calls,2);self.assertEqual(self.source.friendCalls,1)
        self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)),0);self.assertIsNone(self.f.source.callback)
    def test_all_off_and_native_capped_rows_make_no_profile_or_friendship_call(self):
        self.f.step();self.assertEqual(len(self.f.executor.queued),0)
        self.h.lua.globals().warReply.warStatus.targets[1].warStatus.pairRemaining=0
        self.base.start();self.f.executor.queued[1]();self.h.at(.25);self.f.step()
        self.assertEqual(len(self.f.executor.queued),1);self.assertIsNone(self.source.friendCalls)
    def test_disable_before_queued_profile_prevents_remote_and_friendship(self):
        self.begin_profile();self.f.app.Set(self.f.app,'warCombat.enabled',False);self.f.step();self.f.executor.queued[2]()
        self.assertEqual(self.f.executor.calls,1);self.assertIsNone(self.source.friendCalls)
    def test_unload_during_friendship_yield_cannot_publish_profile(self):
        self.source.Friendship=self.h.lua.eval('function() coroutine.yield("friendship");return false end')
        self.f.tab.warProfiles=self.profiles=self.h.load('src/tabs/combat/PlayerProfileQuery.luau').new(lua_table(self.h.lua,self.h.session),'a'*64,self.base.q,self.source)
        self.begin_profile();self.h.lua.globals().warProfileJob=self.f.executor.queued[2]
        self.assertEqual(self.h.lua.execute('warProfileThread=coroutine.create(warProfileJob);local ok,value=coroutine.resume(warProfileThread);assert(ok);return value'),'friendship')
        self.f.app.Destroy(self.f.app);self.h.lua.execute('assert(coroutine.resume(warProfileThread))')
        self.assertIsNone(self.profiles.Read(self.profiles,self.f.result.before))
    def test_roster_change_during_remote_does_not_call_friendship_or_publish(self):
        self.begin_profile();self.h.lua.globals().warRaw.native.derived.war.enemyId='other-enemy'
        self.f.executor.queued[2]();self.assertIsNone(self.source.friendCalls)
        self.assertIsNone(self.profiles.Read(self.profiles,self.f.result.before))
    def test_native_or_friendship_failure_stays_unknown_and_backs_off(self):
        self.h.lua.globals().warProfileReply.ok=False;self.begin_profile();self.f.executor.queued[2]()
        self.h.at(.5);self.f.step();self.assertIsNone(self.source.friendCalls)
        self.assertIsNone(self.f.runtime.allowanceSnapshot.warRosterProof.profiles['42'])
        self.h.at(1);self.f.step();self.assertEqual(len(self.f.executor.queued),2)
    def test_repeated_planner_ticks_reuse_profile_observation(self):
        self.begin_profile();self.f.executor.queued[2]()
        for at in (.5,.75,1):self.h.at(at);self.f.step()
        self.assertEqual(len(self.f.executor.queued),2);self.assertEqual(self.source.friendCalls,1)
    def test_friendship_lookup_failure_remains_unknown_in_owned_war_profile(self):
        self.source.Friendship=self.h.lua.eval('function() error("unavailable") end')
        self.f.tab.warProfiles=self.profiles=self.h.load('src/tabs/combat/PlayerProfileQuery.luau').new(lua_table(self.h.lua,self.h.session),'a'*64,self.base.q,self.source)
        self.begin_profile();self.f.executor.queued[2]();self.h.at(.5);self.f.step()
        row=self.f.runtime.allowanceSnapshot.warRosterProof.profiles['42']
        self.assertEqual(row.friendshipStatus,'unknown');self.assertIsNone(row.friend)
    def test_refresh_preserves_profile_for_same_identity_but_not_changed_membership(self):
        self.begin_profile();self.f.executor.queued[2]();self.h.at(1)
        raw=self.f.result.before;raw.revision=2;raw.capturedAt=1;raw.native.serverNow+=1
        self.h.lua.globals().warReply.warStatus.serverNow=raw.native.serverNow
        call=self.base.q.Prepare(self.base.q,raw)[0]
        self.assertTrue(self.base.q.Commit(self.base.q,self.base.q.Accept(self.base.q,raw,call,self.h.lua.globals().warReply)[0]))
        self.f.step();self.assertEqual(len(self.f.executor.queued),2);self.assertEqual(self.source.friendCalls,1)
        raw.native.derived.war.enemyId='changed-enemy';self.f.step()
        self.assertIsNone(self.f.runtime.allowanceSnapshot.warRosterProof)
    def tearDown(self):self.base.tearDown()
