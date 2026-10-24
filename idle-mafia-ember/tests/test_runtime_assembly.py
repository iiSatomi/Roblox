"""Runtime composition preserves a bounded constructor failure reason."""
import unittest

from engine_harness import Harness, lua_table


PAGES = ("heists", "jobs", "operations", "favors", "combat", "crew",
         "inventory", "collection", "money", "property", "safehouse",
         "prestige", "shop", "blackMarket", "family", "territory",
         "contracts", "trophies", "skills", "rewards", "events")


class RuntimeAssemblyTests(unittest.TestCase):
    def test_constructor_error_reports_only_first_line(self):
        h = Harness()
        deps = lua_table(h.lua, {
            "Catalog": {}, "FeatureRegistry": {},
            "TabSnapshotAssembler": {},
            "TabComposition": {
                "build": h.lua.eval("function() return { features = {} } end"),
            },
            "identity": h.session, "clock": h.clock,
            "transport": h.transport, "storage": {},
            "AutomationRuntime": {
                "new": h.lua.eval("""function()
                    error([[Specific constructor failure
private second line]])
                end"""),
            },
        })
        for page in PAGES:
            module = h.lua.table()
            module["new"] = h.lua.eval(
                "function() return { id = '" + page + "' } end")
            deps[page[0].upper() + page[1:] + "Tab"] = module
        assembly = h.load("src/engine/RuntimeAssembly.luau")
        runtime, reason = assembly.start(deps)
        self.assertIsNone(runtime)
        self.assertIn("Specific constructor failure", reason)
        self.assertNotIn("private second line", reason)
        self.assertLessEqual(len(reason), 120)


if __name__ == "__main__":
    unittest.main()
