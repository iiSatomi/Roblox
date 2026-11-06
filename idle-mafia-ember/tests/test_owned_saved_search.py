"""Exact saved-user lookup reuses the current hit-list owner and never grants a fight."""
import unittest
from engine_harness import lua_table
import test_owned_hit_list as fixture

class OwnedSavedSearchTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.OwnedHitListTests();self.f.setUp();self.h=self.f.h;self.q=self.f.q;self.raw=self.f.raw
        call=self.f.prepare();self.assertTrue(self.q.Commit(self.q,self.q.Accept(self.q,self.raw,call,self.f.reply)[0]))
        self.target=lua_table(self.h.lua,{'userId':7,'name':'SavedPlayer'})
        self.reply=lua_table(self.h.lua,{'ok':True,'search':'SavedPlayer','list':[{'userId':7,'name':'SavedPlayer','level':12,'stamina':2,'shielded':False,'familyId':'other-family'}]})
    def prepare(self):
        request,why=self.q.PrepareSavedSearch(self.q,self.raw,self.target)
        self.assertIsNotNone(request,why);self.assertEqual((request.remote,request.args[1]),('SearchTarget','SavedPlayer'));return request
    def commit(self,request=None):
        request=request or self.prepare();staged,why=self.q.AcceptSavedSearch(self.q,self.raw,request,self.reply)
        self.assertIsNotNone(staged,why);self.assertTrue(self.q.CommitSavedSearch(self.q,staged));return staged
    def test_exact_identity_search_joins_without_replacing_the_ordinary_list(self):
        self.commit();proof=self.q.Read(self.q,self.raw)
        self.assertEqual([r.userId for r in proof.rows.values()],[42,7])
        proof.rows[2].name='tampered';self.assertEqual(self.q.Read(self.q,self.raw).rows[2].name,'SavedPlayer')
        self.assertEqual(len(self.h.transport.sent),0)
    def test_matching_name_with_wrong_id_never_enters_target_catalog(self):
        self.reply.list[1].userId=8;self.commit()
        self.assertEqual(len(self.q.Read(self.q,self.raw).rows),1)
    def test_missing_or_wrong_echo_negative_pending_or_challenge_never_commits(self):
        for change in ('echo','missing','negative','pending','presence','rate'):
            self.setUp();request=self.prepare()
            if change=='echo':self.reply.search='Other'
            elif change=='missing':self.reply.search=None
            elif change=='negative':self.reply.ok=False
            elif change=='pending':self.reply.pending=True
            else:self.reply.code='presence' if change=='presence' else 'rate_limited'
            self.assertIsNone(self.q.AcceptSavedSearch(self.q,self.raw,request,self.reply)[0])
            self.assertEqual(len(self.q.Read(self.q,self.raw).rows),1)
    def test_scope_revision_request_and_staged_payload_changes_refuse(self):
        request=self.prepare();self.raw.revision+=1
        self.assertIsNone(self.q.AcceptSavedSearch(self.q,self.raw,request,self.reply)[0])
        self.setUp();request=self.prepare();self.q.Prepare(self.q,self.raw)
        self.assertIsNone(self.q.AcceptSavedSearch(self.q,self.raw,request,self.reply)[0])
        self.setUp();request=self.prepare();staged=self.q.AcceptSavedSearch(self.q,self.raw,request,self.reply)[0]
        staged.hitListProof.rows[1].userId=8
        self.assertFalse(self.q.CommitSavedSearch(self.q,staged))
    def test_search_does_not_renew_old_result_when_normal_list_refreshes(self):
        self.commit();self.raw.revision=2;self.raw.capturedAt=10;self.raw.native.serverNow=1010
        request=self.q.Prepare(self.q,self.raw)[0]
        self.assertTrue(self.q.Commit(self.q,self.q.Accept(self.q,self.raw,request,self.f.reply)[0]))
        self.raw.revision=3;self.raw.capturedAt=11;self.raw.native.serverNow=1011
        proof=self.q.Read(self.q,self.raw);self.assertIsNotNone(proof);self.assertEqual(len(proof.rows),1)
    def test_search_read_gap_and_per_target_backoff_are_owned_and_do_not_reset_on_negative(self):
        self.reply.list=self.h.lua.table();self.commit()
        self.assertIsNone(self.q.PrepareSavedSearch(self.q,self.raw,self.target)[0])
        self.raw.revision=2;self.raw.capturedAt=60;self.raw.native.serverNow=1060
        request=self.q.Prepare(self.q,self.raw)[0];self.q.Commit(self.q,self.q.Accept(self.q,self.raw,request,self.f.reply)[0])
        other=lua_table(self.h.lua,{'userId':8,'name':'OtherPlayer'})
        self.assertTrue(self.q.SearchReady(self.q,self.raw,other))
        self.assertFalse(self.q.SearchReady(self.q,self.raw,self.target))
    def test_search_source_loss_or_close_hides_only_searched_rows(self):
        source=self.h.lua.execute("return {search=true,Current=function(self,name) return name~='SearchTarget' or self.search end}")
        self.q=self.h.load('src/tabs/combat/HitListQuery.luau').new(lua_table(self.h.lua,self.h.session),'a'*64,source)
        call=self.q.Prepare(self.q,self.raw)[0];self.q.Commit(self.q,self.q.Accept(self.q,self.raw,call,self.f.reply)[0])
        self.commit();source.search=False
        self.assertEqual(len(self.q.Read(self.q,self.raw).rows),1)
        source.search=True;self.assertIsNone(self.q.PrepareSavedSearch(self.q,self.raw,self.target)[0])
        self.q.Close(self.q);self.assertIsNone(self.q.Read(self.q,self.raw))
    def test_changed_quote_or_family_scope_during_lookup_is_refused(self):
        request=self.prepare();self.raw.native.respect=100
        self.assertIsNone(self.q.AcceptSavedSearch(self.q,self.raw,request,self.reply)[0])
    def test_cursor_visits_unqueried_saved_ids_before_reeligible_earlier_target(self):
        self.commit();self.raw.revision=2;self.raw.capturedAt=1800;self.raw.native.serverNow=2800
        request=self.q.Prepare(self.q,self.raw)[0];self.q.Commit(self.q,self.q.Accept(self.q,self.raw,request,self.f.reply)[0])
        rows=lua_table(self.h.lua,[{'userId':7,'name':'SavedPlayer'},{'userId':8,'name':'OtherPlayer'}])
        self.assertEqual(self.q.PickSavedSearch(self.q,self.raw,rows).userId,8)
    def test_normal_refresh_with_different_current_quote_does_not_reuse_searched_row(self):
        self.commit();self.raw.revision=2;self.raw.capturedAt=1;self.raw.native.serverNow=1001;self.raw.native.respect=2
        request=self.q.Prepare(self.q,self.raw)[0];self.q.Commit(self.q,self.q.Accept(self.q,self.raw,request,self.f.reply)[0])
        self.assertEqual(len(self.q.Read(self.q,self.raw).rows),1)
    def test_war_owner_never_accepts_ordinary_saved_search(self):
        q=self.h.load('src/tabs/combat/HitListQuery.luau').new(lua_table(self.h.lua,self.h.session),'a'*64,None,'war')
        self.assertIsNone(q.PrepareSavedSearch(q,self.raw,self.target)[0])
