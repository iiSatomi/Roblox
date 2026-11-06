"""Market price, fee, slot and rental terms come from a matching Config."""
import unittest

from engine_harness import Harness, lua_table


class NativeMarketCatalogTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.module = self.h.load(
            "src/tabs/blackMarket/NativeMarketCatalog.luau")
        self.config = {"MARKET": {"maxPages": 5, "minLevel": 20, "slots": 5,
            "maxSlots": 20, "rentPerPeriod": 1,
            "rentPeriodHours": 12, "rentMaxDays": 7,
            "feePct": .10, "permanentFeePct": .07,
            "minFee": 1, "minPrice": 2,
            "minPriceByRarity": {5: 3, 6: 5, 9: 100},
            "maxPrice": 9999999, "maxQuantity": 999}}
        self.key = "a" * 64

    def catalog(self):
        return self.module.new(lua_table(self.h.lua, self.config),
                               self.key, "r")

    def snapshot(self, permanent=False, slots=2):
        return lua_table(self.h.lua, {"release": "r",
            "native": {"fullSync": True,
                "market": {"extraSlots": slots},
                "derived": {"marketShop": permanent}}})

    def test_current_rental_terms_are_copied(self):
        catalog = self.catalog()
        terms, reason = catalog.RentTerms(catalog, self.snapshot())
        self.assertIsNone(reason)
        self.assertEqual(terms["rentPerPeriod"], 1)
        self.assertEqual(terms["rentPeriodHours"], 12)
        self.assertEqual(terms["release"], "r")
        self.config["MARKET"]["rentPerPeriod"] = 100
        self.assertEqual(terms["rentPerPeriod"], 1)

    def test_sale_terms_use_rarity_fee_and_native_slots(self):
        catalog = self.catalog()
        terms, reason = catalog.SaleTerms(catalog, self.snapshot(), 9)
        self.assertIsNone(reason)
        self.assertEqual(terms["minPrice"], 100)
        self.assertEqual(terms["maxSlots"], 7)
        self.assertEqual(terms["feeRate"], .10)
        self.assertEqual(terms["minFee"], 1)
        self.assertEqual(terms["rentAllowance"], 1)
        terms, reason = catalog.SaleTerms(catalog,
            self.snapshot(permanent=True, slots=99), 2)
        self.assertIsNone(reason)
        self.assertEqual(terms["minPrice"], 2)
        self.assertEqual(terms["maxSlots"], 20)
        self.assertEqual(terms["feeRate"], .07)
        self.assertEqual(terms["rentAllowance"], 0)

    def test_changed_release_or_incomplete_sync_has_no_terms(self):
        catalog = self.catalog()
        snapshot = self.snapshot()
        snapshot["release"] = "new"
        self.assertIsNone(catalog.RentTerms(catalog, snapshot)[0])
        self.assertIsNone(catalog.SaleTerms(catalog, snapshot, 5)[0])
        snapshot = self.snapshot()
        snapshot["native"]["fullSync"] = False
        self.assertIsNone(catalog.RentTerms(catalog, snapshot)[0])
        self.assertIsNone(catalog.SaleTerms(catalog, snapshot, 5)[0])

    def test_invalid_native_slots_or_rarity_blocks_sale_terms(self):
        catalog = self.catalog()
        snapshot = self.snapshot()
        snapshot["native"]["market"]["extraSlots"] = -1
        self.assertIsNone(catalog.SaleTerms(catalog, snapshot, 5)[0])
        self.assertIsNone(catalog.SaleTerms(
            catalog, self.snapshot(), 0)[0])

    def test_malformed_config_or_identity_is_rejected(self):
        self.config["MARKET"]["feePct"] = float("inf")
        with self.assertRaises(Exception):
            self.catalog()
        self.config["MARKET"]["feePct"] = .10
        self.config["MARKET"]["minPriceByRarity"][9] = 0
        with self.assertRaises(Exception):
            self.catalog()
        self.config["MARKET"]["minPriceByRarity"][9] = 100
        with self.assertRaises(Exception):
            self.module.new(lua_table(self.h.lua, self.config),
                            "bad", "r")


if __name__ == "__main__":
    unittest.main()
