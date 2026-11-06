"""Money tab copies the current bank fee and owns both controls."""
import unittest

from engine_harness import Harness, lua_table


class MoneyTabTests(unittest.TestCase):
    def test_release_bound_fee_and_source_guard(self):
        h = Harness()
        module = h.load("src/tabs/money/NativeBankCatalog.luau")
        source = lua_table(h.lua, {"BANK": {"depositFee": 0.1}})
        catalog = module.new(source, "3" * 64, "release-a")
        raw = h.snapshot(native={"fullSync": True})
        enriched, reason = catalog.Enrich(catalog, raw)
        self.assertIsNone(reason)
        self.assertEqual(enriched["bankConfig"]["depositFee"], 0.1)
        self.assertEqual(enriched["bankConfig"]["catalogKey"], "3" * 64)
        source["BANK"]["depositFee"] = 0.2
        self.assertEqual(enriched["bankConfig"]["depositFee"], 0.1)
        raw["release"] = "release-b"
        self.assertIsNone(catalog.Enrich(catalog, raw)[0])


if __name__ == "__main__":
    unittest.main()
