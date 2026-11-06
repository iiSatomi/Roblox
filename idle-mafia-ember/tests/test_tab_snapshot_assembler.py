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

    def test_ten_owned_proofs_allowed_and_eleven_refused(self):
        for count, accepted in ((10,True),(11,False)):
            self.jobs.ownedProofs = self.h.lua.table_from([f"owned{i}Proof" for i in range(count)])
            constructor=self.h.lua.eval("function(module,tabs) return pcall(module.new,tabs) end")
            module=self.h.load("src/tabs/TabSnapshotAssembler.luau")
            self.assertEqual(constructor(module,self.h.lua.table_from([self.jobs]))[0],accepted)

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

    def test_declared_proof_replaces_caller_data_using_current_settings(self):
        tab = self.h.lua.execute("""return {id='crew',ownedProofs={'crewReplacementOwnerProof'},
            Enrich=function(self,raw,settings)
                assert(raw.crewReplacementOwnerProof==nil)
                local result={} for key,value in pairs(raw) do result[key]=value end
                result.crewReplacementOwnerProof={slot=settings.crewRoll.custom.slot}
                return result end} """)
        assembler = self.module.new(lua_table(self.h.lua, [tab]))
        raw = self.h.snapshot()
        raw.crewReplacementOwnerProof = self.h.lua.table_from({'slot': 99})
        enriched, reasons = assembler.Enrich(assembler, raw, lua_table(self.h.lua,
            {'crewRoll': {'custom': {'slot': 3}}}))
        self.assertIsNone(reasons.crew)
        self.assertEqual(enriched.crewReplacementOwnerProof.slot, 3)
        self.assertEqual(raw.crewReplacementOwnerProof.slot, 99)

    def test_proof_declaration_cannot_claim_native_or_another_tabs_proof(self):
        for key in ('native', 'session', 'catalogKey'):
            self.jobs.ownedProofs = self.h.lua.table_from([key])
            with self.assertRaises(Exception):
                self.module.new(lua_table(self.h.lua, [self.jobs]))
        self.jobs.ownedProofs = self.h.lua.table_from(['sharedProof'])
        self.operations.ownedProofs = self.h.lua.table_from(['sharedProof'])
        with self.assertRaises(Exception):
            self.module.new(lua_table(self.h.lua, [self.jobs, self.operations]))

    def test_sparse_tab_list_is_rejected(self):
        tabs = self.h.lua.table()
        tabs[1], tabs[3] = self.jobs, self.operations
        with self.assertRaises(Exception):
            self.module.new(tabs)


if __name__ == "__main__":
    unittest.main()
