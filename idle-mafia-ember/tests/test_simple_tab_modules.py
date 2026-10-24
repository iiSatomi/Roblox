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
            "MarketBrowse": self.h.load("src/features/MarketBrowse.luau"),
            "MarketPrices": self.h.load("src/features/MarketPrices.luau"),
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
