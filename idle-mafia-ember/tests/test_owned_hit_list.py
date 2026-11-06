"""Current hit-list reads are one-use, scoped, detached and never enable player attacks."""
import unittest
from engine_harness import Harness,lua_table

class OwnedHitListTests(unittest.TestCase):
    def setUp(self):
        self.h=Harness();self.q=self.h.load('src/tabs/combat/HitListQuery.luau').new(lua_table(self.h.lua,self.h.session),'a'*64)
        self.raw=self.h.snapshot(native={'fullSync':True,'serverNow':1000})
        self.reply=lua_table(self.h.lua,{'ok':True,'list':[{'userId':42,'name':'Target','level':128,
            'stamina':2,'shielded':False,'familyId':'foreign-family','prestige':2,'respect':100}]})
    def prepare(self):
        call,why=self.q.Prepare(self.q,self.raw);self.assertIsNotNone(call,why)
        self.assertEqual((call.remote,call.arity,call.args[1]),('GetHitList',1,False));return call
    def test_owned_current_quote_preserves_family_and_stamina_without_spending_or_friend_assumption(self):
        call=self.prepare();staged,why=self.q.Accept(self.q,self.raw,call,self.reply)
        self.assertIsNotNone(staged,why);self.assertTrue(self.q.Commit(self.q,staged))
        proof=self.q.Read(self.q,self.raw);row=proof.rows[1]
        self.assertEqual((row.familyId,row.stamina,row.prestige),('foreign-family',2,2));self.assertIsNone(row.friend)
        self.assertEqual(proof.sourceKey,'a'*64);self.assertEqual(len(self.h.transport.sent),0)
    def test_stale_or_replaced_request_cannot_activate_a_proof(self):
        old=self.prepare();new=self.prepare();self.assertIsNone(self.q.Accept(self.q,self.raw,old,self.reply)[0])
        self.raw.revision=2;self.assertIsNone(self.q.Accept(self.q,self.raw,new,self.reply)[0]);self.assertIsNone(self.q.Read(self.q,self.raw))
    def test_tampered_request_or_staged_payload_is_not_committed(self):
        call=self.prepare();call.args[1]=True;self.assertIsNone(self.q.Accept(self.q,self.raw,call,self.reply)[0])
        call=self.prepare();staged=self.q.Accept(self.q,self.raw,call,self.reply)[0]
        staged.hitListProof.rows[1].stamina=1;self.assertFalse(self.q.Commit(self.q,staged))
    def test_read_and_commit_are_detached_and_sync_change_drops_old_proof(self):
        call=self.prepare();staged=self.q.Accept(self.q,self.raw,call,self.reply)[0];self.q.Commit(self.q,staged)
        self.reply.list[1].familyId='own-family';proof=self.q.Read(self.q,self.raw);proof.rows[1].stamina=5
        self.assertEqual(self.q.Read(self.q,self.raw).rows[1].stamina,2)
        self.raw.native.serverNow+=1;self.assertIsNone(self.q.Read(self.q,self.raw))
    def test_close_fences_inflight_reply_commit_and_proof(self):
        call=self.prepare();staged=self.q.Accept(self.q,self.raw,call,self.reply)[0];self.q.Close(self.q)
        self.assertFalse(self.q.Commit(self.q,staged));self.assertIsNone(self.q.Read(self.q,self.raw));self.assertIsNone(self.q.Prepare(self.q,self.raw)[0])
    def test_invalid_family_metadata_never_becomes_a_foreign_family(self):
        for value in ('',-1,'family\nother'):
            self.reply.list[1].familyId=value;call=self.prepare()
            self.assertIsNone(self.q.Accept(self.q,self.raw,call,self.reply)[0])

    def test_source_retirement_at_commit_is_sticky_and_never_resurrects_old_proof(self):
        source=self.h.lua.execute('return {valid=true,Current=function(self) return self.valid end}')
        self.q=self.h.load('src/tabs/combat/HitListQuery.luau').new(lua_table(self.h.lua,self.h.session),'a'*64,source)
        call=self.prepare();staged=self.q.Accept(self.q,self.raw,call,self.reply)[0];source.valid=False
        self.assertFalse(self.q.Commit(self.q,staged));source.valid=True
        self.assertIsNone(self.q.Read(self.q,self.raw));self.assertIsNone(self.q.Prepare(self.q,self.raw)[0])
    def test_staged_header_cannot_be_rebound_at_commit(self):
        call=self.prepare();staged=self.q.Accept(self.q,self.raw,call,self.reply)[0];staged.revision+=1
        self.assertFalse(self.q.Commit(self.q,staged))

    def test_target_metadata_survives_new_resource_sync_only_with_explicit_bounded_read_age(self):
        call=self.prepare();staged=self.q.Accept(self.q,self.raw,call,self.reply)[0];self.q.Commit(self.q,staged)
        self.raw.revision=2;self.raw.capturedAt=1;self.raw.native.serverNow=1001
        proof=self.q.Read(self.q,self.raw);self.assertIsNotNone(proof)
        self.assertEqual((proof.header.revision,proof.capturedAt,proof.readHeader.revision,proof.observedAt),(2,1,1,0))
        self.assertEqual(proof.observedServerNow,1000)
    def test_target_cache_expires_by_either_native_or_local_time_and_never_moves_backwards(self):
        call=self.prepare();staged=self.q.Accept(self.q,self.raw,call,self.reply)[0];self.q.Commit(self.q,staged)
        for at,server in ((11,1001),(1,1011),(1,999)):
            self.raw.revision=2;self.raw.capturedAt=at;self.raw.native.serverNow=server
            self.assertIsNone(self.q.Read(self.q,self.raw))

    def test_native_hit_list_war_status_supplies_inactive_proof_without_another_rpc(self):
        self.reply.warStatus=lua_table(self.h.lua,{'day':0,'serverNow':1000.5,'targets':[]})
        call=self.prepare();staged=self.q.Accept(self.q,self.raw,call,self.reply)[0];self.q.Commit(self.q,staged)
        self.assertIs(self.q.Read(self.q,self.raw).war.active,False)
    def test_absent_or_wrong_day_war_status_never_becomes_inactive(self):
        for status in (None,{'day':1,'serverNow':1000,'targets':[]}):
            self.reply.warStatus=lua_table(self.h.lua,status) if status else None
            call=self.prepare();staged=self.q.Accept(self.q,self.raw,call,self.reply)[0];self.q.Commit(self.q,staged)
            self.assertIsNone(self.q.Read(self.q,self.raw).war)
    def test_active_summary_is_preserved_as_active_without_guessing_enemy_identity(self):
        self.reply.warStatus=lua_table(self.h.lua,{'day':0,'serverNow':1000.5,'targets':[],'summary':{}})
        call=self.prepare();staged=self.q.Accept(self.q,self.raw,call,self.reply)[0];self.q.Commit(self.q,staged)
        proof=self.q.Read(self.q,self.raw);self.assertTrue(proof.war.active);self.assertIsNone(proof.war.enemyFamilyId)

    def test_own_war_or_family_change_invalidates_only_inactive_war_proof(self):
        self.reply.warStatus=lua_table(self.h.lua,{'day':0,'serverNow':1000,'targets':[]})
        call=self.prepare();staged=self.q.Accept(self.q,self.raw,call,self.reply)[0];self.q.Commit(self.q,staged)
        self.raw.revision=2;self.raw.capturedAt=1;self.raw.native.serverNow=1001
        self.raw.native.family=lua_table(self.h.lua,{'id':'new-family'})
        proof=self.q.Read(self.q,self.raw);self.assertIsNotNone(proof);self.assertIsNone(proof.war)
    def test_own_pricing_change_requires_new_quote_but_pool_sync_does_not(self):
        call=self.prepare();staged=self.q.Accept(self.q,self.raw,call,self.reply)[0];self.q.Commit(self.q,staged)
        self.raw.revision=2;self.raw.capturedAt=1;self.raw.native.serverNow=1001
        self.raw.native.pools=lua_table(self.h.lua,{'health':99,'stamina':10})
        self.assertIsNotNone(self.q.Read(self.q,self.raw))
        self.raw.native.respect=100;self.assertIsNone(self.q.Read(self.q,self.raw));self.assertTrue(self.q.NeedsRead(self.q,self.raw))
    def test_day_change_invalidates_cached_war_proof(self):
        self.raw.native.serverNow=86399
        self.reply.warStatus=lua_table(self.h.lua,{'day':0,'serverNow':86399.5,'targets':[]})
        call=self.prepare();staged=self.q.Accept(self.q,self.raw,call,self.reply)[0];self.q.Commit(self.q,staged)
        self.raw.revision=2;self.raw.capturedAt=1;self.raw.native.serverNow=86401
        self.assertIsNone(self.q.Read(self.q,self.raw).war)

    def test_stale_same_day_war_status_and_far_future_time_are_not_current_permission(self):
        for at in (1,1011):
            self.reply.warStatus=lua_table(self.h.lua,{'day':0,'serverNow':at,'targets':[]})
            call=self.prepare();staged=self.q.Accept(self.q,self.raw,call,self.reply)[0];self.q.Commit(self.q,staged)
            self.assertIsNone(self.q.Read(self.q,self.raw).war)
    def test_changed_family_requests_fresh_war_proof_without_repolling_missing_status_each_tick(self):
        self.reply.warStatus=lua_table(self.h.lua,{'day':0,'serverNow':1000,'targets':[]})
        call=self.prepare();staged=self.q.Accept(self.q,self.raw,call,self.reply)[0];self.q.Commit(self.q,staged)
        self.raw.revision=2;self.raw.capturedAt=1;self.raw.native.serverNow=1001;self.raw.native.family=lua_table(self.h.lua,{'id':'new'})
        self.assertTrue(self.q.NeedsRead(self.q,self.raw))
        self.reply.warStatus=None;call=self.prepare();staged=self.q.Accept(self.q,self.raw,call,self.reply)[0];self.q.Commit(self.q,staged)
        self.assertFalse(self.q.NeedsRead(self.q,self.raw))

    def test_repeated_regressed_status_cannot_erase_the_accepted_war_highwater(self):
        for at,summary,known in ((1001,{},True),(1000.5,None,False),(1000.5,None,False)):
            status={'day':0,'serverNow':at,'targets':[]}
            if summary is not None: status['summary']=summary
            self.reply.warStatus=lua_table(self.h.lua,status)
            call=self.prepare();staged=self.q.Accept(self.q,self.raw,call,self.reply)[0]
            self.assertTrue(self.q.Commit(self.q,staged))
            proof=self.q.Read(self.q,self.raw)
            self.assertEqual(proof.war is not None,known)
            if known: self.assertTrue(proof.war.active)

    def active_status(self, enemy='enemy-family', targets=None):
        self.raw.native.family=lua_table(self.h.lua,{'id':'own-family'})
        self.raw.native.derived=lua_table(self.h.lua,{'war':{'state':'active','enemyId':'enemy-family'}})
        summary={} if enemy is None else {'enemyId':enemy}
        return {'day':0,'serverNow':1000.5,'summary':summary,'targets':targets or []}
    def war_proof(self, status):
        self.reply.warStatus=lua_table(self.h.lua,status)
        call=self.prepare();staged=self.q.Accept(self.q,self.raw,call,self.reply)[0]
        self.assertTrue(self.q.Commit(self.q,staged));return self.q.Read(self.q,self.raw).war
    def test_source_owned_summary_enemy_id_is_retained_without_a_second_read(self):
        proof=self.war_proof(self.active_status())
        self.assertEqual(proof.enemyFamilyId,'enemy-family');self.assertTrue(proof.active)
        self.assertEqual(len(self.h.transport.sent),0)
    def test_native_roster_family_fallback_requires_consistent_unambiguous_identity(self):
        rows=[{'userId':43,'familyId':'enemy-family'},{'userId':44,'familyId':'enemy-family'}]
        self.assertEqual(self.war_proof(self.active_status(None,rows)).enemyFamilyId,'enemy-family')
        for bad in ([{'userId':42,'familyId':'other'}],
                    [{'userId':42,'familyId':'enemy-family'},{'userId':42,'familyId':'enemy-family'}],
                    [{'userId':42}], [{'userId':42,'familyId':99}]):
            self.assertIsNone(self.war_proof(self.active_status(None,bad)).enemyFamilyId)
    def test_conflicting_or_invalid_enemy_never_permits_ordinary_selection(self):
        for enemy in ('own-family','',0,99,'bad\nfamily'):
            self.assertIsNone(self.war_proof(self.active_status(enemy)).enemyFamilyId)
        self.assertIsNone(self.war_proof(self.active_status('enemy-family',[{'userId':42,'familyId':'other'}])).enemyFamilyId)
        self.raw.native.derived=None
        self.assertIsNone(self.war_proof({'day':0,'serverNow':1000.5,'summary':{'enemyId':'enemy-family'},'targets':[]}).enemyFamilyId)
    def test_changed_enemy_on_new_sync_invalidates_cached_identity_before_ttl(self):
        self.assertEqual(self.war_proof(self.active_status()).enemyFamilyId,'enemy-family')
        self.raw.revision=2;self.raw.capturedAt=1;self.raw.native.serverNow=1001
        self.raw.native.derived.war.enemyId='replacement-enemy'
        self.assertIsNone(self.q.Read(self.q,self.raw).war);self.assertTrue(self.q.NeedsRead(self.q,self.raw))
