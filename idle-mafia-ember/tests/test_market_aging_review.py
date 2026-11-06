"""Old owned Market listings are review suggestions, never relist calls."""
import unittest

from engine_harness import Harness, lua_table


class MarketAgingReviewTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.review = self.h.load(
            "src/tabs/blackMarket/MarketAgingReview.luau")

    def inputs(self):
        listings = {"session": "s", "account": "a", "place": "p",
            "release": "r", "revision": 4, "capturedAt": 10,
            "serverNow": 100000, "listingCount": 2,
            "listings": {"older": {"state": "live", "item": "w_baton",
                "price": 10, "qty": 2, "left": 2,
                "createdAt": 80000},
                "newer": {"state": "live", "item": "w_gavel",
                "price": 9, "qty": 1, "left": 1,
                "createdAt": 85000}}}
        rap = {"w_baton": {"itemId": "w_baton",
                "capturedAt": 10, "available": True,
                "sales": 12, "quantity": 20, "average": 10},
            "w_gavel": {"itemId": "w_gavel",
                "capturedAt": 10, "available": True,
                "sales": 11, "quantity": 18, "average": 9}}
        settings = {"minAgeHours": 1, "minSales": 10,
                    "minSoldUnits": 14, "demandMultiplier": 2,
                    "maxReviews": 5}
        return [lua_table(self.h.lua, x) for x in
                (listings, rap, settings, 11)]

    def test_ranked_suggestions_are_read_only(self):
        rows, reason = self.review.assess(*self.inputs())
        self.assertIsNone(reason)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1]["listingId"], "older")
        self.assertEqual(rows[2]["listingId"], "newer")
        self.assertTrue(rows[1]["reviewOnly"])
        self.assertIsNone(rows[1]["remote"])

    def test_stale_or_insufficient_demand_is_skipped(self):
        values = self.inputs()
        values[1]["w_baton"]["capturedAt"] = -200
        values[1]["w_gavel"]["sales"] = 5
        rows, reason = self.review.assess(*values)
        self.assertIsNone(reason)
        self.assertEqual(len(rows), 0)
        values = self.inputs()
        values[1]["w_baton"]["quantity"] = 1
        values[1]["w_gavel"]["available"] = False
        self.assertEqual(len(self.review.assess(*values)[0]), 0)

    def test_sold_closed_or_young_listing_is_not_suggested(self):
        values = self.inputs()
        values[0]["listings"]["older"]["left"] = 0
        values[0]["listings"]["newer"]["state"] = "sold"
        self.assertEqual(len(self.review.assess(*values)[0]), 0)
        values = self.inputs()
        values[0]["listings"]["older"]["createdAt"] = 99000
        values[0]["listings"]["newer"]["createdAt"] = 99000
        self.assertEqual(len(self.review.assess(*values)[0]), 0)

    def test_high_ask_or_small_review_cap(self):
        values = self.inputs()
        values[0]["listings"]["older"]["price"] = 12
        rows, reason = self.review.assess(*values)
        self.assertIsNone(reason)
        self.assertEqual(len(rows), 1)
        values = self.inputs()
        values[2]["maxReviews"] = 1
        self.assertEqual(len(self.review.assess(*values)[0]), 1)

    def test_bad_identity_count_or_time_fails_closed(self):
        values = self.inputs()
        values[0]["listingCount"] = 1
        self.assertIsNone(self.review.assess(*values)[0])
        values = self.inputs()
        values[0]["serverNow"] = float("inf")
        self.assertIsNone(self.review.assess(*values)[0])
        values = self.inputs()
        values[0]["account"] = ""
        self.assertIsNone(self.review.assess(*values)[0])


if __name__ == "__main__":
    unittest.main()
