"""Ordinary Job evidence must match one selected Job and saved baseline."""
import unittest

from engine_harness import Harness, lua_table


class JobsEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.evidence = self.h.load("src/features/JobsEvidence.luau")
        self.proposal = self.h.proposal()
        self.proposal["intent"]["targetId"] = "j_watch"
        self.proposal["intent"]["expectedCost"] = 1
        self.proposal["intent"]["catalogKey"] = "build-1"
        self.before = self.h.snapshot(native={
            "fullSync": True, "level": 2, "jobs": {
                "j_watch": {"completions": 3, "masteryProgress": 3},
                "j_tag": {"completions": 7},
            }, "pools": {"energy": 5},
        }, catalogKey="build-1",
            jobCatalog=[{"id": "j_watch", "level": 1, "energy": 1,
                         "cash": 60, "xp": 2}],
            masteryRules=[{"completions": 25,
                           "energyDiscount": 0}])
        self.header, _ = self.h.contracts.validateSnapshot(
            self.before, lua_table(self.h.lua, self.h.session)
        )

    def capture(self):
        return self.evidence.capture(self.proposal, self.before)

    def after(self, watch=3, tag=7, revision=2, **changes):
        native = {"fullSync": True, "jobs": {
            "j_watch": {"completions": watch, "masteryProgress": watch},
            "j_tag": {"completions": tag},
        }, "pools": {"energy": 4}}
        raw = self.h.snapshot(revision=revision, native=native, **changes)
        return raw

    def evaluate(self, after, reply=None, baseline=None):
        if baseline is None:
            baseline, reason = self.capture()
            self.assertIsNone(reason)
        return self.evidence.evaluate(
            self.proposal, self.header, after,
            lua_table(self.h.lua, reply) if reply is not None else None,
            baseline,
        )

    def test_matching_reply_and_job_progress_confirm(self):
        self.assertEqual(self.evaluate(self.after(watch=4), {"ok": True}), "confirmed")

    def test_reply_or_other_job_or_resource_change_alone_is_pending(self):
        for after in (self.after(), self.after(tag=8),
                      self.after(watch=4, revision=1)):
            self.assertEqual(self.evaluate(after, {"ok": True}), "pending")
        self.assertEqual(self.evaluate(self.after(watch=4)), "pending")

    def test_explicit_rejection_without_matching_progress(self):
        self.assertEqual(self.evaluate(self.after(), {
            "ok": False, "code": "rate_limited"}), "rejected")
        self.assertEqual(self.evaluate(self.after(watch=4), {
            "ok": False, "code": "rate_limited"}), "pending")

    def test_wrong_identity_or_partial_sync_never_confirms(self):
        self.assertEqual(self.evaluate(self.after(watch=4, account="other"),
                                       {"ok": True}), "pending")
        partial = self.after(watch=4)
        partial["native"]["fullSync"] = False
        self.assertEqual(self.evaluate(partial, {"ok": True}), "pending")

    def test_baseline_copies_progress_and_rejects_incomplete_before(self):
        baseline, reason = self.capture()
        self.assertIsNone(reason)
        self.before["native"]["jobs"]["j_watch"]["completions"] = 99
        self.assertEqual(self.evaluate(self.after(watch=4), {"ok": True},
                                       baseline), "confirmed")
        self.before["native"]["fullSync"] = False
        self.assertIsNone(self.capture()[0])

    def test_first_completion_can_start_from_missing_job_record(self):
        self.before["native"]["jobs"]["j_watch"] = None
        baseline, reason = self.capture()
        self.assertIsNone(reason)
        self.assertEqual(self.evaluate(self.after(watch=1), {"ok": True},
                                       baseline), "confirmed")

    def test_preflight_rechecks_quote_unlock_energy_and_native_owner(self):
        cases = (
            ("catalogKey", "build-2"),
            ("jobCatalog", [{"id": "j_watch", "level": 1,
                             "energy": 2, "cash": 60, "xp": 2}]),
        )
        for field, value in cases:
            with self.subTest(field=field):
                original = self.before[field]
                self.before[field] = lua_table(self.h.lua, value)
                self.assertIsNone(self.capture()[0])
                self.before[field] = original
        native = self.before["native"]
        for field, value in (("level", 0), ("autoJob", {"mode": "one"}),
                             ("pools", {"energy": 0})):
            with self.subTest(native=field):
                original = native[field]
                native[field] = lua_table(self.h.lua, value)
                self.assertIsNone(self.capture()[0])
                native[field] = original

    def test_broker_captures_baseline_before_send_and_confirms_after_replication(self):
        self.h.policy["captureBefore"] = self.evidence.capture
        self.h.policy["confirm"] = self.evidence.evaluate
        self.assertEqual(self.h.broker.Offer(
            self.h.broker, self.proposal, self.before)[0], "admitted")
        self.assertEqual(self.h.broker.Tick(self.h.broker, self.before), "sent")
        self.h.transport["callbacks"][1](lua_table(self.h.lua, {"ok": True}))
        self.assertEqual(self.h.broker.Observe(
            self.h.broker, self.after(watch=4)), "confirmed")

    def test_broker_does_not_send_without_complete_job_baseline(self):
        self.h.policy["captureBefore"] = self.evidence.capture
        self.h.policy["confirm"] = self.evidence.evaluate
        incomplete = self.h.snapshot(native={"fullSync": False, "jobs": {}})
        self.h.broker.Offer(self.h.broker, self.proposal, incomplete)
        self.assertEqual(self.h.broker.Tick(self.h.broker, incomplete), "baseline_failed")
        self.assertEqual(len(self.h.transport["sent"]), 0)

    def test_broker_does_not_send_when_quote_changes_after_admission(self):
        self.h.policy["captureBefore"] = self.evidence.capture
        self.assertEqual(self.h.broker.Offer(
            self.h.broker, self.proposal, self.before)[0], "admitted")
        self.before["jobCatalog"][1]["energy"] = 2
        self.assertEqual(self.h.broker.Tick(
            self.h.broker, self.before), "baseline_failed")
        self.assertEqual(len(self.h.transport["sent"]), 0)


if __name__ == "__main__":
    unittest.main()
