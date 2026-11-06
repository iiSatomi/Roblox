"""Existing economy actions compose through their owning tabs."""
import unittest

from engine_harness import Harness, lua_table


CASES = [
    ("money", [
        ("bank", "BankState", "BankDeposits", "BankDepositsEvidence"),
        ("withdraw", "WithdrawalState", "PurposeWithdrawals", "PurposeWithdrawalsEvidence"),
    ]),
    ("property", [
        ("properties", "PropertiesState", "Properties", "PropertiesEvidence"),
    ]),
    ("safehouse", [
        ("safehouse", "SafehouseState", "SafehouseUpgrades", "SafehouseUpgradesEvidence"),
    ]),
]


class EconomyTabModuleTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.registry = self.h.load("src/engine/FeatureRegistry.luau")
        self.catalog = self.h.load("src/ui/Catalog.luau")

    def test_each_tab_owns_its_independent_descriptors(self):
        for page, rows in CASES:
            with self.subTest(page=page):
                deps = {}
                for _, reader, planner, evidence in rows:
                    deps[reader] = self.h.load("src/game/" + reader + ".luau")
                    deps[planner] = self.h.load("src/features/" + planner + ".luau")
                    deps[evidence] = self.h.load("src/features/" + evidence + ".luau")
                if page == "money":
                    deps["NativeBankCatalog"] = self.h.load(
                        "src/tabs/money/NativeBankCatalog.luau")
                    deps["config"] = {"BANK": {"depositFee": 0.1}}
                    deps["fingerprint"] = "3" * 64
                    deps["release"] = "release-a"
                if page == "property":
                    deps["NativePropertyCatalog"] = self.h.load(
                        "src/tabs/property/NativePropertyCatalog.luau")
                    deps["gameData"] = {"PROPERTIES": [
                        {"id": "p_a", "level": 1, "baseCost": 100,
                         "incomePerHour": 20}]}
                    deps["config"] = {"PROPERTY": {"costGrowth": 1.18,
                        "maxOwned": 10}}
                    deps["fingerprint"] = "3" * 64
                    deps["release"] = "release-a"
                if page == "safehouse":
                    deps["NativeSafehouseCatalog"] = self.h.load(
                        "src/tabs/safehouse/NativeSafehouseCatalog.luau")
                    deps["config"] = {"SAFEHOUSE": [
                        {"name": "Tier " + str(i), "level": i,
                         "cost": (i - 1) * 1000, "mult": 1 + i / 100}
                        for i in range(1, 19)]}
                    deps["fingerprint"] = "3" * 64
                    deps["release"] = "release-a"
                module = self.h.load("src/tabs/" + page + "/Module.luau")
                tab = module.new(lua_table(self.h.lua, deps))
                specs, reason = self.registry.fromTabs(
                    lua_table(self.h.lua, [tab]), self.catalog)
                self.assertIsNone(reason)
                self.assertEqual([specs[i]["id"] for i in range(1, len(rows)+1)],
                                 [row[0] for row in rows])
                del deps[rows[-1][3]]
                with self.assertRaises(Exception):
                    module.new(lua_table(self.h.lua, deps))


if __name__ == "__main__":
    unittest.main()
