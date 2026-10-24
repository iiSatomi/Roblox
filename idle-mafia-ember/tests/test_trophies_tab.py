"""Trophy source, custody and goal hints remain distinct from trade-ins."""
import unittest

from engine_harness import Harness, lua_table


class TrophiesTabTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.context = self.h.load("src/game/Context.luau").new(
            self.h.contracts)
        self.focus = self.h.load(
            "src/tabs/trophies/TrophyFocusState.luau")
        self.blocked = self.h.load(
            "src/tabs/trophies/TrophyFocusBlocked.luau")

    def test_saved_catalog_marks_consuming_trade_ins(self):
        module = self.h.load(
            "src/tabs/trophies/NativeTrophyCatalog.luau")
        catalog = module.new(lua_table(self.h.lua, {
            "ITEMS": [{"id": "t_eldersignet", "kind": "trophy"},
                      {"id": "t_vesperacase", "kind": "trophy"},
                      {"id": "bg_reward", "kind": "background"}],
            "TROPHY_TRADE_INS": {"t_vesperacase": {"items": []}}}),
            "a" * 64, "release-a")
        raw = self.h.snapshot(release="release-a",
                              native={"fullSync": True})
        enriched, reason = catalog.Enrich(catalog, raw)
        self.assertIsNone(reason)
        self.assertFalse(enriched["trophyCatalog"][1]["tradeIn"])
        self.assertTrue(enriched["trophyCatalog"][2]["tradeIn"])
        self.assertEqual(enriched["trophyCatalog"][3]["kind"],
                         "background")

    def test_focus_reports_routes_without_borrowing(self):
        raw = self.h.snapshot(native={"fullSync": True,
            "derived": {"trophyReady": ["t_eldersignet"]},
            "inventory": {}, "inventoryBound": {},
            "collection": {}, "collectionBound": {}},
            trophyCatalog=[{"id": "t_eldersignet", "kind": "trophy"},
                           {"id": "t_vesperacase", "kind": "trophy",
                            "tradeIn": True},
                           {"id": "t_streetname", "kind": "trophy"}],
            catalogKey="trophy-release-a")
        context = self.context.Read(self.context, raw,
            lua_table(self.h.lua, self.h.session), 0, 2)[0]
        view, reason = self.focus.read(raw, context)
        self.assertIsNone(reason)
        inspect = self.blocked.inspect
        self.assertEqual(inspect(view, lua_table(self.h.lua,
            {"goalId": "t_eldersignet"}))["status"], "ready")
        self.assertEqual(inspect(view, lua_table(self.h.lua,
            {"goalId": "t_vesperacase"}))["status"], "blocked")
        level = inspect(view, lua_table(self.h.lua,
            {"goalId": "t_streetname"}))
        self.assertEqual((level["status"], level["feature"]),
                         ("mapped", "jobs"))
        self.assertIsNone(self.blocked.propose(view,
            lua_table(self.h.lua, {"enabled": True}))[0])
        raw["native"]["collection"]["t_streetname"] = -1
        self.assertIsNone(self.focus.read(raw, context)[0])


if __name__ == "__main__":
    unittest.main()
