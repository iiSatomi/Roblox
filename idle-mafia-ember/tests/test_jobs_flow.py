"""Fake-adapter UI to ordinary Jobs broker flow; never contacts Roblox."""
import unittest

from engine_harness import Harness, lua_table


class JobsFlowTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.storage = self.h.lua.execute("""
            return { data = {}, strictRecovery = true,
                Read = function(self, key) return self.data[key] end,
                Write = function(self, key, value) self.data[key] = value end }
        """)
        modules = lua_table(self.h.lua, {
            "Contracts": self.h.contracts,
            "Broker": self.h.load("src/engine/Broker.luau"),
            "Journal": self.h.load("src/engine/Journal.luau"),
            "Context": self.h.load("src/game/Context.luau"),
            "JobsState": self.h.load("src/game/JobsState.luau"),
            "Jobs": self.h.load("src/features/Jobs.luau"),
            "JobsEvidence": self.h.load("src/features/JobsEvidence.luau"),
            "Scheduler": self.h.load("src/engine/Scheduler.luau"),
            "Session": self.h.load("src/engine/Session.luau"),
            "Checkpoint": self.h.load("src/storage/Checkpoint.luau"),
        })
        tab = self.h.load("src/tabs/jobs/Module.luau").new(
            lua_table(self.h.lua, {
                "NativeJobCatalog": self.h.load(
                    "src/tabs/jobs/NativeJobCatalog.luau"),
                "JobsState": modules["JobsState"], "Jobs": modules["Jobs"],
                "JobsEvidence": modules["JobsEvidence"],
                "gameData": {"JOBS": [{"id": "j_watch", "level": 1,
                    "energy": 1, "cash": 60, "xp": 2}]},
                "config": {"MASTERY": [{"completions": 25,
                    "energyDiscount": 0}]},
                "fingerprint": "a" * 64, "release": "release-a",
            }))
        self.runtime = self.h.load("src/features/JobsRuntime.luau").new(
            lua_table(self.h.lua, {
                "clock": self.h.clock, "transport": self.h.transport,
                "storage": self.storage, "identity": self.h.session,
                "modules": modules, "tab": tab,
            })
        )
        self.ember = self.h.load("tests/ember_double.lua")()
        deps = lua_table(self.h.lua, {
            "Ember": self.ember,
            "Catalog": self.h.load("src/ui/Catalog.luau"),
            "Settings": self.h.load("src/storage/Settings.luau"),
            "EmberAdapter": self.h.load("src/ui/EmberAdapter.luau"),
            "JobsRuntime": self.runtime,
            "JobsTab": self.h.load("src/tabs/jobs/Module.luau"),
        })
        self.app = self.h.load("src/App.luau").start(deps)

    def raw(self, revision=1, completions=0):
        return self.h.snapshot(
            revision=revision,
            native={"fullSync": True, "level": 2, "pools": {"energy": 5},
                    "jobs": {"j_watch": {"completions": completions}},
                    "derived": {"autoJobs": False}},
        )

    def test_ui_settings_send_then_confirm_on_exact_progress(self):
        self.app.Set(self.app, "jobs.enabled", True)
        self.app.Resume(self.app)
        self.app.Step(self.app, self.raw())
        self.assertEqual(len(self.h.transport["sent"]), 1)
        self.assertIn("Awaiting", self.app.ui.features.jobs.status.value)
        self.h.transport["callbacks"][1](lua_table(self.h.lua, {"ok": True}))
        self.app.Step(self.app, self.raw())
        self.assertNotIn("Confirmed", self.app.ui.features.jobs.status.value)
        self.app.Step(self.app, self.raw(2, 1))
        self.assertIn("Confirmed", self.app.ui.features.jobs.status.value)

    def test_selected_job_setting_reaches_jobs_planner(self):
        self.assertTrue(self.app.Set(self.app, "jobs.policy", "Selected job")[0])
        self.assertTrue(self.app.Set(self.app, "jobs.custom.selectedJobId", "j_watch")[0])
        self.app.Set(self.app, "jobs.enabled", True)
        self.app.Resume(self.app)
        self.app.Step(self.app, self.raw())
        self.assertEqual(len(self.h.transport["sent"]), 1)
        self.assertEqual(self.h.transport["sent"][1]["intent"]["targetId"], "j_watch")

    def test_disable_and_stop_prevent_new_requests(self):
        self.app.Set(self.app, "jobs.enabled", True)
        self.app.Resume(self.app)
        self.app.Set(self.app, "jobs.enabled", False)
        self.app.Step(self.app, self.raw())
        self.assertEqual(len(self.h.transport["sent"]), 0)
        self.app.Stop(self.app)
        resumed, reason = self.app.Resume(self.app)
        self.assertFalse(resumed)
        self.assertIn("reload", reason)
        self.app.Set(self.app, "jobs.enabled", True)
        self.app.Step(self.app, self.raw())
        self.assertEqual(len(self.h.transport["sent"]), 0)

    def test_jobs_tab_rejects_mismatched_release_and_ignores_supplied_quote(self):
        self.app.Set(self.app, "jobs.enabled", True)
        self.app.Resume(self.app)
        wrong = self.raw()
        wrong["release"] = "other-release"
        self.app.Step(self.app, wrong)
        self.assertEqual(len(self.h.transport["sent"]), 0)
        self.assertIn("matching full Sync",
                      self.runtime.Status(self.runtime)["reason"])
        valid = self.raw()
        valid["jobCatalog"] = lua_table(self.h.lua, [
            {"id": "j_watch", "level": 1, "energy": 99,
             "cash": 999999, "xp": 999999}])
        self.app.Step(self.app, valid)
        self.assertEqual(len(self.h.transport["sent"]), 1)
        self.assertEqual(self.h.transport["sent"][1]["resources"]["energy"], 1)

    def test_failed_renderer_pauses_future_sends(self):
        self.app.Set(self.app, "jobs.enabled", True)
        self.app.Resume(self.app)
        self.app.ui.features.jobs.status.throwNext = True
        result = self.app.Step(self.app, self.raw())
        self.assertFalse(result[0])
        self.assertTrue(self.app.model.paused)
        self.assertEqual(self.runtime.Status(self.runtime)["state"], "paused")
        self.app.Step(self.app, self.raw())
        self.assertLessEqual(len(self.h.transport["sent"]), 1)

    def test_rejection_and_unconfirmed_status_are_distinct(self):
        self.app.Set(self.app, "jobs.enabled", True)
        self.app.Resume(self.app)
        self.app.Step(self.app, self.raw())
        self.h.transport["callbacks"][1](lua_table(self.h.lua, {"ok": False}))
        self.app.Step(self.app, self.raw())
        self.assertIn("Rejected", self.app.ui.features.jobs.status.value)
        self.assertEqual(self.runtime.Status(self.runtime)["uncertainCount"], 0)

        self.h.at(1)
        self.app.Step(self.app, self.raw(revision=2))
        self.assertEqual(len(self.h.transport["sent"]), 2)
        self.h.at(46)
        self.app.Step(self.app, self.raw(revision=2))
        self.assertIn("Unconfirmed", self.app.ui.features.jobs.status.value)
        self.assertEqual(self.runtime.Status(self.runtime)["lastOutcome"],
                         "skipped_unconfirmed")

    def tearDown(self):
        if hasattr(self, "app"):
            self.app.Destroy(self.app)
        else:
            self.runtime.Close(self.runtime)


if __name__ == "__main__":
    unittest.main()
