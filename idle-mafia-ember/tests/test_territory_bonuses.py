"""Territory watch uses authoritative holder bonus sources, not nominal sums."""
import unittest
from engine_harness import Harness, lua_table


class TerritoryBonusTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.module = self.h.load("src/tabs/territory/TerritoryBonuses.luau")

    def raw(self):
        return self.h.snapshot(native={"fullSync": True, "family": {"id": "fam-a"},
            "derived": {"territoryBonusSources": {"known": True, "familyId": "fam-a",
                "kinds": {"landlord": {"total": 0.15, "active": ["d1", "d2"],
                    "inactive": ["d3"]}, "crateLuck": {"total": 0.25,
                    "active": ["d4"], "inactive": []}}}}})

    def test_effective_total_and_active_ids_are_copied(self):
        raw = self.raw()
        result, reason = self.module.read(raw, raw)
        self.assertIsNone(reason)
        self.assertEqual(result.kinds.landlord.totalPct, 15)
        self.assertEqual(result.kinds.crateLuck.totalPct, 25)
        raw.native.derived.territoryBonusSources.kinds.landlord.active[1] = "changed"
        self.assertEqual(result.kinds.landlord.active[1], "d1")
        text = self.module.summary(result)
        self.assertIn("landlord +15", text)
        self.assertIn("2/2 active", text)

    def test_loading_other_family_oversized_or_inconsistent_sources_are_rejected(self):
        for change in ("loading", "family", "three", "duplicate", "cap", "false"):
            raw = self.raw()
            source = raw.native.derived.territoryBonusSources
            if change == "loading": source.known = False
            elif change == "family": source.familyId = "other"
            elif change == "three": source.kinds.landlord.active[3] = "d9"
            elif change == "duplicate": source.kinds.landlord.inactive[1] = "d1"
            elif change == "cap": source.kinds.crateLuck.total = 0.26
            else: source.kinds.landlord.total = False
            self.assertIsNone(self.module.read(raw, raw)[0], change)


if __name__ == "__main__": unittest.main()
