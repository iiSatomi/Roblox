"""Optional native Job bounds retain legacy constraints through actual App paths."""
import unittest
import test_jobs_flow as fixture
import test_trophy_goal_runtime as shared_fixture
from engine_harness import lua_table
class JobBoundsAppTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.JobsFlowTests();self.f.setUp();self.app=self.f.app;self.h=self.f.h
    def tearDown(self):self.f.tearDown()
    def set(self,key,value):
        self.assertTrue(self.app.Set(self.app,"jobs.custom."+key,value)[0])
    def run_job(self):
        self.app.Set(self.app,"jobs.enabled",True);self.app.Resume(self.app);self.app.Step(self.app,self.f.raw())
    def test_disabled_bounds_preserve_cached_values_without_restricting_jobs(self):
        self.set("minLevel",100);self.set("maxCost",0);self.run_job();self.assertEqual(len(self.h.transport.sent),1)
    def test_level_and_current_cost_boundaries_are_inclusive(self):
        self.set("limitsEnabled",True)
        for key in ("minLevel","maxLevel","minCost","maxCost"):self.set(key,1)
        self.run_job();self.assertEqual(len(self.h.transport.sent),1)
    def test_below_minimum_level_does_not_send(self):
        self.set("limitsEnabled",True);self.set("minLevel",2);self.run_job();self.assertEqual(len(self.h.transport.sent),0)
    def test_above_maximum_cost_does_not_send(self):
        self.set("limitsEnabled",True);self.set("maxCost",0);self.run_job();self.assertEqual(len(self.h.transport.sent),0)
    def test_inverted_bounds_wait_instead_of_clamping_or_ignoring_user_constraint(self):
        self.set("limitsEnabled",True);self.set("minLevel",3);self.set("maxLevel",2)
        self.run_job();self.assertEqual(len(self.h.transport.sent),0)
    def test_other_profitable_job_is_filtered_before_ranking(self):
        data={"JOBS":[{"id":"j_watch","level":1,"energy":1,"cash":60,"xp":2},{"id":"j_tag","level":2,"energy":2,"cash":600,"xp":100}]}
        self.f.runtime.tab.catalog=self.h.load("src/tabs/jobs/NativeJobCatalog.luau").new(lua_table(self.h.lua,data),lua_table(self.h.lua,{"MASTERY":[{"completions":25,"energyDiscount":0}]}),"a"*64,"release-a")
        self.set("limitsEnabled",True);self.set("maxLevel",1);self.run_job()
        self.assertEqual(len(self.h.transport.sent),1);self.assertIn("j_watch",self.h.transport.sent[1].actionKey)
    def test_bounds_use_discounted_native_cost_not_catalog_base_energy(self):
        data={"JOBS":[{"id":"j_watch","level":1,"energy":3,"cash":60,"xp":2}]}
        self.f.runtime.tab.catalog=self.h.load("src/tabs/jobs/NativeJobCatalog.luau").new(lua_table(self.h.lua,data),lua_table(self.h.lua,{"MASTERY":[{"completions":25,"energyDiscount":.5}]}),"a"*64,"release-a")
        self.set("limitsEnabled",True);self.set("minCost",2);self.set("maxCost",2)
        self.app.Set(self.app,"jobs.enabled",True);self.app.Resume(self.app)
        raw=self.f.raw();raw.native.jobs.j_watch.masteryTier=1;raw.native.jobs.j_watch.masteryProgress=25;raw.native.jobs.j_watch.completions=25
        self.app.Step(self.app,raw);self.assertEqual(len(self.h.transport.sent),1)
    def test_numeric_input_rejects_fractional_or_negative_level_bounds(self):
        for key,value in (("minLevel",1.5),("maxLevel",0),("minCost",-1),("maxCost",float("nan"))):
            self.assertFalse(self.app.Set(self.app,"jobs.custom."+key,value)[0])
    def test_tightening_bounds_before_shared_executor_emission_prevents_unsent_call(self):
        f=shared_fixture.TrophyGoalRuntimeTests();f.setUp()
        try:
            f.app.Set(f.app,"jobs.enabled",True);f.app.Set(f.app,"jobs.custom.limitsEnabled",True)
            f.app.Step(f.app,f.raw());f.app.Set(f.app,"jobs.custom.maxCost",0)
            f.executor.callback();self.assertEqual(len(f.executor.calls),0)
        finally:f.tearDown()
    def test_below_minimum_cost_and_inverted_cost_range_do_not_send(self):
        self.set("limitsEnabled",True);self.set("minCost",2);self.run_job()
        self.assertEqual(len(self.h.transport.sent),0)
        self.set("minCost",3);self.set("maxCost",2);self.app.Step(self.app,self.f.raw())
        self.assertEqual(len(self.h.transport.sent),0)
    def test_native_confirmation_still_settles_a_sent_job_after_bounds_are_tightened(self):
        self.set("limitsEnabled",True);self.run_job();self.assertEqual(len(self.h.transport.sent),1)
        self.set("maxCost",0);self.h.transport.callbacks[1](lua_table(self.h.lua,{"ok":True}))
        self.app.Step(self.app,self.f.raw(revision=2,completions=1))
        self.assertEqual(self.f.runtime.Status(self.f.runtime).lastOutcome,"confirmed")
        self.assertEqual(len(self.h.transport.sent),1)
    def test_job_numeric_controls_use_existing_typed_input_path(self):
        control=self.app.ui.handles["jobs.custom.minLevel"]
        control.Set(control,"2");self.f.ember.Flush()
        self.assertEqual(self.app.model["values"]["jobs.custom.minLevel"],2)
    def test_trophy_borrowing_respects_job_bounds(self):
        f=shared_fixture.TrophyGoalRuntimeTests();f.setUp()
        try:
            f.targets()
            for key,value in (("jobs.enabled",True),("jobs.custom.limitsEnabled",True),("jobs.custom.minLevel",2),
                ("trophyFocus.enabled",True),("trophyFocus.custom.goalId","t_ashportkey"),("trophyFocus.custom.borrowJobs",True)):
                self.assertTrue(f.app.Set(f.app,key,value)[0])
            f.app.Step(f.app,f.target_raw());self.assertIsNone(f.executor.callback)
        finally:f.tearDown()
if __name__=="__main__":unittest.main()
