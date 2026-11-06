"""A complete Market research read reports opportunities and rejection reasons."""
import unittest

from engine_harness import Harness, lua_table


class MarketResearchViewTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.view = self.h.load(
            "src/tabs/blackMarket/MarketResearchView.luau")
        self.watch = self.h.load(
            "src/tabs/blackMarket/MarketWatchOpportunity.luau")
        self.browse = {"kind": "all", "more": False,
            "capturedAt": 10, "rows": [
                {"id": "L1", "item": "w_baton", "qty": 1,
                 "price": 8, "mine": False},
                {"id": "L2", "item": "w_baton", "qty": 1,
                 "price": 14, "mine": False}]}
        self.rap = {"w_baton": {"itemId": "w_baton",
            "capturedAt": 10, "available": True,
            "sales": 15, "quantity": 30, "average": 14}}
        self.history = {"w_baton": {"itemId": "w_baton",
            "capturedAt": 10, "recent": [
                {"price": 14}, {"price": 15}, {"price": 16}]}}
        self.items = {"w_baton": {"id": "w_baton",
            "kind": "weapon", "rarity": 5, "tradable": True}}
        self.terms = {"w_baton": {"release": "r",
            "minPrice": 3, "maxPrice": 9999999,
            "minFee": 1, "feeRate": .1,
            "rentAllowance": 1}}
        self.settings = {"minSales": 10, "minUnits": 14,
            "minMargin": 2, "minMarginPct": 10,
            "undercutGold": 1, "floorPct": 90,
            "requireCoverage": True}

    def assess(self):
        return self.view.assess(*[lua_table(self.h.lua, value) for value in (
            self.browse, self.rap, self.history,
            self.items, self.terms, self.settings, 11)], self.watch)

    def test_complete_read_reports_winner_and_rejection(self):
        result, reason = self.assess()
        self.assertIsNone(reason)
        self.assertTrue(result.readOnly)
        self.assertTrue(result.paginationComplete)
        self.assertEqual(result.opportunityCount, 1)
        self.assertEqual(result.opportunities[1].listingId, "L1")
        self.assertEqual(result.rejectedCount, 1)
        self.assertIn("resale ask", result.rejected[1].reason.lower())

    def test_partial_read_reports_bounded_rows_without_quotes_but_stale_read_has_no_report(self):
        self.browse["more"] = True
        result,reason=self.assess()
        self.assertIsNone(reason)
        self.assertFalse(result.paginationComplete)
        self.assertTrue(result.truncated)
        self.assertEqual((result.totalRows,result.opportunityCount),(2,0))
        self.browse["more"] = False
        self.browse["capturedAt"] = -100
        self.assertIsNone(self.assess()[0])


if __name__ == "__main__":
    unittest.main()
