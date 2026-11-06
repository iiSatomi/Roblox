"""Reviewed legacy Market choices must reach every original consumer, inertly."""
import json
import unittest
from engine_harness import lua_table
from test_redundant_store import plain
import test_profile_management as profiles
import test_market_flip_runtime as flips


class LegacyMarketPreferencesTests(unittest.TestCase):
    def setUp(self):
        self.f = profiles.ProfileManagementTests()
        self.f.setUp()
        self.app, self.h = self.f.app, self.f.h

    def tearDown(self):
        self.f.tearDown()

    def preview(self, **choices):
        return self.app.PreviewImport(self.app, json.dumps({"version": 17, **choices}))

    def test_exclusions_reach_both_trade_lanes_without_widening_read_scope(self):
        source = {"marketSellBlockedItems": {"w_baton": True, "w_pipe": False},
                  "marketSellBlockedKinds": {"armor": True},
                  "marketSellBlockedRarities": {"Secret": True, "Common": False}}
        accepted, reason = self.preview(**source)
        self.assertTrue(accepted, reason)
        values = self.app.staged["values"]
        for lane in ("marketSell", "marketFlip"):
            for key, want in (("excludedItems", "w_baton"), ("excludedKinds", "armor"), ("excludedRarities", "7")):
                self.assertEqual(values[lane + ".custom." + key], want)
            self.assertFalse(values[lane + ".enabled"])
            self.assertEqual(values[lane + ".custom.maxListAttempts"], 0)
        self.assertEqual(values["marketFlip.custom.maxAttempts"], 0)
        self.assertEqual(values["marketWatch.custom.excludedItems"], "")
        self.assertFalse(values["marketWatch.enabled"])
        self.assertEqual(plain(self.app.importReview.original), {"version": 17, **source})
        self.assertTrue(self.app.model.paused)
        self.assertEqual(len(self.f.base.storage.data), 0)

    def test_imported_exclusion_blocks_actual_flip_until_explicitly_changed(self):
        accepted, reason = self.preview(marketSellBlockedItems={"w_baton": True})
        self.assertTrue(accepted, reason)
        f = flips.MarketFlipRuntimeTests()
        f.setUp()
        try:
            self.assertTrue(f.app.ApplyProfile(f.app, lua_table(f.h.lua, plain(self.app.staged)))[0])
            self.assertTrue(f.app.model.paused)
            self.assertEqual(len(f.executor.calls), 0)
            f.choose()
            raw = f.raw()
            f.warm(raw)
            f.app.Step(f.app, raw)
            f.executor.Drain(f.executor)
            self.assertEqual(len(f.executor.calls), 0, "Legacy excluded item was bought")
            self.assertTrue(f.app.Set(f.app, "marketFlip.custom.excludedItems", "")[0])
            f.warm(raw)
            f.app.Step(f.app, raw)
            f.executor.Drain(f.executor)
            self.assertEqual(len(f.executor.calls), 1)
            self.assertEqual(f.executor.calls[1].args[1], "buy")
        finally:
            f.tearDown()

    def test_invalid_shared_exclusion_cannot_stage_either_lane(self):
        for key, value in (("marketSellBlockedItems", {"w_baton": "true"}),
                           ("marketSellBlockedKinds", {"unknown": True}),
                           ("marketSellBlockedRarities", {"Secret": 1})):
            with self.subTest(key=key):
                accepted, reason = self.preview(**{key: value})
                self.assertFalse(accepted)
                self.assertIn(key, reason)
                self.assertIsNone(self.app.staged)
                self.assertEqual(plain(self.app.importReview.original[key]), value)
                self.assertEqual(len(self.f.base.storage.data), 0)


    def test_reviewed_price_preferences_reach_selling_and_flipping_only(self):
        accepted, reason = self.preview(marketUndercutGold=0, marketPriceFloorPct=100, marketRentGoldReserve=12)
        self.assertTrue(accepted, reason)
        values = self.app.staged["values"]
        for lane in ("marketSell", "marketFlip"):
            self.assertEqual(values[lane + ".custom.undercutGold"], 0)
            self.assertEqual(values[lane + ".custom.floorPct"], 100)
            self.assertFalse(values[lane + ".enabled"])
        self.assertEqual(values["marketRent.custom.goldReserve"], 12)
        self.assertFalse(values["marketRent.enabled"])
        self.assertEqual(values["marketRent.custom.maxAttempts"], 0)
        self.assertEqual(values["marketRent.custom.maxGoldSpend"], 0)
        self.assertEqual(values["marketWatch.custom.undercutGold"], 1)
        self.assertEqual(values["marketWatch.custom.floorPct"], 95)

    def test_price_and_reserve_bounds_refuse_coercion_or_clamping(self):
        for key, values in (("marketUndercutGold", (-1, 4, 0.5, "2", True)),
                            ("marketPriceFloorPct", (89, 101, 95.5, "95", False)),
                            ("marketRentGoldReserve", (-1, 1000000001, 1.5, "5", True))):
            for value in values:
                with self.subTest(key=key, value=value):
                    accepted, reason = self.preview(**{key: value})
                    self.assertFalse(accepted)
                    self.assertIn(key, reason)
                    self.assertIsNone(self.app.staged)
                    self.assertEqual(self.app.importReview.original[key], value)

    def test_imported_floor_and_undercut_reach_actual_sell_quote(self):
        import test_market_sell_runtime as sells
        for undercut in (0, 1):
            with self.subTest(undercut=undercut):
                accepted, reason = self.preview(marketUndercutGold=undercut, marketPriceFloorPct=100)
                self.assertTrue(accepted, reason)
                f = sells.MarketSellRuntimeTests()
                f.setUp()
                try:
                    self.assertTrue(f.app.ApplyProfile(f.app, lua_table(f.h.lua, plain(self.app.staged)))[0])
                    self.assertTrue(f.app.model.paused)
                    for key, value in {"enabled": True, "custom.selectedItemId": "w_baton",
                                       "custom.maxListings": 1, "custom.maxListAttempts": 1,
                                       "custom.minNet": 1, "custom.likelyOnly": False}.items():
                        self.assertTrue(f.app.Set(f.app, "marketSell." + key, value)[0])
                    f.app.Resume(f.app)
                    raw = f.raw()
                    f.warm(raw)
                    f.app.Step(f.app, raw)
                    f.executor.Drain(f.executor)
                    self.assertEqual(len(f.executor.calls), 1 if undercut == 0 else 0)
                    if undercut == 1:
                        # A 100%-of-RAP floor holds the 13-Gold ask; an explicit change permits it.
                        f.app.Set(f.app, "marketSell.custom.floorPct", 90)
                        f.app.Step(f.app, raw)
                        f.executor.Drain(f.executor)
                        self.assertEqual(len(f.executor.calls), 1)
                    self.assertEqual(f.executor.calls[1].args[4], 14 - undercut)
                finally:
                    f.tearDown()

    def test_imported_gold_reserve_reaches_actual_rental_admission(self):
        import test_market_rent_runtime as rents
        accepted, reason = self.preview(marketRentGoldReserve=12)
        self.assertTrue(accepted, reason)
        f = rents.MarketRentRuntimeTests()
        f.setUp()
        try:
            self.assertTrue(f.app.ApplyProfile(f.app, lua_table(f.h.lua, plain(self.app.staged)))[0])
            self.assertTrue(f.app.model.paused)
            for key, value in (("enabled", True), ("custom.maxAttempts", 1), ("custom.maxGoldSpend", 2)):
                self.assertTrue(f.app.Set(f.app, "marketRent." + key, value)[0])
            f.app.Resume(f.app)
            f.step(loose=10, bound=3)
            self.assertEqual(len(f.executor.queued), 0)
            self.assertEqual(len(f.executor.calls), 0)
            f.app.Set(f.app, "marketRent.custom.goldReserve", 8)
            f.step(revision=2, loose=10, bound=3)
            f.executor.Drain(f.executor)
            self.assertEqual(len(f.executor.calls), 1)
        finally:
            f.tearDown()

    def test_absolute_net_margin_keeps_explicit_legacy_default_and_custom_thresholds(self):
        for margin in (1, 10, 25, 1000000):
            with self.subTest(margin=margin):
                accepted, reason = self.preview(marketFlipMinMargin=margin)
                self.assertTrue(accepted, reason)
                values = self.app.staged["values"]
                self.assertEqual(values["marketFlip.custom.minMargin"], margin)
                self.assertEqual(self.app.importReview.mapped["marketFlip.custom.minMargin"], margin)
                self.assertEqual(values["marketFlip.custom.minMarginPct"], 10)
                self.assertEqual(values["marketWatch.custom.minMargin"], 2)
                self.assertEqual(values["marketFlip.custom.sessionBudget"], 0)
                self.assertEqual(values["marketFlip.custom.maxAttempts"], 0)
                self.assertEqual(values["marketFlip.custom.maxListAttempts"], 0)
                self.assertFalse(any(value for key, value in values.items() if key.endswith(".enabled")))
                self.assertTrue(self.app.ApplyProfile(self.app, self.app.staged)[0])
                self.assertTrue(self.app.model.paused)
                self.assertEqual(len(self.f.base.storage.data), 0)

    def test_margin_outside_exact_current_integer_range_is_reviewable_without_clamping(self):
        for value in (0, 1000001, 9999999, 1.5, "25", True):
            with self.subTest(value=value):
                accepted, reason = self.preview(marketFlipMinMargin=value)
                self.assertFalse(accepted)
                self.assertIn("marketFlipMinMargin", reason)
                self.assertIsNone(self.app.staged)
                self.assertEqual(self.app.importReview.original.marketFlipMinMargin, value)

    def test_imported_margin_blocks_actual_buy_until_explicitly_changed(self):
        accepted, reason = self.preview(marketFlipMinMargin=25)
        self.assertTrue(accepted, reason)
        f = flips.MarketFlipRuntimeTests()
        f.setUp()
        try:
            self.assertTrue(f.app.ApplyProfile(f.app, lua_table(f.h.lua, plain(self.app.staged)))[0])
            for key, value in {"enabled": True, "custom.scope": "Selected item",
                               "custom.selectedItemId": "w_baton", "custom.maxBuy": 8,
                               "custom.sessionBudget": 8, "custom.goldReserve": 5,
                               "custom.maxAttempts": 1, "custom.maxListAttempts": 1,
                               "custom.minMarginPct": 0, "custom.undercutGold": 0,
                               "custom.floorPct": 90, "custom.requireCoverage": True}.items():
                self.assertTrue(f.app.Set(f.app, "marketFlip." + key, value)[0])
            self.assertEqual(f.app.model["values"]["marketFlip.custom.minMargin"], 25)
            f.app.Resume(f.app)
            raw = f.raw()
            f.warm(raw); f.app.Step(f.app, raw); f.executor.Drain(f.executor)
            self.assertEqual(len(f.executor.calls), 0)
            self.assertEqual(f.tab.transactions.BuyUsage(f.tab.transactions).spent, 0)
            self.assertTrue(f.app.Set(f.app, "marketFlip.custom.minMargin", 3)[0])
            f.warm(raw); f.app.Step(f.app, raw); f.executor.Drain(f.executor)
            self.assertEqual(len(f.executor.calls), 1)
            self.assertEqual(f.executor.calls[1].args[1], "buy")
        finally:
            f.tearDown()

    def test_margin_import_does_not_clear_unknown_custody_or_consumed_allowance(self):
        accepted, reason = self.preview(marketFlipMinMargin=25)
        self.assertTrue(accepted, reason)
        f = flips.MarketFlipRuntimeTests()
        f.setUp()
        try:
            f.begin_buy({"ok": True, "pending": True})
            custody = plain(f.tab.transactions.Active(f.tab.transactions))
            usage = plain(f.tab.transactions.BuyUsage(f.tab.transactions))
            records = plain(f.runtime.checkpoint.Records(f.runtime.checkpoint))
            self.assertEqual(usage["spent"], 8)
            self.assertEqual(len(records), 1)
            self.assertTrue(f.app.ApplyProfile(f.app, lua_table(f.h.lua, plain(self.app.staged)))[0])
            self.assertTrue(f.app.model.paused)
            self.assertFalse(f.app.model["values"]["marketFlip.enabled"])
            self.assertEqual(plain(f.tab.transactions.Active(f.tab.transactions)), custody)
            self.assertEqual(plain(f.tab.transactions.BuyUsage(f.tab.transactions)), usage)
            self.assertEqual(plain(f.runtime.checkpoint.Records(f.runtime.checkpoint)), records)
            self.assertEqual(len(f.executor.calls), 1)
        finally:
            f.tearDown()

if __name__ == "__main__":
    unittest.main()
