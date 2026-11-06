"""Rewards tab copies saved ladder and keeps monthly config authoritative."""
import unittest

from engine_harness import Harness, lua_table


RUNGS = [
    {"seconds": 300, "kind": "cash", "flat": 10000,
     "tiers": {2: {"kind": "cash", "minutes": 15}}},
    {"seconds": 900, "kind": "energy"},
    {"seconds": 1800, "kind": "crate", "crate": "crate_loot"},
    {"seconds": 3600, "kind": "seals", "amount": 2},
    {"seconds": 5400, "kind": "xpboost", "minutes": 30,
     "weekend": {"kind": "gold", "amount": 3}},
    {"seconds": 7200, "kind": "mystery"},
    {"seconds": 10800, "kind": "crate",
     "crate": "crate_consumables_bound", "bound": True},
]


class RewardsTabTests(unittest.TestCase):
    def test_source_copy_and_monthly_disabled(self):
        h = Harness()
        module = h.load("src/tabs/rewards/NativeRewardsCatalog.luau")
        catalog = module.new(lua_table(h.lua, {
            "LADDER": RUNGS, "LADDER_TIERS": [1, 10, 30, 102],
            "GROUP": {"id": 674050067},
            "MONTHLY_CALENDAR": {"enabled": False}}),
            "a" * 64, "release-a")
        raw = h.snapshot(release="release-a",
                         native={"fullSync": True})
        enriched, reason = catalog.Enrich(catalog, raw)
        self.assertIsNone(reason)
        self.assertEqual(enriched["ladderCatalog"][5]
                         ["weekend"]["amount"], 3)
        self.assertEqual(enriched["ladderTiers"][4], 102)
        self.assertEqual(enriched["groupConfig"]["id"], 674050067)
        self.assertFalse(enriched["monthlyConfig"]["enabled"])
        self.assertIsNone(enriched["weekendBuff"])
        self.assertIsNone(enriched["groupMembership"])
        raw["release"] = "other"
        self.assertIsNone(catalog.Enrich(catalog, raw)[0])


if __name__ == "__main__":
    unittest.main()
