"""One-period Market rental recovery never replays an uncertain send."""
import unittest

from engine_harness import Harness, lua_table


class MarketTransactionsTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.module = self.h.load(
            "src/tabs/blackMarket/MarketTransactions.luau")
        self.storage = self.h.lua.execute("""return {
            strictRecovery = true, data = {}, fail = false,
            Read = function(self, key) return self.data[key] end,
            Write = function(self, key, value)
                if self.fail then error('disk unavailable') end
                self.data[key] = value
                return true
            end,
        }""")
        self.scope = lua_table(self.h.lua, self.h.session)
        self.tx, reason = self.module.new(self.storage, self.scope)
        self.assertIsNone(reason)
        self.list_evidence = self.h.load(
            "src/tabs/blackMarket/MarketListEvidence.luau")

    def raw(self, revision=1, loose=8, bound=2,
            until=900, now=1000):
        return self.h.snapshot(revision=revision, native={
            "fullSync": True, "serverNow": now,
            "market": {"shopUntil": until},
            "inventory": {"gold_bar": loose},
            "inventoryBound": {"gold_bar": bound}})

    def proposal(self):
        return lua_table(self.h.lua, {**self.h.session,
            "revision": 1, "feature": "marketRent",
            "intent": {"kind": "marketRent", "periods": 1,
                "cost": 1, "durationSeconds": 43200}})

    def test_restart_reconciles_only_exact_newer_rental(self):
        prepared, reason = self.tx.PrepareRent(
            self.tx, self.proposal(), self.raw())
        self.assertTrue(prepared, reason)
        self.assertEqual(self.tx.Active(self.tx).stage, "prepared")
        self.assertTrue(self.tx.MarkSending(self.tx)[0])
        restarted, reason = self.module.new(self.storage, self.scope)
        self.assertIsNone(reason)
        self.assertEqual(restarted.Active(restarted).stage, "sent")
        self.assertFalse(restarted.PrepareRent(
            restarted, self.proposal(), self.raw())[0])
        self.assertEqual(restarted.Reconcile(restarted,
            self.raw(revision=2, loose=8))[0], "uncertain")
        self.assertEqual(restarted.Active(restarted).stage, "sent")
        self.assertEqual(restarted.Reconcile(restarted,
            self.raw(revision=2, loose=7,
                until=44200, now=1002))[0], "observed")
        self.assertTrue(restarted.ClearObserved(restarted)[0])
        cleared, reason = self.module.new(self.storage, self.scope)
        self.assertIsNone(reason)
        self.assertIsNone(cleared.Active(cleared))

    def test_unchanged_revision_and_wrong_account_do_not_resolve(self):
        self.tx.PrepareRent(self.tx, self.proposal(), self.raw())
        self.tx.MarkSending(self.tx)
        self.assertEqual(self.tx.Reconcile(self.tx, self.raw())[0], "waiting")
        wrong = self.raw(revision=2, loose=7, until=44200)
        wrong.account = "other-account"
        self.assertEqual(self.tx.Reconcile(self.tx, wrong)[0], "waiting")
        self.assertFalse(self.tx.ClearObserved(self.tx)[0])

    def test_persistence_failure_prevents_send_transition(self):
        self.tx.PrepareRent(self.tx, self.proposal(), self.raw())
        self.storage.fail = True
        sent, reason = self.tx.MarkSending(self.tx)
        self.assertFalse(sent)
        self.assertIn("persistence", reason)
        self.assertEqual(self.tx.Active(self.tx).stage, "prepared")

    def test_invalid_rental_snapshot_is_refused_without_throwing(self):
        for before in (None, False, self.h.lua.table()):
            self.assertFalse(self.tx.PrepareRent(self.tx, self.proposal(), before)[0])

    def test_corrupt_saved_record_blocks_restart(self):
        self.tx.PrepareRent(self.tx, self.proposal(), self.raw())
        key = self.tx.key
        self.storage.data[key].transaction.cost = -1
        restarted, reason = self.module.new(self.storage, self.scope)
        self.assertIsNone(restarted)
        self.assertIn("Corrupt", reason)

    def list_raw(self, revision=1, loose=5, bound=1,
                 listings=None, now=1000):
        raw = self.h.snapshot(revision=revision, native={
            "fullSync": True, "serverNow": now,
            "market": {"shopUntil": 2000,
                "listings": listings if listings is not None else {}},
            "inventory": {"w_baton": loose},
            "inventoryBound": {"w_baton": bound}})
        return raw

    def list_proposal(self):
        return lua_table(self.h.lua, {**self.h.session,
            "revision": 1, "feature": "marketSell",
            "preflightOnly": True,
            "intent": {"kind": "marketList",
                "itemId": "w_baton", "quantity": 2,
                "ask": 9}})

    def listing(self, qty=2, price=9):
        return {"state": "live", "itemOrigin": {
            "total": qty, "free": 0}, "item": "w_baton",
            "indexed": 3, "price": price,
            "qty": qty, "left": qty,
            "createdAt": 1001}

    def test_failed_listing_stage_save_does_not_authorize_or_change_local_allowance(self):
        tx, _ = self.module.new(self.storage, self.scope, self.list_evidence)
        tx.PrepareOwnedList(tx, self.list_proposal(), self.list_raw())
        self.storage.fail = True
        self.assertFalse(tx.MarkSending(tx, 2)[0])
        self.assertEqual(tx.Active(tx).stage, "prepared")
        self.assertEqual(tx.ListingAttempts(tx)[0], 0)
        self.storage.fail = False
        self.assertTrue(tx.MarkSending(tx, 2)[0])
        self.assertEqual(tx.ListingAttempts(tx)[0], 1)

    def test_legacy_listing_envelope_never_invents_an_unused_allowance(self):
        tx, _ = self.module.new(self.storage, self.scope, self.list_evidence)
        tx.PrepareOwnedList(tx, self.list_proposal(), self.list_raw())
        self.storage.data[tx.key].listingAttempts = None
        restored, reason = self.module.new(self.storage, self.scope, self.list_evidence)
        self.assertIsNone(reason)
        self.assertIsNotNone(restored.Active(restored))
        self.assertIsNone(restored.ListingAttempts(restored)[0])
        self.assertFalse(restored.MarkSending(restored, 2)[0])

    def test_runtime_listing_corrupt_binding_or_counter_refuses_reload(self):
        for field, bad in (("sourceKey", False), ("preparedGeneration", 0), ("actionKey", "")):
            self.setUp()
            tx, _ = self.module.new(self.storage, self.scope, self.list_evidence)
            proposal = self.list_proposal()
            proposal.actionKey = "marketSell:list:one"
            proposal.intent.sourceKey = "a" * 64
            proposal.resources = lua_table(self.h.lua, {"w_baton": 2})
            self.assertTrue(tx.PrepareRuntimeOwnedList(tx, proposal, self.list_raw(), 1)[0])
            self.storage.data[tx.key].transaction[field] = bad
            self.assertIsNone(self.module.new(self.storage, self.scope, self.list_evidence)[0])
        self.setUp()
        self.tx.PrepareRent(self.tx, self.proposal(), self.raw())
        self.storage.data[self.tx.key].transaction = False
        self.assertIsNone(self.module.new(self.storage, self.scope)[0])

    def test_exact_rejected_runtime_listing_can_be_reviewed_without_refunding_attempt(self):
        tx, _ = self.module.new(self.storage, self.scope, self.list_evidence)
        proposal = self.list_proposal()
        proposal.actionKey = "marketSell:list:rejected"
        proposal.intent.sourceKey = "a" * 64
        proposal.resources = lua_table(self.h.lua, {"w_baton": 2})
        tx.PrepareRuntimeOwnedList(tx, proposal, self.list_raw(), 2)
        generation = tx.generation
        tx.AuthorizeRuntimeOwnedList(tx, proposal.actionKey, generation, 2, "a" * 64)
        tx.RecordRuntimeReturn(tx, proposal.actionKey, generation, lua_table(self.h.lua, {"ok": False}))
        changed = self.list_raw(revision=2, loose=4, now=1002)
        self.assertIsNone(tx.RejectedRuntimeReview(tx, changed)[0])
        unchanged = self.list_raw(revision=2, now=1002)
        review, reason = tx.RejectedRuntimeReview(tx, unchanged)
        self.assertIsNone(reason)
        review.generation += 1
        self.assertFalse(tx.ReleaseRejectedRuntimeList(tx, review, unchanged)[0])
        review, _ = tx.RejectedRuntimeReview(tx, unchanged)
        self.assertTrue(tx.ReleaseRejectedRuntimeList(tx, review, unchanged)[0])
        self.assertIsNone(tx.Active(tx))
        self.assertEqual(tx.ListingAttempts(tx)[0], 1)
        self.assertFalse(tx.ReleaseRejectedRuntimeList(tx, review, unchanged)[0])

    def test_closed_callback_can_append_only_exact_runtime_unsent_fact(self):
        tx, _ = self.module.new(self.storage, self.scope, self.list_evidence)
        proposal = self.list_proposal()
        proposal.actionKey = "marketSell:list:unsent"
        proposal.intent.sourceKey = "a" * 64
        proposal.resources = lua_table(self.h.lua, {"w_baton": 2})
        tx.PrepareRuntimeOwnedList(tx, proposal, self.list_raw(), 2)
        generation = tx.generation
        tx.AuthorizeRuntimeOwnedList(tx, proposal.actionKey, generation, 2, "a" * 64)
        tx.Close(tx)
        current, _ = self.module.new(self.storage, self.scope, self.list_evidence)
        self.assertIsNone(current.RuntimeUnsentReview(current)[0])
        before_generation = current.generation
        self.assertTrue(tx.RecordRuntimeUnsent(tx, proposal.actionKey, generation)[0])
        self.assertEqual(current.generation, before_generation)
        review, reason = current.RuntimeUnsentReview(current)
        self.assertIsNone(reason)
        review.generation += 1
        self.assertFalse(current.ReleaseRuntimeUnsent(current, review)[0])
        review, _ = current.RuntimeUnsentReview(current)
        self.assertTrue(current.ReleaseRuntimeUnsent(current, review)[0])
        self.assertEqual(current.ListingAttempts(current)[0], 0)
        self.assertIsNone(current.Active(current))
        self.assertFalse(current.ReleaseRuntimeUnsent(current, review)[0])
        self.assertFalse(tx.RecordRuntimeUnsent(tx, proposal.actionKey, generation)[0])

    def test_runtime_listing_store_exposes_exact_continuation_identity(self):
        tx, _ = self.module.new(self.storage, self.scope, self.list_evidence)
        proposal = self.list_proposal()
        proposal.actionKey = "marketSell:list:continuation"
        proposal.intent.sourceKey = "a" * 64
        proposal.resources = lua_table(self.h.lua, {"w_baton": 2})
        self.assertTrue(tx.PrepareRuntimeOwnedList(tx, proposal, self.list_raw(), 2)[0])
        claims, reason = tx.ReservationClaims(tx)
        self.assertIsNone(reason)
        self.assertEqual(claims.actionKey, proposal.actionKey)

    def test_runtime_listing_authorization_is_exact_and_one_use(self):
        tx, _ = self.module.new(self.storage, self.scope, self.list_evidence)
        proposal = self.list_proposal()
        proposal.preflightOnly = None
        proposal.actionKey = "marketSell:list:one"
        proposal.intent.sourceKey = "a" * 64
        proposal.resources = lua_table(self.h.lua, {"w_baton": 2})
        self.assertTrue(tx.PrepareRuntimeOwnedList(tx, proposal, self.list_raw(), 1)[0])
        record = tx.Active(tx)
        self.assertEqual(record.actionKey, proposal.actionKey)
        self.assertEqual(tx.ListingAttempts(tx)[0], 0)
        generation = tx.generation
        self.assertFalse(tx.AuthorizeRuntimeOwnedList(tx, "other", generation, 1, "a" * 64)[0])
        self.assertFalse(tx.AuthorizeRuntimeOwnedList(tx, proposal.actionKey, generation + 1, 1, "a" * 64)[0])
        self.assertFalse(tx.AuthorizeRuntimeOwnedList(tx, proposal.actionKey, generation, 1, "b" * 64)[0])
        self.assertEqual(tx.ListingAttempts(tx)[0], 0)
        self.assertFalse(tx.AuthorizeRuntimeOwnedList(tx, proposal.actionKey, generation, None, "a" * 64)[0])
        self.assertTrue(tx.AuthorizeRuntimeOwnedList(tx, proposal.actionKey, generation, 1, "a" * 64)[0])
        self.assertFalse(tx.AuthorizeRuntimeOwnedList(tx, proposal.actionKey, generation, 1, "a" * 64)[0])
        restored, _ = self.module.new(self.storage, self.scope, self.list_evidence)
        self.assertEqual(restored.ListingAttempts(restored)[0], 1)
        self.assertEqual(restored.Active(restored).actionKey, proposal.actionKey)
        after = self.list_raw(revision=2, loose=3, listings={"L1": self.listing()}, now=1002)
        self.assertEqual(restored.Reconcile(restored, after)[0], "uncertain")
        reply = lua_table(self.h.lua, {"ok": True})
        self.assertFalse(restored.RecordRuntimeReturn(restored, None, None, reply)[0])
        self.assertFalse(restored.RecordRuntimeReturn(restored, proposal.actionKey, generation + 1, reply)[0])
        self.assertTrue(restored.RecordRuntimeReturn(restored, proposal.actionKey, generation, reply)[0])
        loaded, _ = self.module.new(self.storage, self.scope, self.list_evidence)
        self.assertEqual(loaded.Reconcile(loaded, after)[0], "observed")


    def test_listing_attempt_cap_survives_observation_cleanup_and_restart(self):
        tx, _ = self.module.new(self.storage, self.scope, self.list_evidence)
        self.assertTrue(tx.PrepareOwnedList(tx, self.list_proposal(), self.list_raw())[0])
        self.assertTrue(tx.MarkSending(tx, 1)[0])
        self.assertEqual(tx.ListingAttempts(tx)[0], 1)
        after = self.list_raw(revision=2, loose=3, listings={"L1": self.listing()}, now=1002)
        self.assertEqual(tx.Reconcile(tx, after)[0], "observed")
        self.assertTrue(tx.ClearObserved(tx)[0])
        restored, _ = self.module.new(self.storage, self.scope, self.list_evidence)
        self.assertEqual(restored.ListingAttempts(restored)[0], 1)
        self.assertTrue(restored.PrepareOwnedList(restored, self.list_proposal(), self.list_raw())[0])
        self.assertFalse(restored.MarkSending(restored, 1)[0])
        self.assertEqual(restored.Active(restored).stage, "prepared")
        self.assertFalse(restored.MarkSending(restored, 0)[0])
        self.assertEqual(restored.ListingAttempts(restored)[0], 1)

    def test_owned_listing_survives_restart_and_requires_exact_custody(self):
        tx, reason = self.module.new(self.storage,
            self.scope, self.list_evidence)
        self.assertIsNone(reason)
        self.assertTrue(tx.PrepareOwnedList(tx,
            self.list_proposal(), self.list_raw())[0])
        self.assertTrue(tx.MarkSending(tx)[0])
        restarted, reason = self.module.new(self.storage,
            self.scope, self.list_evidence)
        self.assertIsNone(reason)
        self.assertFalse(restarted.PrepareOwnedList(restarted,
            self.list_proposal(), self.list_raw())[0])
        changed = self.list_raw(revision=2, loose=3,
            listings={"L1": self.listing(price=10)}, now=1002)
        self.assertEqual(restarted.Reconcile(restarted, changed)[0],
                         "uncertain")
        exact = self.list_raw(revision=2, loose=3,
            listings={"L1": self.listing()}, now=1002)
        self.assertEqual(restarted.Reconcile(restarted, exact)[0],
                         "observed")
        self.assertTrue(restarted.ClearObserved(restarted)[0])

    def test_new_session_can_reconcile_lower_local_revision(self):
        tx = self.module.new(self.storage,
            self.scope, self.list_evidence)[0]
        tx.PrepareOwnedList(tx, self.list_proposal(), self.list_raw(
            revision=1))
        tx.MarkSending(tx)
        after = self.list_raw(revision=1, loose=3,
            listings={"L1": self.listing()}, now=1002)
        after.session = "new-session"
        self.assertEqual(tx.Reconcile(tx, after)[0], "observed")

    def test_new_session_rental_uses_server_time_not_local_revision(self):
        self.tx.PrepareRent(self.tx, self.proposal(), self.raw())
        self.tx.MarkSending(self.tx)
        after = self.raw(revision=1, loose=7,
            until=44200, now=1002)
        after.session = "new-session"
        self.assertEqual(self.tx.Reconcile(self.tx, after)[0],
                         "observed")


    def test_stale_loaded_owner_cannot_overwrite_newer_preparation(self):
        stale,reason = self.module.new(self.storage,self.scope)
        self.assertIsNone(reason)
        self.assertTrue(self.tx.PrepareRent(self.tx,self.proposal(),self.raw())[0])
        self.assertFalse(stale.PrepareRent(stale,self.proposal(),self.raw())[0])
        current,_ = self.module.new(self.storage,self.scope)
        self.assertEqual(current.Active(current).stage,'prepared')

    def test_yielding_write_fences_reload_and_unloaded_owner_cannot_advance(self):
        self.storage.Write = self.h.lua.eval('''function(self,key,value)
            self.data[key]=value; if not self.yielded then self.yielded=true; coroutine.yield('saving') end; return true end''')
        self.h.lua.globals().marketRaceTx,self.h.lua.globals().marketRaceP,self.h.lua.globals().marketRaceBefore = self.tx,self.proposal(),self.raw()
        self.h.lua.execute('marketRaceThread=coroutine.create(function() return marketRaceTx:PrepareRent(marketRaceP,marketRaceBefore) end)')
        resume = self.h.lua.eval('function() return coroutine.resume(marketRaceThread) end')
        self.assertEqual(resume(),(True,'saving'))
        self.assertIsNone(self.module.new(self.storage,self.scope)[0])
        self.tx.Close(self.tx)
        result = resume()
        self.assertTrue(result[0])
        self.assertFalse(result[1])
        current,reason = self.module.new(self.storage,self.scope)
        self.assertIsNone(reason)
        self.assertEqual(current.Active(current).stage,'prepared')
        self.assertFalse(self.tx.MarkSending(self.tx)[0])

    def test_ambiguous_persisted_failure_cannot_be_overwritten_by_old_memory(self):
        self.storage.Write = self.h.lua.eval('function(self,key,value) self.data[key]=value; return false end')
        self.assertFalse(self.tx.PrepareRent(self.tx,self.proposal(),self.raw())[0])
        self.storage.Write = self.h.lua.eval('function(self,key,value) self.data[key]=value; return true end')
        self.assertFalse(self.tx.PrepareRent(self.tx,self.proposal(),self.raw())[0])
        current,reason = self.module.new(self.storage,self.scope)
        self.assertIsNone(reason)
        self.assertEqual(current.Active(current).stage,'prepared')


    def test_exact_prepared_review_releases_only_unsent_current_generation(self):
        self.assertTrue(self.tx.PrepareRent(self.tx,self.proposal(),self.raw())[0])
        review,why = self.tx.PreparedReview(self.tx)
        self.assertIsNone(why)
        review.transaction.cost = 2
        self.assertFalse(self.tx.DiscardPrepared(self.tx,review)[0])
        review,_ = self.tx.PreparedReview(self.tx)
        self.assertTrue(self.tx.DiscardPrepared(self.tx,review)[0])
        self.assertIsNone(self.tx.Active(self.tx))
        self.assertTrue(self.tx.PrepareRent(self.tx,self.proposal(),self.raw())[0])
        self.assertFalse(self.tx.DiscardPrepared(self.tx,review)[0])
        sent_review,_ = self.tx.PreparedReview(self.tx)
        self.assertTrue(self.tx.MarkSending(self.tx)[0])
        self.assertIsNone(self.tx.PreparedReview(self.tx)[0])
        self.assertFalse(self.tx.DiscardPrepared(self.tx,sent_review)[0])

    def test_legacy_generation_is_adopted_without_clearing_existing_custody(self):
        self.assertTrue(self.tx.PrepareRent(self.tx,self.proposal(),self.raw())[0])
        self.storage.data[self.tx.key].generation = None
        restored,why = self.module.new(self.storage,self.scope)
        self.assertIsNone(why)
        self.assertEqual(restored.Active(restored).stage,'prepared')
        self.assertTrue(restored.MarkSending(restored)[0])
        self.assertEqual(self.storage.data[restored.key].generation,1)

    def test_legacy_rental_does_not_release_hold_for_loose_expiry_tolerance(self):
        self.tx.PrepareRent(self.tx,self.proposal(),self.raw())
        self.tx.MarkSending(self.tx)
        self.assertEqual(self.tx.Reconcile(self.tx,self.raw(revision=2,loose=7,until=44320,now=1002))[0],'uncertain')


if __name__ == "__main__":
    unittest.main()
