"""Saved Heist definitions are copied into a matching observed Sync only."""
import unittest

from engine_harness import Harness, lua_table


class NativeHeistCatalogTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.module = self.h.load("src/tabs/heists/NativeHeistCatalog.luau")
        self.source = lua_table(self.h.lua, {"HEISTS": [
            {"id": "heist_cornerstore", "level": 12,
             "stake": 10000, "energy": 25, "crateCount": 1},
            {"id": "heist_truck", "level": 20,
             "stake": 50000, "energy": 35, "crateCount": 1},
        ]})

    def adapter(self):
        return self.module.new(self.source, "a" * 64, "release-a")

    def test_full_sync_receives_copied_heist_quotes(self):
        adapter = self.adapter()
        raw = self.h.snapshot(native={"fullSync": True},
            heistCatalog=lua_table(self.h.lua, [{"id": "spoof"}]))
        enriched, reason = adapter.Enrich(adapter, raw)
        self.assertIsNone(reason)
        self.assertEqual(enriched["heistCatalog"][1]["id"],
                         "heist_cornerstore")
        self.assertEqual(enriched["heistCatalog"][2]["stake"], 50000)
        self.assertEqual(enriched["catalogKey"], "a" * 64)
        self.assertEqual(raw["heistCatalog"][1]["id"], "spoof")
        self.source["HEISTS"][1]["stake"] = 1
        self.assertEqual(adapter.Enrich(adapter, raw)[0]
                         ["heistCatalog"][1]["stake"], 10000)

    def test_wrong_release_or_partial_state_fails_closed(self):
        adapter = self.adapter()
        self.assertIsNone(adapter.Enrich(adapter,
            self.h.snapshot(release="wrong", native={"fullSync": True}))[0])
        self.assertIsNone(adapter.Enrich(adapter,
            self.h.snapshot(native={"fullSync": False}))[0])

    def test_duplicate_or_malformed_definition_is_rejected(self):
        self.source["HEISTS"][2]["id"] = "heist_cornerstore"
        with self.assertRaises(Exception):
            self.adapter()
        self.source["HEISTS"][2]["id"] = "heist_truck"
        self.source["HEISTS"][2]["energy"] = -1
        with self.assertRaises(Exception):
            self.adapter()


if __name__ == "__main__":
    unittest.main()
