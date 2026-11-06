"""Contract goals request existing planners without sending a second remote."""
import unittest

from engine_harness import Harness, lua_table


class ContractGoalRequestTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.context = self.h.load("src/game/Context.luau").new(
            self.h.contracts)
        self.reader = self.h.load("src/tabs/contracts/ContractGoalState.luau")
        self.goals = self.h.load("src/tabs/contracts/ContractGoalRequests.luau")

    def raw(self, revision=1, progress=2, reset=5000):
        daily = [
            {"id": "c_rounds", "done": False, "claimed": False,
             "progress": progress, "goal": 12},
            {"id": "c_sweat", "done": False, "claimed": False,
             "progress": 10, "goal": 200},
            {"id": "c_collect", "done": False, "claimed": False,
             "progress": 1, "goal": 3},
            {"id": "c_fight", "done": False, "claimed": False,
             "progress": 0, "goal": 5},
            {"id": "c_unknown", "done": False, "claimed": False,
             "progress": 0, "goal": 5},
        ]
        weekly = [{"id": "w_jobs", "done": False, "claimed": False,
                   "progress": 20, "goal": 250}]
        weekly += [{"id": "w_x" + str(i), "done": False,
                    "claimed": False, "progress": 0, "goal": 10}
                   for i in range(2, 6)]
        return self.h.snapshot(revision=revision, native={
            "fullSync": True, "serverNow": 1000,
            "derived": {"contractDayReset": reset,
                        "contractWeekReset": 90000},
            "contracts": {"daily": daily, "weekly": weekly}},
            catalogKey="contracts-build-1", contractTemplates=[
                {"id": "c_rounds", "key": "jobs"},
                {"id": "c_sweat", "key": "energy"},
                {"id": "c_collect", "key": "ops"},
                {"id": "c_fight", "key": "fightwins"},
                {"id": "w_jobs", "key": "jobs"}])

    def view(self, raw):
        context, reason = self.context.Read(self.context, raw,
            lua_table(self.h.lua, self.h.session),
            self.h.lua.globals().testNow, 2)
        self.assertIsNone(reason)
        view, reason = self.reader.read(raw, context)
        self.assertIsNone(reason)
        return view

    def derive(self, view, **choices):
        settings = {"enabled": True, "borrowJobs": False,
                    "borrowOperations": False, "borrowCollect": False}
        settings.update(choices)
        return self.goals.derive(view, lua_table(self.h.lua, settings))

    def test_explicit_jobs_energy_and_collect_routes(self):
        view = self.view(self.raw())
        result, reason = self.derive(view, borrowJobs=True,
            borrowOperations=True, borrowCollect=True)
        self.assertIsNone(reason)
        requests = list(result["requests"].values())
        self.assertEqual([r["metric"] for r in requests],
            ["completedJobs", "jobEnergySpent",
             "collectedOperations", "completedJobs"])
        self.assertEqual([requests[2]["routes"][i] for i in (1, 2)],
                         ["operations", "collect"])
        self.assertEqual(requests[2]["remaining"], 2)
        self.assertEqual(requests[2]["reset"], 5000)
        self.assertEqual(requests[3]["reset"], 90000)
        self.assertTrue(any(row["key"] == "fightwins"
            for row in result["excluded"].values()))

    def test_borrowing_is_independent_and_defaults_to_none(self):
        view = self.view(self.raw())
        self.assertEqual(len(list(self.derive(view)[0]["requests"].values())), 0)
        self.assertEqual(len(list(self.derive(view,
            borrowOperations=True)[0]["requests"].values())), 0)
        self.assertEqual(len(list(self.derive(view,
            borrowCollect=True)[0]["requests"].values())), 0)
        jobs, _ = self.derive(view, borrowJobs=True)
        self.assertEqual(len(list(jobs["requests"].values())), 3)
        disabled, _ = self.goals.derive(view,
            lua_table(self.h.lua, {"enabled": False,
                "borrowJobs": True}))
        self.assertEqual(len(list(disabled["requests"].values())), 0)

    def test_progress_requires_same_row_and_reset(self):
        before = self.view(self.raw())
        request = self.derive(before, borrowJobs=True)[0]["requests"][1]
        newer = self.view(self.raw(2, progress=3))
        self.assertEqual(self.goals.observe(before, newer, request),
                         "progressed")
        rolled = self.view(self.raw(2, progress=3, reset=6000))
        self.assertEqual(self.goals.observe(before, rolled, request),
                         "pending")
        unchanged = self.view(self.raw(2))
        self.assertEqual(self.goals.observe(before, unchanged, request),
                         "pending")
        done_raw = self.raw(2, progress=12)
        done_raw["native"]["contracts"]["daily"][1]["done"] = True
        done = self.view(done_raw)
        self.assertEqual(self.goals.observe(before, done, request),
                         "complete")

    def test_heist_start_uses_only_its_explicit_borrow_permission(self):
        raw = self.raw(progress=0)
        raw.contractTemplates[1].key = "heiststarts"
        view = self.view(raw)
        self.assertEqual(len(self.derive(view)[0].requests), 0)
        result, reason = self.derive(view, borrowHeists=True)
        self.assertIsNone(reason)
        self.assertEqual(len(result.requests), 1)
        self.assertEqual(result.requests[1].metric, "startedHeists")
        self.assertEqual(list(result.requests[1].routes.values()), ["heists"])

    def test_heist_borrowing_does_not_authorize_help_or_sabotage(self):
        for key in ("heisthelps", "heistsabos"):
            raw = self.raw(progress=0)
            raw.contractTemplates[1].key = key
            result, reason = self.derive(self.view(raw), borrowHeists=True)
            self.assertIsNone(reason)
            self.assertEqual(len(result.requests), 0)


if __name__ == "__main__":
    unittest.main()
