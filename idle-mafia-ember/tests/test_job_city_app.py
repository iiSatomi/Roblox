"""City selection restricts existing native Job eligibility through actual App paths."""
import unittest
import test_jobs_flow as fixture
from engine_harness import lua_table
class JobCityAppTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.JobsFlowTests();self.f.setUp();self.h=self.f.h;self.app=self.f.app
        self.data={"CITIES":[{"id":"city_ashport","firstTier":1},{"id":"city_caldera","firstTier":4}],
            "JOBS":[{"id":"j_watch","tier":1,"level":1,"energy":1,"cash":60,"xp":2},
                {"id":"j_tag","tier":2,"level":1,"energy":1,"cash":60,"xp":4},
                {"id":"j_boost","tier":4,"level":1,"energy":1,"cash":600,"xp":100}]}
        self.rebuild()
    def tearDown(self):self.f.tearDown()
    def rebuild(self):
        self.f.runtime.tab.catalog=self.h.load("src/tabs/jobs/NativeJobCatalog.luau").new(lua_table(self.h.lua,self.data),lua_table(self.h.lua,{"MASTERY":[{"completions":25,"energyDiscount":0}]}),"a"*64,"release-a")
    def run_job(self):
        self.app.Set(self.app,"jobs.enabled",True);self.app.Resume(self.app);self.app.Step(self.app,self.f.raw())
    def test_selected_city_filters_more_profitable_foreign_job(self):
        self.assertTrue(self.app.Set(self.app,"jobs.custom.city","city_ashport")[0]);self.run_job()
        self.assertEqual(len(self.h.transport.sent),1);self.assertIn("j_tag",self.h.transport.sent[1].actionKey)
    def test_default_all_cities_retains_existing_native_choice(self):
        self.run_job();self.assertIn("j_boost",self.h.transport.sent[1].actionKey)
    def test_unavailable_city_never_falls_back_to_another_city(self):
        self.app.Set(self.app,"jobs.custom.city","city_jade");self.run_job()
        self.assertEqual(len(self.h.transport.sent),0)
    def test_selected_job_and_city_constraints_intersect(self):
        self.app.Set(self.app,"jobs.custom.city","city_ashport");self.app.Set(self.app,"jobs.policy","Selected job")
        self.app.Set(self.app,"jobs.custom.selectedJobId","j_boost");self.run_job();self.assertEqual(len(self.h.transport.sent),0)
    def test_missing_or_ambiguous_membership_holds_only_explicit_city_choice(self):
        self.data["CITIES"][1]["firstTier"]=1;self.rebuild()
        self.app.Set(self.app,"jobs.custom.city","city_ashport");self.run_job();self.assertEqual(len(self.h.transport.sent),0)
    def test_city_and_optional_level_cost_bounds_both_apply(self):
        self.app.Set(self.app,"jobs.custom.city","city_ashport");self.app.Set(self.app,"jobs.custom.limitsEnabled",True)
        self.app.Set(self.app,"jobs.custom.minLevel",2);self.run_job();self.assertEqual(len(self.h.transport.sent),0)
    def test_enriched_city_metadata_is_copied(self):
        cat=self.f.runtime.tab.catalog;raw=self.f.raw();raw.release="release-a"
        first=cat.Enrich(cat,raw)[0];self.assertEqual(first.jobCatalog[1].cityId,"city_ashport")
        first.jobCatalog[1].cityId="changed";first.jobCities[1]="changed"
        second=cat.Enrich(cat,raw)[0];self.assertEqual(second.jobCatalog[1].cityId,"city_ashport");self.assertEqual(second.jobCities[1],"city_ashport")
    def test_missing_city_source_does_not_trust_snapshot_injected_membership(self):
        self.data.pop("CITIES");self.rebuild();self.app.Set(self.app,"jobs.custom.city","city_ashport")
        self.app.Set(self.app,"jobs.enabled",True);self.app.Resume(self.app)
        raw=self.f.raw();raw.jobCities=lua_table(self.h.lua,["city_ashport"])
        self.app.Step(self.app,raw);self.assertEqual(len(self.h.transport.sent),0)
        self.app.Set(self.app,"jobs.custom.city","All unlocked cities");self.app.Step(self.app,self.f.raw())
        self.assertEqual(len(self.h.transport.sent),1)
    def test_city_change_before_shared_emission_proves_no_call_was_sent(self):
        import test_trophy_goal_runtime as shared
        f=shared.TrophyGoalRuntimeTests();f.setUp()
        try:
            f.targets();f.app.Set(f.app,"jobs.enabled",True);f.app.Set(f.app,"jobs.custom.city","city_ashport")
            f.app.Step(f.app,f.target_raw());self.assertIsNotNone(f.executor.callback)
            f.app.Set(f.app,"jobs.custom.city","city_caldera");f.executor.callback()
            self.assertEqual(len(f.executor.calls),0)
        finally:f.tearDown()
    def test_city_change_after_send_keeps_exact_old_job_confirmation(self):
        self.app.Set(self.app,"jobs.custom.city","city_ashport");self.run_job()
        self.app.Set(self.app,"jobs.custom.city","city_caldera")
        self.h.transport.callbacks[1](lua_table(self.h.lua,{"ok":True}))
        raw=self.f.raw(revision=2);raw.native.jobs.j_tag=lua_table(self.h.lua,{"completions":1})
        self.app.Step(self.app,raw)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).lastOutcome,"confirmed");self.assertEqual(len(self.h.transport.sent),1)
    def test_trophy_goal_does_not_override_the_selected_city(self):
        import test_trophy_goal_runtime as shared
        f=shared.TrophyGoalRuntimeTests();f.setUp()
        try:
            f.targets()
            for key,value in (("jobs.enabled",True),("jobs.custom.city","city_caldera"),("trophyFocus.enabled",True),
                ("trophyFocus.custom.goalId","t_ashportkey"),("trophyFocus.custom.borrowJobs",True)):
                self.assertTrue(f.app.Set(f.app,key,value)[0])
            f.app.Step(f.app,f.target_raw())
            active=f.runtime.session.broker.active
            self.assertEqual(active.proposal.feature,"jobs");self.assertIn("j_other",active.proposal.actionKey)
        finally:f.tearDown()
if __name__=="__main__":unittest.main()
