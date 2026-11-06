"""Direct owned-item listing uses only unreserved loose surplus."""
import unittest

from engine_harness import Harness, lua_table


class MarketSellDirectPreflightTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.preflight = self.h.load(
            "src/tabs/blackMarket/MarketSellDirectPreflight.luau")

    def inputs(self):
        header = {"session": "s", "account": "a", "place": "p",
                  "release": "r", "revision": 4, "capturedAt": 10}
        custody = dict(header, itemId="w_baton", quantity=2,
            withdraw=0, loose=4, bound=1,
            reservedLoose=2)
        quote = dict(header, itemId="w_baton", quantity=2,
                     withdraw=0, ask=10, fee=1, net=9)
        listings = dict(header, serverNow=1000.5,
            shopUntil=2000, listingCount=0, listings={})
        terms = {"release": "r", "minPrice": 2,
                 "maxPrice": 9999999, "maxSlots": 5,
                 "rentAllowance": 0, "permanent": False}
        settings = {"minNet": 5, "maxListings": 2,
                    "transactionOpen": False}
        return [lua_table(self.h.lua, x) for x in
                (custody, quote, listings, terms, settings, 0, 11)]

    def test_surplus_listing_intent_is_unsent(self):
        proposal, reason = self.preflight.assess(*self.inputs())
        self.assertIsNone(reason)
        self.assertTrue(proposal["preflightOnly"])
        self.assertEqual(proposal["feature"], "marketSell")
        self.assertEqual(proposal["intent"]["kind"], "marketList")
        self.assertEqual(proposal["intent"]["quantity"], 2)
        self.assertEqual(proposal["intent"]["ask"], 10)
        self.assertIsNone(proposal["remote"])

    def test_collection_withdrawal_or_reservation_blocks_direct_list(self):
        values = self.inputs()
        values[0]["withdraw"] = 1
        self.assertIsNone(self.preflight.assess(*values)[0])
        values = self.inputs()
        values[0]["reservedLoose"] = 3
        self.assertIsNone(self.preflight.assess(*values)[0])
        values = self.inputs()
        values[1]["withdraw"] = 1
        self.assertIsNone(self.preflight.assess(*values)[0])

    def test_changed_quote_or_native_price_floor_blocks(self):
        values = self.inputs()
        values[1]["quantity"] = 3
        self.assertIsNone(self.preflight.assess(*values)[0])
        values = self.inputs()
        values[3]["minPrice"] = 11
        self.assertIsNone(self.preflight.assess(*values)[0])
        values = self.inputs()
        values[1]["net"] = 2
        self.assertIsNone(self.preflight.assess(*values)[0])

    def test_shop_or_attempt_limit_blocks(self):
        values = self.inputs()
        values[2]["shopUntil"] = 1050
        self.assertIsNone(self.preflight.assess(*values)[0])
        values = self.inputs()
        values[2]["listingCount"] = 5
        self.assertIsNone(self.preflight.assess(*values)[0])
        values = self.inputs()
        values[5] = 2
        self.assertIsNone(self.preflight.assess(*values)[0])
        values = self.inputs()
        values[4]["transactionOpen"] = True
        self.assertIsNone(self.preflight.assess(*values)[0])

    def test_stale_or_changed_account_sync_blocks(self):
        values = self.inputs()
        values[0]["capturedAt"] = -20
        self.assertIsNone(self.preflight.assess(*values)[0])
        values = self.inputs()
        values[2]["account"] = "other"
        self.assertIsNone(self.preflight.assess(*values)[0])
        values = self.inputs()
        values[1]["revision"] = 5
        self.assertIsNone(self.preflight.assess(*values)[0])


if __name__ == "__main__":
    unittest.main()
