"""Saved 0.26.530 Jobs terms through current UI/broker/native call translation."""
import json
from pathlib import Path
import unittest

import test_automation_runtime as runtime_fixture
from engine_harness import lua_table


ROOT = Path(__file__).resolve().parents[1]


class JobsReleaseParityTests(unittest.TestCase):
    def setUp(self):
        base = runtime_fixture.AutomationRuntimeTests()
        base.setUp()
        self.h, self.base = base.h, base
        modules, order = base.runtime.modules, base.runtime.order
        base.runtime.Close(base.runtime)
        self.saved = json.loads((ROOT / "tests/fixtures/jobs-0.26.530.json").read_text())
        self.tab = self.h.load("src/tabs/jobs/Module.luau").new(lua_table(self.h.lua, {
            "NativeJobCatalog": self.h.load("src/tabs/jobs/NativeJobCatalog.luau"),
            "JobsState": self.h.load("src/game/JobsState.luau"),
            "Jobs": self.h.load("src/features/Jobs.luau"),
            "JobsEvidence": self.h.load("src/features/JobsEvidence.luau"),
            "gameData": {"JOBS": self.saved["jobs"]},
            "config": {"MASTERY": [{"completions": 25, "energyDiscount": 0}]},
            "fingerprint": "a" * 64, "release": "release-a"}))
        for index, spec in order.items():
            if spec.id == "jobs": order[index] = self.tab.Descriptor(self.tab)
        self.executor = self.h.lua.execute("""return { calls={},
            Schedule=function(self, callback) callback(); return true end,
            Invoke=function(self, remote, method, ...)
                self.calls[#self.calls+1]={remote=remote,method=method,args=table.pack(...)}
                return {ok=true}
            end }""")
        adapter = self.h.load("src/transport/NativeDispatchAdapter.luau").new(
            self.h.load("src/transport/NativeCallPlan.luau"), self.executor)
        self.runtime = self.h.load("src/engine/AutomationRuntime.luau").new(lua_table(self.h.lua, {
            "clock": self.h.clock, "transport": adapter, "storage": base.storage,
            "identity": self.h.session, "modules": modules, "features": order}))
        self.app = self.h.load("src/App.luau").start(lua_table(self.h.lua, {
            "Ember": self.h.load("tests/ember_double.lua")(),
            "Catalog": self.h.load("src/ui/Catalog.luau"),
            "Settings": self.h.load("src/storage/Settings.luau"),
            "EmberAdapter": self.h.load("src/ui/EmberAdapter.luau"),
            "JobsTab": self.h.load("src/tabs/jobs/Module.luau"),
            "automationRuntimeInstance": self.runtime}))

    def tearDown(self):
        self.app.Destroy(self.app)

    def raw(self, revision=1, level=196, completed=0, active=False):
        raw = self.base.raw(revision=revision)
        raw.native.level, raw.native.maxLevel = level, 196
        raw.native.pools.energy = 500
        raw.native.jobs.j_rewriteoath = lua_table(self.h.lua, {"completions": completed})
        if active:
            raw.native.autoJob = lua_table(self.h.lua, {"mode": "one", "jobId": "j_rewriteoath"})
        return self.tab.Enrich(self.tab, raw)[0]

    def choose(self, ident="j_rewriteoath"):
        for key, value in (("jobs.enabled", True), ("jobs.policy", "Selected job"),
                           ("jobs.custom.selectedJobId", ident)):
            self.assertTrue(self.app.Set(self.app, key, value)[0])
        self.assertTrue(self.app.Resume(self.app)[0])

    def test_all_102_saved_ids_and_17_tiers_are_selectable(self):
        catalog = json.loads((ROOT / "preview/catalog.json").read_text(encoding="utf-8"))
        feature = next(row for row in catalog["features"] if row["id"] == "jobs")
        choices = feature["custom"][0]["options"]
        self.assertEqual(choices, [row["id"] for row in self.saved["jobs"]])
        self.assertEqual(len(set(choices)), 102)
        self.assertEqual({row["tier"] for row in self.saved["jobs"]}, set(range(1, 18)))
        self.assertEqual(self.raw().jobCatalog[102].id, "j_rewriteoath")

    def test_vespera_and_exiles_current_level_unlock_not_historical_maximum(self):
        for ident in ("j_quarries", "j_firstseat", "j_tollmen", "j_rewriteoath"):
            row = next(row for row in self.saved["jobs"] if row["id"] == ident)
            context = self.h.load("src/game/Context.luau").new(self.h.contracts)
            for level, allowed in ((row["level"] - 1, False), (row["level"], True)):
                raw = self.raw(level=level)
                facts = context.Read(context, raw, lua_table(self.h.lua, self.h.session), 0, 2)[0]
                view = self.h.load("src/game/JobsState.luau").read(raw, facts)[0]
                proposal = self.h.load("src/features/Jobs.luau").propose(view,
                    lua_table(self.h.lua, {"enabled": True, "policy": "Selected job",
                        "selectedJobId": ident}), lua_table(self.h.lua, {}))[0]
                self.assertEqual(proposal is not None, allowed, (ident, level))

    def test_exiles_exact_native_call_and_completion_with_other_tabs_selected(self):
        self.choose()
        self.assertTrue(self.app.Set(self.app, "collect.enabled", True)[0])
        raw = self.raw()
        raw.native.operations.active = lua_table(self.h.lua, [])
        self.assertTrue(self.app.Step(self.app, raw)[0])
        self.assertEqual(len(self.executor.calls), 1)
        call = self.executor.calls[1]
        self.assertEqual((call.remote, call.method, call.args.n, call.args[1]),
                         ("DoJob", "InvokeServer", 1, "j_rewriteoath"))
        self.assertNotEqual(self.runtime.Status(self.runtime).outcomes.jobs, "confirmed")
        after = self.raw(2, completed=1)
        after.native.operations.active = lua_table(self.h.lua, [])
        self.app.Step(self.app, after)
        self.assertEqual(self.runtime.Status(self.runtime).outcomes.jobs, "confirmed")
        self.assertEqual(len(self.executor.calls), 1)

    def test_native_auto_jobs_owns_lane_then_custom_can_resume_when_absent(self):
        self.choose()
        self.app.Step(self.app, self.raw(active=True))
        self.assertEqual(len(self.executor.calls), 0)
        self.app.Step(self.app, self.raw(2))
        self.assertEqual(len(self.executor.calls), 1)


if __name__ == "__main__":
    unittest.main()
