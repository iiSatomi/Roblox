"""Roster-bound war profile data is read-only, eligibility-filtered and separate."""
import unittest
import test_owned_war_roster as roster_fixture
from engine_harness import lua_table

class WarProfileQueryTests(unittest.TestCase):
    def setUp(self):
        self.f=roster_fixture.OwnedWarRosterTests();self.f.setUp();self.h=self.f.h
        self.source=self.f.source
        self.source.Friendship=self.h.lua.eval('function(self) self.friendCalls=(self.friendCalls or 0)+1;return false end')
        self.f.commit();self.targets=self.f.q;self.raw=self.f.raw
        self.q=self.h.load('src/tabs/combat/PlayerProfileQuery.luau').new(lua_table(self.h.lua,self.h.session),'a'*64,self.targets,self.source)
        self.reply=lua_table(self.h.lua,{'ok':True,'profile':{'userId':42,'name':'Enemy','level':128,'maxLevel':150,
            'familyId':'enemy-family','scoutCost':1,'statsHidden':True,'atk':300,'def':100,'crew':3}})
    def prepare(self):
        call,why=self.q.Prepare(self.q,self.raw);self.assertIsNotNone(call,why)
        self.assertEqual((call.remote,call.args[1]),('PlayerProfile',42));return call
    def accept(self):
        call=self.prepare();staged,why=self.q.Accept(self.q,self.raw,call,self.reply)
        self.assertIsNotNone(staged,why);self.assertTrue(self.q.Commit(self.q,staged));return self.q.Read(self.q,self.raw)['42']
    def test_native_eligible_roster_without_ordinary_shield_field_can_be_profiled(self):
        row=self.accept();self.assertTrue(row.statsHidden);self.assertIsNone(row.defense)
        self.assertEqual((row.friend,row.shieldStatus,row.scoutCost),(False,'unknown',1));self.assertEqual(self.source.friendCalls,1)
    def test_capped_or_unscorable_rows_are_skipped_without_remote_or_friendship_calls(self):
        for field,value in [('remaining',0),('attacksRemaining',0),('pairRemaining',0),('canScore',False)]:
            self.setUp();self.f.reply.warStatus.targets[1].warStatus[field]=value;self.f.commit()
            self.assertIsNone(self.q.Prepare(self.q,self.raw)[0]);self.assertIsNone(self.source.friendCalls)
        self.setUp();self.f.reply.warStatus.summary.canScore=False;self.f.commit()
        self.assertIsNone(self.q.Prepare(self.q,self.raw)[0])
    def test_missing_allowance_or_identity_never_triggers_profile_lookup(self):
        for missing in ('warStatus','familyId'):
            self.setUp();self.f.reply.warStatus.targets[1][missing]=None;self.f.commit()
            self.assertIsNone(self.q.Prepare(self.q,self.raw)[0])
    def test_reported_profile_shield_is_distinct_from_missing_shield_evidence(self):
        self.reply.profile.shieldLeft=0;self.assertEqual(self.accept().shieldStatus,'clear')
        self.setUp();self.reply.profile.shieldLeft=10;row=self.accept()
        self.assertEqual(row.shieldStatus,'shielded');self.assertGreater(row.shieldUntil,1010)
    def test_scope_change_before_accept_does_not_call_friendship(self):
        call=self.prepare();self.raw.native.derived.war.enemyId='different-enemy'
        self.assertIsNone(self.q.Accept(self.q,self.raw,call,self.reply)[0]);self.assertIsNone(self.source.friendCalls)
    def test_unchanged_identity_survives_roster_refresh_without_duplicate_profile_read(self):
        self.accept();self.raw.revision=2;self.raw.capturedAt=1;self.raw.native.serverNow=1001
        self.f.reply.warStatus.serverNow=1001.5;self.f.commit()
        self.assertIsNone(self.q.Prepare(self.q,self.raw)[0]);self.assertEqual(self.source.friendCalls,1)
    def test_view_exposes_only_current_matching_profile_and_never_promotes_hidden_power(self):
        self.accept();self.raw.warRosterProof=self.targets.Read(self.targets,self.raw)
        self.raw.warRosterProof.profiles=self.q.Read(self.q,self.raw)
        context=lua_table(self.h.lua,{k:self.raw[k] for k in ('session','account','place','release','revision','capturedAt')})
        context.serverNow=1000
        reader=self.h.load('src/tabs/combat/PlayerTargetState.luau');view,why=reader.readWar(self.raw,context)
        self.assertIsNotNone(view,why);self.assertIsNotNone(view.targets[1].profile)
        self.assertTrue(view.targets[1].profile.statsHidden);self.assertIsNone(view.targets[1].profile.defense)
        self.assertEqual(view.targets[1].profile.shieldStatus,'unknown')
        self.raw.warRosterProof.profiles['42'].familyId='moved-family'
        self.assertIsNone(reader.readWar(self.raw,context)[0].targets[1].profile)

    def test_visible_stats_are_retained_but_unknown_friendship_stays_unknown(self):
        self.source.Friendship=self.h.lua.eval('function() error("unavailable") end')
        self.q=self.h.load('src/tabs/combat/PlayerProfileQuery.luau').new(lua_table(self.h.lua,self.h.session),'a'*64,self.targets,self.source)
        self.reply.profile.statsHidden=False;row=self.accept()
        self.assertEqual((row.attack,row.defense,row.crew),(300,100,3))
        self.assertEqual(row.friendshipStatus,'unknown');self.assertIsNone(row.friend)
    def test_scope_change_inside_friendship_refuses_staging_without_refunding_or_sending(self):
        self.h.lua.globals().warProfileRaw=self.raw
        self.source.Friendship=self.h.lua.eval('function() warProfileRaw.native.derived.war.enemyId="changed";return false end')
        self.q=self.h.load('src/tabs/combat/PlayerProfileQuery.luau').new(lua_table(self.h.lua,self.h.session),'a'*64,self.targets,self.source)
        self.assertIsNone(self.q.Accept(self.q,self.raw,self.prepare(),self.reply)[0])
        self.assertIsNone(self.q.Read(self.q,self.raw))
    def test_rejected_first_eligible_target_does_not_starve_the_next_target(self):
        second=lua_table(self.h.lua,{'userId':43,'name':'Second','level':129,'familyId':'enemy-family',
            'warStatus':{'day':0,'remaining':2,'cap':5,'attacksRemaining':2,'attacksCap':8,'pairRemaining':1,'canScore':True}})
        self.f.reply.warStatus.targets[2]=second;self.f.commit()
        first=self.prepare();self.assertIsNone(self.q.Accept(self.q,self.raw,first,lua_table(self.h.lua,{'ok':False}))[0])
        self.assertEqual(self.q.Prepare(self.q,self.raw)[0].args[1],43)
    def test_expired_profile_is_not_promoted_into_a_fresh_war_view(self):
        self.accept();self.raw.revision=2;self.raw.capturedAt=31;self.raw.native.serverNow=1031
        self.f.reply.warStatus.serverNow=1031.5;self.f.commit()
        self.assertIsNone(self.q.Read(self.q,self.raw)['42']);self.assertIsNotNone(self.q.Prepare(self.q,self.raw)[0])
