"""Catalog -> typed preferences -> App scalars -> tab-owned helper options."""
import unittest

from engine_harness import Harness, ROOT, lua_table


class MarketSettingsTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.catalog = self.h.load("src/ui/Catalog.luau")
        self.settings = self.h.load("src/storage/Settings.luau")
        self.model = self.settings.new(self.catalog)
        self.features = {row.id: row for row in self.catalog.features.values()
                         if row.page == "blackMarket"}

    def module(self):
        path = ROOT / "src/tabs/blackMarket/MarketSettings.luau"
        self.assertTrue(path.is_file(), "Missing tab-owned MarketSettings")
        return self.h.load(path.relative_to(ROOT).as_posix())

    def options(self, feature, **changes):
        prefix = feature + ".custom."
        values = {key[len(prefix):]: value for key, value in self.model["values"].items()
                  if key.startswith(prefix)}
        values["enabled"] = True
        values.update(changes)
        return lua_table(self.h.lua, values)

    def state(self, **changes):
        values = dict(transactionOpen=False, spent=0,
            attempted=0, listingAttempts=0, withdrawAttempts=0)
        values.update(changes)
        return lua_table(self.h.lua, values)

    def test_defaults_off_zero_independent_budgets_and_collection_opt_in(self):
        expected = {"marketWatch": {"scope", "selectedItemId", "excludedItems",
                "excludedKinds", "excludedRarities", "minSales", "minUnits",
                "minMargin", "minMarginPct", "undercutGold", "floorPct",
                "requireCoverage", "minAgeHours", "demandMultiplier", "maxReviews"},
            "marketSell": {"scope", "selectedItemId", "excludedItems", "excludedKinds",
                "excludedRarities", "keepLoose", "maxQuantity", "fromCollection",
                "maxWithdraw", "maxWithdrawAttempts", "minNet", "minSales", "minUnits",
                "likelyOnly", "undercutGold", "floorPct", "maxListings", "maxListAttempts"},
            "marketFlip": {"scope", "selectedItemId", "excludedItems", "excludedKinds",
                "excludedRarities", "minSales", "minUnits", "minMargin", "minMarginPct",
                "undercutGold", "floorPct", "requireCoverage", "maxBuy", "sessionBudget",
                "goldReserve", "maxAttempts", "maxListAttempts"},
            "marketRent": {"goldReserve", "maxAttempts", "maxGoldSpend"},
            "marketManage": {"minEarnings"}}
        for feature, fields in expected.items():
            self.assertFalse(self.model["values"][feature + ".enabled"])
            self.assertEqual({row.id for row in self.features[feature].custom.values()}, fields)
        self.assertFalse(self.model["values"]["marketSell.custom.fromCollection"])
        for key in ("marketFlip.custom.maxBuy", "marketFlip.custom.sessionBudget",
                    "marketFlip.custom.maxAttempts", "marketRent.custom.maxGoldSpend",
                    "marketRent.custom.maxAttempts", "marketSell.custom.maxListings"):
            self.assertEqual(self.model["values"][key], 0)

    def test_ui_builds_every_catalog_control_using_existing_scalar_types(self):
        app, ember, _ = self.app()
        for feature in self.features.values():
            self.assertTrue(app.ui.features[feature.id].tabOwned)
            for field in feature.custom.values():
                key = feature.id + ".custom." + field.id
                control = app.ui.handles[key]
                self.assertIsNotNone(control, key)
                expected = {"number": "Input", "text": "Input",
                            "select": "Dropdown", "boolean": "Toggle"}[field.type]
                self.assertEqual(control.kind, expected)
                self.assertEqual(app.model["values"][key], field.value)
        self.assertEqual(len(self.h.transport.sent), 0)
        handle = app.ui.handles["marketSell.custom.keepLoose"]
        self.assertIsNotNone(handle)
        handle.Set(handle, "4")
        ember.Flush()
        self.assertEqual(app.model["values"]["marketSell.custom.keepLoose"], 4)
        handle.Set(handle, "4.5")
        ember.Flush()
        self.assertEqual(app.model["values"]["marketSell.custom.keepLoose"], 4)

    def app(self):
        ember = self.h.load("tests/ember_double.lua")()
        runtime = self.h.lua.execute("""return { features = {
            marketWatch = {}, marketSell = {}, marketFlip = {}, marketRent = {}, marketManage = {} },
            Status = function() return {state = 'paused'} end,
            Step = function(self, raw, settings) self.last = settings end,
            Pause = function() end, Resume = function() end,
            Stop = function() end, Close = function() end,
        }""")
        deps = lua_table(self.h.lua, {"Ember": ember, "Catalog": self.catalog,
            "Settings": self.settings, "EmberAdapter": self.h.load("src/ui/EmberAdapter.luau"),
            "BlackMarketTab": self.h.load("src/tabs/blackMarket/Module.luau"),
            "automationRuntimeInstance": runtime})
        return self.h.load("src/App.luau").start(deps), ember, runtime

    def tab(self):
        self.module()
        deps = {p.stem: self.h.load(p.relative_to(ROOT).as_posix())
                for p in (ROOT / "src/tabs/blackMarket").glob("*.luau")
                if p.name != "Module.luau"}
        for name, folder in (("MarketEarningsState", "game"),
                ("MarketEarnings", "features"), ("MarketEarningsEvidence", "features"),
                ("MarketBrowse", "features"), ("MarketPrices", "features"),
                ("MarketRap", "features"), ("MarketReadRuntime", "features")):
            deps[name] = self.h.load(f"src/{folder}/{name}.luau")
        return self.h.load("src/tabs/blackMarket/Module.luau").new(lua_table(self.h.lua, deps))

    def test_app_generic_mapping_projects_exact_sell_watch_flip_rent_options(self):
        tab = self.tab()
        app, _, runtime = self.app()
        choices = {"marketSell": {"scope": "All eligible items", "keepLoose": 3,
                "maxQuantity": 2, "maxListings": 4, "maxListAttempts": 1,
                "fromCollection": True, "maxWithdraw": 2, "maxWithdrawAttempts": 1,
                "excludedItems": " w_gavel, w_pipe,w_gavel ", "excludedKinds": "vehicle",
                "excludedRarities": "1, 2", "minNet": 4},
            "marketWatch": {"scope": "All eligible items", "minMargin": 4},
            "marketFlip": {"scope": "Selected item", "selectedItemId": "w_baton",
                "maxBuy": 8, "sessionBudget": 30, "goldReserve": 20,
                "maxAttempts": 2, "maxListAttempts": 1},
            "marketRent": {"maxGoldSpend": 3, "maxAttempts": 1, "goldReserve": 50}}
        for feature, values in choices.items():
            self.assertTrue(app.Set(app, feature + ".enabled", True)[0])
            for key, value in values.items():
                self.assertTrue(app.Set(app, feature + ".custom." + key, value)[0], key)
        app.Step(app, self.h.snapshot())
        for feature in self.features:
            for field in self.features[feature].custom.values():
                self.assertEqual(runtime.last[feature][field.id],
                    app.model["values"][feature + ".custom." + field.id])
        sell, reason = tab.ProjectSettings(tab, "marketSell", runtime.last.marketSell, self.state())
        self.assertIsNone(reason)
        self.assertEqual(sell.custody.keepLoose, 3)
        self.assertEqual(sell.custody.maxQuantity, 2)
        self.assertTrue(sell.custody.fromCollection)
        self.assertTrue(sell.custody.blockedItems.w_gavel)
        self.assertTrue(sell.custody.blockedRarities[2])
        self.assertEqual(sell.quote.minNet, 4)
        self.assertEqual(sell.withdraw.maxWithdraw, 2)
        self.assertEqual(sell.directList.maxListings, 4)
        self.assertEqual(sell.followupList.maxListAttempts, 1)
        watch = tab.ProjectSettings(tab, "marketWatch", runtime.last.marketWatch, None)[0]
        self.assertEqual(watch.watch.minMargin, 4)
        flip = tab.ProjectSettings(tab, "marketFlip", runtime.last.marketFlip, self.state())[0]
        self.assertEqual(flip.buyBudget.sessionBudget, 30)
        self.assertEqual(flip.buyBudget.goldReserve, 20)
        rent = tab.ProjectSettings(tab, "marketRent", runtime.last.marketRent, self.state())[0]
        self.assertEqual(rent.rent.maxGoldSpend, 3)
        self.assertEqual(rent.rent.goldReserve, 50)
        self.assertEqual(len(self.h.transport.sent), 0)

    def test_zero_limits_do_not_borrow_and_explicit_state_limits_remaining_rent(self):
        module = self.module()
        for feature in ("marketSell", "marketFlip", "marketRent"):
            options = self.options(feature, **({"scope": "All eligible items"} if feature != "marketRent" else {}))
            self.assertIsNone(module.project(feature, options, self.state())[0])
        options = self.options("marketRent", maxGoldSpend=3, maxAttempts=2)
        state = self.state()
        state.spent = 1
        projected, reason = module.project("marketRent", options, state)
        self.assertIsNone(reason)
        self.assertEqual(projected.rent.maxGoldSpend, 2)
        state.spent = 3
        self.assertIsNone(module.project("marketRent", options, state)[0])
        self.assertIsNone(module.project("marketRent", options, None)[0])

    def test_selection_exclusion_and_unknown_kind_or_rarity_fail_closed(self):
        module = self.module()
        options = self.options("marketWatch")
        self.assertIsNone(module.project("marketWatch", options, None)[0])
        options.scope = "All eligible items"
        for field, value in (("excludedItems", "w_a,,w_b"),
                ("excludedItems", "w_a,"), ("excludedItems", "x" * 121),
                ("excludedItems", ",".join(f"item_{i}" for i in range(65))),
                ("excludedKinds", "spaceship"), ("excludedRarities", "10"),
                ("minSales", 2), ("floorPct", 89), ("requireCoverage", "true")):
            old = options[field]
            options[field] = value
            self.assertIsNone(module.project("marketWatch", options, None)[0], field)
            options[field] = old
        options.excludedItems = " w_pipe, w_pipe, w_gavel "
        projected = module.project("marketWatch", options, None)[0]
        self.assertEqual(len(list(projected.selection.blockedItems.keys())), 2)
        item = lua_table(self.h.lua, {"id": "w_pipe", "kind": "weapon", "rarity": 2})
        self.assertFalse(module.allows(projected, item)[0])
        item.id = "w_baton"
        self.assertTrue(module.allows(projected, item)[0])
        options.scope, options.selectedItemId = "Selected item", "w_gavel"
        projected = module.project("marketWatch", options, None)[0]
        self.assertFalse(module.allows(projected, item)[0])

    def test_csv_validation_is_opt_in_and_legacy_profiles_default_new_keys(self):
        self.assertTrue(self.model.Set(self.model, "marketSell.custom.excludedItems", "w_a, w_b")[0])
        self.assertFalse(self.model.Set(self.model, "shop.custom.itemId", "w_a,w_b")[0])
        for value in ("a,,b", "a,", ",a", "a@2", "x" * 121):
            self.assertFalse(self.model.Set(self.model, "marketSell.custom.excludedItems", value)[0])
        fresh = self.settings.new(self.catalog)
        profile = lua_table(self.h.lua, {"schema": 1, "values": {
            "marketManage.enabled": True, "marketManage.custom.minEarnings": 3}})
        values, reason = fresh.Validate(fresh, profile)
        self.assertIsNone(reason)
        fresh.Commit(fresh, values)
        self.assertEqual(fresh["values"]["marketManage.custom.minEarnings"], 3)
        self.assertEqual(fresh["values"]["marketFlip.custom.sessionBudget"], 0)
        self.assertFalse(fresh["values"]["marketSell.custom.fromCollection"])
        self.assertFalse(fresh["values"]["marketSell.enabled"])

    def test_projected_shapes_are_accepted_by_actual_existing_market_helpers(self):
        from test_market_sale_custody import MarketSaleCustodyTests
        from test_market_sale_quote import MarketSaleQuoteTests
        from test_market_watch_opportunity import MarketWatchOpportunityTests
        from test_market_flip_preflight import MarketFlipPreflightTests
        from test_market_rent_quote import MarketRentQuoteTests

        def project(fixture, feature, **changes):
            options = dict(self.options(feature, **changes).items())
            module = fixture.h.load("src/tabs/blackMarket/MarketSettings.luau")
            projected, reason = module.project(feature,
                lua_table(fixture.h.lua, options), lua_table(fixture.h.lua, {
                    "transactionOpen": False, "spent": 0, "attempted": 0,
                    "listingAttempts": 0, "withdrawAttempts": 0}))
            self.assertIsNone(reason)
            return projected

        custody = MarketSaleCustodyTests()
        custody.setUp()
        sell = project(custody, "marketSell", scope="All eligible items",
            maxListings=2, maxListAttempts=1, keepLoose=3, maxQuantity=2)
        values = custody.inputs(loose=5)
        values[4] = sell.custody
        candidate, reason = custody.module.assess(*values)
        self.assertIsNone(reason)
        self.assertEqual(candidate.quantity, 2)
        sell.custody.blockedItems.w_baton = True
        self.assertIsNone(custody.module.assess(*values)[0])

        quote = MarketSaleQuoteTests()
        quote.setUp()
        sell = project(quote, "marketSell", scope="All eligible items", maxListings=2, maxListAttempts=1)
        values = quote.inputs()
        values[6] = sell.quote
        self.assertIsNotNone(quote.quote.assess(*values)[0])

        watch = MarketWatchOpportunityTests()
        watch.setUp()
        projected = project(watch, "marketWatch", scope="All eligible items", floorPct=90)
        values = watch.inputs()
        values[6] = projected.watch
        self.assertIsNotNone(watch.watch.assess(*values)[0])

        flip = MarketFlipPreflightTests()
        flip.setUp()
        projected = project(flip, "marketFlip", scope="All eligible items",
            maxBuy=10, sessionBudget=20, maxAttempts=2, maxListAttempts=1, goldReserve=5)
        values = flip.inputs()
        values[4:7] = [projected.buyBudget, projected.spent, projected.attempted]
        self.assertIsNotNone(flip.preflight.assess(*values)[0])

        rent = MarketRentQuoteTests()
        rent.setUp()
        projected = project(rent, "marketRent", maxGoldSpend=1, maxAttempts=1, goldReserve=5)
        values = rent.inputs()
        values[3:5] = [projected.rent, projected.attempted]
        self.assertIsNotNone(rent.quote.assess(*values)[0])

    def test_every_catalog_field_is_revalidated_at_tab_boundary(self):
        module = self.module()
        choices = {"marketWatch": {"scope": "All eligible items"},
            "marketSell": {"scope": "All eligible items", "maxListings": 1, "maxListAttempts": 1},
            "marketFlip": {"scope": "All eligible items", "maxBuy": 10,
                "sessionBudget": 20, "maxAttempts": 1, "maxListAttempts": 1},
            "marketRent": {"maxGoldSpend": 1, "maxAttempts": 1}, "marketManage": {}}
        for feature, changes in choices.items():
            options = self.options(feature, **changes)
            self.assertIsNotNone(module.project(feature, options, self.state())[0])
            for field in self.features[feature].custom.values():
                old = options[field.id]
                options[field.id] = ({"number": float("nan"), "boolean": "true",
                    "text": "@invalid", "select": "Unknown"})[field.type]
                self.assertIsNone(module.project(feature, options, self.state())[0], field.id)
                options[field.id] = old
            options.unexpected = True
            self.assertIsNone(module.project(feature, options, self.state())[0])

    def test_typed_run_facts_and_disabled_features_cannot_reset_limits(self):
        module = self.module()
        options = self.options("marketFlip", scope="All eligible items", maxBuy=10,
            sessionBudget=20, maxAttempts=2, maxListAttempts=1)
        for state in (None, self.state(spent=-1), self.state(attempted=1.5),
                      self.state(transactionOpen="false")):
            self.assertIsNone(module.project("marketFlip", options, state)[0])
        options.enabled = False
        self.assertIn("disabled", module.project("marketFlip", options, self.state())[1])
        options.enabled = "true"
        self.assertIsNone(module.project("marketFlip", options, self.state())[0])


if __name__ == "__main__":
    unittest.main()
