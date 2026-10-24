"""Synthetic current-client Job reader; no game request is made."""
import unittest

from engine_harness import Harness, lua_table


class JobsStateTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.context = self.h.load("src/game/Context.luau").new(self.h.contracts)
        self.reader = self.h.load("src/game/JobsState.luau")
        self.native = {
            "fullSync": True, "level": 2, "pools": {"energy": 5},
            "jobs": {"j_watch": {"completions": 30, "masteryProgress": 30,
                                 "masteryTier": 1}},
            "derived": {"autoJobs": False},
        }
        self.raw = {
            **self.h.session, "revision": 1, "capturedAt": 0,
            "native": self.native, "catalogKey": "build-1",
            "jobCatalog": [
                {"id": "j_watch", "level": 1, "energy": 20,
                 "cash": 60, "xp": 2},
                {"id": "j_tag", "level": 2, "energy": 2,
                 "cash": 120, "xp": 4},
            ],
            "masteryRules": [
                {"completions": 25, "energyDiscount": 0},
                {"completions": 50, "energyDiscount": 0.05},
            ],
        }

    def read(self):
        raw = lua_table(self.h.lua, self.raw)
        context, reason = self.context.Read(
            self.context, raw, lua_table(self.h.lua, self.h.session),
            self.h.lua.globals().testNow, 2,
        )
        if context is None:
            return None, reason
        return self.reader.read(raw, context)

    def test_complete_snapshot_normalizes_current_mastery_cost(self):
        view, reason = self.read()
        self.assertIsNone(reason)
        self.assertEqual(view["catalogKey"], "build-1")
        self.assertEqual(view["level"], 2)
        self.assertEqual(view["energy"], 5)
        self.assertEqual(view["jobs"][1]["cost"], 20)
        self.assertEqual(view["jobs"][1]["masteryTier"], 1)
        self.assertEqual(view["jobs"][2]["cost"], 2)
        self.native["jobs"]["j_watch"] = {"completions": 55,
                                            "masteryProgress": 55, "masteryTier": 2}
        upgraded, _ = self.read()
        self.assertEqual(upgraded["jobs"][1]["cost"], 19)

    def test_active_and_unknown_native_owner_block_read(self):
        self.native["autoJob"] = {"mode": "one", "jobId": "j_watch"}
        self.assertIsNone(self.read()[0])
        del self.native["autoJob"]
        self.native["fullSync"] = False
        self.assertIsNone(self.read()[0])

    def test_missing_state_or_invalid_tier_never_defaults_to_eligible(self):
        del self.native["jobs"]
        self.assertIsNone(self.read()[0])
        self.native["jobs"] = {"j_watch": {"masteryTier": 9}}
        self.assertIsNone(self.read()[0])

    def test_revision_or_catalog_change_fails_closed(self):
        raw = lua_table(self.h.lua, self.raw)
        context, _ = self.context.Read(
            self.context, raw, lua_table(self.h.lua, self.h.session), 0, 2)
        raw["revision"] = 2
        self.assertIsNone(self.reader.read(raw, context)[0])
        self.raw["jobCatalog"].append(dict(self.raw["jobCatalog"][0]))
        self.assertIsNone(self.read()[0])

    def test_missing_catalog_or_rules_block(self):
        del self.raw["jobCatalog"]
        self.assertIsNone(self.read()[0])
        self.raw["jobCatalog"] = [{"id": "j_watch", "level": 1,
                                   "energy": 20, "cash": 60, "xp": 2}]
        del self.raw["masteryRules"]
        self.assertIsNone(self.read()[0])

    def test_sparse_catalog_is_not_silently_truncated(self):
        raw = lua_table(self.h.lua, self.raw)
        context, _ = self.context.Read(
            self.context, raw, lua_table(self.h.lua, self.h.session), 0, 2)
        raw["jobCatalog"][3] = lua_table(self.h.lua, {
            "id": "j_boost", "level": 3, "energy": 3, "cash": 200, "xp": 7})
        raw["jobCatalog"][2] = None
        view, reason = self.reader.read(raw, context)
        self.assertIsNone(view)
        self.assertIsNotNone(reason)


if __name__ == "__main__":
    unittest.main()
