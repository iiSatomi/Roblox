"""Native warStatus read ownership, detached projection and source isolation."""
import unittest
from engine_harness import Harness,lua_table

class OwnedWarRosterTests(unittest.TestCase):
    def setUp(self):
        self.h=Harness();self.source=self.h.lua.execute('return {valid=true,Current=function(self) return self.valid end}')
        self.module=self.h.load('src/tabs/combat/HitListQuery.luau')
        self.q=self.module.new(lua_table(self.h.lua,self.h.session),'a'*64,self.source,'war')
        self.raw=self.h.snapshot(native={'fullSync':True,'serverNow':1000,'family':{'id':'own-family'},
            'derived':{'war':{'state':'active','enemyId':'enemy-family'}}})
        self.reply=lua_table(self.h.lua,{'ok':True,'warStatus':{'day':0,'serverNow':1000.5,
            'summary':{'enemyId':'enemy-family','ownRemaining':8,'ownCap':20,'canScore':True,'eligibleAt':0,'canFeed':False},
            'targets':[{'userId':42,'name':'Enemy','level':128,'familyId':'enemy-family',
                'warStatus':{'day':0,'remaining':3,'cap':5,'attacksRemaining':2,'attacksCap':8,'pairRemaining':1,'canScore':True}}]}})
    def prepare(self):
        call,why=self.q.Prepare(self.q,self.raw);self.assertIsNotNone(call,why)
        self.assertEqual((call.remote,call.arity,call.args[1]),('GetHitList',1,'warStatus'));return call
    def commit(self):
        call=self.prepare();staged,why=self.q.Accept(self.q,self.raw,call,self.reply)
        self.assertIsNotNone(staged,why);self.assertIsNone(staged.hitListProof)
        self.assertTrue(self.q.Commit(self.q,staged));return self.q.Read(self.q,self.raw)
    def test_exact_war_only_reply_without_ordinary_list_retains_native_id_and_allowances(self):
        proof=self.commit();self.assertEqual(proof.war.enemyFamilyId,'enemy-family')
        self.assertEqual((proof.rows[1].userId,proof.rows[1].warStatus.remaining,proof.rows[1].warStatus.pairRemaining),(42,3,1))
        self.assertEqual((proof.war.ownRemaining,proof.war.ownCap,proof.war.canScore,proof.war.canFeed),(8,20,True,False))
        self.assertIsNone(proof.rows[1].stamina);self.assertIsNone(proof.rows[1].friend)
    def test_roster_uses_only_war_targets_even_if_reply_contains_an_ordinary_list(self):
        self.reply.list=lua_table(self.h.lua,[{'userId':99,'name':'Ordinary','level':10,'familyId':'other-family'}])
        self.assertEqual(self.commit().rows[1].userId,42)
    def test_inactive_empty_native_reply_is_known_without_inventing_caps(self):
        self.raw.native.derived=None;self.reply.warStatus.summary=None;self.reply.warStatus.targets=self.h.lua.table()
        proof=self.commit();self.assertIs(proof.war.active,False);self.assertIsNone(proof.war.ownRemaining)
    def test_projection_is_detached_and_staged_tampering_refuses_commit(self):
        proof=self.commit();proof.rows[1].warStatus.remaining=999;self.reply.warStatus.targets[1].warStatus.remaining=1
        self.assertEqual(self.q.Read(self.q,self.raw).rows[1].warStatus.remaining,3)
        call=self.prepare();staged=self.q.Accept(self.q,self.raw,call,self.reply)[0]
        staged.warRosterProof.rows[1].warStatus.remaining=999;self.assertFalse(self.q.Commit(self.q,staged))
    def test_bad_caps_day_or_identity_never_become_war_permission(self):
        for field,value in [('remaining',6),('day',1),('canScore','yes'),('attacksRemaining',9),('pairRemaining',-1)]:
            with self.subTest(field=field):
                self.setUp();self.reply.warStatus.targets[1].warStatus[field]=value
                self.assertIsNone(self.commit().rows[1].warStatus)
        self.setUp();self.reply.warStatus.targets[1].familyId='other-family'
        self.assertIsNone(self.commit().war.enemyFamilyId)
    def test_missing_summary_fields_stay_unknown_instead_of_defaulting_to_permission(self):
        self.reply.warStatus.summary.canScore=None;self.reply.warStatus.summary.ownRemaining=None
        proof=self.commit();self.assertIsNone(proof.war.canScore);self.assertIsNone(proof.war.ownRemaining)
    def test_close_and_native_source_retirement_fence_pending_reply(self):
        for close in (False,True):
            self.setUp();call=self.prepare()
            if close:self.q.Close(self.q)
            else:self.source.valid=False
            self.assertIsNone(self.q.Accept(self.q,self.raw,call,self.reply)[0]);self.assertIsNone(self.q.Read(self.q,self.raw))
    def test_war_id_change_expires_roster_and_regressed_status_cannot_erase_highwater(self):
        self.commit();self.raw.revision=2;self.raw.capturedAt=1;self.raw.native.serverNow=1001
        self.raw.native.derived.war.enemyId='new-enemy'
        self.assertIsNone(self.q.Read(self.q,self.raw));self.assertTrue(self.q.NeedsRead(self.q,self.raw))
        self.setUp();self.commit();self.reply.warStatus.serverNow=1000.25
        self.assertIsNone(self.commit().war)
    def test_war_owner_does_not_expose_ordinary_refresh_or_search(self):
        with self.assertRaises(Exception):self.q.Describe(self.q,True)
        self.assertIsNone(self.q.DescribeSearch(self.q,'Enemy')[0])

    def war_view(self, raw=None):
        raw=raw or self.raw
        context=lua_table(self.h.lua,{key:raw[key] for key in ('session','account','place','release','revision','capturedAt')})
        context.serverNow=raw.native.serverNow
        reader=self.h.load('src/tabs/combat/PlayerTargetState.luau')
        self.assertIsNotNone(reader.readWar,'War state reader is missing')
        return reader.readWar(raw,context)
    def test_war_state_view_retains_native_caps_without_claiming_target_readiness(self):
        proof=self.commit();self.raw.warRosterProof=proof
        view,why=self.war_view();self.assertIsNotNone(view,why)
        self.assertEqual((view.status,view.war.enemyFamilyId,view.targets[1].warStatus.attacksRemaining),('observed','enemy-family',2))
        self.assertIsNone(view.targets[1].stats);self.assertIsNone(view.targets[1].friend)
    def test_war_view_refuses_wrong_owner_header_and_stale_source_times(self):
        self.raw.warRosterProof=self.commit()
        self.raw.warRosterProof.header.account='another'
        self.assertIsNone(self.war_view()[0])
        self.raw.warRosterProof=self.q.Read(self.q,self.raw)
        self.raw.warRosterProof.observedServerNow=989
        self.assertIsNone(self.war_view()[0])
    def test_unknown_enemy_never_produces_a_war_view_and_inactive_is_explicit(self):
        self.reply.warStatus.summary.enemyId=None;self.reply.warStatus.targets[1].familyId=None
        self.raw.warRosterProof=self.commit();self.assertIsNone(self.war_view()[0])
        self.setUp();self.raw.native.derived=None;self.reply.warStatus.summary=None;self.reply.warStatus.targets=self.h.lua.table()
        self.raw.warRosterProof=self.commit();view,why=self.war_view()
        self.assertIsNotNone(view,why);self.assertIs(view.war.active,False);self.assertEqual(len(view.targets),0)
    def test_view_keeps_missing_allowances_unknown_and_does_not_mutate_owned_proof(self):
        self.reply.warStatus.targets[1].warStatus=None;self.raw.warRosterProof=self.commit()
        view,why=self.war_view();self.assertIsNotNone(view,why);self.assertIsNone(view.targets[1].warStatus)
        view.targets[1].name='changed';self.assertEqual(self.raw.warRosterProof.rows[1].name,'Enemy')
