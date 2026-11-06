"""Sale quote is non-sending and uses fresh item-specific research."""
import unittest

from engine_harness import Harness, lua_table


class MarketSaleQuoteTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.quote = self.h.load(
            "src/tabs/blackMarket/MarketSaleQuote.luau")
        self.header = {"session": "s", "account": "a", "place": "p",
                       "release": "r", "revision": 4, "capturedAt": 10}

    def inputs(self):
        custody = dict(self.header, itemId="w_baton", quantity=3,
                       withdraw=0)
        rap = {"itemId": "w_baton", "capturedAt": 10,
               "quantity": 20, "sales": 12, "average": 10,
               "available": True}
        history = {"itemId": "w_baton", "capturedAt": 10,
                   "recent": [{"price": 10}, {"price": 11},
                              {"price": 12}], "days": []}
        browse = {"kind": "item", "arg": "w_baton",
                  "capturedAt": 10, "more": False,
                  "rows": [{"id": "other_1", "item": "w_baton",
                            "qty": 2, "price": 11, "mine": False}]}
        listings = dict(self.header, listingCount=0, listings={},
                        serverNow=1000, shopUntil=2000)
        terms = {"release": "r", "minPrice": 2,
                 "maxPrice": 9999999, "minFee": 1,
                 "maxQuantity": 999, "feeRate": 0.1,
                 "rentAllowance": 0,
                 "permanent": False, "maxSlots": 5}
        settings = {"minSales": 3, "minUnits": 3, "minNet": 5,
                    "likelyOnly": False, "undercutGold": 1,
                    "floorPct": 95}
        return [lua_table(self.h.lua, value) for value in
                (custody, rap, history, browse, listings, terms, settings, 10)]

    def assess(self, values):
        return self.quote.assess(*values)

    def test_competitor_quote_and_native_fee_are_conservative(self):
        candidate, reason = self.assess(self.inputs())
        self.assertIsNone(reason)
        self.assertEqual(candidate["itemId"], "w_baton")
        self.assertEqual(candidate["ask"], 10)
        self.assertEqual(candidate["fee"], 1)
        self.assertEqual(candidate["net"], 9)
        self.assertEqual(candidate["quantity"], 3)
        self.assertEqual(candidate["competingUnits"], 2)

    def test_likely_only_reduces_quantity_to_demand_coverage(self):
        values = self.inputs()
        values[1]["quantity"] = 14
        values[3]["rows"][1]["qty"] = 8
        values[6]["likelyOnly"] = True
        candidate, reason = self.assess(values)
        self.assertIsNone(reason)
        self.assertEqual(candidate["quantity"], 1)
        self.assertEqual(candidate["withdraw"], 0)
        self.assertGreaterEqual(candidate["turnover"], 1.5)

    def test_likely_only_rejects_insufficient_sold_units(self):
        values = self.inputs()
        values[1]["quantity"] = 13
        values[6]["likelyOnly"] = True
        self.assertIsNone(self.assess(values)[0])

    def test_incomplete_or_stale_research_cannot_price_owned_item(self):
        for index, field, value in ((3, "more", True),
                                    (1, "capturedAt", -111),
                                    (2, "capturedAt", -111),
                                    (3, "capturedAt", -111),
                                    (3, "arg", "other_item")):
            with self.subTest(index=index, field=field):
                values = self.inputs()
                values[index][field] = value
                self.assertIsNone(self.assess(values)[0])

    def test_own_listing_supply_and_minimum_net_hold(self):
        values = self.inputs()
        values[4]["listings"]["ours"] = lua_table(self.h.lua, {
            "item": "w_baton", "left": 4, "qty": 4,
            "price": 11, "state": "active"})
        values[4]["listingCount"] = 1
        candidate, reason = self.assess(values)
        self.assertIsNone(reason)
        self.assertEqual(candidate["competingUnits"], 6)
        values[6]["minNet"] = 10
        self.assertIsNone(self.assess(values)[0])

    def test_floor_price_and_mismatched_sync_identity_reject(self):
        values = self.inputs()
        values[3]["rows"][1]["price"] = 9
        self.assertIsNone(self.assess(values)[0])
        values = self.inputs()
        values[4]["revision"] = 5
        self.assertIsNone(self.assess(values)[0])

    def test_native_minimum_fee_quantity_and_release_apply(self):
        values = self.inputs()
        values[5]["minFee"] = 2
        values[5]["maxQuantity"] = 2
        candidate, reason = self.assess(values)
        self.assertIsNone(reason)
        self.assertEqual(candidate["fee"], 2)
        self.assertEqual(candidate["quantity"], 2)
        values[5]["release"] = "old"
        self.assertIsNone(self.assess(values)[0])

    def test_fractional_native_server_clock_is_valid(self):
        values = self.inputs()
        values[4]["serverNow"] = 1000.5
        candidate, reason = self.assess(values)
        self.assertIsNone(reason)
        self.assertEqual(candidate["itemId"], "w_baton")


if __name__ == "__main__":
    unittest.main()
