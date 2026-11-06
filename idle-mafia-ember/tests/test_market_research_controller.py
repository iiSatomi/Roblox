"""Read-only Market research uses real parsers through the shared request lane."""
import unittest
from engine_harness import Harness, ROOT, lua_table
import test_native_market_catalog as catalog_fixture


class MarketResearchControllerTests(unittest.TestCase):
    def setUp(self, feature="marketWatch"):
        self.feature=feature
        self.h = Harness()
        config = catalog_fixture.NativeMarketCatalogTests()
        config.setUp()
        paths = {name: "src/features/" + name + ".luau" for name in ("MarketBrowse", "MarketPrices", "MarketRap")}
        paths.update({name: "src/tabs/blackMarket/" + name + ".luau" for name in (
            "MarketBrowsePages", "MarketSettings", "NativeMarketCatalog", "MarketResearchView",
            "MarketWatchOpportunity", "MarketBlocked", "MarketListingsState", "MarketAgingReview")})
        # Listings reader is an existing game module in the pinned dependency set.
        paths["MarketListingsState"] = "src/tabs/blackMarket/MarketListingsState.luau"
        deps = {name: self.h.load(path) for name, path in paths.items()}
        deps.update(researchFeature=feature, identity=self.h.session, clock=self.h.clock, config=config.config,
            fingerprint="a" * 64, release="release-a", gameData={"ITEMS_BY_ID": {
                "w_baton": {"id": "w_baton", "kind": "weapon", "rarity": 5, "tradable": True}}})
        self.owner = self.h.load("src/tabs/blackMarket/MarketResearchController.luau").new(lua_table(self.h.lua, deps))
        self.reader = self.h.load("src/transport/NativeSnapshotReader.luau").new(
            lua_table(self.h.lua, self.h.session), self.h.clock, "a" * 64)
        self.native = lua_table(self.h.lua, {"serverNow": 1000, "market": {"extraSlots": 0, "listings": {}, "shopUntil": 2000},
            "derived": {"marketShop": False}})
        self.reader.ObserveSync(self.reader, self.native)
        self.executor = self.h.lua.execute("""return {calls={},queued={},pages=1,latency=0,
            Schedule=function(self,fn) self.queued[#self.queued+1]=fn return true end,
            InvokeOwned=function(self,lease,remote,method,...)
                local args=table.pack(...); assert(remote=='MarketAction' and args.n==4)
                self.calls[#self.calls+1]=args
                testNow=testNow+self.latency
                if args[1]=='browse' then
                    return {ok=true,pages=self.pages,more=self.more==true,stale=self.stale==true,small=self.small==true,rows={
                        {id='L1',item='w_baton',qty=1,price=self.salePrice or 8,mine=false},
                        {id='L2',item='w_baton',qty=1,price=14,mine=false}}} end
                if args[1]=='rap' then return {ok=true,values={w_baton={sales=15,quantity=30,average=14,available=true}}} end
                if args[1]=='prices' then return {ok=true,item=args[2],recent={{price=14},{price=15},{price=16}},days={}} end
                error('Unexpected mutation')
            end}""")
        self.sources = self.owner.Sources(self.owner)
        self.lane = self.h.load("src/engine/RequestLane.luau").new(self.h.clock)
        self.h.lua.globals().marketNativeReader = self.reader
        specs = [{"id": row.id, "interval": row.interval} for row in self.sources.values()]
        self.coordinator = self.h.load("src/transport/ReadCoordinator.luau").new(lua_table(self.h.lua, {
            "clock": self.h.clock, "lane": self.lane, "sources": self.sources, "executor": self.executor,
            "budget": self.h.load("src/engine/ReadBudget.luau").new(self.h.clock, lua_table(self.h.lua, specs), 5, 60),
            "currentSnapshot": self.h.lua.eval("function() return marketNativeReader:Capture() end")}))
        self.settings = self.h.load("src/storage/Settings.luau").new(self.h.load("src/ui/Catalog.luau"), True)
        self.settings.Set(self.settings, "marketWatch.enabled", True)
        self.settings.Set(self.settings, "marketWatch.custom.scope", "All eligible items")
        self.settings.Set(self.settings, "marketWatch.custom.floorPct", 90)

    def test_flip_research_runs_through_shared_lane_without_enabling_watch(self):
        self.tearDown();self.setUp('marketFlip')
        self.settings.Set(self.settings,'marketWatch.enabled',False)
        self.settings.Set(self.settings,'marketFlip.enabled',True)
        self.settings.Set(self.settings,'marketFlip.custom.scope','All eligible items')
        self.settings.Set(self.settings,'marketFlip.custom.floorPct',90)
        self.warm()
        self.assertGreater(len(self.executor.calls),0)
        self.assertFalse(self.settings['values']['marketWatch.enabled'])
        self.assertTrue(all(row.id.startswith('marketFlip') for row in self.sources.values()))
        view=self.view()
        if isinstance(view,tuple): view=view[0]
        self.assertIsNotNone(view)
        self.assertTrue(view.readOnly)

    def tearDown(self):
        self.coordinator.Close(self.coordinator)
        self.owner.Close(self.owner)
        self.reader.Close(self.reader)

    def options(self):
        values = {key.removeprefix(self.feature+".custom."): value for key, value in self.settings["values"].items()
            if key.startswith(self.feature+".custom.")}
        values["enabled"] = self.settings["values"][self.feature+".enabled"]
        return lua_table(self.h.lua, values)

    def step(self, drain=True):
        settings = lua_table(self.h.lua, {self.feature: {"enabled": self.settings["values"][self.feature+".enabled"], "custom": self.options()}})
        eligible = self.h.lua.table()
        for source in self.sources.values():
            eligible[source.id] = source.enabled(settings, None)
        self.coordinator.Step(self.coordinator, self.reader.Capture(self.reader)[0], eligible)
        if drain:
            queued, self.executor.queued = self.executor.queued, self.h.lua.table()
            for callback in queued.values():
                callback()

    def view(self):
        raw = self.reader.Capture(self.reader)[0]
        return self.owner.View(self.owner, raw, raw)

    def warm(self, count=8):
        for index in range(count):
            self.h.at(index * .2)
            self.step()

    def test_browse_rap_and_history_produce_a_read_only_margin_report(self):
        self.warm()
        view, reason = self.view()
        self.assertIsNone(reason)
        self.assertTrue(view.readOnly)
        self.assertEqual(view.research.opportunityCount, 1)
        self.assertEqual(view.research.opportunities[1].listingId, "L1")
        self.assertEqual({call[1] for call in self.executor.calls.values()}, {"browse", "rap", "prices"})

    def test_one_native_cumulative_budget_replaces_pages_without_followup_merge(self):
        self.executor.pages = 2
        self.step()
        self.assertEqual(self.view()[0].research.totalRows,2)
        self.warm()
        self.assertEqual(self.view()[0].research.opportunityCount, 1)
        self.assertEqual({call[4] for call in self.executor.calls.values() if call[1] == "browse"}, {5})

    def test_fifteen_second_sync_cadence_finishes_without_cross_frame_page_merge(self):
        self.executor.latency=1.3
        self.step()
        self.assertEqual(self.view()[0].research.totalRows,2)
        self.h.at(8);self.step()
        self.assertEqual(len(self.executor.calls),1)
        for at in (15,30,45):
            self.h.at(at);self.reader.ObserveSync(self.reader,self.native);self.step()
        view,reason=self.view()
        self.assertIsNone(reason)
        self.assertEqual(view.research.opportunityCount,1)
        self.assertEqual([[call[i] for i in range(1,5)] for call in self.executor.calls.values()
            if call[1]=='browse'],[['browse','all',None,5],['browse','all',None,5]])

    def test_selected_item_uses_exact_native_scope_and_late_reply_is_not_current(self):
        self.settings.Set(self.settings,'marketWatch.custom.scope','Selected item')
        self.settings.Set(self.settings,'marketWatch.custom.selectedItemId','w_baton')
        self.warm()
        self.assertEqual([self.executor.calls[1][i] for i in range(1,5)],['browse','item','w_baton',5])
        self.assertEqual(self.view()[0].research.opportunityCount,1)
        self.h.at(15);self.reader.ObserveSync(self.reader,self.native)
        self.executor.latency=2.1;self.step()
        self.assertIsNone(self.view()[0])

    def test_more_stale_and_small_results_are_honest_partial_reports_without_quotes(self):
        for flag in ('more','stale','small'):
            with self.subTest(flag=flag):
                self.tearDown();self.setUp();setattr(self.executor,flag,True)
                self.warm();view,reason=self.view();self.assertIsNone(reason)
                self.assertFalse(view.research.paginationComplete)
                self.assertTrue(view.research.truncated)
                self.assertEqual((view.research.totalRows,view.research.opportunityCount),(2,0))

    def test_filters_disable_and_shared_mutation_custody_are_respected(self):
        self.settings.Set(self.settings, "marketWatch.enabled", False)
        self.step()
        self.assertEqual(len(self.executor.calls), 0)
        self.settings.Set(self.settings, "marketWatch.enabled", True)
        self.lane.TryAcquire(self.lane, "mutation", "busy", 45)
        self.step()
        self.assertEqual(len(self.executor.calls), 0)

    def test_market_sell_item_research_runs_through_black_market_tab_with_watch_off(self):
        self.executor.salePrice = 14
        self.native.inventory = lua_table(self.h.lua, {"w_baton": 2, "w_spare": 2})
        self.native.inventoryBound = lua_table(self.h.lua, {})
        self.reader.ObserveSync(self.reader, self.native)
        self.executor.pages = 2
        deps = {path.stem: self.h.load(path.relative_to(ROOT).as_posix())
            for path in (ROOT / "src/tabs/blackMarket").glob("*.luau")
            if path.stem != "Module"}
        for name in ("MarketEarnings", "MarketEarningsEvidence", "MarketBrowse",
            "MarketPrices", "MarketRap", "MarketReadRuntime"):
            deps[name] = self.h.load("src/features/" + name + ".luau")
        deps["MarketEarningsState"] = self.h.load("src/game/MarketEarningsState.luau")
        deps.update(identity=self.h.session, clock=self.h.clock,
            config=lua_table(self.h.lua, {"MARKET": {
                "maxPages": 5, "minLevel": 1, "slots": 2, "maxSlots": 5,
                "rentPerPeriod": 2, "rentPeriodHours": 24,
                "rentMaxDays": 30, "feePct": .1,
                "permanentFeePct": .05, "minFee": 1,
                "minPrice": 2, "maxPrice": 1000,
                "maxQuantity": 10, "minPriceByRarity": {5: 2}}}),
            fingerprint="a" * 64, release="release-a",
            gameData={"ITEMS_BY_ID": {
                "w_baton": {"id": "w_baton", "kind": "weapon", "rarity": 5, "tradable": True}}})
        deps["gameData"]["ITEMS_BY_ID"]["w_spare"] = {
            "id": "w_spare", "kind": "weapon", "rarity": 5, "tradable": True}
        deps["storage"] = self.h.lua.execute("""return {strictRecovery=true,data={},
            Read=function(self,key) return self.data[key] end,
            Write=function(self,key,value) self.data[key]=value return true end}""")
        deps["marketPresence"] = self.h.lua.execute("""local gate={allowed=true}
            gate.check=function() return gate.allowed, 'manual check' end
            gate.handle=function() return true end return gate""")
        Tab = self.h.load("src/tabs/blackMarket/Module.luau")
        tab = Tab.new(lua_table(self.h.lua, deps))
        sources = tab.ReadSources(tab)
        source_ids = {source.id for source in sources.values()}
        self.assertIn("marketSellBrowse", source_ids)
        settings = lua_table(self.h.lua, {"marketWatch": {"enabled": False},
            "marketSell": {"enabled": True, "custom": {
                "scope": "All eligible items", "selectedItemId": "w_baton",
                "excludedItems": "", "excludedKinds": "",
                "excludedRarities": "", "keepLoose": 1}}})
        self.assertFalse(settings.marketWatch.enabled)
        specs = [{"id": source.id, "interval": source.interval}
            for source in sources.values()]
        self.h.lua.globals().marketNativeReader = self.reader
        coordinator = self.h.load("src/transport/ReadCoordinator.luau").new(
            lua_table(self.h.lua, {"clock": self.h.clock, "lane": self.lane,
                "sources": sources, "executor": self.executor,
                "budget": self.h.load("src/engine/ReadBudget.luau").new(
                    self.h.clock, lua_table(self.h.lua, specs), 10, 60),
                "currentSnapshot": self.h.lua.eval(
                    "function() return marketNativeReader:Capture() end")}))
        for index in range(12):
            self.h.at(index * .2)
            self.reader.ObserveSync(self.reader, self.native)
            eligible = self.h.lua.table()
            for source in sources.values():
                eligible[source.id] = source.enabled(settings, None)
            coordinator.Step(coordinator, self.reader.Capture(self.reader)[0], eligible)
            queued, self.executor.queued = self.executor.queued, self.h.lua.table()
            for callback in queued.values(): callback()
        calls = list(self.executor.calls.values())
        self.assertEqual({call[1] for call in calls}, {"browse", "rap", "prices"})
        item_browses = [call for call in calls if call[1] == "browse"]
        self.assertEqual({call[3] for call in item_browses}, {"w_baton"})
        self.assertEqual({call[4] for call in item_browses}, {5})
        raw = self.reader.Capture(self.reader)[0]
        raw.marketSellOwnerProof = lua_table(self.h.lua, {"attempted": 999})
        enriched, _ = tab.Enrich(tab, raw)
        self.assertEqual(enriched.marketSellOwnerProof.attempted, 0)
        self.assertFalse(enriched.marketSellOwnerProof.transactionOpen)
        self.assertEqual(enriched.marketSellOwnerProof.generation, 0)
        wrong_scope = lua_table(self.h.lua, {**self.h.session, "account": "other",
            "revision": 1, "capturedAt": 0, "native": {"fullSync": True},
            "marketSellOwnerProof": {"attempted": 999}})
        self.assertIsNone(tab.Enrich(tab, wrong_scope)[0].marketSellOwnerProof)
        view, reason = tab.research.SaleView(tab.research, raw, raw)
        self.assertIsNone(reason)
        self.assertEqual(view.itemId, "w_baton")
        self.assertEqual(view.browse.kind, "item")
        self.assertEqual(view.browse.arg, "w_baton")
        seller = next(row for row in tab.Descriptors(tab).values()
            if row.id == "marketSell")
        sale_view, sale_reason = seller.reader.read(raw, raw)
        self.assertIsNone(sale_reason)
        self.assertEqual(sale_view.itemId, "w_baton")
        # Actual descriptor projects sale preferences and current protection.
        raw.native.crew = lua_table(self.h.lua, [{}])
        raw.native.collection = self.h.lua.table()
        raw.native.collectionBound = self.h.lua.table()
        raw.native.market.extraSlots = 0
        raw.native.serverNow = 1000
        raw.native.market.shopUntil = 2000
        raw.native.derived = lua_table(self.h.lua, {"marketShop": False})
        context = lua_table(self.h.lua, {key: raw[key] for key in
            ("session", "account", "place", "release", "revision", "capturedAt")})
        context.collectionProtection = lua_table(self.h.lua, {
            **{key: raw[key] for key in ("session", "account", "place", "release", "revision", "capturedAt")},
            "covers": {"gear": True, "cosmetics": True}, "protected": {}})
        options = {key.removeprefix("marketSell.custom."): value
            for key, value in self.settings["values"].items()
            if key.startswith("marketSell.custom.")}
        options.update(scope="All eligible items", selectedItemId="w_baton",
            keepLoose=1, minNet=1, likelyOnly=False, undercutGold=0, floorPct=90)
        sale_view, _ = seller.reader.read(raw, context)
        preview, why = tab.research.SalePreview(tab.research, sale_view,
            lua_table(self.h.lua, {"enabled": True, "custom": options}))
        self.assertIsNone(why)
        self.assertEqual(preview.custody.quantity, 1)
        self.assertEqual(preview.quote.itemId, "w_baton")
        # The non-sending proposal builder uses the actual owner proof and caps.
        raw.marketSellOwnerProof = enriched.marketSellOwnerProof
        options["maxListings"], options["maxListAttempts"] = 1, 1
        planned, why = tab.research.PlanSale(tab.research, sale_view,
            lua_table(self.h.lua, {"enabled": True, "custom": options}))
        self.assertIsNone(why)
        self.assertEqual(planned.resources.w_baton, 1)
        self.assertEqual(planned.intent.kind, "marketList")
        self.assertIsNone(planned.preflightOnly)
        self.assertEqual(planned.intent.ownerGeneration, 1)
        deps["marketPresence"].allowed = False
        self.assertIsNone(tab.research.PlanSale(tab.research, sale_view,
            lua_table(self.h.lua, {"enabled": True, "custom": options}))[0])
        deps["marketPresence"].allowed = True

        raw.collectionProtection = context.collectionProtection
        validated, why = self.h.load("src/engine/Contracts.luau").validateProposal(planned, raw)
        self.assertIsNone(why)
        captured, why = tab.research.CaptureSale(tab.research, validated, raw)
        self.assertIsNone(why)
        self.assertEqual(captured.quantity, 1)
        self.assertEqual(captured.ask, planned.intent.ask)
        validated.intent.ask += 1
        self.assertIsNone(tab.research.CaptureSale(tab.research, validated, raw)[0])

        raw.marketSellOwnerProof.attempted = 1
        self.assertIsNone(tab.research.PlanSale(tab.research, sale_view,
            lua_table(self.h.lua, {"enabled": True, "custom": options}))[0])
        raw.marketSellOwnerProof.attempted = 0

        runtime_proposal, preview_report = seller.planner.propose(sale_view,
            lua_table(self.h.lua, {"enabled": True, "custom": options}))
        self.assertIsNotNone(runtime_proposal)
        self.assertIsNone(preview_report)
        raw.native.market.shopUntil = 1000
        self.assertIsNone(tab.research.SalePreview(tab.research, sale_view,
            lua_table(self.h.lua, {"enabled": True, "custom": options}))[0])
        raw.native.market.shopUntil = 2000
        options["minNet"] = 100
        self.assertIsNone(tab.research.SalePreview(tab.research, sale_view,
            lua_table(self.h.lua, {"enabled": True, "custom": options}))[0])
        price_rejected_source = next(source for source in sources.values()
            if source.id == "marketSellBrowse")
        price_next = price_rejected_source.prepare(raw)
        self.assertEqual(price_next.args[3], "w_spare")
        options["minNet"] = 1

        context.collectionProtection.reserved = lua_table(self.h.lua, {"w_baton": 1})
        self.assertIsNone(tab.research.SalePreview(tab.research, sale_view,
            lua_table(self.h.lua, {"enabled": True, "custom": options}))[0])
        context.collectionProtection.reserved.w_baton = 0
        context.collectionProtection.protected.w_baton = 2
        sale_view, _ = seller.reader.read(raw, context)
        self.assertIsNone(tab.research.SalePreview(tab.research, sale_view,
            lua_table(self.h.lua, {"enabled": True, "custom": options}))[0])
        candidate_source = next(source for source in sources.values()
            if source.id == "marketSellBrowse")
        next_item = candidate_source.prepare(raw)
        self.assertEqual(next_item.args[3], "w_spare")
        context.collectionProtection.revision = raw.revision + 1
        self.assertIsNone(tab.research.SalePreview(tab.research, sale_view,
            lua_table(self.h.lua, {"enabled": True, "custom": options}))[0])

        proposal, report = seller.planner.propose(view, lua_table(self.h.lua, {}))
        self.assertIsNone(proposal)
        self.assertIn("w_baton", report)
        self.assertFalse(any(call[1] in {"list", "buy", "withdraw"}
            for call in calls))
        sell_browse = next(source for source in sources.values()
            if source.id == "marketSellBrowse")
        self.h.at(18)
        self.reader.ObserveSync(self.reader, self.native)
        stale_raw = self.reader.Capture(self.reader)[0]
        self.assertIsNone(tab.research.SaleView(tab.research,
            stale_raw, stale_raw)[0])
        self.assertTrue(sell_browse.enabled(settings, None))
        refreshed = sell_browse.prepare(stale_raw)
        self.assertEqual([refreshed.args[i] for i in range(1, 5)],
                         ["browse", "item", "w_baton", 5])
        settings.marketSell.custom.excludedItems = "w_baton,w_spare"
        self.assertTrue(sell_browse.enabled(settings, None))
        self.assertIsNone(sell_browse.prepare(stale_raw)[0])
        # Selection changes invalidate both queued work and already accepted data.
        view, reason = tab.research.SaleView(tab.research,
            stale_raw, stale_raw)
        self.assertIsNone(view)
        self.assertEqual(reason, "No eligible loose Market item")
        coordinator.Close(coordinator)
        tab.Close(tab)

    def test_market_sell_changed_selection_fences_a_queued_item_browse(self):
        deps = {path.stem: self.h.load(path.relative_to(ROOT).as_posix())
            for path in (ROOT / "src/tabs/blackMarket").glob("*.luau")
            if path.stem != "Module"}
        for name in ("MarketEarnings", "MarketEarningsEvidence", "MarketBrowse",
            "MarketPrices", "MarketRap", "MarketReadRuntime"):
            deps[name] = self.h.load("src/features/" + name + ".luau")
        deps["MarketEarningsState"] = self.h.load("src/game/MarketEarningsState.luau")
        config = catalog_fixture.NativeMarketCatalogTests()
        config.setUp()
        deps.update(identity=self.h.session, clock=self.h.clock,
            config=lua_table(self.h.lua, config.config), fingerprint="a" * 64,
            release="release-a", gameData={"ITEMS_BY_ID": {
                "w_baton": {"id": "w_baton", "kind": "weapon", "rarity": 5, "tradable": True}}})
        tab = self.h.load("src/tabs/blackMarket/Module.luau").new(
            lua_table(self.h.lua, deps))
        sources = tab.ReadSources(tab)
        browse_source = next(source for source in sources.values()
            if source.id == "marketSellBrowse")
        raw = lua_table(self.h.lua, {**self.h.session, "revision": 1,
            "capturedAt": 0, "native": {"fullSync": True,
                "inventory": {"w_baton": 2}, "inventoryBound": {}}})
        settings = lua_table(self.h.lua, {"marketWatch": {"enabled": False},
            "marketSell": {"enabled": True, "custom": {
                "scope": "Selected item", "selectedItemId": "w_baton",
                "excludedItems": "", "excludedKinds": "",
                "excludedRarities": "", "keepLoose": 1}}})
        self.assertTrue(browse_source.enabled(settings, None))
        request = browse_source.prepare(raw)
        self.assertEqual([request.args[i] for i in range(1, 5)],
                         ["browse", "item", "w_baton", 5])
        wrong_session = lua_table(self.h.lua, {**self.h.session,
            "session": "other-run", "revision": 1, "capturedAt": 0,
            "native": {"fullSync": True, "inventory": {"w_baton": 2},
                "inventoryBound": {}}})
        self.assertIsNone(browse_source.accept(wrong_session, request,
            lua_table(self.h.lua, {"ok": True, "pages": 1,
                "more": False, "rows": []})))
        settings.marketSell.custom.excludedItems = "w_baton"
        self.assertTrue(browse_source.enabled(settings, None))
        self.assertIsNone(browse_source.prepare(raw)[0])
        accepted = browse_source.accept(raw, request, lua_table(self.h.lua,
            {"ok": True, "pages": 1, "more": False, "rows": []}))
        self.assertIsNone(accepted)
        self.assertIsNone(tab.research.SaleView(tab.research, raw, raw)[0])
        settings.marketSell.custom.excludedItems = ""
        self.assertTrue(browse_source.enabled(settings, None))
        disabled_request = browse_source.prepare(raw)
        self.assertIsNotNone(disabled_request)
        settings.marketSell.enabled = False
        self.assertFalse(browse_source.enabled(settings, None))
        self.assertIsNone(browse_source.accept(raw, disabled_request,
            lua_table(self.h.lua, {"ok": True, "pages": 1,
                "more": False, "rows": []})))
        raw.native.inventory = lua_table(self.h.lua, {})
        raw.native.inventoryBound = lua_table(self.h.lua, {"w_baton": 2})
        settings.marketSell.enabled = True
        self.assertTrue(browse_source.enabled(settings, None))
        self.assertIsNone(browse_source.prepare(raw)[0])
        raw.native.inventory = lua_table(self.h.lua, {"w_baton": 2})
        close_request = browse_source.prepare(raw)
        self.assertIsNotNone(close_request)
        tab.Close(tab)
        self.assertIsNone(browse_source.accept(raw, close_request,
            lua_table(self.h.lua, {"ok": True, "pages": 1,
                "more": False, "rows": []})))
        self.assertFalse(browse_source.commit(lua_table(self.h.lua,
            {"kind": "item", "arg": "w_baton", "page": 1,
                "pages": 1, "capturedAt": 0, "more": False, "rows": []})))
        self.assertIsNone(tab.research.SaleView(tab.research, raw, raw)[0])

    def test_exclusions_change_current_report_without_a_purchase(self):
        self.warm()
        self.settings.Set(self.settings, "marketWatch.custom.excludedItems", "w_baton")
        self.step()
        view, reason = self.view()
        self.assertIsNone(reason)
        self.assertEqual(view.research.opportunityCount, 0)

    def test_stale_native_reply_and_closed_owner_do_not_commit(self):
        self.step(False)
        self.reader.ObserveSync(self.reader, self.native)
        self.executor.queued[1]()
        self.assertEqual(len(self.executor.calls), 0)
        self.assertIsNone(self.view()[0])
        self.owner.Close(self.owner)
        self.assertIsNone(self.view()[0])

    def test_wrong_account_and_expired_browse_do_not_present_current_opportunities(self):
        self.warm()
        raw = self.reader.Capture(self.reader)[0]
        raw.account = "other-account"
        self.assertIsNone(self.owner.View(self.owner, raw, raw)[0])
        self.h.at(17)
        self.reader.ObserveSync(self.reader, self.native)
        self.assertIsNone(self.view()[0])

    def test_current_owned_listing_aging_is_reported_without_cancel_or_relist(self):
        self.native.serverNow = 100000
        self.native.market.listings = lua_table(self.h.lua, {"mine": {"state": "live", "item": "w_baton",
            "indexed": 1, "price": 14, "qty": 1, "left": 1, "createdAt": 1000,
            "itemOrigin": {"total": 1, "free": 0}}})
        self.reader.ObserveSync(self.reader, self.native)
        self.warm()
        view, reason = self.view()
        self.assertIsNone(reason)
        self.assertEqual(len(view.aging), 1)
        self.assertEqual(view.aging[1].listingId, "mine")
        self.assertTrue(view.aging[1].reviewOnly)
        self.assertIsNone(view.aging[1].remote)

    def test_app_runs_research_reports_margin_and_never_sends_gameplay(self):
        modules = {name: self.h.load("src/engine/" + name + ".luau") for name in (
            "Contracts", "Broker", "Journal", "Session", "Scheduler", "ResourceReservations")}
        modules["Checkpoint"] = self.h.load("src/storage/Checkpoint.luau")
        modules["Context"] = self.h.load("src/game/Context.luau")
        runtime = self.h.load("src/engine/AutomationRuntime.luau").new(lua_table(self.h.lua, {
            "clock": self.h.clock, "transport": self.h.transport, "identity": self.h.session, "modules": modules,
            "storage": self.h.lua.execute("return {strictRecovery=true,Read=function() end,Write=function() return true end}"),
            "features": [self.owner.Descriptor(self.owner)], "readCoordinator": self.coordinator, "readSources": self.sources}))
        app = self.h.load("src/App.luau").start(lua_table(self.h.lua, {
            "Ember": self.h.load("tests/ember_double.lua")(), "Catalog": self.h.load("src/ui/Catalog.luau"),
            "Settings": self.h.load("src/storage/Settings.luau"), "EmberAdapter": self.h.load("src/ui/EmberAdapter.luau"),
            "BlackMarketTab": self.h.load("src/tabs/blackMarket/Module.luau"), "automationRuntimeInstance": runtime}))
        app.Set(app, "marketWatch.enabled", True)
        app.Set(app, "marketWatch.custom.scope", "All eligible items")
        app.Set(app, "marketWatch.custom.floorPct", 90)
        app.Resume(app)
        try:
            for index in range(8):
                self.h.at(index * .2)
                app.Step(app, self.reader.Capture(self.reader)[0])
                queued, self.executor.queued = self.executor.queued, self.h.lua.table()
                for callback in queued.values():
                    callback()
            report = runtime.Status(runtime).reasons.marketWatch
            self.assertIn("1 research candidates", report)
            self.assertIn("estimated margin 3 Gold", report)
            self.assertIn("prices ready 1/1 items", report)
            self.assertEqual(len(self.h.transport.sent), 0)
            self.assertIsNone(app.ui.features.marketWatch.blockedReason)
        finally:
            app.Destroy(app)
