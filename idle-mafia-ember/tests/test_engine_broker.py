"""Single owner, preflight and pacing behavior with a fake transport."""
from pathlib import Path
import unittest

from engine_harness import Harness, ROOT, lua_table


class BrokerTests(unittest.TestCase):
    def setUp(self):
        for name in ("Broker.luau", "Journal.luau"):
            self.assertTrue((ROOT / "src/engine" / name).is_file(), f"{name} missing")
        self.h = Harness()

    def test_one_owner_and_successful_reply_is_not_confirmation(self):
        h = self.h
        self.assertEqual(h.broker.Offer(h.broker, h.proposal(), h.snapshot())[0], "admitted")
        self.assertEqual(h.broker.Offer(h.broker, h.proposal(key="other"), h.snapshot())[0], "wait")
        h.broker.Tick(h.broker, h.snapshot())
        self.assertEqual(len(h.transport["sent"]), 1)
        h.transport["callbacks"][1](lua_table(h.lua, {"ok": True}))
        self.assertEqual(h.broker.Status(h.broker)["active"]["phase"], "returned")
        self.assertEqual(h.broker.Offer(h.broker, h.proposal(key="other"), h.snapshot())[0], "wait")

    def test_stale_preflight_drops_unsent_proposal(self):
        h = self.h
        h.broker.Offer(h.broker, h.proposal(), h.snapshot())
        h.at(3)
        h.broker.Tick(h.broker, h.snapshot(captured_at=0))
        self.assertEqual(len(h.transport["sent"]), 0)
        self.assertIsNone(h.broker.Status(h.broker)["active"])

    def test_session_identity_is_fixed_when_broker_is_created(self):
        h = self.h
        h.policy["session"]["account"] = "other"
        snapshot = h.snapshot(account="other")
        proposal = h.proposal()
        proposal["account"] = "other"
        status, reason = h.broker.Offer(h.broker, proposal, snapshot)
        self.assertEqual(status, "blocked")
        self.assertIn("account", reason)

    def test_next_send_waits_one_full_second_after_confirmation(self):
        h = self.h
        h.broker.Offer(h.broker, h.proposal(), h.snapshot())
        h.broker.Tick(h.broker, h.snapshot())
        confirmed = h.snapshot(revision=2, proofKey="jobs:j_watch:1")
        self.assertEqual(h.broker.Observe(h.broker, confirmed), "confirmed")
        h.at(0.999)
        proposal = h.proposal(key="jobs:j_tag:2", revision=2)
        self.assertEqual(h.broker.Offer(h.broker, proposal, h.snapshot(revision=2))[0], "admitted")
        h.broker.Tick(h.broker, h.snapshot(revision=2))
        self.assertEqual(len(h.transport["sent"]), 1)
        h.at(1.0)
        h.broker.Tick(h.broker, h.snapshot(revision=2))
        self.assertEqual(len(h.transport["sent"]), 2)

    def test_reply_only_confirmation_cannot_resolve_unchanged_state(self):
        h = self.h
        h.policy["confirm"] = h.lua.eval("function() return 'confirmed' end")
        h.broker.Offer(h.broker, h.proposal(), h.snapshot())
        h.broker.Tick(h.broker, h.snapshot())
        h.transport["callbacks"][1](lua_table(h.lua, {"ok": True}))
        self.assertEqual(h.broker.Observe(h.broker, h.snapshot()), "pending")
        self.assertIsNotNone(h.broker.Status(h.broker)["active"])

    def test_server_rate_limit_cools_only_rejected_feature(self):
        h = self.h
        h.broker.Offer(h.broker, h.proposal(), h.snapshot())
        h.broker.Tick(h.broker, h.snapshot())
        h.transport["callbacks"][1](lua_table(h.lua, {
            "ok": False, "code": "rate_limited", "retryIn": 12}))
        self.assertEqual(h.broker.Observe(h.broker,
            h.snapshot(rejectionKey="jobs:j_watch:1")), "rejected")
        h.at(1)
        self.assertEqual(h.broker.Offer(h.broker,
            h.proposal(key="jobs:j_tag:2"), h.snapshot())[0], "blocked")
        self.assertEqual(h.broker.Offer(h.broker,
            h.proposal(feature="operations", key="operations:1"),
            h.snapshot())[0], "admitted")
        h.broker.Tick(h.broker, h.snapshot())
        self.assertEqual(h.broker.Observe(h.broker,
            h.snapshot(revision=2, proofKey="operations:1")), "confirmed")
        h.at(11)
        later = h.proposal(key="jobs:j_tag:2", revision=2)
        self.assertEqual(h.broker.Offer(h.broker,
            later, h.snapshot(revision=2))[0], "blocked")
        h.at(12)
        self.assertEqual(h.broker.Offer(h.broker,
            later, h.snapshot(revision=2))[0], "admitted")


if __name__ == "__main__":
    unittest.main()
