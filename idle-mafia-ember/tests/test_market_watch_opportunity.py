"""Read-only Market watch estimates margins from complete fresh research."""
import unittest

from engine_harness import Harness, lua_table


class MarketWatchOpportunityTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.watch = self.h.load(
            "src/tabs/blackMarket/MarketWatchOpportunity.luau")

    def inputs(self):
        browse = {"kind": "all", "capturedAt": 10,
            "more": False, "rows": [
                {"id": "L1", "item": "w_baton", "price": 8,
                 "qty": 1, "mine": False},
                {"id": "L2", "item": "w_baton", "price": 14,
                 "qty": 1, "mine": False}]}
        rap = {"itemId": "w_baton", "capturedAt": 10,
               "available": True, "sales": 15,
               "quantity": 30, "average": 14}
        history = {"itemId": "w_baton", "capturedAt": 10,
                   "recent": [{"price": 14}, {"price": 15},
                              {"price": 16}]}
        item = {"id": "w_baton", "kind": "weapon",
                "rarity": 5, "tradable": True}
        terms = {"release": "r", "minPrice": 3,
                 "maxPrice": 9999999, "minFee": 1,
                 "feeRate": .1, "rentAllowance": 1}
        settings = {"minSales": 10, "minUnits": 14,
                    "minMargin": 2, "minMarginPct": 10,
                    "undercutGold": 1, "floorPct": 90,
                    "requireCoverage": True}
        return [lua_table(self.h.lua, x) for x in
                (browse, "L1", rap, history, item, terms,
                 settings, 11)]

    def test_complete_fresh_discount_is_hypothetical_only(self):
        candidate, reason = self.watch.assess(*self.inputs())
        self.assertIsNone(reason)
        self.assertTrue(candidate["hypothetical"])
        self.assertEqual(candidate["listingId"], "L1")
        self.assertEqual(candidate["buy"], 8)
        self.assertEqual(candidate["ask"], 13)
        self.assertEqual(candidate["fee"], 1)
        self.assertEqual(candidate["rentAllowance"], 1)
        self.assertEqual(candidate["margin"], 3)
        self.assertEqual(candidate["kind"], "weapon")

    def test_incomplete_stale_or_wrong_scope_rejected(self):
        for index, field, value in ((0, "more", True),
                                    (0, "kind", "item"),
                                    (0, "capturedAt", -20),
                                    (2, "capturedAt", -200),
                                    (3, "itemId", "other")):
            with self.subTest(index=index, field=field):
                values = self.inputs()
                values[index][field] = value
                self.assertIsNone(self.watch.assess(*values)[0])

    def test_own_multiunit_or_changed_target_rejected(self):
        values = self.inputs()
        values[0]["rows"][1]["mine"] = True
        self.assertIsNone(self.watch.assess(*values)[0])
        values = self.inputs()
        values[0]["rows"][1]["qty"] = 2
        self.assertIsNone(self.watch.assess(*values)[0])
        values = self.inputs()
        values[1] = "missing"
        self.assertIsNone(self.watch.assess(*values)[0])

    def test_nontradable_gold_or_insufficient_demand_rejected(self):
        values = self.inputs()
        values[4]["tradable"] = False
        self.assertIsNone(self.watch.assess(*values)[0])
        values = self.inputs()
        values[4]["kind"] = "gold"
        self.assertIsNone(self.watch.assess(*values)[0])
        values = self.inputs()
        values[2]["sales"] = 9
        self.assertIsNone(self.watch.assess(*values)[0])
        values = self.inputs()
        values[2]["quantity"] = 1
        self.assertIsNone(self.watch.assess(*values)[0])

    def test_margin_floor_and_native_rarity_price_hold(self):
        values = self.inputs()
        values[6]["minMargin"] = 4
        self.assertIsNone(self.watch.assess(*values)[0])
        values = self.inputs()
        values[5]["minPrice"] = 14
        self.assertIsNone(self.watch.assess(*values)[0])
        values = self.inputs()
        values[5]["minFee"] = 4
        self.assertIsNone(self.watch.assess(*values)[0])

    def test_supply_coverage_rejects_crowded_market(self):
        values = self.inputs()
        values[0]["rows"][2]["qty"] = 30
        self.assertIsNone(self.watch.assess(*values)[0])


if __name__ == "__main__":
    unittest.main()
