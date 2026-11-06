"""Durable, bounded fight history and interrupted generic-checkpoint cleanup."""
import unittest
import test_player_fight_evidence as fixture
from engine_harness import lua_table

class PlayerFightLedgerTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.PlayerFightEvidenceTests();self.f.setUp();self.h=self.f.h
        self.storage=self.h.lua.execute("""return {strictRecovery=true,data={},Read=function(self,k) return self.data[k] end,
            Write=function(self,k,v) if self.fail then return false end;self.data[k]=v;return true end}""")
        self.module=self.h.load('src/tabs/combat/PlayerFightLedger.luau');self.owner=self.new()
    def new(self):
        owner,why=self.module.new(self.storage,lua_table(self.h.lua,self.h.session),self.f.e)
        self.assertIsNotNone(owner,why);return owner
    def record(self,owner=None):
        owner=owner or self.owner;return owner.Record(owner,self.f.data(),self.f.after)
    def test_exact_settlement_saved_once_and_exposes_detached_target_history(self):
        self.assertTrue(self.record()[0]);self.assertTrue(self.record()[0])
        summary=self.owner.Summary(self.owner);self.assertEqual((summary.fights,summary.wins,summary.cash,summary.stamina),(1,1,36274716,1))
        rows=self.owner.History(self.owner,'combat',42,self.f.now+1)
        self.assertEqual((len(rows),rows[1].cash,rows[1].won),(1,36274716,True))
        self.assertEqual(len(self.owner.History(self.owner,'warCombat',42,self.f.now+1)),0)
        rows[1].cash=0;self.assertEqual(self.owner.Summary(self.owner).cash,36274716)
    def test_saved_lookup_candidates_are_detached_owned_recent_ordinary_identities(self):
        self.assertTrue(self.record()[0]);targets=self.owner.SavedTargets(self.owner,self.f.before)
        self.assertEqual((targets[1].userId,targets[1].name),(42,'Target B'))
        self.assertEqual(targets[1].history[1].cash,36274716)
        targets[1].name='forged';targets[1].history[1].cash=0
        again=self.owner.SavedTargets(self.owner,self.f.before)
        self.assertEqual((again[1].name,again[1].history[1].cash),('Target B',36274716))
        self.f.before.account='other';self.assertIsNone(self.owner.SavedTargets(self.owner,self.f.before))
    def test_saved_lookup_excludes_future_and_expired_fights_and_refuses_closed_ledger(self):
        self.assertTrue(self.record()[0]);raw=self.f.before;raw.native.serverNow=self.f.now-1
        self.assertEqual(len(self.owner.SavedTargets(self.owner,raw)),0)
        raw.native.serverNow=self.f.now+31*86400
        self.assertEqual(len(self.owner.SavedTargets(self.owner,raw)),0)
        self.owner.Close(self.owner);self.assertIsNone(self.owner.SavedTargets(self.owner,raw))
    def test_reloaded_ledger_recovers_exact_saved_result_without_replay_or_notification(self):
        self.record();owner=self.new();after=self.f.after;after.session='fresh-session';after.playerFightProof=None
        after.playerFightHistoryProof=owner.Proof(owner,after)
        self.assertEqual(self.f.e.recoverSaved(self.f.data(),after),'confirmed')
        self.assertTrue(owner.Record(owner,self.f.data(),after)[0]);self.assertEqual(owner.Summary(owner).fights,1)
    def test_different_initial_reply_or_request_cannot_borrow_old_settlement(self):
        self.record();after=self.f.after;after.playerFightProof=None
        after.playerFightHistoryProof=self.owner.Proof(self.owner,after)
        self.f.initial['cashEstimate']=0;self.assertIsNone(self.f.e.recoverSaved(self.f.data(),after))
        self.f.initial['cashEstimate']=self.owner.Summary(self.owner).recent[1].initial.cashEstimate
        self.f.p.requestId=2;self.assertIsNone(self.f.e.recoverSaved(self.f.data(),after))
    def test_only_settled_proof_counts_and_failed_write_does_not_claim_success(self):
        self.f.after.playerFightProof.attempts[1].status='ambiguous';self.assertFalse(self.record()[0])
        self.f.after.playerFightProof.attempts[1].status='settled';self.storage.fail=True
        self.assertFalse(self.record()[0]);self.assertEqual(self.owner.Summary(self.owner).fights,0)
        self.storage.fail=False;self.assertEqual(self.new().Summary(self.new()).fights,0)
    def test_ambiguous_successful_write_reloads_once_and_old_owner_stays_faulted(self):
        self.storage.Write=self.h.lua.eval('function(self,k,v) self.data[k]=v;return false end')
        self.assertFalse(self.record()[0]);self.assertFalse(self.record()[0])
        self.storage.Write=self.h.lua.eval('function(self,k,v) self.data[k]=v;return true end')
        reloaded=self.new();self.assertEqual(reloaded.Summary(reloaded).fights,1)
        self.assertTrue(reloaded.Record(reloaded,self.f.data(),self.f.after)[0])
    def test_stale_owner_cannot_overwrite_newer_history(self):
        old=self.new();self.record();self.assertFalse(self.record(old)[0]);self.assertEqual(self.new().Summary(self.new()).fights,1)
    def test_closed_owner_cannot_write_or_export_current_proof(self):
        self.owner.Close(self.owner);self.assertFalse(self.record()[0]);self.assertIsNone(self.owner.Proof(self.owner,self.f.after))
    def test_changed_storage_totals_or_sparse_history_fail_closed(self):
        self.record();key=self.owner.key;raw=self.storage.data[key];raw.fights=2
        self.assertIsNone(self.module.new(self.storage,lua_table(self.h.lua,self.h.session),self.f.e)[0])
    def test_recent_window_bounded_but_totals_survive_compaction(self):
        for n in range(1,36):
            self.f.p.requestId=n;self.f.p.actionKey=f'combat:42:{n}'
            self.f.initial['fightId']=self.f.final['fightId']=f'fixture-fight-{n}'
            attempt=self.f.after.playerFightProof.attempts[1];attempt.actionKey=self.f.p.actionKey
            attempt.initial=lua_table(self.h.lua,self.f.initial);attempt.receipt=lua_table(self.h.lua,self.f.final)
            self.assertTrue(self.record()[0])
        summary=self.owner.Summary(self.owner);self.assertEqual((summary.fights,len(summary.recent)),(35,32))
        self.assertEqual(summary.recent[1].requestId,4);self.assertEqual(self.new().Summary(self.new()).cash,35*36274716)
    def test_same_fight_cannot_count_again_under_new_request(self):
        self.record();self.f.p.requestId=2
        self.assertFalse(self.record()[0]);self.assertEqual(self.owner.Summary(self.owner).fights,1)
    def test_scope_and_future_or_aged_history_never_become_usable_samples(self):
        self.record();after=self.f.after;after.account='other';self.assertIsNone(self.owner.Proof(self.owner,after))
        self.assertEqual(len(self.owner.History(self.owner,'combat',42,self.f.now-1)),0)
        self.assertEqual(len(self.owner.History(self.owner,'combat',42,self.f.now+31*86400)),0)
    def test_invalid_native_payload_fields_and_no_numbered_request_cannot_persist(self):
        self.f.p.requestId=None;self.assertFalse(self.record()[0]);self.assertEqual(len(self.storage.data),0)

    def test_fractional_replication_time_persists_and_history_accepts_fractional_now(self):
        self.f.before.native.serverNow+=.25;self.f.p.intent.serverNow=self.f.before.native.serverNow
        self.f.baseline=self.f.e.capture(self.f.p,self.f.before)[0]
        self.assertTrue(self.record()[0]);owner=self.new()
        self.assertEqual(len(owner.History(owner,'combat',42,self.f.now+1.5)),1)
