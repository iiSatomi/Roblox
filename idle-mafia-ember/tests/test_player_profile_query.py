"""Owned native profile/Roblox-reported friendship facts; never Scout or Attack."""
import unittest
from engine_harness import Harness,lua_table

class PlayerProfileQueryTests(unittest.TestCase):
    def setUp(self):
        self.h=Harness();self.source=self.h.lua.execute("""return {valid=true,friend=false,calls=0,
            Current=function(self) return self.valid end,Friendship=function(self) self.calls=self.calls+1;return self.friend end}""")
        self.targets=self.h.load('src/tabs/combat/HitListQuery.luau').new(lua_table(self.h.lua,self.h.session),'a'*64,self.source)
        self.raw=self.h.snapshot(native={'fullSync':True,'serverNow':1000});self.seed()
        self.q=self.h.load('src/tabs/combat/PlayerProfileQuery.luau').new(lua_table(self.h.lua,self.h.session),'a'*64,self.targets,self.source)
        self.reply=lua_table(self.h.lua,{'ok':True,'profile':{'userId':42,'name':'Target','level':128,'maxLevel':211,
            'familyId':'foreign-family','scoutCost':1,'statsHidden':True,'atk':300,'def':100,'crew':3}})
    def seed(self):
        request=self.targets.Prepare(self.targets,self.raw)[0]
        reply=lua_table(self.h.lua,{'ok':True,'list':[{'userId':42,'name':'Target','level':128,'stamina':2,
            'familyId':'foreign-family','shielded':False}]})
        staged=self.targets.Accept(self.targets,self.raw,request,reply)[0];self.targets.Commit(self.targets,staged)
    def prepare(self):
        request,why=self.q.Prepare(self.q,self.raw);self.assertIsNotNone(request,why)
        self.assertEqual((request.remote,request.args[1],request.arity),('PlayerProfile',42,1));return request
    def accept(self):
        request=self.prepare();staged,why=self.q.Accept(self.q,self.raw,request,self.reply)
        self.assertIsNotNone(staged,why);self.assertTrue(self.q.Commit(self.q,staged));return self.q.Read(self.q,self.raw)['42']
    def test_hidden_stats_are_not_promoted_and_scout_quote_is_independent(self):
        row=self.accept();self.assertTrue(row.statsHidden);self.assertIsNone(row.defense)
        self.assertEqual(row.scoutCost,1);self.assertFalse(row.friend)
        self.assertEqual(self.source.calls,1);self.assertIsNone(self.q.Prepare(self.q,self.raw)[0])
    def test_public_stats_require_visible_flag_and_valid_native_numbers(self):
        self.reply.profile.statsHidden=False;row=self.accept()
        self.assertEqual((row.attack,row.defense,row.crew),(300,100,3))
        row.defense=0;self.assertEqual(self.q.Read(self.q,self.raw)['42'].defense,100)
    def test_native_public_profile_omits_hidden_and_scout_fields(self):
        self.reply.profile.statsHidden=None;self.reply.profile.scoutCost=None
        row=self.accept()
        self.assertFalse(row.statsHidden);self.assertIsNone(row.scoutCost)
        self.assertEqual((row.attack,row.defense,row.crew),(300,100,3))
        self.assertEqual(row.shieldStatus,'unknown')
    def test_absent_hidden_flag_requires_complete_public_numbers_and_no_scout_quote(self):
        for field,value in [('atk',None),('def',None),('crew',None),('atk',float('nan')),('scoutCost',1)]:
            with self.subTest(field=field,value=value):
                self.setUp();self.reply.profile.statsHidden=None;self.reply.profile.scoutCost=None
                self.reply.profile[field]=value
                self.assertIsNone(self.q.Accept(self.q,self.raw,self.prepare(),self.reply)[0])
    def test_hidden_profile_without_exact_scout_quote_stays_unavailable(self):
        self.reply.profile.scoutCost=None
        self.assertIsNone(self.q.Accept(self.q,self.raw,self.prepare(),self.reply)[0])
    def test_wrong_user_level_family_or_invalid_stats_never_commit(self):
        for field,value in [('userId',43),('level',129),('familyId','other'),('statsHidden',None),('scoutCost',0)]:
            with self.subTest(field=field):
                self.setUp();self.reply.profile[field]=value;request=self.prepare()
                self.assertIsNone(self.q.Accept(self.q,self.raw,request,self.reply)[0])
        self.setUp();self.reply.profile.statsHidden=False;self.reply.profile['def']=float('nan')
        self.assertIsNone(self.q.Accept(self.q,self.raw,self.prepare(),self.reply)[0])
    def test_friendship_failure_is_unknown_and_never_defaults_to_not_friend(self):
        self.source.Friendship=self.h.lua.eval('function() error("friend lookup failed") end')
        self.q=self.h.load('src/tabs/combat/PlayerProfileQuery.luau').new(lua_table(self.h.lua,self.h.session),'a'*64,self.targets,self.source)
        row=self.accept();self.assertIsNone(row.friend);self.assertEqual(row.friendshipStatus,'unknown')
    def test_stale_snapshot_request_or_target_list_generation_refuses_profile(self):
        request=self.prepare();self.raw.revision=2
        self.assertIsNone(self.q.Accept(self.q,self.raw,request,self.reply)[0])
        self.setUp();request=self.prepare();self.seed()
        self.assertIsNone(self.q.Accept(self.q,self.raw,request,self.reply)[0])
    def test_source_retirement_during_friendship_yield_cannot_commit(self):
        self.h.lua.globals().profileSource=self.source
        self.source.Friendship=self.h.lua.eval('function() profileSource.valid=false;return false end')
        self.q=self.h.load('src/tabs/combat/PlayerProfileQuery.luau').new(lua_table(self.h.lua,self.h.session),'a'*64,self.targets,self.source)
        self.assertIsNone(self.q.Accept(self.q,self.raw,self.prepare(),self.reply)[0])
        self.source.valid=True;self.assertIsNone(self.q.Read(self.q,self.raw))
    def test_close_or_tampered_staging_never_exposes_profile(self):
        request=self.prepare();staged=self.q.Accept(self.q,self.raw,request,self.reply)[0]
        staged.playerProfileRead.defense=999;self.assertFalse(self.q.Commit(self.q,staged))
        self.q.Close(self.q);self.assertIsNone(self.q.Read(self.q,self.raw));self.assertIsNone(self.q.Prepare(self.q,self.raw)[0])
    def test_engine_reported_friend_stays_excluded_as_friend(self):
        self.source.friend=True;self.assertTrue(self.accept().friend)

    def test_profile_cache_survives_own_pool_sync_without_repeating_native_or_friend_reads(self):
        self.accept();self.raw.revision=2;self.raw.capturedAt=1;self.raw.native.serverNow=1001
        row=self.q.Read(self.q,self.raw)['42'];self.assertEqual(row.observedServerNow,1000)
        self.assertIsNone(self.q.Prepare(self.q,self.raw)[0]);self.assertEqual(self.source.calls,1)
    def test_new_hit_list_reuses_profile_only_for_unchanged_identity_within_30_seconds(self):
        self.accept();self.raw.revision=2;self.raw.capturedAt=20;self.raw.native.serverNow=1020;self.seed()
        self.assertIsNone(self.q.Prepare(self.q,self.raw)[0]);self.assertEqual(self.source.calls,1)
        self.raw.revision=3;self.raw.capturedAt=31;self.raw.native.serverNow=1031;self.seed()
        self.assertIsNotNone(self.q.Prepare(self.q,self.raw)[0])

    def test_unreadable_first_target_does_not_starve_later_profiles(self):
        request=self.targets.Prepare(self.targets,self.raw)[0]
        rows=[{'userId':42,'name':'Target','level':128,'stamina':2,'familyId':'foreign-family','shielded':False},
            {'userId':43,'name':'Other','level':129,'stamina':1,'familyId':'foreign-family','shielded':False}]
        staged=self.targets.Accept(self.targets,self.raw,request,lua_table(self.h.lua,{'ok':True,'list':rows}))[0]
        self.targets.Commit(self.targets,staged)
        first=self.q.Prepare(self.q,self.raw)[0];self.assertEqual(first.args[1],42)
        self.assertIsNone(self.q.Accept(self.q,self.raw,first,lua_table(self.h.lua,{'ok':False}))[0])
        second=self.q.Prepare(self.q,self.raw)[0];self.assertEqual(second.args[1],43)
        self.reply.profile.userId=43;self.reply.profile.name='Other';self.reply.profile.level=129
        result=self.q.Accept(self.q,self.raw,second,self.reply)[0];self.assertTrue(self.q.Commit(self.q,result))
        known=self.q.Read(self.q,self.raw);self.assertIsNone(known['42']);self.assertIsNotNone(known['43'])
        self.assertEqual(self.q.Prepare(self.q,self.raw)[0].args[1],42)

    def test_numeric_zero_shield_from_owned_native_list_can_be_profiled_without_losing_raw_fact(self):
        request=self.targets.Prepare(self.targets,self.raw)[0]
        response=lua_table(self.h.lua,{'ok':True,'list':[{'userId':42,'name':'Target','level':128,
            'stamina':2,'familyId':'foreign-family','shielded':0}]})
        staged=self.targets.Accept(self.targets,self.raw,request,response)[0];self.targets.Commit(self.targets,staged)
        row=self.targets.Read(self.targets,self.raw).rows[1]
        self.assertIs(row.shielded,False);self.assertEqual(row.nativeShielded,0)
        self.assertEqual(self.q.Prepare(self.q,self.raw)[0].args[1],42)

    def test_stricter_public_stat_age_requests_free_profile_refresh(self):
        self.reply.profile.statsHidden=False;self.accept()
        self.raw.revision=2;self.raw.capturedAt=6;self.raw.native.serverNow=1006
        self.assertTrue(self.q.NeedsRead(self.q,self.raw,5))
        self.assertIsNotNone(self.q.Prepare(self.q,self.raw,5)[0])
    def test_hidden_profile_does_not_repeat_free_read_for_public_stat_age(self):
        self.accept();self.raw.revision=2;self.raw.capturedAt=6;self.raw.native.serverNow=1006
        self.assertFalse(self.q.NeedsRead(self.q,self.raw,5))

    def test_owned_scout_result_is_cached_by_identity_and_expiry_without_exposing_hidden_public_stats(self):
        import test_player_scout_evidence as scout_fixture
        f=scout_fixture.PlayerScoutEvidenceTests();f.provided_h=self.h;f.setUp()
        self.q=self.h.load('src/tabs/combat/PlayerProfileQuery.luau').new(lua_table(self.h.lua,self.h.session),'a'*64,self.targets,self.source,f.e)
        self.accept()
        # Rebind the Scout fixture to this exact current target/profile identity.
        f.p.intent.familyId='foreign-family';f.before.hitListProof.rows[1].familyId='foreign-family'
        f.before.hitListProof.profiles['42'].familyId='foreign-family';f.baseline=f.e.capture(f.p,f.before)[0]
        f.after.native.serverNow=1001.25
        self.assertTrue(self.q.RecordScout(self.q,f.data(),f.after)[0])
        self.raw.revision=2;self.raw.capturedAt=1;self.raw.native.serverNow=1001.25
        row=self.q.Read(self.q,self.raw)['42']
        self.assertTrue(row.statsHidden);self.assertIsNone(row.defense)
        self.assertEqual((row.scout.kind,row.scout.defense,row.scout.level),('scout',100,128))
        row.scout.defense=999;self.assertEqual(self.q.Read(self.q,self.raw)['42'].scout.defense,100)
        f.after.native.pools.stamina=18;self.assertFalse(self.q.RecordScout(self.q,f.data(),f.after)[0])
        self.q.Close(self.q);self.assertFalse(self.q.RecordScout(self.q,f.data(),f.after)[0])

    def test_owned_scout_gap_cache_is_bounded_and_old_facts_do_not_get_a_new_lifetime(self):
        import test_player_scout_evidence as scout_fixture
        f=scout_fixture.PlayerScoutEvidenceTests();f.provided_h=self.h;f.setUp()
        self.q=self.h.load('src/tabs/combat/PlayerProfileQuery.luau').new(
            lua_table(self.h.lua,self.h.session),'a'*64,self.targets,self.source,f.e)
        f.after.native.respect=1
        self.assertIsNone(self.targets.Read(self.targets,f.after))
        for target in range(1000,1130):
            f.p.intent.target=target;f.p.requestId=target;f.p.actionKey='combat:scout:'+str(target)
            f.before.hitListProof.rows[1].userId=target
            profile=f.before.hitListProof.profiles['42'] if target==1000 else f.before.hitListProof.profiles[str(target-1)]
            profile.userId=target
            f.before.hitListProof.profiles=lua_table(self.h.lua,{str(target):profile})
            f.baseline=f.e.capture(f.p,f.before)[0];self.assertIsNotNone(f.baseline)
            self.assertTrue(self.q.RecordScout(self.q,f.data(),f.after)[0])
        self.assertEqual(len(list(self.q.scoutCache.keys())),128)
        self.assertIsNone(self.q.scoutCache['1000']);self.assertIsNone(self.q.scoutCache['1001'])
        self.assertEqual(self.q.scoutCache['1129'].at,f.before.native.serverNow)
        f.after.revision+=1;f.after.capturedAt=1801;f.after.native.serverNow+=1801
        self.assertTrue(self.q.RecordScout(self.q,f.data(),f.after)[0])
        self.assertEqual(len(list(self.q.scoutCache.keys())),0)

    def test_native_profile_shield_is_kept_with_a_conservative_expiry(self):
        self.reply.profile.shieldLeft=10;self.reply.profile.serverNow=1002
        row=self.accept();self.assertGreaterEqual(row.shieldUntil,1012)
        self.setUp();self.reply.profile.shieldLeft=10
        row=self.accept();self.assertGreaterEqual(row.shieldUntil,1040)
        self.setUp();self.reply.profile.shieldLeft=-1
        self.assertIsNone(self.q.Accept(self.q,self.raw,self.prepare(),self.reply)[0])
