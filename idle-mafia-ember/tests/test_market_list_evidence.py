"""Owned Market listing needs exact newer listing and inventory custody."""
import unittest

from engine_harness import Harness, lua_table


class MarketListEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.evidence = self.h.load(
            "src/tabs/blackMarket/MarketListEvidence.luau")
        self.header = {"session": "s", "account": "a", "place": "p",
                       "release": "r"}

    def proposal(self):
        return lua_table(self.h.lua, dict(self.header, revision=4,
            feature="marketSell", intent={"kind": "marketList",
                "itemId": "w_baton", "quantity": 2, "ask": 9}))

    def listing(self, item="w_baton", qty=2, price=9):
        return {"state": "live", "itemOrigin": {"total": qty,
                "free": 0}, "item": item, "indexed": 3,
                "price": price, "qty": qty, "left": qty,
                "createdAt": 1001}

    def raw(self, revision=4, loose=5, bound=1, listings=None):
        return lua_table(self.h.lua, dict(self.header, revision=revision,
            capturedAt=revision + 6, native={"fullSync": True,
                "serverNow": 1000 + revision,
                "inventory": {"w_baton": loose},
                "inventoryBound": {"w_baton": bound},
                "market": {"shopUntil": 2000,
                    "listings": listings if listings is not None else {}}}))

    def test_exact_new_listing_and_loose_inventory_drop_confirm(self):
        proposal = self.proposal()
        before = self.raw()
        baseline, reason = self.evidence.capture(proposal, before)
        self.assertIsNone(reason)
        after = self.raw(5, loose=3, listings={"L1": self.listing()})
        result = self.evidence.evaluate(proposal, before, after,
            lua_table(self.h.lua, {"ok": True}), baseline)
        self.assertEqual(result, "confirmed")

    def test_confirmed_flip_listing_uses_same_exact_custody_rule(self):
        proposal = self.proposal()
        proposal["feature"] = "marketFlip"
        proposal["preflightOnly"] = True
        before = self.raw()
        baseline, reason = self.evidence.capture(proposal, before)
        self.assertIsNone(reason)
        after = self.raw(5, loose=3,
                         listings={"L1": self.listing()})
        self.assertEqual(self.evidence.evaluate(proposal,
            before, after, lua_table(self.h.lua, {"ok": True}),
            baseline), "confirmed")

    def test_reply_only_wrong_item_price_or_quantity_never_confirms(self):
        proposal = self.proposal()
        before = self.raw()
        baseline = self.evidence.capture(proposal, before)[0]
        self.assertEqual(self.evidence.evaluate(proposal, before, before,
            lua_table(self.h.lua, {"ok": True}), baseline), "pending")
        for listing in (self.listing(item="other"),
                        self.listing(qty=1), self.listing(price=10)):
            with self.subTest(listing=listing):
                after = self.raw(5, loose=3, listings={"L1": listing})
                self.assertEqual(self.evidence.evaluate(proposal, before,
                    after, lua_table(self.h.lua, {"ok": True}), baseline),
                    "pending")

    def test_two_new_listings_or_unchanged_inventory_are_ambiguous(self):
        proposal = self.proposal()
        before = self.raw()
        baseline = self.evidence.capture(proposal, before)[0]
        after = self.raw(5, loose=5, listings={"L1": self.listing()})
        self.assertEqual(self.evidence.evaluate(proposal, before, after,
            lua_table(self.h.lua, {"ok": True}), baseline), "pending")
        after = self.raw(5, loose=3, listings={"L1": self.listing(),
                                            "L2": self.listing()})
        self.assertEqual(self.evidence.evaluate(proposal, before, after,
            lua_table(self.h.lua, {"ok": True}), baseline), "pending")

    def test_bound_inventory_drop_never_confirms(self):
        proposal = self.proposal()
        before = self.raw()
        baseline = self.evidence.capture(proposal, before)[0]
        after = self.raw(5, loose=3, bound=0,
                         listings={"L1": self.listing()})
        self.assertEqual(self.evidence.evaluate(proposal, before, after,
            lua_table(self.h.lua, {"ok": True}), baseline), "pending")

    def test_rejection_without_state_change_is_rejected(self):
        proposal = self.proposal()
        before = self.raw()
        baseline = self.evidence.capture(proposal, before)[0]
        self.assertEqual(self.evidence.evaluate(proposal, before,
            self.raw(5), lua_table(self.h.lua, {"ok": False}), baseline),
            "rejected")
        after = self.raw(5, loose=3, listings={"L1": self.listing()})
        self.assertEqual(self.evidence.evaluate(proposal, before, after,
            lua_table(self.h.lua, {"ok": False}), baseline), "pending")

    def test_negative_reply_with_uncertain_or_stale_custody_stays_pending(self):
        proposal, before = self.proposal(), self.raw()
        baseline = self.evidence.capture(proposal, before)[0]
        cases = [(before, {"ok": False}),
            (self.raw(5, loose=4), {"ok": False}),
            (self.raw(5, bound=0), {"ok": False}),
            (self.raw(5), {"ok": False, "pending": True}),
            (self.raw(5), {"ok": False, "code": "rate_limited"}),
            (self.raw(5), {"ok": False, "code": "presence"})]
        for after, reply in cases:
            self.assertEqual(self.evidence.evaluate(proposal, before, after,
                lua_table(self.h.lua, reply), baseline), "pending")

    def test_incomplete_baseline_cannot_be_captured(self):
        proposal = self.proposal()
        before = self.raw()
        before["native"]["fullSync"] = False
        self.assertIsNone(self.evidence.capture(proposal, before)[0])

    def test_capture_refuses_invalid_native_timestamp(self):
        for value in (None, -1, float("nan"), float("inf"), "1004"):
            before = self.raw()
            before.native.serverNow = value
            self.assertIsNone(self.evidence.capture(self.proposal(), before)[0])

    def test_observed_listing_does_not_confirm_missing_pending_or_limited_reply(self):
        proposal, before = self.proposal(), self.raw()
        baseline = self.evidence.capture(proposal, before)[0]
        after = self.raw(5, loose=3, listings={"L1": self.listing()})
        for reply in (None, {"ok": True, "pending": True},
                      {"ok": True, "code": "rate_limited"}):
            self.assertEqual(self.evidence.evaluate(proposal, before, after,
                lua_table(self.h.lua, reply), baseline), "pending")


if __name__ == "__main__":
    unittest.main()
