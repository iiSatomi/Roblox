"""Recall custody is persisted before emission and never silently reacquired."""
import unittest

from engine_harness import Harness, lua_table


class RecallTransactionTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.h.session["account"] = "123"
        self.module = self.h.load("src/tabs/territory/RecallTransactions.luau")
        self.scope = lua_table(self.h.lua, {**self.h.session, "userId": 123})
        self.store = self.h.lua.execute("""return {strictRecovery = true, data = {}, writes = 0,
            Read = function(self, key) return self.data[key] end,
            Write = function(self, key, value)
                if self.fail then return false end
                self.writes = self.writes + 1; self.data[key] = value; return true
            end}
        """)
        self.before = self.h.snapshot(native={"fullSync": True, "serverNow": 100,
            "family": {"id": "fam-a"}, "crew": [{},
                {"name": "A", "rarity": 1, "healId": "member-a", "duty": "d1",
                 "dutyToken": "deploy-a", "dutyAt": 90},
                {"name": "B", "rarity": 1, "healId": "member-b"}]})
        self.proposal = lua_table(self.h.lua, {**self.h.session, "revision": 1,
            "feature": "station", "actionKey": "recall:d1:member-a:100001", "resources": {},
            "intent": {"kind": "territoryRecall", "requestId": 100001,
                "districtId": "d1", "userId": 123, "memberIndex": 2,
                "deploymentId": "deploy-a", "at": 90, "memberName": "A", "rarity": 1}})

    def owner(self):
        owner, reason = self.module.new(self.store, self.scope,
            lua_table(self.h.lua, {"release": self.h.session["release"], "recallCooldownSeconds": 60}))
        self.assertIsNone(reason)
        return owner

    def test_submission_requires_persisted_preparation_and_sending(self):
        owner = self.owner()
        self.assertIsNone(owner.SubmitCall(owner, self.before, 0)[0])
        self.assertTrue(owner.Prepare(owner, self.proposal, self.before, 0)[0])
        self.assertEqual(self.store.writes, 1)
        self.assertIsNone(owner.SubmitCall(owner, self.before, 0)[0])
        self.assertTrue(owner.MarkSending(owner, self.before, 0)[0])
        self.assertEqual(self.store.writes, 2)
        call, reason = owner.SubmitCall(owner, self.before, 0)
        self.assertIsNone(reason)
        self.assertEqual((call.remote, call.arity, call.args[1], call.args[2]),
                         ("TerritoryAction", 3, "recallcrew", 100001))
        self.assertIsNone(owner.SubmitCall(owner, self.before, 0)[0])

    def test_same_name_and_rarity_are_distinguished_by_stable_member_identity(self):
        self.before.native.crew[3].name = "A"
        owner = self.owner()
        self.assertTrue(owner.Prepare(owner, self.proposal, self.before, 0)[0])

    def test_nonselected_legacy_deployment_uses_its_real_token_without_fabricated_heal_id(self):
        other = self.before.native.crew[3]
        other.healId, other.duty, other.dutyToken, other.dutyAt = None, "d2", "legacy-deployment-b", 80
        owner = self.owner()
        self.assertTrue(owner.Prepare(owner, self.proposal, self.before, 0)[0])
        self.assertEqual(owner.Active(owner).baseline.members["3"].key, "deployment:legacy-deployment-b")
        owner.MarkSending(owner, self.before, 0)
        owner.SubmitCall(owner, self.before, 0)
        owner.AcceptReply(owner, 100001, lua_table(self.h.lua, {"ok": True, "settled": [owner.Active(owner).target]}))
        after = self.h.snapshot(revision=2, native={"fullSync": True, "serverNow": 101,
            "family": {"id": "fam-a"}, "crew": [{},
                {"name": "A", "rarity": 1, "healId": "member-a"},
                {"name": "B", "rarity": 1, "duty": "d2", "dutyToken": "legacy-deployment-b", "dutyAt": 80}]})
        self.assertEqual(owner.Reconcile(owner, after)[0], "observed")

    def test_selected_member_without_return_stable_identity_or_duplicate_deployment_token_blocks(self):
        self.before.native.crew[2].healId = None
        owner = self.owner()
        self.assertFalse(owner.Prepare(owner, self.proposal, self.before, 0)[0])
        self.before.native.crew[2].healId = "member-a"
        other = self.before.native.crew[3]
        other.healId, other.duty, other.dutyToken = None, "d2", "deploy-a"
        self.assertFalse(owner.Prepare(owner, self.proposal, self.before, 0)[0])

    def test_duplicate_stable_member_identity_blocks_preparation(self):
        self.before.native.crew[3].healId = "member-a"
        owner = self.owner()
        self.assertFalse(owner.Prepare(owner, self.proposal, self.before, 0)[0])

    def test_foreign_storage_account_or_numeric_player_cannot_prepare(self):
        owner = self.owner()
        self.proposal.account = "other-account"
        self.assertFalse(owner.Prepare(owner, self.proposal, self.before, 0)[0])
        self.proposal.account = "123"
        self.proposal.intent.userId = 124
        self.assertFalse(owner.Prepare(owner, self.proposal, self.before, 0)[0])
        self.proposal.intent.userId = 123
        self.before.native.userId = 124
        self.assertFalse(owner.Prepare(owner, self.proposal, self.before, 0)[0])

    def test_new_owner_cannot_overwrite_another_prepared_claim(self):
        owner, other = self.owner(), self.owner()
        self.assertTrue(owner.Prepare(owner, self.proposal, self.before, 0)[0])
        self.proposal.intent.requestId = 100002
        self.proposal.actionKey = "recall:foreign-owner"
        self.assertFalse(other.Prepare(other, self.proposal, self.before, 0)[0])
        self.assertEqual(self.owner().Active(self.owner()).requestId, 100001)

    def test_restored_preparation_does_not_silently_rearm_emission(self):
        owner = self.owner()
        self.assertTrue(owner.Prepare(owner, self.proposal, self.before, 0)[0])
        restored = self.owner()
        self.assertFalse(restored.MarkSending(restored, self.before, 0)[0])

    def test_pending_native_reply_persists_without_refunding_or_rearming(self):
        owner = self.owner()
        owner.Prepare(owner, self.proposal, self.before, 0)
        owner.MarkSending(owner, self.before, 0)
        owner.SubmitCall(owner, self.before, 0)
        self.assertTrue(owner.AcceptReply(owner, 100001,
            lua_table(self.h.lua, {"ok": True, "pending": True}))[0])
        restored = self.owner()
        self.assertEqual(restored.Active(restored).stage, "sent")
        self.assertTrue(restored.Active(restored).replyReceived)
        self.assertIsNone(restored.SubmitCall(restored, self.before, 0)[0])

    def test_only_local_proven_unsent_claim_can_clear_a_sent_gate(self):
        owner = self.owner()
        owner.Prepare(owner, self.proposal, self.before, 0)
        owner.MarkSending(owner, self.before, 0)
        restored = self.owner()
        self.assertFalse(restored.CancelUnsent(restored, 100001, self.proposal.actionKey)[0])
        self.assertTrue(owner.CancelUnsent(owner, 100001, self.proposal.actionKey)[0])
        self.assertEqual(self.owner().Receipt(self.owner()).outcome, "known_unsent")

    def test_recovered_preparation_can_close_without_rearming(self):
        owner = self.owner()
        owner.Prepare(owner, self.proposal, self.before, 0)
        restored = self.owner()
        self.assertTrue(restored.RecoverPrepared(restored)[0])
        self.assertEqual(self.owner().Receipt(self.owner()).outcome, "known_unsent")

    def test_confirmed_cleanup_keeps_exact_receipt_across_checkpoint_cleanup_window(self):
        owner = self.owner()
        owner.Prepare(owner, self.proposal, self.before, 0)
        owner.MarkSending(owner, self.before, 0)
        owner.SubmitCall(owner, self.before, 0)
        target = owner.Active(owner).target
        self.assertTrue(owner.AcceptReply(owner, 100001,
            lua_table(self.h.lua, {"ok": True, "settled": [target]}))[0])
        after = self.h.snapshot(revision=2, native={"fullSync": True, "serverNow": 101,
            "family": {"id": "fam-a"}, "crew": [{},
                {"name": "A", "rarity": 1, "healId": "member-a"},
                {"name": "B", "rarity": 1, "healId": "member-b"}]})
        self.assertEqual(owner.Reconcile(owner, after)[0], "observed")
        self.assertTrue(owner.ClearObserved(owner)[0])
        restored = self.owner()
        self.assertIsNone(restored.Active(restored))
        receipt = restored.Receipt(restored)
        self.assertEqual((receipt.outcome, receipt.record.requestId, receipt.record.target.deploymentId),
                         ("confirmed", 100001, "deploy-a"))

    def test_home_duty_without_cleared_native_pending_flags_cannot_confirm(self):
        owner = self.owner()
        owner.Prepare(owner, self.proposal, self.before, 0)
        owner.MarkSending(owner, self.before, 0)
        owner.SubmitCall(owner, self.before, 0)
        target = owner.Active(owner).target
        owner.AcceptReply(owner, 100001, lua_table(self.h.lua, {"ok": True, "settled": [target]}))
        after = self.h.snapshot(revision=2, native={"fullSync": True, "serverNow": 101,
            "family": {"id": "fam-a"}, "crew": [{},
                {"name": "A", "rarity": 1, "healId": "member-a", "recalling": True},
                {"name": "B", "rarity": 1, "healId": "member-b"}]})
        self.assertEqual(owner.Reconcile(owner, after)[0], "uncertain")
        after.native.crew[2].recalling = None
        after.native.crew[2].stationed = True
        self.assertEqual(owner.Reconcile(owner, after)[0], "uncertain")


if __name__ == "__main__":
    unittest.main()
