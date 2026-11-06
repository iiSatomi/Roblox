"""Saved GameData/Config Jobs constants feed the ordinary Jobs planner."""
import unittest

from engine_harness import Harness, lua_table


class NativeJobCatalogTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.module = self.h.load("src/tabs/jobs/NativeJobCatalog.luau")
        self.game = lua_table(self.h.lua, {"JOBS": [
            {"id": "j_watch", "level": 1, "energy": 1,
             "cash": 60, "xp": 2},
            {"id": "j_tag", "level": 2, "energy": 2,
             "cash": 120, "xp": 4},
        ]})
        self.config = lua_table(self.h.lua, {"MASTERY": [
            {"completions": 25, "energyDiscount": 0},
            {"completions": 50, "energyDiscount": 0.05},
        ]})
        self.fingerprint = "a" * 64

    def adapter(self):
        return self.module.new(self.game, self.config,
                               self.fingerprint, "release-a")

    def test_observed_sync_feeds_jobs_reader_and_planner(self):
        adapter = self.adapter()
        reader = self.h.load("src/transport/NativeSnapshotReader.luau").new(
            lua_table(self.h.lua, self.h.session), self.h.clock)
        native = lua_table(self.h.lua, {"level": 2,
            "jobs": {"j_watch": {"completions": 2}},
            "pools": {"energy": 2}})
        self.assertTrue(reader.ObserveSync(reader, native))
        raw, reason = adapter.Enrich(adapter, reader.Capture(reader)[0])
        self.assertIsNone(reason)
        context = self.h.load("src/game/Context.luau").new(
            self.h.contracts, None, None, None, None, None, None, None)
        facts, reason = context.Read(context, raw,
            lua_table(self.h.lua, self.h.session), 0, 2)
        self.assertIsNone(reason)
        view, reason = self.h.load("src/game/JobsState.luau").read(raw, facts)
        self.assertIsNone(reason)
        proposal, reason = self.h.load("src/features/Jobs.luau").propose(
            view, lua_table(self.h.lua, {"enabled": True,
                "policy": "Selected job", "selectedJobId": "j_watch"}),
            lua_table(self.h.lua, {}))
        self.assertIsNone(reason)
        self.assertEqual(proposal["intent"]["targetId"], "j_watch")
        self.assertEqual(proposal["resources"]["energy"], 1)

    def test_catalog_is_copied_and_release_bound(self):
        adapter = self.adapter()
        self.game["JOBS"][1]["energy"] = 99
        raw = self.h.snapshot(native={"fullSync": True})
        enriched, reason = adapter.Enrich(adapter, raw)
        self.assertIsNone(reason)
        self.assertEqual(enriched["jobCatalog"][1]["energy"], 1)
        enriched["jobCatalog"][1]["energy"] = 99
        again = adapter.Enrich(adapter, raw)[0]
        self.assertEqual(again["jobCatalog"][1]["energy"], 1)
        self.assertIsNone(adapter.Enrich(adapter,
            self.h.snapshot(release="other", native={"fullSync": True}))[0])
        self.assertIsNone(adapter.Enrich(adapter,
            self.h.snapshot(native={"fullSync": False}))[0])

    def test_invalid_saved_catalog_fails_closed(self):
        self.game["JOBS"][2]["id"] = "j_watch"
        with self.assertRaises(Exception):
            self.adapter()

    def test_jobs_tab_entry_owns_catalog_and_feature_descriptor(self):
        entry = self.h.load("src/tabs/jobs/Module.luau")
        tab = entry.new(lua_table(self.h.lua, {
            "NativeJobCatalog": self.module,
            "JobsState": self.h.load("src/game/JobsState.luau"),
            "Jobs": self.h.load("src/features/Jobs.luau"),
            "JobsEvidence": self.h.load("src/features/JobsEvidence.luau"),
            "gameData": self.game, "config": self.config,
            "fingerprint": self.fingerprint, "release": "release-a",
        }))
        descriptor = tab.Descriptor(tab)
        self.assertEqual(descriptor["id"], "jobs")
        self.assertEqual(tab["id"], "jobs")
        self.assertEqual(tab.Descriptors(tab)[1]["id"], "jobs")
        self.assertIsNotNone(descriptor["reader"]["read"])
        self.assertIsNotNone(descriptor["planner"]["propose"])
        self.assertIsNotNone(descriptor["evidence"]["evaluate"])
        enriched = tab.Enrich(tab,
            self.h.snapshot(native={"fullSync": True}))[0]
        self.assertEqual(enriched["catalogKey"], self.fingerprint)
        self.game["JOBS"][2]["id"] = "j_tag"
        self.config["MASTERY"][2]["completions"] = 20
        with self.assertRaises(Exception):
            self.adapter()


if __name__ == "__main__":
    unittest.main()
