"""A flip buy needs exact newer Gold and unbound-item custody."""
import unittest

from engine_harness import Harness, lua_table


class MarketBuyEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.evidence = self.h.load(
            "src/tabs/blackMarket/MarketBuyEvidence.luau")
        self.header = {"session": "s", "account": "a", "place": "p",
                       "release": "r"}

    def proposal(self):
        return lua_table(self.h.lua, dict(self.header, revision=4,
            preflightOnly=True, feature="marketFlip",
            intent={"kind": "marketBuy", "listingId": "L1",
                "itemId": "w_baton", "quantity": 1,
                "quotedPrice": 8, "expectedAsk": 13,
                "expectedMargin": 3}))

    def listing(self, left=2):
        return {"state": "live", "item": "w_gavel",
                "indexed": 1, "price": 9, "qty": 2,
                "left": left, "createdAt": 900,
                "itemOrigin": {"total": 2, "free": 0}}

    def raw(self, revision=4, gold=20, bound_gold=2,
            items=1, bound_items=0, listings=None):
        return lua_table(self.h.lua, dict(self.header,
            revision=revision, capturedAt=revision + 6,
            native={"fullSync": True, "serverNow": 1000 + revision,
                "inventory": {"gold_bar": gold,
                              "w_baton": items},
                "inventoryBound": {"gold_bar": bound_gold,
                                   "w_baton": bound_items},
                "market": {"listings": listings if listings is not None
                    else {"ours": self.listing()}}}))

    def assess(self, after, reply=None):
        proposal, before = self.proposal(), self.raw()
        baseline, reason = self.evidence.capture(proposal, before)
        self.assertIsNone(reason)
        return self.evidence.evaluate(proposal, before,
            after, lua_table(self.h.lua, reply or {"ok": True}),
            baseline)

    def test_exact_newer_gold_spend_and_loose_item_confirm(self):
        self.assertEqual(self.assess(self.raw(5, gold=12, items=2)),
                         "confirmed")

    def test_reply_only_or_wrong_gold_delta_stays_pending(self):
        self.assertEqual(self.assess(self.raw()), "pending")
        self.assertEqual(self.assess(self.raw(5, gold=13,
                                              items=2)), "pending")
        self.assertEqual(self.assess(self.raw(5, gold=11,
                                              items=2)), "pending")

    def test_wrong_item_or_bound_custody_stays_pending(self):
        self.assertEqual(self.assess(self.raw(5, gold=12,
                                              items=1)), "pending")
        self.assertEqual(self.assess(self.raw(5, gold=12,
            items=2, bound_gold=1)), "pending")
        self.assertEqual(self.assess(self.raw(5, gold=12,
            items=2, bound_items=1)), "pending")

    def test_other_owned_listing_change_is_ambiguous(self):
        self.assertEqual(self.assess(self.raw(5, gold=12, items=2,
            listings={"ours": self.listing(left=1)})), "pending")
        self.assertEqual(self.assess(self.raw(5, gold=12, items=2,
            listings={"ours": self.listing(),
                      "other": self.listing()})), "pending")

    def test_rejection_and_conflicting_state(self):
        self.assertEqual(self.assess(self.raw(5), {"ok": False}),
                         "rejected")
        self.assertEqual(self.assess(
            self.raw(5, gold=12, items=2), {"ok": False}), "pending")

    def test_rejection_needs_fresh_state_and_definitive_reply(self):
        self.assertEqual(self.assess(self.raw(), {'ok':False}), 'pending')
        for reply in ({'ok':False,'pending':True},{'ok':False,'code':'rate_limited'},
                      {'ok':False,'code':'presence'}):
            self.assertEqual(self.assess(self.raw(5),reply),'pending')

    def test_saved_buy_outcome_requires_exact_baseline_reply_and_custody(self):
        p,before=self.proposal(),self.raw()
        baseline=self.evidence.capture(p,before)[0]
        data=lua_table(self.h.lua,{'proposal':p,'before':before,'baseline':baseline,'reply':{'ok':True}})
        after=self.raw(0,gold=12,items=2);after.session='reloaded';after.native.serverNow=1005
        self.assertEqual(self.evidence.recoverSaved(data,after),'confirmed')
        data.reply=lua_table(self.h.lua,{'code':'presence'})
        self.assertIsNone(self.evidence.recoverSaved(data,after))
        data.reply=lua_table(self.h.lua,{'ok':True});baseline.price=7
        self.assertIsNone(self.evidence.recoverSaved(data,after))

    def test_incomplete_or_wrong_account_cannot_confirm(self):
        after = self.raw(5, gold=12, items=2)
        after["native"]["fullSync"] = False
        self.assertEqual(self.assess(after), "pending")
        after = self.raw(5, gold=12, items=2)
        after["account"] = "other"
        self.assertEqual(self.assess(after), "pending")

    def test_missing_quote_or_gold_baseline_is_rejected(self):
        proposal = self.proposal()
        proposal["preflightOnly"] = False
        self.assertIsNone(self.evidence.capture(
            proposal, self.raw())[0])
        proposal = self.proposal()
        before = self.raw(gold=0)
        self.assertIsNone(self.evidence.capture(proposal, before)[0])

    def test_restart_observation_requires_newer_server_time_and_exact_custody(self):
        self.assertTrue(callable(self.evidence.observe))
        baseline = self.evidence.capture(self.proposal(), self.raw())[0]
        after = self.raw(0, gold=12, items=2)
        after.session = "restart"
        after.native.serverNow = baseline.serverNow
        self.assertFalse(self.evidence.observe(baseline, after))
        after.native.serverNow += 1
        self.assertTrue(self.evidence.observe(baseline, after))
        after.native.inventoryBound.w_baton = 1
        self.assertFalse(self.evidence.observe(baseline, after))
        after.native.inventoryBound.w_baton = 0
        after.native.inventory.gold_bar = 11
        self.assertFalse(self.evidence.observe(baseline, after))

    def test_observation_does_not_replace_reply_requirements(self):
        self.assertTrue(callable(self.evidence.observe))
        proposal, before = self.proposal(), self.raw()
        baseline = self.evidence.capture(proposal, before)[0]
        after = self.raw(5, gold=12, items=2)
        self.assertTrue(self.evidence.observe(baseline, after))
        for reply in (None, {"ok": False}, {"ok": True, "pending": True},
                      {"ok": True, "code": "rate_limited"}):
            self.assertEqual(self.evidence.evaluate(proposal, before, after,
                lua_table(self.h.lua, reply), baseline), "pending")

    def test_malformed_timestamp_never_captures_or_observes(self):
        self.assertTrue(callable(self.evidence.observe))
        baseline = self.evidence.capture(self.proposal(), self.raw())[0]
        for value in (None, -1, float("nan"), float("inf"), "1004"):
            before, after = self.raw(), self.raw(5, gold=12, items=2)
            before.native.serverNow = after.native.serverNow = value
            self.assertIsNone(self.evidence.capture(self.proposal(), before)[0])
            self.assertFalse(self.evidence.observe(baseline, after))


if __name__ == "__main__":
    unittest.main()
