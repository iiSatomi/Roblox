"""Pure ordinary Job proposals, without a sender or paid controller."""
import unittest

from engine_harness import Harness, lua_table


class JobsPlannerTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.context = self.h.load("src/game/Context.luau").new(self.h.contracts)
        self.reader = self.h.load("src/game/JobsState.luau")
        self.jobs = self.h.load("src/features/Jobs.luau")
        self.raw = {
            **self.h.session, "revision": 1, "capturedAt": 0,
            "catalogKey": "build-1",
            "native": {"fullSync": True, "level": 3,
                       "pools": {"energy": 5},
                       "jobs": {"j_watch": {"completions": 24,
                                            "masteryProgress": 24, "masteryTier": 0}},
                       "derived": {"autoJobs": False}},
            "jobCatalog": [
                {"id": "j_watch", "level": 1, "energy": 1, "cash": 60, "xp": 2},
                {"id": "j_tag", "level": 2, "energy": 2, "cash": 120, "xp": 8},
                {"id": "j_boost", "level": 3, "energy": 3, "cash": 500, "xp": 3},
            ],
            "masteryRules": [{"completions": 25, "energyDiscount": 0},
                             {"completions": 50, "energyDiscount": 0.05}],
        }

    def view(self):
        raw = lua_table(self.h.lua, self.raw)
        context, reason = self.context.Read(
            self.context, raw, lua_table(self.h.lua, self.h.session), 0, 2)
        self.assertIsNone(reason)
        view, reason = self.reader.read(raw, context)
        self.assertIsNone(reason)
        return view

    def propose(self, policy="Balanced", reservations=None, **settings):
        options = {"enabled": True, "policy": policy, **settings}
        return self.jobs.propose(
            self.view(), lua_table(self.h.lua, options),
            lua_table(self.h.lua, reservations or {}),
        )

    def test_supported_policies_choose_deterministically(self):
        xp, _ = self.propose("XP")
        cash, _ = self.propose("Cash")
        balanced, _ = self.propose("Balanced")
        self.assertEqual(xp["intent"]["targetId"], "j_tag")
        self.assertEqual(cash["intent"]["targetId"], "j_boost")
        self.assertEqual(balanced["intent"]["targetId"], "j_tag")
        self.assertEqual(xp["resources"]["energy"], 2)
        self.assertEqual(self.h.contracts.validateProposal(xp, self.view())[1], None)

    def test_selected_job_requires_exact_current_id_and_unlock(self):
        chosen, _ = self.propose("Selected job", selectedJobId="j_watch")
        self.assertEqual(chosen["intent"]["targetId"], "j_watch")
        missing, _ = self.propose("Selected job", selectedJobId="old-id")
        self.assertIsNone(missing)
        self.raw["native"]["level"] = 1
        locked, _ = self.propose("Selected job", selectedJobId="j_boost")
        self.assertIsNone(locked)

    def test_mastery_targets_nearest_incomplete_tier(self):
        proposal, _ = self.propose("Mastery")
        self.assertEqual(proposal["intent"]["targetId"], "j_watch")
        self.raw["native"]["jobs"]["j_watch"] = {
            "completions": 55, "masteryProgress": 55, "masteryTier": 2}
        proposal, _ = self.propose("Mastery")
        self.assertNotEqual(proposal["intent"]["targetId"], "j_watch")

    def test_energy_reserve_and_uncertain_exposure_block_spend(self):
        proposal, _ = self.propose("XP", reservations={"energy": 4})
        self.assertEqual(proposal["intent"]["targetId"], "j_watch")
        blocked, reason = self.propose("XP", reservations={"energy": 4,
                                                          "uncertainEnergy": 1})
        self.assertIsNone(blocked)
        self.assertIn("energy", reason.lower())

    def test_catalog_revision_changes_action_identity(self):
        first, _ = self.propose("Selected job", selectedJobId="j_watch")
        self.raw["revision"] = 2
        self.raw["catalogKey"] = "build-2"
        second, _ = self.propose("Selected job", selectedJobId="j_watch")
        self.assertNotEqual(first["actionKey"], second["actionKey"])
        self.assertEqual(second["intent"]["catalogKey"], "build-2")

    def test_unsupported_city_or_custom_mode_does_not_guess(self):
        self.assertIsNone(self.propose("Custom")[0])
        self.assertIsNone(self.propose("Balanced", city="elsewhere")[0])
        self.assertIsNone(self.propose("Selected job")[0])

    def test_malformed_view_blocks_without_raising(self):
        view = self.view()
        view["catalogKey"] = None
        result, reason = self.jobs.propose(
            view, lua_table(self.h.lua, {"enabled": True, "policy": "XP"}),
            lua_table(self.h.lua, {}),
        )
        self.assertIsNone(result)
        self.assertIsNotNone(reason)


if __name__ == "__main__":
    unittest.main()
