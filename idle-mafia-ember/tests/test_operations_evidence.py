"""An Operation start reply is not an outcome without matching active-run state."""
import unittest

from engine_harness import Harness, lua_table


class OperationsEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.evidence = self.h.load("src/features/OperationsEvidence.luau")
        self.proposal = self.h.proposal("operations", "operations:op_truck:1")
        self.proposal["intent"]["kind"] = "operationStart"
        self.proposal["intent"]["targetId"] = "op_truck"
        self.proposal["intent"]["expectedCost"] = 4000
        self.proposal["intent"]["catalogKey"] = "ops-build"
        self.before = self.raw()
        self.header, _ = self.h.contracts.validateSnapshot(
            self.before, lua_table(self.h.lua, self.h.session))

    def raw(self, revision=1, active=None, **changes):
        data = {"catalogKey": "ops-build", "operationCatalog": [
            {"id": "op_truck", "cost": 4000}],
            "native": {"fullSync": True,
            "cash": 5000 if revision == 1 else 1000, "operations": {
            "active": active if active is not None else [
                {"opId": "op_fence", "remaining": 20, "slot": 1},
            ]}}}
        data.update(changes)
        return self.h.snapshot(revision=revision, **data)

    def evaluate(self, after, reply=None):
        baseline, reason = self.evidence.capture(self.proposal, self.before)
        self.assertIsNone(reason)
        return self.evidence.evaluate(
            self.proposal, self.header, after,
            lua_table(self.h.lua, reply) if reply is not None else None,
            baseline)

    def test_matching_new_active_run_and_reply_confirm(self):
        active = [{"opId": "op_fence", "remaining": 19, "slot": 1},
                  {"opId": "op_truck", "remaining": 3600, "slot": 2}]
        self.assertEqual(self.evaluate(self.raw(2, active), {"ok": True}),
                         "confirmed")

    def test_reply_alone_or_unrelated_run_does_not_confirm(self):
        other = [{"opId": "op_fence", "remaining": 19, "slot": 1},
                 {"opId": "op_fence", "remaining": 600, "slot": 2}]
        self.assertEqual(self.evaluate(self.raw(2), {"ok": True}), "pending")
        self.assertEqual(self.evaluate(self.raw(2, other), {"ok": True}),
                         "pending")
        self.assertEqual(self.evaluate(self.raw(2, [
            {"opId": "op_truck", "remaining": 3600, "slot": 1},
        ]), {"ok": True}), "pending")

    def test_rejection_and_missing_evidence(self):
        self.assertEqual(self.evaluate(self.raw(2), {"ok": False}), "rejected")
        changed = self.raw(2, [{"opId": "op_fence", "remaining": 19},
                               {"opId": "op_truck", "remaining": 3600}])
        self.assertEqual(self.evaluate(changed, {"ok": False}), "pending")
        self.assertEqual(self.evaluate(changed), "pending")
        partial = self.raw(2)
        partial["native"]["fullSync"] = False
        self.assertEqual(self.evaluate(partial, {"ok": False}), "pending")
        wrong = self.raw(2, account="other")
        self.assertEqual(self.evaluate(wrong, {"ok": False}), "pending")

    def test_baseline_requires_complete_matching_operation_state(self):
        self.before["native"]["operations"]["active"] = None
        self.assertIsNone(self.evidence.capture(self.proposal, self.before)[0])

    def test_duplicate_native_slot_cannot_confirm_new_start(self):
        duplicate = self.raw(2, [
            {"opId": "op_fence", "remaining": 19, "slot": 1},
            {"opId": "op_truck", "remaining": 3600, "slot": 1},
        ])
        self.assertEqual(self.evaluate(duplicate, {"ok": True}), "pending")

    def test_exact_new_slot_confirms_duplicate_operation_id(self):
        self.before = self.raw(active=[
            {"opId": "op_truck", "remaining": 20, "slot": 1},
            {"opId": "op_truck", "remaining": 19, "slot": 2},
        ])
        self.header, _ = self.h.contracts.validateSnapshot(
            self.before, lua_table(self.h.lua, self.h.session))
        after = self.raw(2, [
            {"opId": "op_truck", "remaining": 18, "slot": 1},
            {"opId": "op_truck", "remaining": 17, "slot": 2},
            {"opId": "op_truck", "remaining": 3600, "slot": 3},
        ])
        self.assertEqual(self.evaluate(after, {"ok": True}), "confirmed")

    def test_start_requires_exact_quote_debit_and_all_prior_slots(self):
        active = [{"opId": "op_fence", "remaining": 19, "slot": 1},
                  {"opId": "op_truck", "remaining": 3600, "slot": 2}]
        no_debit = self.raw(2, active)
        no_debit["native"]["cash"] = 5000
        self.assertEqual(self.evaluate(no_debit, {"ok": True}), "pending")
        wrong_debit = self.raw(2, active)
        wrong_debit["native"]["cash"] = 4999
        self.assertEqual(self.evaluate(wrong_debit, {"ok": True}), "pending")
        exact = self.raw(2, active)
        exact["native"]["cash"] = 1000
        self.assertEqual(self.evaluate(exact, {"ok": True}), "confirmed")

    def test_start_refuses_stale_catalog_quote_before_send(self):
        self.before["catalogKey"] = "new-build"
        self.proposal["intent"]["catalogKey"] = "old-build"
        self.assertIsNone(self.evidence.capture(self.proposal, self.before)[0])
        self.before["catalogKey"] = "old-build"
        self.before["operationCatalog"] = lua_table(self.h.lua, [
            {"id": "op_truck", "cost": 4500}])
        self.assertIsNone(self.evidence.capture(self.proposal, self.before)[0])


if __name__ == "__main__":
    unittest.main()
