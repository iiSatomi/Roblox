"""Remaining offline descriptors load under their UI pages."""
import unittest

from engine_harness import Harness, lua_table


PAGES = ("blackMarket",)


class SimpleTabModuleTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.registry = self.h.load("src/engine/FeatureRegistry.luau")
        self.catalog = self.h.load("src/ui/Catalog.luau")
        self.deps = {"SimpleTab": self.h.load("src/tabs/SimpleTab.luau"),
            "MarketSettings": self.h.load("src/tabs/blackMarket/MarketSettings.luau"),
            "MarketBrowse": self.h.load("src/features/MarketBrowse.luau"),
            "MarketPrices": self.h.load("src/features/MarketPrices.luau"),
            "MarketRap": self.h.load("src/features/MarketRap.luau"),
            "MarketListingsState": self.h.load(
                "src/tabs/blackMarket/MarketListingsState.luau"),
            "MarketSaleCustody": self.h.load(
                "src/tabs/blackMarket/MarketSaleCustody.luau"),
            "MarketSaleQuote": self.h.load(
                "src/tabs/blackMarket/MarketSaleQuote.luau"),
            "MarketBrowsePages": self.h.load(
                "src/tabs/blackMarket/MarketBrowsePages.luau"),
            "MarketListEvidence": self.h.load(
                "src/tabs/blackMarket/MarketListEvidence.luau"),
            "MarketRentQuote": self.h.load(
                "src/tabs/blackMarket/MarketRentQuote.luau"),
            "MarketRentEvidence": self.h.load(
                "src/tabs/blackMarket/MarketRentEvidence.luau"),
            "NativeMarketCatalog": self.h.load(
                "src/tabs/blackMarket/NativeMarketCatalog.luau"),
            "MarketWatchOpportunity": self.h.load(
                "src/tabs/blackMarket/MarketWatchOpportunity.luau"),
            "MarketResearchView": self.h.load(
                "src/tabs/blackMarket/MarketResearchView.luau"),
            "MarketTransactions": self.h.load(
                "src/tabs/blackMarket/MarketTransactions.luau"),
            "MarketAgingReview": self.h.load(
                "src/tabs/blackMarket/MarketAgingReview.luau"),
            "MarketFlipPreflight": self.h.load(
                "src/tabs/blackMarket/MarketFlipPreflight.luau"),
            "MarketBuyEvidence": self.h.load(
                "src/tabs/blackMarket/MarketBuyEvidence.luau"),
            "MarketFlipListPreflight": self.h.load(
                "src/tabs/blackMarket/MarketFlipListPreflight.luau"),
            "MarketCollectionWithdrawPreflight": self.h.load(
                "src/tabs/blackMarket/MarketCollectionWithdrawPreflight.luau"),
            "MarketCollectionWithdrawEvidence": self.h.load(
                "src/tabs/blackMarket/MarketCollectionWithdrawEvidence.luau"),
            "MarketSellListPreflight": self.h.load(
                "src/tabs/blackMarket/MarketSellListPreflight.luau"),
            "MarketSellDirectPreflight": self.h.load(
                "src/tabs/blackMarket/MarketSellDirectPreflight.luau"),
            "MarketBlocked": self.h.load(
                "src/tabs/blackMarket/MarketBlocked.luau"),
            "MarketReadRuntime": self.h.load(
                "src/features/MarketReadRuntime.luau")}
        for row in self.registry.requirements().values():
            for name, folder in ((row["reader"], "game"),
                                 (row["planner"], "features"),
                                 (row["evidence"], "features")):
                if name not in self.deps:
                    self.deps[name] = self.h.load(
                        "src/" + folder + "/" + name + ".luau")

    def test_remaining_tab_entries_match_catalog_pages(self):
        tabs = []
        deps = lua_table(self.h.lua, self.deps)
        for page in PAGES:
            entry = self.h.load("src/tabs/" + page + "/Module.luau")
            tabs.append(entry.new(deps))
        specs, reason = self.registry.fromTabs(
            lua_table(self.h.lua, tabs), self.catalog)
        self.assertIsNone(reason)
        self.assertEqual(len(specs), 5)
        self.assertEqual({spec["id"] for spec in specs.values()}, {
            "marketWatch", "marketSell", "marketFlip",
            "marketRent", "marketManage"})

    def test_missing_module_blocks_owning_tab(self):
        del self.deps["MarketEarningsEvidence"]
        entry = self.h.load("src/tabs/blackMarket/Module.luau")
        with self.assertRaises(Exception):
            entry.new(lua_table(self.h.lua, self.deps))

    def test_black_market_tab_builds_rap_research_without_gameplay_send(self):
        entry = self.h.load("src/tabs/blackMarket/Module.luau")
        tab = entry.new(lua_table(self.h.lua, self.deps))
        budget = self.h.load("src/engine/ReadBudget.luau").new(
            self.h.clock, lua_table(self.h.lua, [
                {"id": "marketRap", "interval": 120}]), 8, 300)
        executor = self.h.lua.execute("""return {
            queued = {}, calls = 0,
            Schedule = function(self, callback)
                self.queued[#self.queued + 1] = callback
            end,
            Invoke = function(self, remote, method, command, ids)
                self.calls = self.calls + 1
                assert(remote == 'MarketAction' and command == 'rap')
                return { ok = true, values = {
                    [ids[1]] = { quantity = 1, sales = 2,
                        average = 3, available = true },
                } }
            end,
            Drain = function(self)
                for _, callback in ipairs(self.queued) do callback() end
                self.queued = {}
            end,
        }""")
        received = self.h.lua.table_from([])
        self.h.lua.globals().market_result = received
        callback = self.h.lua.eval("""function(kind, result)
            market_result[#market_result + 1] = {
                kind = kind, result = result,
            }
        end""")
        research = tab.NewResearch(tab, budget, executor, self.h.clock,
                                   callback)
        self.assertTrue(research.QueueRap(research,
            lua_table(self.h.lua, ["w_baton"]))[0])
        self.assertEqual(research.Step(research), "scheduled")
        executor.Drain(executor)
        self.assertEqual(executor["calls"], 1)
        self.assertEqual(received[1]["kind"], "marketRap")
        self.assertEqual(received[1]["result"]["values"]["w_baton"]["sales"], 2)

    def test_black_market_tab_reads_listing_from_full_sync(self):
        entry = self.h.load("src/tabs/blackMarket/Module.luau")
        tab = entry.new(lua_table(self.h.lua, self.deps))
        header = {"session": "s", "account": "a", "place": "p",
                  "release": "r", "revision": 4, "capturedAt": 10}
        raw = dict(header)
        raw["native"] = {"fullSync": True, "serverNow": 1000,
            "market": {"shopUntil": 2000, "listings": {}}}
        view, reason = tab.ReadListings(tab, lua_table(self.h.lua, raw),
                                        lua_table(self.h.lua, header))
        self.assertIsNone(reason)
        self.assertEqual(view["listingCount"], 0)

    def test_black_market_tab_exposes_non_sending_rental_contracts(self):
        entry = self.h.load("src/tabs/blackMarket/Module.luau")
        tab = entry.new(lua_table(self.h.lua, self.deps))
        self.assertIsNotNone(tab.RentEvidence(tab)["capture"])
        header = {"session": "s", "account": "a", "place": "p",
                  "release": "r", "revision": 4, "capturedAt": 10}
        raw = dict(header, native={"fullSync": True, "level": 50,
            "serverNow": 1000, "inventory": {"gold_bar": 8},
            "inventoryBound": {"gold_bar": 2},
            "derived": {"marketShop": False},
            "market": {"shopUntil": 900}})
        proposal, reason = tab.AssessRent(tab,
            lua_table(self.h.lua, raw), lua_table(self.h.lua, header),
            lua_table(self.h.lua, {"release": "r", "minLevel": 20,
                "rentPerPeriod": 1, "rentPeriodHours": 12,
                "rentMaxDays": 7}),
            lua_table(self.h.lua, {"goldReserve": 5,
                "maxAttempts": 1, "maxGoldSpend": 1}), 0)
        self.assertIsNone(reason)
        self.assertEqual(proposal["intent"]["periods"], 1)

    def test_black_market_tab_creates_source_bound_market_catalog(self):
        entry = self.h.load("src/tabs/blackMarket/Module.luau")
        tab = entry.new(lua_table(self.h.lua, self.deps))
        config = {"MARKET": {"minLevel": 20, "slots": 5,
            "maxSlots": 20, "rentPerPeriod": 1,
            "rentPeriodHours": 12, "rentMaxDays": 7,
            "feePct": .1, "permanentFeePct": .07,
            "minFee": 1, "minPrice": 2,
            "maxPages": 5, "minPriceByRarity": {5: 3}, "maxPrice": 9999999,
            "maxQuantity": 999}}
        catalog = tab.NewMarketCatalog(tab,
            lua_table(self.h.lua, config), "a" * 64, "r")
        terms, reason = catalog.RentTerms(catalog,
            lua_table(self.h.lua, {"release": "r",
                "native": {"fullSync": True}}))
        self.assertIsNone(reason)
        self.assertEqual(terms["rentPeriodHours"], 12)

    def test_black_market_tab_exposes_read_only_watch_assessment(self):
        entry = self.h.load("src/tabs/blackMarket/Module.luau")
        tab = entry.new(lua_table(self.h.lua, self.deps))
        self.assertIsNotNone(tab.AssessOpportunity)
        self.assertIsNotNone(tab.ReviewAgingListings)
        self.assertIsNotNone(tab.AssessFlip)
        self.assertIsNotNone(tab.BuyEvidence(tab)["capture"])
        self.assertIsNotNone(tab.AssessFlipList)
        self.assertIsNotNone(tab.AssessCollectionWithdraw)
        self.assertIsNotNone(tab.CollectionWithdrawEvidence(tab)["capture"])
        self.assertIsNotNone(tab.AssessSellAfterWithdraw)
        self.assertIsNotNone(tab.AssessDirectSale)

    def test_sparse_tab_definition_is_rejected(self):
        rows = self.h.lua.table()
        rows[1] = lua_table(self.h.lua, ["skills", "SkillsState",
                                       "Skills", "SkillsEvidence"])
        rows[3] = rows[1]
        with self.assertRaises(Exception):
            self.deps["SimpleTab"].new("skills",
                lua_table(self.h.lua, self.deps), rows)


if __name__ == "__main__":
    unittest.main()
