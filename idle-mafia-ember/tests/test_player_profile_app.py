"""Actual App/coordinator target -> profile -> friendship reads. No player mutation."""
import unittest
import test_owned_hit_list_app as fixture
from engine_harness import lua_table

class PlayerProfileAppTests(unittest.TestCase):
    def setUp(self):
        self.base=fixture.OwnedHitListAppTests();self.base.setUp();self.f=self.base.f;self.h=self.f.h
        self.source=self.base.currentSource
        self.source.Friendship=self.h.lua.eval('function(self) self.friendCalls=(self.friendCalls or 0)+1;return false end')
        self.profiles=self.h.load('src/tabs/combat/PlayerProfileQuery.luau').new(lua_table(self.h.lua,self.h.session),'a'*64,self.base.q,self.source)
        self.f.tab.playerProfiles=self.profiles
        self.h.lua.globals().profileReply=lua_table(self.h.lua,{'ok':True,'profile':{'userId':42,'name':'Target B',
            'level':128,'maxLevel':211,'familyId':'foreign-family','scoutCost':1,'statsHidden':True}})
        self.f.executor.InvokeOwned=self.h.lua.eval("""function(self,token,remote,method,arg)
            self.calls=self.calls+1
            if remote=='GetHitList' then assert(arg==false);return hitReply end
            assert(remote=='PlayerProfile' and arg==42);return profileReply
        end""")
        self.f.runtime.readCoordinator.Close(self.f.runtime.readCoordinator)
        sources=self.f.tab.ReadSources(self.f.tab,self.f.f.reader)
        budget=self.h.load('src/engine/ReadBudget.luau').new(self.h.clock,lua_table(self.h.lua,[
            {'id':'combatHitList','interval':1},{'id':'combatProfile','interval':1}]),5,60)
        self.f.runtime.readSources=sources
        self.f.runtime.readCoordinator=self.h.load('src/transport/ReadCoordinator.luau').new(lua_table(self.h.lua,{'clock':self.h.clock,
            'lane':self.f.lane,'budget':budget,'executor':self.f.executor,'sources':sources,
            'currentSnapshot':self.h.lua.eval('function() return hitRaw end')}))
    def begin_profile(self):
        self.base.start();self.f.executor.queued[1]();self.h.at(.25);self.f.step()
        self.assertEqual(len(self.f.executor.queued),2)
    def test_current_profile_and_reported_friendship_reach_owned_app_proof_without_scout(self):
        self.begin_profile();self.f.executor.queued[2]();self.h.at(.5);self.f.step()
        row=self.f.runtime.allowanceSnapshot.hitListProof.profiles['42']
        self.assertEqual((row.scoutCost,row.statsHidden,row.friend),(1,True,False));self.assertIsNone(row.defense)
        self.assertEqual(self.f.executor.calls,2);self.assertEqual(self.source.friendCalls,1)
        self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)),0)
        self.assertIsNone(self.f.source.callback)
    def test_native_public_reply_reaches_actual_app_without_inventing_scout_or_shield(self):
        profile=self.h.lua.globals().profileReply.profile
        profile.statsHidden=None;profile.scoutCost=None
        profile.atk=300;profile['def']=100;profile.crew=3
        self.begin_profile();self.f.executor.queued[2]();self.h.at(.5);self.f.step()
        row=self.f.runtime.allowanceSnapshot.hitListProof.profiles['42']
        self.assertIsNotNone(row);self.assertFalse(row.statsHidden)
        self.assertIsNone(row.scoutCost);self.assertEqual(row.shieldStatus,'unknown')
        self.assertEqual((row.attack,row.defense,row.crew),(300,100,3))
        self.assertEqual(self.f.executor.calls,2)
        self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)),0)
    def test_all_off_has_no_profile_or_friendship_api_call(self):
        self.f.step();self.assertEqual(self.f.executor.calls,0);self.assertIsNone(self.source.friendCalls)
    def test_own_sync_and_planner_ticks_reuse_bounded_profile_observation(self):
        self.begin_profile();self.f.executor.queued[2]();raw=self.f.result.before
        raw.revision=2;raw.capturedAt=1;raw.native.serverNow+=1;self.h.at(1);self.f.step();self.h.at(1.25);self.f.step()
        row=self.f.runtime.allowanceSnapshot.hitListProof.profiles['42'];self.assertFalse(row.friend)
        self.assertEqual(len(self.f.executor.queued),2);self.assertEqual(self.source.friendCalls,1)
    def test_disable_queued_profile_skips_external_api_and_remote(self):
        self.begin_profile();self.f.app.Set(self.f.app,'combat.enabled',False);self.f.step();self.f.executor.queued[2]()
        self.assertEqual(self.f.executor.calls,1);self.assertIsNone(self.source.friendCalls)
    def test_unload_during_yielding_friendship_lookup_cannot_publish_profile(self):
        self.source.Friendship=self.h.lua.eval('function() coroutine.yield("friend lookup");return false end')
        # Pin the new test API before constructing the owner.
        self.f.tab.playerProfiles=self.profiles=self.h.load('src/tabs/combat/PlayerProfileQuery.luau').new(lua_table(self.h.lua,self.h.session),'a'*64,self.base.q,self.source)
        self.begin_profile();self.h.lua.globals().profileJob=self.f.executor.queued[2]
        self.assertEqual(self.h.lua.execute('profileCoroutine=coroutine.create(profileJob);local ok,value=coroutine.resume(profileCoroutine);assert(ok);return value'),'friend lookup')
        self.f.app.Destroy(self.f.app);self.h.lua.execute('assert(coroutine.resume(profileCoroutine))')
        self.assertIsNone(self.profiles.Read(self.profiles,self.f.result.before))
    def test_retired_source_reply_does_not_trigger_a_friendship_request(self):
        self.begin_profile();self.source.valid=False;self.f.executor.queued[2]()
        self.assertIsNone(self.source.friendCalls);self.assertIsNone(self.profiles.Read(self.profiles,self.f.result.before))
    def test_source_passes_requested_public_stat_age_to_free_profile_query(self):
        self.h.lua.globals().profileReply.profile.statsHidden=False
        self.h.lua.globals().profileReply.profile.atk=300;self.h.lua.globals().profileReply.profile['def']=100
        self.h.lua.globals().profileReply.profile.crew=3
        self.begin_profile();self.f.executor.queued[2]();raw=self.f.result.before
        raw.revision=2;raw.capturedAt=6;raw.native.serverNow+=6;self.h.at(6);self.f.step()
        source=next(s for s in self.f.runtime.readSources.values() if s.id=='combatProfile')
        self.assertTrue(source.enabled(lua_table(self.h.lua,{'combat':{'enabled':True,'scoutMaxAge':5}})))
        self.assertEqual(source.prepare(raw)[0].remote,'PlayerProfile')
    def tearDown(self):self.base.tearDown()
