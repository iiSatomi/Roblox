"""Market sale Collection withdrawal stays above a protected checkpoint."""
import unittest

from engine_harness import Harness, lua_table


class MarketCollectionWithdrawTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.preflight = self.h.load(
            "src/tabs/blackMarket/MarketCollectionWithdrawPreflight.luau")
        self.evidence = self.h.load(
            "src/tabs/blackMarket/MarketCollectionWithdrawEvidence.luau")
        self.header = {"session": "s", "account": "a", "place": "p",
                       "release": "r"}

    def inputs(self):
        header = dict(self.header, revision=4, capturedAt=10)
        custody = dict(header, itemId="w_baton", quantity=3,
            withdraw=2, loose=1, bound=0, collected=12,
            collectedBound=0, collectedTotal=12,
            collectionSurplus=2, checkpointFloor=10)
        quote = dict(header, itemId="w_baton", quantity=3,
                     withdraw=2, ask=10, fee=1, net=9)
        listings = dict(header, serverNow=1000.5,
            shopUntil=2000, listingCount=0, listings={})
        terms = {"release": "r", "permanent": False,
                 "maxSlots": 5}
        settings = {"maxWithdraw": 5, "maxAttempts": 1}
        return [lua_table(self.h.lua, x) for x in
                (custody, quote, listings, terms, settings, 0, 11)]

    def raw(self, revision=4, loose=1, collected=12,
            bound=0, collected_bound=0, gold=20,
            extra_variant=None):
        collection = {"w_baton": collected}
        if extra_variant is not None:
            collection["w_baton@2"] = extra_variant
        return lua_table(self.h.lua, dict(self.header,
            revision=revision, capturedAt=revision + 6,
            native={"fullSync": True, "serverNow": 1000 + revision,
                "inventory": {"w_baton": loose,
                              "gold_bar": gold},
                "inventoryBound": {"w_baton": bound,
                                   "gold_bar": 2},
                "collection": collection,
                "collectionBound": {"w_baton": collected_bound}}))

    def proposal(self):
        return self.preflight.assess(*self.inputs())[0]

    def test_unsent_withdraw_intent_and_exact_newer_transfer(self):
        proposal, reason = self.preflight.assess(*self.inputs())
        self.assertIsNone(reason)
        self.assertTrue(proposal["preflightOnly"])
        self.assertEqual(proposal["intent"]["quantity"], 2)
        self.assertIsNone(proposal["remote"])
        before = self.raw()
        baseline, reason = self.evidence.capture(proposal, before)
        self.assertIsNone(reason)
        after = self.raw(5, loose=3, collected=10)
        result = self.evidence.evaluate(proposal, before, after,
            lua_table(self.h.lua, {"ok": True, "moved": 2}), baseline)
        self.assertEqual(result, "confirmed")

    def test_checkpoint_and_bound_collection_restrictions(self):
        values = self.inputs()
        values[0]["checkpointFloor"] = 11
        self.assertIsNone(self.preflight.assess(*values)[0])
        values = self.inputs()
        values[0]["collected"] = 1
        self.assertIsNone(self.preflight.assess(*values)[0])
        proposal = self.proposal()
        self.assertIsNone(self.evidence.capture(
            proposal, self.raw(collected=11))[0])

    def test_quote_sync_shop_and_attempt_caps_block(self):
        values = self.inputs()
        values[1]["revision"] = 5
        self.assertIsNone(self.preflight.assess(*values)[0])
        values = self.inputs()
        values[2]["shopUntil"] = 1050
        self.assertIsNone(self.preflight.assess(*values)[0])
        values = self.inputs()
        values[5] = 1
        self.assertIsNone(self.preflight.assess(*values)[0])

    def test_reply_only_or_wrong_transfer_never_confirms(self):
        proposal, before = self.proposal(), self.raw()
        baseline = self.evidence.capture(proposal, before)[0]
        for after, reply in ((self.raw(), {"ok": True, "moved": 2}),
                             (self.raw(5, loose=2, collected=10),
                              {"ok": True, "moved": 2}),
                             (self.raw(5, loose=3, collected=10),
                              {"ok": True, "moved": 1}),
                             (self.raw(5, loose=3, collected=10,
                                       gold=19), {"ok": True,
                                                  "moved": 2})):
            with self.subTest(reply=reply):
                self.assertEqual(self.evidence.evaluate(proposal,
                    before, after, lua_table(self.h.lua, reply),
                    baseline), "pending")

    def test_variant_or_bound_change_is_ambiguous(self):
        proposal, before = self.proposal(), self.raw()
        baseline = self.evidence.capture(proposal, before)[0]
        after = self.raw(5, loose=3, collected=10,
                         extra_variant=1)
        self.assertEqual(self.evidence.evaluate(proposal,
            before, after, lua_table(self.h.lua, {"ok": True,
                "moved": 2}), baseline), "pending")
        after = self.raw(5, loose=3, collected=10, bound=1)
        self.assertEqual(self.evidence.evaluate(proposal,
            before, after, lua_table(self.h.lua, {"ok": True,
                "moved": 2}), baseline), "pending")

    def test_rejection_and_conflicting_state(self):
        proposal, before = self.proposal(), self.raw()
        baseline = self.evidence.capture(proposal, before)[0]
        self.assertEqual(self.evidence.evaluate(proposal,
            before, self.raw(5), lua_table(self.h.lua,
                {"ok": False}), baseline), "rejected")
        self.assertEqual(self.evidence.evaluate(proposal,
            before, self.raw(5, loose=3, collected=10),
            lua_table(self.h.lua, {"ok": False}),
            baseline), "pending")

    def test_restart_observation_uses_server_time_and_exact_base_transfer(self):
        self.assertTrue(callable(self.evidence.observe))
        baseline = self.evidence.capture(self.proposal(), self.raw())[0]
        after = self.raw(0, loose=3, collected=10)
        after.session = "restart"
        after.native.serverNow = baseline.serverNow
        self.assertFalse(self.evidence.observe(baseline, after))
        after.native.serverNow += 1
        self.assertTrue(self.evidence.observe(baseline, after))
        for field, key, value in (("inventoryBound", "w_baton", 1),
                                  ("collection", "w_baton@2", 1),
                                  ("inventory", "gold_bar", 19)):
            changed = self.raw(0, loose=3, collected=10)
            changed.session = "restart"
            changed.native.serverNow = baseline.serverNow + 1
            changed.native[field][key] = value
            self.assertFalse(self.evidence.observe(baseline, changed))

    def test_state_observation_keeps_ordinary_reply_requirements(self):
        self.assertTrue(callable(self.evidence.observe))
        proposal, before = self.proposal(), self.raw()
        baseline = self.evidence.capture(proposal, before)[0]
        after = self.raw(5, loose=3, collected=10)
        self.assertTrue(self.evidence.observe(baseline, after))
        for reply in (None, {"ok": False}, {"ok": True, "moved": 1},
                      {"ok": True, "moved": 2, "code": "rate_limited"},
                      {"ok": True, "moved": 2, "pending": True}):
            self.assertEqual(self.evidence.evaluate(proposal, before, after,
                lua_table(self.h.lua, reply), baseline), "pending")

    def test_bad_timestamp_or_same_session_revision_cannot_observe(self):
        self.assertTrue(callable(self.evidence.observe))
        baseline = self.evidence.capture(self.proposal(), self.raw())[0]
        after = self.raw(4, loose=3, collected=10)
        after.native.serverNow += 1
        self.assertFalse(self.evidence.observe(baseline, after))
        for value in (None, -1, float("nan"), float("inf"), "1004"):
            before, after = self.raw(), self.raw(5, loose=3, collected=10)
            before.native.serverNow = after.native.serverNow = value
            self.assertIsNone(self.evidence.capture(self.proposal(), before)[0])
            self.assertFalse(self.evidence.observe(baseline, after))


if __name__ == "__main__":
    unittest.main()
