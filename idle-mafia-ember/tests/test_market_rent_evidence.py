"""Rent requires exact Gold custody and a newer one-period shop expiry."""
import unittest

from engine_harness import Harness, lua_table


class MarketRentEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.evidence = self.h.load(
            "src/tabs/blackMarket/MarketRentEvidence.luau")
        self.header = {"session": "s", "account": "a", "place": "p",
                       "release": "r"}

    def proposal(self):
        return lua_table(self.h.lua, dict(self.header, revision=4,
            feature="marketRent", intent={"kind": "marketRent",
                "periods": 1, "cost": 1, "durationSeconds": 43200}))

    def raw(self, revision=4, loose=8, bound=2,
            until=900, now=1000):
        return lua_table(self.h.lua, dict(self.header, revision=revision,
            capturedAt=revision + 6, native={"fullSync": True,
                "serverNow": now, "inventory": {"gold_bar": loose},
                "inventoryBound": {"gold_bar": bound},
                "market": {"shopUntil": until}}))

    def assess(self, after, reply=None):
        proposal, before = self.proposal(), self.raw()
        baseline, reason = self.evidence.capture(proposal, before)
        self.assertIsNone(reason)
        result = self.evidence.evaluate(proposal, before, after,
            lua_table(self.h.lua, reply or {"ok": True}), baseline)
        return result

    def test_exact_newer_rental_confirms(self):
        self.assertEqual(self.assess(self.raw(5, 7, 2, 44201, 1002)),
                         "confirmed")

    def test_reply_without_sync_or_gold_change_is_pending(self):
        self.assertEqual(self.assess(self.raw()), "pending")
        self.assertEqual(self.assess(self.raw(5, 8, 2, 44201, 1002)),
                         "pending")

    def test_extra_gold_spend_or_bound_change_is_ambiguous(self):
        self.assertEqual(self.assess(self.raw(5, 6, 2, 44201, 1002)),
                         "pending")
        self.assertEqual(self.assess(self.raw(5, 7, 1, 44201, 1002)),
                         "pending")

    def test_short_or_extra_expiry_is_ambiguous(self):
        self.assertEqual(self.assess(self.raw(5, 7, 2, 30000, 1002)),
                         "pending")
        self.assertEqual(self.assess(self.raw(5, 7, 2, 90000, 1002)),
                         "pending")
        self.assertEqual(self.assess(self.raw(5, 7, 2, 44320, 1002)),
                         "pending")
        self.assertEqual(self.assess(self.raw(5, 7, 2, 44199, 1002)),
                         "pending")

    def test_rejected_reply_with_advanced_state_stays_pending(self):
        self.assertEqual(self.assess(self.raw(5), {"ok": False}),
                         "rejected")
        self.assertEqual(self.assess(
            self.raw(5, 7, 2, 44201, 1002), {"ok": False}), "pending")

    def test_wrong_account_or_incomplete_sync_cannot_confirm(self):
        after = self.raw(5, 7, 2, 44201, 1002)
        after["account"] = "other"
        self.assertEqual(self.assess(after), "pending")
        after = self.raw(5, 7, 2, 44201, 1002)
        after["native"]["fullSync"] = False
        self.assertEqual(self.assess(after), "pending")

    def test_baseline_accepts_native_total_gold_but_rejects_insolvent_or_partial_state(self):
        proposal = self.proposal()
        before = self.raw(loose=0, bound=10)
        baseline,reason=self.evidence.capture(proposal,before)
        self.assertIsNone(reason)
        self.assertEqual((baseline.loose,baseline.bound),(0,10))
        self.assertIsNone(self.evidence.capture(proposal,self.raw(loose=0,bound=0))[0])
        before = self.raw()
        before["native"]["fullSync"] = False
        self.assertIsNone(self.evidence.capture(proposal, before)[0])


if __name__ == "__main__":
    unittest.main()
