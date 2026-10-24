"""Per-tab source enrichers must not overwrite one another's release identity."""
import unittest

from engine_harness import Harness, lua_table


class TabSnapshotAssemblerTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.module = self.h.load("src/tabs/TabSnapshotAssembler.luau")
        self.jobs = self.h.lua.execute("""return { id = 'jobs',
            Enrich = function(self, raw)
                local result = {}
                for key, value in pairs(raw) do result[key] = value end
                result.catalogKey = 'release-catalog'
                result.jobCatalog = { { id = 'j_watch' } }
                return result
            end }""")
        self.operations = self.h.lua.execute("""return { id = 'operations',
            Enrich = function(self, raw)
                local result = {}
                for key, value in pairs(raw) do result[key] = value end
                result.catalogKey = 'release-catalog'
                result.operationCatalog = { { id = 'op_fence' } }
                return result
            end }""")

    def test_two_tab_enrichers_preserve_both_catalogs(self):
        assembler = self.module.new(lua_table(self.h.lua,
            [self.jobs, self.operations]))
        raw = self.h.snapshot(native={"fullSync": True})
        combined, reasons = assembler.Enrich(assembler, raw)
        self.assertEqual(combined["jobCatalog"][1]["id"], "j_watch")
        self.assertEqual(combined["operationCatalog"][1]["id"], "op_fence")
        self.assertIsNone(reasons["jobs"])
        self.assertIsNone(reasons["operations"])
        self.assertIsNone(raw["catalogKey"])

    def test_conflicting_catalog_key_blocks_only_second_tab(self):
        self.operations["Enrich"] = self.h.lua.eval("""function(self, raw)
            return { catalogKey = 'different', operationCatalog = {} }
        end""")
        assembler = self.module.new(lua_table(self.h.lua,
            [self.jobs, self.operations]))
        combined, reasons = assembler.Enrich(assembler,
            self.h.snapshot(native={"fullSync": True}))
        self.assertEqual(combined["catalogKey"], "release-catalog")
        self.assertIsNone(combined["operationCatalog"])
        self.assertIn("fingerprint", reasons["operations"])

    def test_duplicate_tab_is_rejected(self):
        with self.assertRaises(Exception):
            self.module.new(lua_table(self.h.lua, [self.jobs, self.jobs]))

    def test_sparse_tab_list_is_rejected(self):
        tabs = self.h.lua.table()
        tabs[1], tabs[3] = self.jobs, self.operations
        with self.assertRaises(Exception):
            self.module.new(tabs)


if __name__ == "__main__":
    unittest.main()
