"""A confirmed Market buy needs fresh custody and sale terms to relist."""
import unittest

from engine_harness import Harness, lua_table


class MarketFlipListPreflightTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.preflight = self.h.load(
            "src/tabs/blackMarket/MarketFlipListPreflight.luau")

    def inputs(self):
        header = {"session": "s", "account": "a", "place": "p",
                  "release": "r", "revision": 5, "capturedAt": 10}
        tx = {"session": "s", "account": "a", "place": "p",
              "release": "r", "stage": "bought",
              "itemId": "w_baton", "sourceListingId": "L1",
              "buyPrice": 8, "beforeLoose": 1, "boundBefore": 0,
              "confirmedRevision": 5, "confirmedAt": 9,
              "listAttempts": 0}
        custody = dict(header, itemId="w_baton", kind="weapon",
            rarity=5, loose=2, bound=0, reservedLoose=1,
            quantity=1, withdraw=0)
        quote = dict(header, itemId="w_baton", quantity=1,
            withdraw=0, ask=13, fee=1, net=11)
        listings = dict(header, serverNow=1000.5,
            shopUntil=2000, listingCount=0, listings={})
        terms = {"release": "r", "minPrice": 3,
                 "maxPrice": 9999999, "maxSlots": 5,
                 "rentAllowance": 1, "permanent": False}
        settings = {"minMargin": 2, "maxListAttempts": 1}
        return [lua_table(self.h.lua, x) for x in
                (tx, custody, quote, listings, terms, settings, 11)]

    def test_current_sold_copy_yields_unsent_list_intent(self):
        proposal, reason = self.preflight.assess(*self.inputs())
        self.assertIsNone(reason)
        self.assertTrue(proposal["preflightOnly"])
        self.assertEqual(proposal["feature"], "marketFlip")
        self.assertEqual(proposal["intent"]["kind"], "marketList")
        self.assertEqual(proposal["intent"]["quantity"], 1)
        self.assertEqual(proposal["intent"]["ask"], 13)
        self.assertIsNone(proposal["remote"])

    def test_unconfirmed_or_old_transaction_cannot_relist(self):
        values = self.inputs()
        values[0]["stage"] = "sent"
        self.assertIsNone(self.preflight.assess(*values)[0])
        values = self.inputs()
        values[0]["confirmedAt"] = -4000
        self.assertIsNone(self.preflight.assess(*values)[0])
        values = self.inputs()
        values[0]["listAttempts"] = 1
        self.assertIsNone(self.preflight.assess(*values)[0])

    def test_native_age_can_rebase_before_restarted_local_clock_epoch(self):
        values = self.inputs()
        values[0]["confirmedAt"] = -9
        self.assertIsNotNone(self.preflight.assess(*values)[0])
        values[0]["confirmedAt"] = -3590
        self.assertIsNone(self.preflight.assess(*values)[0])

    def test_reserved_or_bound_purchased_copy_cannot_relist(self):
        values = self.inputs()
        values[1]["reservedLoose"] = 2
        self.assertIsNone(self.preflight.assess(*values)[0])
        values = self.inputs()
        values[1]["bound"] = 1
        self.assertIsNone(self.preflight.assess(*values)[0])
        values = self.inputs()
        values[1]["withdraw"] = 1
        self.assertIsNone(self.preflight.assess(*values)[0])

    def test_changed_price_or_margin_or_quantity_cannot_relist(self):
        values = self.inputs()
        values[2]["ask"] = 2
        self.assertIsNone(self.preflight.assess(*values)[0])
        values = self.inputs()
        values[2]["net"] = 9
        self.assertIsNone(self.preflight.assess(*values)[0])
        values = self.inputs()
        values[2]["quantity"] = 2
        self.assertIsNone(self.preflight.assess(*values)[0])

    def test_full_or_expired_shop_blocks_listing(self):
        values = self.inputs()
        values[3]["shopUntil"] = 1050
        self.assertIsNone(self.preflight.assess(*values)[0])
        values = self.inputs()
        values[3]["listingCount"] = 5
        self.assertIsNone(self.preflight.assess(*values)[0])

    def test_changed_account_sync_or_source_terms_blocks(self):
        values = self.inputs()
        values[1]["account"] = "other"
        self.assertIsNone(self.preflight.assess(*values)[0])
        values = self.inputs()
        values[3]["revision"] = 6
        self.assertIsNone(self.preflight.assess(*values)[0])
        values = self.inputs()
        values[4]["release"] = "old"
        self.assertIsNone(self.preflight.assess(*values)[0])


if __name__ == "__main__":
    unittest.main()
