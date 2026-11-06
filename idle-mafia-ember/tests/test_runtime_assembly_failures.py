"""Startup failures release previously constructed tab owners and expose the cause."""
import unittest

from engine_harness import Harness


class RuntimeAssemblyFailures(unittest.TestCase):
    def fixture(self):
        h = Harness()
        h.lua.globals().Assembly = h.load("src/engine/RuntimeAssembly.luau")
        h.lua.execute('''
            closed = {}
            deps = {Catalog = {}, FeatureRegistry = {}, TabSnapshotAssembler = {},
                TabComposition = {build = function(tabs) return {tabs = tabs} end}}
            local pages = {"heists", "jobs", "operations", "favors", "combat", "crew",
                "inventory", "collection", "money", "property", "safehouse", "prestige",
                "shop", "blackMarket", "family", "territory", "contracts", "trophies",
                "skills", "rewards", "events"}
            for _, id in ipairs(pages) do
                deps[id:sub(1,1):upper() .. id:sub(2) .. "Tab"] = {new = function()
                    return {id = id, Close = function() table.insert(closed, id) end}
                end}
            end
        ''')
        return h

    def test_constructor_failure_reports_bounded_cause_and_closes_prior_owners(self):
        h = self.fixture()
        h.lua.execute('''
            deps.OperationsTab.new = function() error("Strict own-account recall storage required\\nprivate detail") end
            result, reason = Assembly.compose(deps)
        ''')
        self.assertIsNone(h.lua.globals().result)
        self.assertIn("Strict own-account recall storage required", h.lua.globals().reason)
        self.assertNotIn("private detail", h.lua.globals().reason)
        self.assertEqual(list(h.lua.globals().closed.values()), ["jobs", "heists"])

    def test_missing_module_closes_owners_even_if_one_close_raises(self):
        h = self.fixture()
        h.lua.execute('''
            deps.JobsTab.new = function() return {id="jobs", Close=function()
                table.insert(closed,"jobs"); error("close failed") end} end
            deps.OperationsTab = nil
            result, reason = Assembly.compose(deps)
        ''')
        self.assertIsNone(h.lua.globals().result)
        self.assertEqual(list(h.lua.globals().closed.values()), ["jobs", "heists"])

    def test_runtime_environment_failure_closes_all_composed_owners(self):
        h = self.fixture()
        h.lua.execute("result, reason = Assembly.start(deps)")
        self.assertIsNone(h.lua.globals().result)
        self.assertEqual(len(h.lua.globals().closed), 21)
        self.assertEqual(h.lua.globals().closed[1], "events")

    def test_throwing_read_close_preserves_constructor_error_and_tab_cleanup(self):
        h = self.fixture()
        h.lua.execute('''
            deps.HeistsTab.new = function() return {id="heists",
                Close=function() table.insert(closed,"heists") end,
                ReadSources=function() return {{id="board", interval=5}} end} end
            deps.identity, deps.clock, deps.transport, deps.storage = {}, {}, {}, {}
            deps.nativeReader, deps.nativeExecutor, deps.requestLane = {}, {}, {}
            deps.ReadBudget = {new=function() return {} end}
            deps.ReadCoordinator = {new=function() return {Close=function() error("cleanup failed") end} end}
            deps.AutomationRuntime = {new=function() error("original runtime failure") end}
            succeeded, result, reason = pcall(Assembly.start, deps)
        ''')
        self.assertTrue(h.lua.globals().succeeded)
        self.assertIsNone(h.lua.globals().result)
        self.assertIn("original runtime failure", h.lua.globals().reason)
        self.assertEqual(len(h.lua.globals().closed), 21)


if __name__ == "__main__":
    unittest.main()
