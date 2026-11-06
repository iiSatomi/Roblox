"""After Collection withdrawal, selling rechecks custody and current ask."""
import unittest

from engine_harness import Harness, lua_table


class MarketSellListPreflightTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.preflight = self.h.load(
            "src/tabs/blackMarket/MarketSellListPreflight.luau")

    def inputs(self):
        header = {"session": "s", "account": "a", "place": "p",
                  "release": "r", "revision": 5, "capturedAt": 10}
        tx = {"session": "s", "account": "a", "place": "p",
              "release": "r", "stage": "withdrawn",
              "itemId": "w_baton", "withdrawnQuantity": 2,
              "plannedQuantity": 3, "beforeLoose": 1,
              "beforeBound": 0, "beforeCollected": 12,
              "checkpointFloor": 10,
              "confirmedRevision": 5, "confirmedAt": 9,
              "listAttempts": 0}
        custody = dict(header, itemId="w_baton", loose=3,
            bound=0, collected=10, collectedTotal=10,
            checkpointFloor=10, quantity=3, withdraw=0)
        quote = dict(header, itemId="w_baton", quantity=3,
            withdraw=0, ask=10, fee=1, net=9)
        listings = dict(header, serverNow=1000.5,
            shopUntil=2000, listingCount=0, listings={})
        terms = {"release": "r", "minPrice": 2,
                 "maxPrice": 9999999, "maxSlots": 5,
                 "rentAllowance": 0, "permanent": False}
        settings = {"minNet": 5, "maxListAttempts": 1}
        return [lua_table(self.h.lua, x) for x in
                (tx, custody, quote, listings, terms, settings, 11)]

    def test_current_withdrawn_surplus_yields_unsent_list(self):
        proposal, reason = self.preflight.assess(*self.inputs())
        self.assertIsNone(reason)
        self.assertTrue(proposal["preflightOnly"])
        self.assertEqual(proposal["feature"], "marketSell")
        self.assertEqual(proposal["intent"]["kind"], "marketList")
        self.assertEqual(proposal["intent"]["quantity"], 3)
        self.assertEqual(proposal["intent"]["ask"], 10)
        self.assertIsNone(proposal["remote"])

    def test_stale_or_unconfirmed_transaction_blocks(self):
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

    def test_changed_collection_or_bound_custody_blocks(self):
        values = self.inputs()
        values[1]["loose"] = 2
        self.assertIsNone(self.preflight.assess(*values)[0])
        values = self.inputs()
        values[1]["collected"] = 11
        self.assertIsNone(self.preflight.assess(*values)[0])
        values = self.inputs()
        values[1]["bound"] = 1
        self.assertIsNone(self.preflight.assess(*values)[0])
        values = self.inputs()
        values[1]["collectedTotal"] = 9
        self.assertIsNone(self.preflight.assess(*values)[0])

    def test_researched_quantity_price_and_net_must_still_pass(self):
        values = self.inputs()
        values[2]["quantity"] = 2
        self.assertIsNone(self.preflight.assess(*values)[0])
        values = self.inputs()
        values[2]["net"] = 3
        self.assertIsNone(self.preflight.assess(*values)[0])
        values = self.inputs()
        values[4]["minPrice"] = 11
        self.assertIsNone(self.preflight.assess(*values)[0])

    def test_shop_closed_full_or_changed_identity_blocks(self):
        values = self.inputs()
        values[3]["shopUntil"] = 1050
        self.assertIsNone(self.preflight.assess(*values)[0])
        values = self.inputs()
        values[3]["listingCount"] = 5
        self.assertIsNone(self.preflight.assess(*values)[0])
        values = self.inputs()
        values[2]["revision"] = 6
        self.assertIsNone(self.preflight.assess(*values)[0])


if __name__ == "__main__":
    unittest.main()
