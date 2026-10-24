"""Modular tab entries provide one validated descriptor and source boundary."""
import unittest

from engine_harness import Harness, lua_table


class TabCompositionTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.module = self.h.load("src/tabs/TabComposition.luau")
        self.registry = self.h.load("src/engine/FeatureRegistry.luau")
        self.assembler = self.h.load("src/tabs/TabSnapshotAssembler.luau")
        self.catalog = self.h.load("src/ui/Catalog.luau")
        self.reader = self.h.load("src/game/JobsState.luau")
        self.planner = self.h.load("src/features/Jobs.luau")
        self.evidence = self.h.load("src/features/JobsEvidence.luau")
        self.jobs = self.h.lua.execute("""return {
            id = 'jobs', Descriptors = function(self)
                return { { id = 'jobs', reader = reader,
                    planner = planner, evidence = evidence } }
            end, Enrich = function(self, raw)
                local result = {}
                for k, v in pairs(raw) do result[k] = v end
                result.catalogKey = 'bound'
                return result
            end }""")
        self.h.lua.globals().reader = self.reader
        self.h.lua.globals().planner = self.planner
        self.h.lua.globals().evidence = self.evidence

    def test_builds_features_and_optional_enricher(self):
        result, reason = self.module.build(
            lua_table(self.h.lua, [self.jobs]), self.catalog,
            self.registry, self.assembler)
        self.assertIsNone(reason)
        self.assertEqual(result["features"][1]["id"], "jobs")
        self.assertEqual(result["featurePages"]["jobs"], "jobs")
        raw = self.h.snapshot()
        enriched, reasons = result["snapshotAssembler"].Enrich(
            result["snapshotAssembler"], raw)
        self.assertEqual(enriched["catalogKey"], "bound")
        self.assertIsNone(reasons["jobs"])

    def test_invalid_tab_fails_before_composition(self):
        self.jobs["id"] = "heists"
        result, reason = self.module.build(
            lua_table(self.h.lua, [self.jobs]), self.catalog,
            self.registry, self.assembler)
        self.assertIsNone(result)
        self.assertIsNotNone(reason)

    def test_missing_required_tab_fails_before_sender_construction(self):
        result, reason = self.module.build(
            lua_table(self.h.lua, [self.jobs]), self.catalog,
            self.registry, self.assembler,
            lua_table(self.h.lua, ["jobs", "operations"]))
        self.assertIsNone(result)
        self.assertIn("operations", reason)

    def test_matching_required_tab_list_succeeds(self):
        result, reason = self.module.build(
            lua_table(self.h.lua, [self.jobs]), self.catalog,
            self.registry, self.assembler,
            lua_table(self.h.lua, ["jobs"]))
        self.assertIsNone(reason)
        self.assertEqual(result["features"][1]["id"], "jobs")


if __name__ == "__main__":
    unittest.main()
