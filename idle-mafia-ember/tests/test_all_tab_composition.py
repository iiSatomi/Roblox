"""All current offline descriptors compose through tab-owned modules."""
import unittest

from engine_harness import Harness, lua_table


PAGES = ("heists", "jobs", "operations", "favors", "combat", "crew", "inventory", "collection", "money",
         "property", "safehouse", "prestige", "shop", "contracts", "trophies", "skills",
         "rewards", "events", "blackMarket", "family", "territory")


class AllTabCompositionTests(unittest.TestCase):
    def test_all_current_descriptors_and_owned_source_adapters(self):
        h = Harness()
        registry = h.load("src/engine/FeatureRegistry.luau")
        deps = {
            "MarketSettings": h.load("src/tabs/blackMarket/MarketSettings.luau"),
            "SimpleTab": h.load("src/tabs/SimpleTab.luau"),
            "NativeJobCatalog": h.load("src/tabs/jobs/NativeJobCatalog.luau"),
            "NativeOperationsCatalog": h.load(
                "src/tabs/operations/NativeOperationsCatalog.luau"),
            "NativeHeistCatalog": h.load(
                "src/tabs/heists/NativeHeistCatalog.luau"),
            "SequenceRecovery": h.load(
                "src/tabs/heists/SequenceRecovery.luau"),
            "BoardQuery": h.load("src/tabs/heists/BoardQuery.luau"),
            "BoardReadRuntime": h.load(
                "src/tabs/heists/BoardReadRuntime.luau"),
            "HitListQuery": h.load("src/tabs/combat/HitListQuery.luau"),
            "PlayerProfileQuery": h.load("src/tabs/combat/PlayerProfileQuery.luau"),
            "nativeReadSource": h.lua.execute("return {Current=function() return true end,Friendship=function() return false end}"),
            "FightReceipts": h.load("src/tabs/combat/FightReceipts.luau"),
            "PlayerFightUsage": h.load("src/tabs/combat/PlayerFightUsage.luau"),
            "PlayerFightEvidence": h.load("src/tabs/combat/PlayerFightEvidence.luau"),
            "PlayerScoutEvidence": h.load("src/tabs/combat/PlayerScoutEvidence.luau"),
            "PlayerFightPlanner": h.load("src/tabs/combat/PlayerFightPlanner.luau"),
            "TargetSelection": h.load("src/tabs/combat/TargetSelection.luau"),
            "PlayerFightLedger": h.load("src/tabs/combat/PlayerFightLedger.luau"),
            "PlayerTargetState": h.load("src/tabs/combat/PlayerTargetState.luau"),
            "BlockedFight": h.load("src/tabs/combat/BlockedFight.luau"),
            "FamilyBossQuery": h.load("src/tabs/combat/FamilyBossQuery.luau"),
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
            "PrestigeReset": h.load("src/tabs/prestige/PrestigeReset.luau"),
            "PrestigeBlocked": h.load(
                "src/features/PrestigeBlocked.luau"),
            "NativeShopCatalog": h.load(
                "src/tabs/shop/NativeShopCatalog.luau"),
            "MarketBrowse": h.load("src/features/MarketBrowse.luau"),
            "MarketPrices": h.load("src/features/MarketPrices.luau"),
            "MarketRap": h.load("src/features/MarketRap.luau"),
            "MarketListingsState": h.load(
                "src/tabs/blackMarket/MarketListingsState.luau"),
            "MarketSaleCustody": h.load(
                "src/tabs/blackMarket/MarketSaleCustody.luau"),
            "MarketSaleQuote": h.load(
                "src/tabs/blackMarket/MarketSaleQuote.luau"),
            "MarketBrowsePages": h.load(
                "src/tabs/blackMarket/MarketBrowsePages.luau"),
            "MarketListEvidence": h.load(
                "src/tabs/blackMarket/MarketListEvidence.luau"),
            "MarketRentQuote": h.load(
                "src/tabs/blackMarket/MarketRentQuote.luau"),
            "MarketRentEvidence": h.load(
                "src/tabs/blackMarket/MarketRentEvidence.luau"),
            "NativeMarketCatalog": h.load(
                "src/tabs/blackMarket/NativeMarketCatalog.luau"),
            "MarketWatchOpportunity": h.load(
                "src/tabs/blackMarket/MarketWatchOpportunity.luau"),
            "MarketResearchView": h.load(
                "src/tabs/blackMarket/MarketResearchView.luau"),
            "MarketTransactions": h.load(
                "src/tabs/blackMarket/MarketTransactions.luau"),
            "MarketAgingReview": h.load(
                "src/tabs/blackMarket/MarketAgingReview.luau"),
            "MarketFlipPreflight": h.load(
                "src/tabs/blackMarket/MarketFlipPreflight.luau"),
            "MarketBuyEvidence": h.load(
                "src/tabs/blackMarket/MarketBuyEvidence.luau"),
            "MarketFlipListPreflight": h.load(
                "src/tabs/blackMarket/MarketFlipListPreflight.luau"),
            "MarketCollectionWithdrawPreflight": h.load(
                "src/tabs/blackMarket/MarketCollectionWithdrawPreflight.luau"),
            "MarketCollectionWithdrawEvidence": h.load(
                "src/tabs/blackMarket/MarketCollectionWithdrawEvidence.luau"),
            "MarketSellListPreflight": h.load(
                "src/tabs/blackMarket/MarketSellListPreflight.luau"),
            "MarketSellDirectPreflight": h.load(
                "src/tabs/blackMarket/MarketSellDirectPreflight.luau"),
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
            "RewardEffects": h.load("src/tabs/rewards/RewardEffects.luau"),
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
                       "TERRITORY": {"injurySeconds": 1200,
                           "healStaminaCost": 5, "healSeconds": 300},
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
        injected.NativeEventShopSource = h.load('src/tabs/events/NativeEventShopSource.luau')
        injected.EventShopBuyer = h.load('src/tabs/events/EventShopBuyer.luau')
        event_definition = lua_table(h.lua, {'MEDAL': 'event_medal','MAX_ITEM_COUNT': 99,
            'ROWS': [{'key': 'gold','kind': 'item','item': 'gold_bar','price': 3,'count': 1}]})
        event_attributes = lua_table(h.lua, {'GlobalEventShop': True,'GlobalEventShopEnd': 2000})
        h.lua.globals().assemblyEventAttributes = event_attributes
        injected.eventShopSource = injected.NativeEventShopSource.new(event_definition,
            h.lua.eval('function() return assemblyEventAttributes end'), 'a' * 64, 'release-a')[0]
        for name in ("TerritoryReadSources", "DistrictQuery", "FortificationQuery"):
            injected[name] = h.load("src/tabs/territory/" + name + ".luau")
        assembly = h.load("src/engine/RuntimeAssembly.luau")
        result, reason = assembly.compose(injected)
        self.assertIsNone(reason)
        event_descriptor = next(spec for spec in result.features.values() if spec.id == 'eventShop')
        self.assertIsNotNone(event_descriptor.canDispatch)
        event_raw = h.snapshot(native={'fullSync': True,'serverNow': 1000})
        event_enriched = injected.eventShopSource.Enrich(injected.eventShopSource, event_raw)[0]
        event_proposal = h.proposal('eventShop', 'buy')
        event_proposal.intent = lua_table(h.lua, {'sourceKey': 'a' * 64,
            'sourceGeneration': event_enriched.eventShopProof.sourceGeneration})
        self.assertTrue(event_descriptor.canDispatch(event_proposal))
        event_attributes.GlobalEventShop = False
        self.assertFalse(event_descriptor.canDispatch(event_proposal))
        event_attributes.GlobalEventShop = True
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
        self.assertEqual(enriched["healRules"]["healStaminaCost"], 5)
        self.assertEqual(enriched["healRules"]["healSeconds"], 300)
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
                             ("ResourceReservations", "engine"),
                             ("AllowanceReset", "engine"),
                             ("EventShopUsage", "tabs/events"),
                             ("PendingAction", "storage"),
                             ("Contracts", "engine"), ("Scheduler", "engine"),
                             ("Context", "game"), ("EconomyContext", "game"),
                             ("BuffContext", "game"), ("HeistBoardState", "game"),
                             ("BossStageState", "game"), ("GlobalBossState", "game"),
                             ("BossShopState", "game"),
                             ("FamilyTakedownState", "game")):
            injected[name] = h.load("src/" + folder + "/" + name + ".luau")
        injected.clock = h.clock
        injected.requestLane = h.load("src/engine/RequestLane.luau").new(h.clock)
        injected.ReadCoordinator = h.load("src/transport/ReadCoordinator.luau")
        injected.ReadBudget = h.load("src/engine/ReadBudget.luau")
        injected.nativeReader = h.load("src/transport/NativeSnapshotReader.luau").new(
            lua_table(h.lua, h.session), h.clock, "a" * 64)
        injected.nativeExecutor = h.lua.execute("""return {
            Schedule=function() error('All-off read scheduled') end,
            InvokeOwned=function() error('All-off read invoked') end}""")
        injected.transport = h.transport
        injected.storage = h.lua.execute("""return {strictRecovery = true,
            data = {}, Read = function(self, key) return self.data[key] end,
            Write = function(self, key, value)
                self.data[key] = value; return true
            end }""")
        injected.MarketResearchController = h.load("src/tabs/blackMarket/MarketResearchController.luau")
        for name in ('MarketRentRuntime','MarketRentUsage','MarketPayoutLedger'):
            injected[name] = h.load('src/tabs/blackMarket/' + name + '.luau')
        injected.config.MARKET = lua_table(h.lua, {"minLevel": 20, "slots": 5, "maxSlots": 20,
            "rentPerPeriod": 1, "rentPeriodHours": 12, "rentMaxDays": 7, "feePct": .1,
            "permanentFeePct": .07, "minFee": 1, "minPrice": 2, "maxPrice": 9999999,
            "maxPages": 5, "maxQuantity": 999, "minPriceByRarity": {5: 3}})
        for name in ('CrewReplacement','CrewReplacementTransactions','CrewReplacementRuntime','CrewRecoveryReview'):
            injected[name] = h.load('src/tabs/crew/' + name + '.luau')
        injected.config.CREW.hireTiers[1].odds = lua_table(h.lua,[50,30,20,0,0,0,0,0])
        injected.config.CREW.hireTiers[1].oddsLucky = lua_table(h.lua,[40,30,30,0,0,0,0,0])
        runtime, reason = assembly.start(injected)
        self.assertIsNone(reason)
        self.assertEqual(len(list(runtime["features"].items())), len(expected))
        self.assertEqual(runtime.Status(runtime)["state"], "paused")
        self.assertIsNotNone(runtime.readCoordinator)
        self.assertIsNotNone(runtime.features.crewRoll.lifecycle)
        self.assertTrue(runtime.SupportsFeatureRecovery(runtime,'crewRoll'))
        crew_tab = next(tab for tab in runtime.tabInstances.values() if tab.id == 'crew')
        self.assertIsNotNone(crew_tab.replacementOwner)
        self.assertTrue(runtime.SupportsAllowanceReset(runtime))
        market_tab = next(tab for tab in runtime.tabInstances.values() if tab.id == "blackMarket")
        self.assertIsNotNone(market_tab.transactions)
        self.assertIsNotNone(market_tab.research)
        self.assertIsNotNone(market_tab.payoutLedger)
        self.assertIsNotNone(market_tab.rentCatalog)
        self.assertIsNotNone(runtime.features.marketManage.recordOutcome)
        self.assertIsNotNone(runtime.features.marketRent.recoverSaved)
        rent_proof = runtime.checkpoint.MarketRentUsage(runtime.checkpoint,h.snapshot())[0]
        self.assertEqual((rent_proof.attempted,rent_proof.spent),(0,0))
        proposal = h.proposal("marketRent", "rent")
        proposal.intent = lua_table(h.lua, {"kind": "marketRent", "periods": 1, "cost": 1, "durationSeconds": 43200})
        held_raw = h.snapshot(native={"fullSync": True, "serverNow": 1000,
            "inventory": {"gold_bar": 8}, "inventoryBound": {}, "market": {"shopUntil": 900}})
        self.assertTrue(market_tab.transactions.PrepareRent(market_tab.transactions, proposal, held_raw)[0])
        held, hold_reason = runtime.reservationOwner.Held(runtime.reservationOwner, held_raw)
        self.assertIsNone(hold_reason)
        self.assertEqual(held["items"]["L:gold_bar"], 1)
        # Actual tab lifecycle observes exact saved rental state while all
        # features are off; it must never resubmit the old command.
        self.assertTrue(market_tab.transactions.MarkSending(market_tab.transactions)[0])
        runtime.Step(runtime, held_raw, h.lua.table())
        self.assertEqual(market_tab.transactions.Active(market_tab.transactions).stage, "sent")
        recovered = h.snapshot(revision=2, native={"fullSync": True, "serverNow": 1002,
            "inventory": {"gold_bar": 7}, "inventoryBound": {}, "market": {"shopUntil": 44200}})
        runtime.Step(runtime, recovered, h.lua.table())
        self.assertEqual(market_tab.transactions.Active(market_tab.transactions).stage, "observed")
        self.assertIsNone(runtime.reservationOwner.Held(runtime.reservationOwner, recovered)[0]["items"]["L:gold_bar"])
        self.assertEqual(len(h.transport.sent), 0)
        self.assertEqual({row.id for row in runtime.readSources.values()}, {"combatHitList", "combatSavedSearch", "combatProfile", "combatWarRoster", "combatWarProfile", "familyBoss", "heistBoard",
            "territoryMap", "territoryDistrict", "residencyView", "fortificationView",
            "marketBrowse", "marketRap", "marketPrices", "marketSellBrowse",
            "marketSellRap", "marketSellPrices", "marketFlipBrowse", "marketFlipRap", "marketFlipPrices", "marketFlipListBrowse", "marketFlipListRap", "marketFlipListPrices"})
        self.assertEqual(len(h.transport["sent"]), 0)
        injected.automationRuntimeInstance = runtime
        injected.allowedFeatures = lua_table(h.lua, {
            "jobs": True, "bosses": True})
        injected.Settings = h.load("src/storage/Settings.luau")
        injected.EmberAdapter = h.load("src/ui/EmberAdapter.luau")
        injected.Ember = h.load("tests/ember_double.lua")()
        app = h.load("src/App.luau").start(injected)
        self.assertFalse(app.model.paused)
        self.assertIn("Runtime connected", app.ui.window.options.StatusBar.Text)
        self.assertFalse(app.Set(app, "shop.enabled", True)[0])
        self.assertFalse(app.Set(app, "operations.enabled", True)[0])
        self.assertTrue(app.Set(app, "jobs.enabled", True)[0])
        self.assertTrue(app.Set(app, "bosses.enabled", True)[0])
        self.assertEqual(len(h.transport["sent"]), 0)
        app.Destroy(app)
        self.assertTrue(runtime.readCoordinator.Status(runtime.readCoordinator).closed)
        self.assertIsNone(injected.eventShopSource.Enrich(injected.eventShopSource, event_raw)[0])
        injected.nativeReader.Close(injected.nativeReader)
        injected.TerritoryTab = None
        missing, reason = assembly.compose(injected)
        self.assertIsNone(missing)
        self.assertIn("territory", reason)


if __name__ == "__main__":
    unittest.main()
