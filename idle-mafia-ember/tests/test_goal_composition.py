"""Composed Contract/Trophy goals arbitrate real ordinary planners safely."""
import unittest

from engine_harness import Harness, lua_table


class GoalCompositionTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.registry = self.h.load("src/engine/FeatureRegistry.luau")
        self.catalog = self.h.load("src/ui/Catalog.luau")
        self.modules = {"Contracts": self.h.contracts}
        for name, folder in (("Broker", "engine"), ("Journal", "engine"),
                             ("Context", "game"), ("Scheduler", "engine"),
                             ("Session", "engine"), ("Checkpoint", "storage")):
            self.modules[name] = self.h.load(f"src/{folder}/{name}.luau")
        self.storage = self.h.lua.execute("""return {
            data = {}, strictRecovery = true,
            Read = function(self, key) return self.data[key] end,
            Write = function(self, key, value)
                self.data[key] = value; return true
            end }""")
        self.make_tab = self.h.lua.eval("""function(id, specs)
            return {id = id, Descriptors = function() return specs end}
        end""")

    def goal_spec(self, feature):
        if feature == "autoContracts":
            folder, reader, blocked, requests = (
                "contracts", "ContractGoalState", "ContractGoalBlocked",
                "ContractGoalRequests")
        else:
            folder, reader, blocked, requests = (
                "trophies", "TrophyFocusState", "TrophyFocusBlocked",
                "TrophyGoalRequests")
        return {"id": feature,
                "reader": self.h.load(f"src/tabs/{folder}/{reader}.luau"),
                "planner": self.h.load(f"src/tabs/{folder}/{blocked}.luau"),
                "evidence": self.h.load(f"src/tabs/{folder}/{blocked}.luau"),
                "goals": self.h.load(f"src/tabs/{folder}/{requests}.luau")}

    def compose(self, feature, spec=None):
        jobs = {"id": "jobs", "reader": self.h.load("src/game/JobsState.luau"),
                "planner": self.h.load("src/features/Jobs.luau"),
                "evidence": self.h.load("src/features/JobsEvidence.luau")}
        page = "contracts" if feature == "autoContracts" else "trophies"
        tabs = lua_table(self.h.lua, [
            self.make_tab("jobs", lua_table(self.h.lua, [jobs])),
            self.make_tab(page, lua_table(self.h.lua, [
                spec if spec is not None else self.goal_spec(feature)])),
        ])
        return self.h.load("src/tabs/TabComposition.luau").build(
            tabs, self.catalog, self.registry,
            self.h.load("src/tabs/TabSnapshotAssembler.luau"))

    def runtime(self, feature):
        composed, reason = self.compose(feature)
        self.assertIsNone(reason)
        return self.h.load("src/engine/AutomationRuntime.luau").new(
            lua_table(self.h.lua, {
                "modules": self.modules, "features": composed["features"],
                "featurePages": composed["featurePages"],
                "clock": self.h.clock, "transport": self.h.transport,
                "storage": self.storage, "identity": self.h.session,
            }))

    def raw(self, revision=1, progress=0, ready=False, owned=False):
        row = {"id": "c_jobs", "done": progress >= 2,
               "claimed": False, "progress": progress, "goal": 2}
        rows = [row] + [{"id": f"c_other{i}", "done": False,
                        "claimed": False, "progress": 0, "goal": 10}
                       for i in range(4)]
        return self.h.snapshot(revision=revision, catalogKey="a" * 64,
            native={"fullSync": True, "serverNow": 1000 + revision,
                    "level": 10, "cash": 100, "pools": {"energy": 10},
                    "jobs": {"j_target": {"completions": progress}},
                    "inventory": {"t_ashportkey": 1} if owned else {},
                    "inventoryBound": {}, "collection": {}, "collectionBound": {},
                    "contracts": {"daily": rows, "weekly": rows},
                    "derived": {"autoJobs": False,
                                "contractDayReset": 2000,
                                "contractWeekReset": 3000,
                                "trophyReady": ["t_ashportkey"] if ready else []}},
            contractTemplates=[{"id": "c_jobs", "key": "jobs"}],
            trophyCatalog=[{"id": "t_ashportkey", "kind": "trophy",
                            "goal": {"kind": "mastery", "goldTier": 1,
                                     "ids": ["j_target"]}}],
            jobCatalog=[{"id": "j_other", "level": 1, "energy": 1,
                         "cash": 100, "xp": 1},
                        {"id": "j_target", "level": 1, "energy": 1,
                         "cash": 1, "xp": 1}],
            masteryRules=[{"name": "Gold", "completions": 10,
                           "energyDiscount": 0}])

    def settings(self, feature, **changes):
        value = {"jobs": {"enabled": True, "policy": "Cash"},
                 feature: {"enabled": True, "borrowJobs": True,
                           "goalId": "t_ashportkey"}}
        value.update(changes)
        return lua_table(self.h.lua, value)

    def test_contract_goal_is_routed_after_tab_composition(self):
        runtime = self.runtime("autoContracts")
        runtime.Resume(runtime)
        status = runtime.Step(runtime, self.raw(), self.settings("autoContracts"))
        state = status["goals"]["autoContracts"]
        self.assertIsNotNone(state, "Composed Contract goals must reach arbitration")
        self.assertTrue(state["routed"])
        self.assertEqual(state["target"], "c_jobs")
        self.assertEqual(self.h.transport["sent"][1]["feature"], "jobs")

    def test_explicit_hire_borrowing_derives_only_current_native_hires_goal(self):
        raw = self.raw()
        raw.contractTemplates[1].key = "hires"
        reader = self.h.load("src/tabs/contracts/ContractGoalState.luau")
        view,reason = reader.read(raw,raw)
        self.assertIsNone(reason)
        requests,reason = self.goal_spec("autoContracts")["goals"].derive(view,
            lua_table(self.h.lua,{"enabled":True,"borrowHires":True}))
        self.assertIsNone(reason)
        self.assertEqual(len(requests.requests),2)
        self.assertEqual(requests.requests[1].routes[1],"crewHire")

    def test_trophy_goal_chooses_remaining_target_using_ordinary_limits(self):
        runtime = self.runtime("trophyFocus")
        runtime.Resume(runtime)
        runtime.Step(runtime, self.raw(), self.settings("trophyFocus"))
        sent = self.h.transport["sent"][1]
        self.assertEqual(sent["intent"]["targetId"], "j_target",
                         "Cash policy must be filtered to the selected Trophy city")
        self.assertEqual(sent["feature"], "jobs")

    def test_goals_do_not_enable_an_ordinary_feature(self):
        for feature in ("autoContracts", "trophyFocus"):
            with self.subTest(feature=feature):
                runtime = self.runtime(feature)
                runtime.Resume(runtime)
                status = runtime.Step(runtime, self.raw(), self.settings(
                    feature, jobs={"enabled": False, "policy": "Cash"}))
                self.assertEqual(len(self.h.transport["sent"]), 0)
                self.assertFalse(status["goals"][feature]["routed"])
                runtime.Close(runtime)

    def test_unborrowed_trophy_does_not_override_ordinary_job_choice(self):
        runtime = self.runtime("trophyFocus")
        runtime.Resume(runtime)
        status = runtime.Step(runtime, self.raw(), self.settings("trophyFocus",
            trophyFocus={"enabled": True, "borrowJobs": False,
                         "goalId": "t_ashportkey"}))
        self.assertEqual(self.h.transport["sent"][1]["intent"]["targetId"],
                         "j_other")
        self.assertFalse(status["goals"]["trophyFocus"]["routed"])

    def test_trophy_target_cannot_bypass_ordinary_level_bounds(self):
        runtime = self.runtime("trophyFocus")
        runtime.Resume(runtime)
        raw = self.raw()
        raw["jobCatalog"][2]["level"] = 2
        status = runtime.Step(runtime, raw, self.settings("trophyFocus",
            jobs={"enabled": True, "policy": "Cash", "limitsEnabled": True,
                  "minLevel": 1, "maxLevel": 1}))
        self.assertEqual(self.h.transport["sent"][1]["intent"]["targetId"],
                         "j_other")
        self.assertFalse(status["goals"]["trophyFocus"]["routed"])

    def test_trophy_target_cannot_spend_shared_energy_reserve(self):
        runtime = self.runtime("trophyFocus")
        runtime.Resume(runtime)
        status = runtime.Step(runtime, self.raw(), self.settings("trophyFocus",
            jobs={"enabled": True, "policy": "Cash", "energyReserve": 10}))
        self.assertEqual(len(self.h.transport["sent"]), 0)
        self.assertFalse(status["goals"]["trophyFocus"]["routed"])

    def test_contract_progress_and_completion_require_new_native_observations(self):
        runtime = self.runtime("autoContracts")
        runtime.Resume(runtime)
        settings = self.settings("autoContracts", jobs={"enabled": True,
            "policy": "Selected job", "selectedJobId": "j_target"})
        first = runtime.Step(runtime, self.raw(), settings)
        self.assertEqual(first["goals"]["autoContracts"]["state"], "waiting")
        self.h.transport["callbacks"][1](lua_table(self.h.lua, {"ok": True}))
        unchanged = runtime.Step(runtime, self.raw(), settings)
        self.assertEqual(unchanged["goals"]["autoContracts"]["state"], "waiting")
        self.h.at(1)
        progressed = runtime.Step(runtime, self.raw(2, progress=1), settings)
        self.assertEqual(progressed["goals"]["autoContracts"]["state"], "progressed")
        self.assertEqual(progressed["outcomes"]["jobs"], "confirmed")
        self.h.transport["callbacks"][2](lua_table(self.h.lua, {"ok": True}))
        self.h.at(2)
        complete = runtime.Step(runtime, self.raw(3, progress=2), settings)
        self.assertEqual(complete["goals"]["autoContracts"]["state"], "complete")
        self.assertFalse(complete["goals"]["autoContracts"]["routed"])
        self.assertTrue(settings["jobs"]["enabled"],
                        "Completing a goal must preserve the ordinary user choice")

    def test_contract_reset_boundary_is_not_reported_as_progress(self):
        runtime = self.runtime("autoContracts")
        runtime.Resume(runtime)
        settings = self.settings("autoContracts", jobs={"enabled": True,
            "policy": "Selected job", "selectedJobId": "j_target"})
        runtime.Step(runtime, self.raw(), settings)
        self.h.transport["callbacks"][1](lua_table(self.h.lua, {"ok": True}))
        self.h.at(1)
        raw = self.raw(2, progress=1)
        raw["native"]["derived"]["contractDayReset"] = 4000
        raw["native"]["derived"]["contractWeekReset"] = 5000
        status = runtime.Step(runtime, raw, settings)
        self.assertEqual(status["goals"]["autoContracts"]["state"], "waiting")

    def test_ready_or_owned_trophy_needs_a_separate_claim_feature(self):
        for ready, owned, expected in ((True, False, "ready"),
                                       (False, True, "owned")):
            with self.subTest(expected=expected):
                runtime = self.runtime("trophyFocus")
                runtime.Resume(runtime)
                status = runtime.Step(runtime, self.raw(ready=ready, owned=owned),
                    self.settings("trophyFocus", jobs={"enabled": False}))
                self.assertEqual(status["goals"]["trophyFocus"]["state"], expected)
                self.assertFalse(status["goals"]["trophyFocus"]["routed"])
                self.assertEqual(len(self.h.transport["sent"]), 0)
                runtime.Close(runtime)

    def test_paused_and_closed_runtime_do_not_route_or_send_goal_actions(self):
        runtime = self.runtime("trophyFocus")
        settings = self.settings("trophyFocus")
        paused = runtime.Step(runtime, self.raw(), settings)
        self.assertEqual(paused["state"], "paused")
        self.assertEqual(len(self.h.transport["sent"]), 0)
        runtime.Resume(runtime)
        runtime.Close(runtime)
        closed = runtime.Step(runtime, self.raw(), settings)
        self.assertEqual(closed["state"], "closed")
        self.assertEqual(len(self.h.transport["sent"]), 0)
        self.assertEqual(list(closed["goals"].items()), [])

    def test_malformed_goal_module_fails_composition(self):
        valid = self.goal_spec("autoContracts")["goals"]
        for malformed in (False, {}, {"derive": valid.derive},
                          {"derive": False, "observe": valid.observe}):
            with self.subTest(malformed=malformed):
                spec = self.goal_spec("autoContracts")
                spec["goals"] = malformed
                composed, reason = self.compose("autoContracts", spec)
                self.assertIsNone(composed)
                self.assertIn("goal", reason.lower())


if __name__ == "__main__":
    unittest.main()
