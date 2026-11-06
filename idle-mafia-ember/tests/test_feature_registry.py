"""All implemented offline feature descriptors compose atomically."""
import unittest

from engine_harness import Harness, lua_table


MODULES = {
    "heists": ("HeistBoardState", "HeistStart", "HeistStartEvidence"),
    "heistCollect": ("HeistBoardState", "HeistCollect", "HeistCollectEvidence"),
    "favors": ("FavorsState", "FavorHelp", "FavorHelpEvidence"),
    "sabotage": ("SabotageState", "Sabotage", "SabotageEvidence"),
    "jobs": ("JobsState", "Jobs", "JobsEvidence"),
    "bosses": ("BossesState", "Bosses", "BossesEvidence"),
    "globalBossAttack": ("GlobalBossAttackState", "GlobalBossAttack", "GlobalBossAttackEvidence"),
    "globalBossClaim": ("GlobalBossClaimState", "GlobalBossClaim", "GlobalBossClaimEvidence"),
    "familyBossAttacks": ("FamilyBossAttackState", "FamilyBossAttacks", "FamilyBossAttacksEvidence"),
    "familyBossClaims": ("FamilyBossClaimState", "FamilyBossClaims", "FamilyBossClaimsEvidence"),
    "bossShop": ("BossShopBuyState", "BossShopBuy", "BossShopBuyEvidence"),
    "operations": ("OperationsState", "OperationsStart", "OperationsEvidence"),
    "collect": ("OperationsState", "OperationsCollect", "OperationsCollectEvidence"),
    "skills": ("SkillsState", "Skills", "SkillsEvidence"),
    "groupBonus": ("GroupBonusState", "GroupBonus", "GroupBonusEvidence"),
    "monthlyRewards": ("MonthlyRewardsState", "MonthlyRewards", "MonthlyRewardsEvidence"),
    "trophies": ("EarnedTrophiesState", "EarnedTrophies", "EarnedTrophiesEvidence"),
    "playtime": ("PlaytimeState", "Playtime", "PlaytimeEvidence"),
    "contracts": ("ContractEntriesState", "ContractEntries", "ContractEntriesEvidence"),
    "bonuses": ("ContractBonusesState", "ContractBonuses", "ContractBonusesEvidence"),
    "briefcases": ("FreeBriefcasesState", "FreeBriefcases", "FreeBriefcasesEvidence"),
    "bank": ("BankState", "BankDeposits", "BankDepositsEvidence"),
    "safehouse": ("SafehouseState", "SafehouseUpgrades", "SafehouseUpgradesEvidence"),
    "withdraw": ("WithdrawalState", "PurposeWithdrawals", "PurposeWithdrawalsEvidence"),
    "properties": ("PropertiesState", "Properties", "PropertiesEvidence"),
    "prestige": ("PrestigeState", "PrestigeBlocked", "PrestigeBlocked"),
    "shop": ("ShopState", "ShopBuy", "ShopBuyEvidence"),
    "familyCash": ("FamilyState", "FamilyBlocked", "FamilyBlocked"),
    "familyStamina": ("FamilyState", "FamilyBlocked", "FamilyBlocked"),
    "familyGold": ("FamilyState", "FamilyBlocked", "FamilyBlocked"),
    "marketManage": ("MarketEarningsState", "MarketEarnings", "MarketEarningsEvidence"),
}


class FeatureRegistryTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.registry = self.h.load("src/engine/FeatureRegistry.luau")
        self.catalog = self.h.load("src/ui/Catalog.luau")
        exports = {}
        for reader, planner, evidence in MODULES.values():
            exports[reader] = self.h.load("src/game/" + reader + ".luau")
            exports[planner] = self.h.load("src/features/" + planner + ".luau")
            exports[evidence] = self.h.load("src/features/" + evidence + ".luau")
        self.exports = lua_table(self.h.lua, exports)

    def test_complete_registry_matches_ui_ids_and_methods(self):
        requirements = self.registry.requirements()
        self.assertEqual({row["id"] for row in requirements.values()},
                         set(MODULES))
        requirements[1]["id"] = "changed"
        self.assertEqual(self.registry.requirements()[1]["id"], "heists")
        specs, reason = self.registry.build(self.exports, self.catalog)
        self.assertIsNone(reason)
        self.assertEqual(len(specs), len(MODULES))
        self.assertEqual({spec["id"] for spec in specs.values()}, set(MODULES))
        self.assertEqual([spec["id"] for spec in specs.values()][:6],
                         ["heists", "heistCollect", "favors", "sabotage",
                          "jobs", "bosses"])

    def test_missing_export_or_method_fails_atomically(self):
        self.exports["BankDepositsEvidence"] = None
        specs, reason = self.registry.build(self.exports, self.catalog)
        self.assertIsNone(specs)
        self.assertIn("BankDepositsEvidence", reason)
        self.exports["BankDepositsEvidence"] = lua_table(self.h.lua, {})
        self.assertIsNone(self.registry.build(self.exports, self.catalog)[0])

    def test_missing_or_duplicate_ui_feature_fails(self):
        catalog = lua_table(self.h.lua, {"features": [
            {"id": feature["id"]} for feature in self.catalog["features"].values()
            if feature["id"] != "bank"]})
        specs, reason = self.registry.build(self.exports, catalog)
        self.assertIsNone(specs)
        self.assertIn("bank", reason)
        catalog = lua_table(self.h.lua, {"features": [
            {"id": feature["id"]} for feature in self.catalog["features"].values()
        ] + [{"id": "bank"}]})
        self.assertIsNone(self.registry.build(self.exports, catalog)[0])

    def test_modular_tab_descriptors_match_their_ui_page(self):
        entry = self.h.load("src/tabs/jobs/Module.luau")
        tab = entry.new(lua_table(self.h.lua, {
            "NativeJobCatalog": self.h.load(
                "src/tabs/jobs/NativeJobCatalog.luau"),
            "JobsState": self.exports["JobsState"],
            "Jobs": self.exports["Jobs"],
            "JobsEvidence": self.exports["JobsEvidence"],
            "gameData": {"JOBS": [{"id": "j_watch", "level": 1,
                "energy": 1, "cash": 60, "xp": 2}]},
            "config": {"MASTERY": [{"completions": 25,
                "energyDiscount": 0}]},
            "fingerprint": "a" * 64, "release": "release-a",
        }))
        specs, reason = self.registry.fromTabs(
            lua_table(self.h.lua, [tab]), self.catalog)
        self.assertIsNone(reason)
        self.assertEqual(len(specs), 1)
        self.assertEqual(specs[1]["id"], "jobs")
        self.assertIsNone(self.registry.fromTabs(
            lua_table(self.h.lua, [tab, tab]), self.catalog)[0])
        tab["id"] = "heists"
        self.assertIsNone(self.registry.fromTabs(
            lua_table(self.h.lua, [tab]), self.catalog)[0])

    def test_sparse_tab_list_fails_before_descriptor_load(self):
        tabs = self.h.lua.table()
        tabs[1] = self.h.lua.execute("return { id = 'jobs' }")
        tabs[3] = self.h.lua.execute("return { id = 'operations' }")
        specs, reason = self.registry.fromTabs(tabs, self.catalog)
        self.assertIsNone(specs)
        self.assertEqual(reason, "Missing tab registry inputs")


if __name__ == "__main__":
    unittest.main()
