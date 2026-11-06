"""Replicated Market listings are read by exact account Sync, not mine reply."""
import unittest

from engine_harness import Harness, lua_table


class MarketListingsStateTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.reader = self.h.load(
            "src/tabs/blackMarket/MarketListingsState.luau")
        self.header = {"session": "s", "account": "a", "place": "p",
                       "release": "r", "revision": 4, "capturedAt": 10}
        self.context = lua_table(self.h.lua, self.header)

    def raw(self, listings=None):
        data = dict(self.header)
        data["native"] = {"fullSync": True, "serverNow": 1000,
            "market": {"shopUntil": 2000, "earnings": 0,
                       "listings": listings if listings is not None else {}}}
        return lua_table(self.h.lua, data)

    def listing(self):
        return {"state": "active", "itemOrigin": {"total": 2,
                "free": 0}, "item": "w_baton", "indexed": 3,
                "price": 9, "qty": 2, "left": 2, "createdAt": 900}

    def test_copies_current_listing_and_custody_fields(self):
        raw = self.raw({"listing_1": self.listing()})
        view, reason = self.reader.read(raw, self.context)
        self.assertIsNone(reason)
        self.assertEqual(view["listingCount"], 1)
        self.assertEqual(view["shopUntil"], 2000)
        self.assertEqual(view["serverNow"], 1000)
        self.assertEqual(view["listings"]["listing_1"]["itemOrigin"]["total"], 2)
        raw["native"]["market"]["listings"]["listing_1"]["left"] = 0
        self.assertEqual(view["listings"]["listing_1"]["left"], 2)

    def test_empty_full_sync_is_valid(self):
        view, reason = self.reader.read(self.raw(), self.context)
        self.assertIsNone(reason)
        self.assertEqual(view["listingCount"], 0)

    def test_fractional_native_server_clock_is_valid(self):
        raw = self.raw()
        raw["native"]["serverNow"] = 1000.5
        view, reason = self.reader.read(raw, self.context)
        self.assertIsNone(reason)
        self.assertEqual(view["serverNow"], 1000.5)

    def test_changed_state_or_header_is_not_treated_as_listing_proof(self):
        raw = self.raw({"listing_1": self.listing()})
        raw["native"]["fullSync"] = False
        self.assertIsNone(self.reader.read(raw, self.context)[0])
        raw["native"]["fullSync"] = True
        raw["revision"] = 5
        self.assertIsNone(self.reader.read(raw, self.context)[0])

    def test_malformed_listing_and_custody_are_rejected(self):
        for change in ({"left": 3}, {"price": -1},
                       {"itemOrigin": {"total": 2, "free": 3}},
                       {"item": ""}, {"createdAt": float("inf")}):
            with self.subTest(change=change):
                listing = self.listing()
                listing.update(change)
                self.assertIsNone(self.reader.read(
                    self.raw({"listing_1": listing}), self.context)[0])

    def test_bad_listing_map_key_is_rejected(self):
        self.assertIsNone(self.reader.read(
            self.raw({123: self.listing()}), self.context)[0])


if __name__ == "__main__":
    unittest.main()
