"""Durable exact claims precede native act and survive ambiguity without replay."""
import unittest

from engine_harness import Harness, lua_table


class HeistTransactionTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.module = self.h.load("src/tabs/heists/HeistTransactions.luau")
        self.pending = self.h.load("src/storage/PendingAction.luau")
        self.plan = self.h.load("src/tabs/heists/HeistCallPlan.luau")
        self.evidence = self.h.load("src/features/HeistStartEvidence.luau")
        self.readers = self.h.lua.table(heists=self.evidence)
        self.store = self.h.lua.execute("""return {data = {}, strictRecovery = true, fail = false,
            Read = function(self,key) return self.data[key] end,
            Write = function(self,key,value)
                if self.fail then return false end
                self.data[key] = value
                return true
            end} """)
        self.before = self.h.snapshot(native={"fullSync": True, "serverNow": 1987300,
            "level": 20, "cash": 100, "pools": {"energy": 10}},
            catalogKey="a" * 64, heistCatalog=[{"id": "h_a", "level": 10,
                "stake": 10, "energy": 2, "crateCount": 1}],
            heistBoardProof={"account": "user-a", "capturedAt": 0,
                "board": {"ok": True, "rows": [], "startsLeft": 2,
                          "bustWait": 0, "serverNow": 1987300}})
        self.proposal = self.h.proposal(feature="heists", key="heists:23:h_a")
        self.proposal.intent = lua_table(self.h.lua, {"kind": "heistStart", "heistId": "h_a",
            "expectedStake": 10, "expectedEnergy": 2, "startsBefore": 2,
            "serverDay": 23, "catalogKey": "a" * 64, "needsSequence": True})
        self.proposal.resources = lua_table(self.h.lua, {"cash": 10, "energy": 2})
        self.baseline = self.evidence.capture(self.proposal, self.before)[0]
        self.assertIsNotNone(self.baseline)
        self.native = lua_table(self.h.lua, {"sequence": 7, "controllersClear": True})
        self.owner = self.new_owner()

    def new_owner(self):
        owner, why = self.module.new(self.store, lua_table(self.h.lua, self.h.session),
                                    self.pending, self.plan, self.readers)
        self.assertIsNone(why)
        return owner

    def prepare(self):
        self.assertTrue(self.owner.Prepare(self.owner, self.proposal, self.before,
                                          self.baseline, self.native, 0)[0])

    def test_claim_is_persisted_before_authorization_and_keeps_native_sequence(self):
        self.prepare()
        active = self.owner.Active(self.owner)
        self.assertEqual((active.sequence, active.actionName, active.arg1), (8, "start", "h_a"))
        self.assertFalse(active.sent)
        call, reason = self.owner.MarkSending(self.owner, self.proposal, self.native, 0)
        self.assertIsNone(reason)
        self.assertEqual(call.nativeSequence, 8)
        self.assertTrue(self.owner.Active(self.owner).sent)
        restored = self.new_owner()
        self.assertEqual(restored.Active(restored).sequence, 8)
        self.assertIsNone(restored.MarkSending(restored, self.proposal, self.native, 0)[0])

    def test_failed_write_or_changed_native_counter_cannot_authorize(self):
        self.store.fail = True
        self.assertFalse(self.owner.Prepare(self.owner, self.proposal, self.before,
                                           self.baseline, self.native, 0)[0])
        self.setUp()
        self.prepare()
        self.native.sequence = 8
        self.assertIsNone(self.owner.MarkSending(self.owner, self.proposal, self.native, 0)[0])

    def test_uncertain_timeout_retains_claim_and_status_record_never_replays(self):
        self.prepare()
        self.owner.MarkSending(self.owner, self.proposal, self.native, 0)
        self.assertFalse(self.owner.Resolve(self.owner, self.proposal.actionKey, 8,
                                           "skipped_unconfirmed", self.before)[0])
        record = self.owner.RecoveryRecord(self.owner)
        self.assertTrue(record.sent)
        recovery = self.h.load("src/tabs/heists/SequenceRecovery.luau")
        call = recovery.statusCall(record, lua_table(self.h.lua, self.h.session))[0]
        self.assertEqual([call.args[i] for i in (1, 2, 3)], ["status", "h_a", 8])
        restored = self.new_owner()
        self.assertFalse(restored.CancelUnsent(restored, self.proposal.actionKey, 8)[0])

    def test_restored_prepared_claim_is_known_unsent_and_fences_old_authorizer(self):
        self.prepare()
        restored = self.new_owner()
        self.assertTrue(restored.RecoverPrepared(restored)[0])
        self.assertIsNone(restored.Active(restored))
        self.assertEqual(restored.Receipt(restored).outcome, "known_unsent")
        self.assertIsNone(self.owner.MarkSending(self.owner, self.proposal, self.native, 0)[0])

    def test_exact_success_settles_and_keeps_receipt_for_checkpoint_cleanup(self):
        self.prepare()
        self.owner.MarkSending(self.owner, self.proposal, self.native, 0)
        reply = lua_table(self.h.lua, {"ok": True, "runId": "run-a"})
        self.assertTrue(self.owner.AcceptReply(self.owner, self.proposal.actionKey, 8, reply)[0])
        self.before.revision = 2
        board = self.before.heistBoardProof.board
        board.startsLeft = 1
        board.mine = lua_table(self.h.lua, {"id": "run-a", "heistId": "h_a", "endsAt": 1987400})
        self.assertTrue(self.owner.Resolve(self.owner, self.proposal.actionKey, 8,
                                          "confirmed", self.before)[0])
        self.assertIsNone(self.owner.Active(self.owner))
        self.assertEqual(self.owner.Receipt(self.owner).outcome, "confirmed")

    def test_other_writer_and_mismatched_sequence_cannot_claim_or_record_a_reply(self):
        other = self.new_owner()
        self.prepare()
        self.assertFalse(other.Prepare(other, self.proposal, self.before,
                                       self.baseline, self.native, 0)[0])
        self.owner.MarkSending(self.owner, self.proposal, self.native, 0)
        self.assertFalse(self.owner.AcceptReply(self.owner, self.proposal.actionKey, 9,
                                               lua_table(self.h.lua, {"ok": True}))[0])

    def test_transient_negative_reply_keeps_status_recovery_open(self):
        self.prepare()
        self.owner.MarkSending(self.owner, self.proposal, self.native, 0)
        for code in ("busy", "presence", "rate_limited", "no_pending"):
            with self.subTest(code=code):
                self.assertFalse(self.owner.AcceptReply(self.owner, self.proposal.actionKey, 8,
                    lua_table(self.h.lua, {"ok": False, "code": code}))[0])
                self.assertIsNone(self.owner.Active(self.owner).recovery.reply)


if __name__ == "__main__":
    unittest.main()
