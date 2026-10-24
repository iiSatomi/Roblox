"""All current offline descriptors compose through tab-owned modules."""
import unittest

from engine_harness import Harness, lua_table


PAGES = ("heists", "jobs", "operations", "favors", "combat", "crew", "inventory", "collection", "money",
         "property", "safehouse", "prestige", "shop", "contracts", "trophies", "skills",
         "rewards", "events", "blackMarket", "family", "territory")


class AllTabCompositionTests(unittest.TestCase):
    def test_all_current_descriptors_and_two_source_adapters(self):
        h = Harness()
        registry = h.load("src/engine/FeatureRegistry.luau")
        deps = {
            "SimpleTab": h.load("src/tabs/SimpleTab.luau"),
            "NativeJobCatalog": h.load("src/tabs/jobs/NativeJobCatalog.luau"),
            "NativeOperationsCatalog": h.load(
                "src/tabs/operations/NativeOperationsCatalog.luau"),
            "NativeHeistCatalog": h.load(
                "src/tabs/heists/NativeHeistCatalog.luau"),
            "SequenceRecovery": h.load(
                "src/tabs/heists/SequenceRecovery.luau"),
            "BoardQuery": h.load("src/tabs/heists/BoardQuery.luau"),
            "HitListQuery": h.load("src/tabs/combat/HitListQuery.luau"),
            "PlayerTargetState": h.load("src/tabs/combat/PlayerTargetState.luau"),
            "BlockedFight": h.load("src/tabs/combat/BlockedFight.luau"),
            "RosterState": h.load("src/tabs/crew/RosterState.luau"),
            "AutoEquipCrew": h.load("src/tabs/crew/AutoEquipCrew.luau"),
            "CrewSort": h.load("src/tabs/crew/CrewSort.luau"),
            "CrewHeal": h.load("src/tabs/crew/CrewHeal.luau"),
            "CrewTrain": h.load("src/tabs/crew/CrewTrain.luau"),
            "CrewHire": h.load("src/tabs/crew/CrewHire.luau"),
            "CrewHealItems": h.load(
                "src/tabs/crew/CrewHealItems.luau"),
            "NativeHireCatalog": h.load(
                "src/tabs/crew/NativeHireCatalog.luau"),
            "NativeHealItemCatalog": h.load(
                "src/tabs/crew/NativeHealItemCatalog.luau"),
            "CrewGear": h.load("src/tabs/crew/CrewGear.luau"),
            "CrewRollState": h.load(
                "src/tabs/crew/CrewRollState.luau"),
            "Restoratives": h.load(
                "src/tabs/inventory/Restoratives.luau"),
            "NativeRestorativeCatalog": h.load(
                "src/tabs/inventory/NativeRestorativeCatalog.luau"),
            "Chests": h.load("src/tabs/inventory/Chests.luau"),
            "NativeCrateCatalog": h.load(
                "src/tabs/inventory/NativeCrateCatalog.luau"),
            "Cosmetics": h.load(
                "src/tabs/inventory/Cosmetics.luau"),
            "CollectionDonate": h.load(
                "src/tabs/collection/CollectionDonate.luau"),
            "NativeCollectionCatalog": h.load(
                "src/tabs/collection/NativeCollectionCatalog.luau"),
            "NativeBankCatalog": h.load(
                "src/tabs/money/NativeBankCatalog.luau"),
            "NativePropertyCatalog": h.load(
                "src/tabs/property/NativePropertyCatalog.luau"),
            "NativeSafehouseCatalog": h.load(
                "src/tabs/safehouse/NativeSafehouseCatalog.luau"),
            "PrestigeState": h.load(
                "src/game/PrestigeState.luau"),
            "PrestigeBlocked": h.load(
                "src/features/PrestigeBlocked.luau"),
            "NativeShopCatalog": h.load(
                "src/tabs/shop/NativeShopCatalog.luau"),
            "MarketBrowse": h.load("src/features/MarketBrowse.luau"),
            "MarketPrices": h.load("src/features/MarketPrices.luau"),
            "MarketReadRuntime": h.load(
                "src/features/MarketReadRuntime.luau"),
            "MarketBlocked": h.load(
                "src/tabs/blackMarket/MarketBlocked.luau"),
            "FamilyQuery": h.load(
                "src/tabs/family/FamilyQuery.luau"),
            "TerritoryMapQuery": h.load(
                "src/tabs/territory/TerritoryMapQuery.luau"),
            "ResidencyQuery": h.load(
                "src/tabs/territory/ResidencyQuery.luau"),
            "TerritoryState": h.load(
                "src/tabs/territory/TerritoryState.luau"),
            "ReadAttachment": h.load(
                "src/tabs/territory/ReadAttachment.luau"),
            "TerritoryBlocked": h.load(
                "src/tabs/territory/TerritoryBlocked.luau"),
            "ContractGoalState": h.load(
                "src/tabs/contracts/ContractGoalState.luau"),
            "ContractGoalBlocked": h.load(
                "src/tabs/contracts/ContractGoalBlocked.luau"),
            "ContractCashQuote": h.load(
                "src/tabs/contracts/ContractCashQuote.luau"),
            "NativeContractCatalog": h.load(
                "src/tabs/contracts/NativeContractCatalog.luau"),
            "NativeTrophyCatalog": h.load(
                "src/tabs/trophies/NativeTrophyCatalog.luau"),
            "TrophyFocusState": h.load(
                "src/tabs/trophies/TrophyFocusState.luau"),
            "TrophyFocusBlocked": h.load(
                "src/tabs/trophies/TrophyFocusBlocked.luau"),
            "NativeSkillCatalog": h.load(
                "src/tabs/skills/NativeSkillCatalog.luau"),
            "NativeRewardsCatalog": h.load(
                "src/tabs/rewards/NativeRewardsCatalog.luau"),
            "EventShopBlocked": h.load(
                "src/tabs/events/EventShopBlocked.luau"),
            "gearSets": h.lua.execute("""return {slotBonus =
                function() return 0, 0 end}"""),
            "NativeTrainingCatalog": h.load(
                "src/tabs/crew/NativeTrainingCatalog.luau"),
            "combatRules": {"hospitalHealth": 20,
                            "staminaCost": 1, "dailyTargetCap": 5},
            "identity": h.session,
            "gameData": {"HEISTS": [{"id": "h_a", "level": 1,
                                     "stake": 100, "energy": 2,
                                     "crateCount": 1}],
                         "JOBS": [{"id": "j_watch", "level": 1,
                                  "energy": 1, "cash": 10, "xp": 2}],
                         "ITEMS": [{"id": "t_eldersignet",
                                    "kind": "trophy"}],
                         "TROPHY_TRADE_INS": {},
                         "OPERATIONS": [{"id": "op_fence", "duration": 60,
                                         "cost": 10, "cash": 20, "xp": 2}],
                         "CRATES": {},
                         "PROPERTIES": [{"id": "p_a", "level": 1,
                             "baseCost": 100, "incomePerHour": 20}],
                         "SHOP": [{"item": "w_a", "price": 100}],
                         "ITEMS_BY_ID": {item: {"id": item,
                            "kind": "consumable", "restore": {
                                "pool": pool, "percent": percent}}
                            for item, pool, percent in (
                                ("con_bandages", "health", 25),
                                ("con_medkit_small", "health", 50),
                                ("con_medkit_large", "health", 100),
                                ("con_energy_small", "energy", 25),
                                ("con_energy", "energy", 50),
                                ("con_energy_pack", "energy", 100),
                                ("con_peanuts", "stamina", 25),
                                ("con_sandwich", "stamina", 50),
                                ("con_lunchbox", "stamina", 100))}
                            | {"crate_a": {"id": "crate_a",
                                           "kind": "crate"},
                               "bg_a": {"id": "bg_a",
                                        "kind": "background",
                                        "atk": 1, "def": 1},
                               "w_a": {"id": "w_a", "kind": "weapon",
                                       "rarity": 4, "atk": 2,
                                       "def": 1}}},
            "config": {"MASTERY": [{"completions": 10,
                                     "energyDiscount": 0}],
                       "LEVEL": {"allocation": {
                           stat: ({"baseCost": 1, "costMultiplier": 2}
                                  if stat == "property" else
                                  {"baseCost": 1,
                                   "costEvery": 3 if stat in
                                       ("attack", "defense") else 5})
                           for stat in ("energy", "stamina", "health",
                                        "attack", "defense", "property")}},
                       "LADDER": [{"seconds": i * 300,
                                   "kind": "energy"} for i in range(1, 8)],
                       "LADDER_TIERS": [1, 10, 30, 102],
                       "GROUP": {"id": 674050067},
                       "MONTHLY_CALENDAR": {"enabled": False},
                       "CRATE_BATCH_MAX": 10,
                       "BANK": {"depositFee": 0.1},
                       "PROPERTY": {"costGrowth": 1.18,
                           "maxOwned": 10},
                       "SAFEHOUSE": [{"name": "Tier " + str(i),
                           "level": i, "cost": (i - 1) * 1000,
                           "mult": 1 + i / 100}
                           for i in range(1, 19)],
                       "PRESTIGE": {"maxRank": 6,
                           "levelByRank": [200, 200, 200, 210, 220, 230]},
                       "COLLECTION": {"bonusByRarity": [1, 2, 3, 5],
                           "tiers": [{"count": 1, "mult": 1},
                                     {"count": 10, "mult": 2}]},
                       "TERRITORY": {"injurySeconds": 1200},
                       "CONSUMABLES": {"cooldownSeconds": 3,
                                       "henchmanCooldownSeconds": 3},
                       "CONTRACTS": {"DAILY_TIERS": [1, 1, 2, 2, 3],
                           "WEEKLY_TIERS": [4, 4, 4, 4, 4],
                           "TEMPLATES": [{"id": "c_jobs", "key": "jobs"}],
                           "BONUS": {"seals": 2, "energyRefill": True},
                           "WEEKLY_BONUS": {"seals": 12,
                               "crate": "crate_fixervault"}},
                       "CREW": {"hireTiers": [
                           {"id": "street", "cost": 10000}],
                           "training": {"minRarity": 4,
                           "maxLevel": 1, "maxConcurrent": 1,
                           "cost": {i: [100] for i in range(4, 9)},
                           "minutes": {i: [5] for i in range(4, 9)}}}},
            "fingerprint": "a" * 64, "release": "release-a",
        }
        for row in registry.requirements().values():
            for name, folder in ((row["reader"], "game"),
                                 (row["planner"], "features"),
                                 (row["evidence"], "features")):
                if name not in deps:
                    deps[name] = h.load("src/" + folder + "/" + name + ".luau")
        deps["Catalog"] = h.load("src/ui/Catalog.luau")
        deps["FeatureRegistry"] = registry
        deps["TabComposition"] = h.load("src/tabs/TabComposition.luau")
        deps["TabSnapshotAssembler"] = h.load(
            "src/tabs/TabSnapshotAssembler.luau")
        for page in PAGES:
            deps[page[0].upper() + page[1:] + "Tab"] = h.load(
                "src/tabs/" + page + "/Module.luau")
        injected = lua_table(h.lua, deps)
        assembly = h.load("src/engine/RuntimeAssembly.luau")
        result, reason = assembly.compose(injected)
        self.assertIsNone(reason)
        expected = {row["id"] for row in registry.requirements().values()}
        expected.update(("combat", "warCombat", "crew", "crewGear",
                         "crewRoll", "crewSort",
                         "crewHeal", "crewTrain", "crewHire",
                         "crewHealItems", "restoratives", "chests",
                         "cosmetics", "collectionDonate", "autoContracts",
                         "trophyFocus", "eventShop", "territoryWatch",
                         "station", "residency", "marketWatch",
                         "marketSell", "marketFlip", "marketRent"))
        self.assertEqual({spec["id"] for spec in result["features"].values()},
                         expected)
        catalog_ids = {feature["id"] for feature in deps["Catalog"]["features"].values()}
        self.assertEqual(expected, catalog_ids,
                         "Every visible switch needs a loaded tab descriptor")
        for lane in (deps["MarketBlocked"]["watch"],
                     deps["MarketBlocked"]["trade"]):
            self.assertIsNone(lane.read()[0])
            self.assertIsNone(lane.propose()[0])
            self.assertIsNone(lane.capture()[0])
            self.assertEqual(lane.evaluate(), "pending")
        pages = {spec["id"]: spec["page"]
                 for spec in result["features"].values()}
        self.assertEqual(pages["jobs"], "jobs")
        self.assertEqual(pages["sabotage"], "heists")
        self.assertEqual(pages["collect"], "operations")
        raw = h.snapshot(native={"fullSync": True})
        enriched, reasons = result["snapshotAssembler"].Enrich(
            result["snapshotAssembler"], raw)
        self.assertIsNone(reasons["jobs"])
        self.assertIsNone(reasons["operations"])
        self.assertIsNone(reasons["heists"])
        self.assertEqual(enriched["heistCatalog"][1]["id"], "h_a")
        self.assertEqual(enriched["jobCatalog"][1]["id"], "j_watch")
        self.assertEqual(enriched["operationCatalog"][1]["id"], "op_fence")
        self.assertEqual(enriched["trainingCatalog"]["cost"][4][1], 100)
        self.assertEqual(enriched["hireCatalog"]["tiers"]["street"], 10000)
        self.assertEqual(enriched["contractTemplates"][1]["key"], "jobs")
        self.assertEqual(enriched["skillRules"]["property"]
                         ["costMultiplier"], 2)
        self.assertEqual(enriched["groupConfig"]["id"], 674050067)
        self.assertFalse(enriched["monthlyConfig"]["enabled"])
        self.assertEqual(enriched["healItemCatalog"]["items"]
                         ["con_bandages"], 25)
        self.assertEqual(enriched["restorativeCatalog"]["items"][1]
                         ["id"], "con_bandages")
        self.assertTrue(enriched["ownedCrateCatalog"]["crates"]["crate_a"])
        self.assertEqual(enriched["collectionCatalog"]["items"]
                         ["w_a"]["rarity"], 4)
        self.assertEqual(enriched["gearSourceKey"], "a" * 64)
        self.assertEqual(enriched["cosmeticSourceKey"], "a" * 64)
        context_module = h.load("src/game/Context.luau")
        context = context_module.new(h.contracts)
        view, reason = context.Read(context, enriched,
            lua_table(h.lua, h.session), 0, 2)
        self.assertIsNone(reason)
        for key in ("trainingCatalogKey", "hireCatalogKey",
                    "healItemCatalogKey", "restorativeCatalogKey",
                    "crateCatalogKey", "collectionCatalogKey",
                    "gearSourceKey", "cosmeticSourceKey"):
            self.assertEqual(view[key], "a" * 64, key)
        self.assertEqual(enriched["bankConfig"]["depositFee"], 0.1)
        injected.AutomationRuntime = h.load(
            "src/engine/AutomationRuntime.luau")
        for name, folder in (("Journal", "engine"), ("Broker", "engine"),
                             ("Checkpoint", "storage"), ("Session", "engine"),
                             ("Contracts", "engine"), ("Scheduler", "engine"),
                             ("Context", "game"), ("EconomyContext", "game"),
                             ("BuffContext", "game"), ("HeistBoardState", "game"),
                             ("BossStageState", "game"), ("GlobalBossState", "game"),
                             ("BossShopState", "game"),
                             ("FamilyTakedownState", "game")):
            injected[name] = h.load("src/" + folder + "/" + name + ".luau")
        injected.clock = h.clock
        injected.transport = h.transport
        injected.storage = h.lua.execute("""return {strictRecovery = true,
            data = {}, Read = function(self, key) return self.data[key] end,
            Write = function(self, key, value)
                self.data[key] = value; return true
            end }""")
        runtime, reason = assembly.start(injected)
        self.assertIsNone(reason)
        self.assertEqual(len(list(runtime["features"].items())), len(expected))
        self.assertEqual(runtime.Status(runtime)["state"], "paused")
        self.assertEqual(len(h.transport["sent"]), 0)
        injected.TerritoryTab = None
        missing, reason = assembly.compose(injected)
        self.assertIsNone(missing)
        self.assertIn("territory", reason)


if __name__ == "__main__":
    unittest.main()
