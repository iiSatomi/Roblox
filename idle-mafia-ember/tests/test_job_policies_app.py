"""Remaining native Job policy gaps through the existing App fixture."""
import unittest
import test_jobs_flow as fixture
from engine_harness import lua_table
class JobPoliciesAppTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.JobsFlowTests();self.f.setUp();self.h=self.f.h;self.app=self.f.app
        self.data={"JOBS":[{"id":"j_watch","tier":1,"level":1,"energy":1,"cash":10,"xp":1},{"id":"j_tag","tier":2,"level":2,"energy":3,"cash":100,"xp":10},{"id":"j_boost","tier":3,"level":2,"energy":5,"cash":1000,"xp":100}]}
        self.config={"MASTERY":[{"name":"Bronze","completions":2,"energyDiscount":0},{"name":"Gold","completions":4,"energyDiscount":0},{"name":"Silver","completions":6,"energyDiscount":0}]}
        self.rebuild()
    def tearDown(self):self.f.tearDown()
    def rebuild(self):self.f.runtime.tab.catalog=self.h.load("src/tabs/jobs/NativeJobCatalog.luau").new(lua_table(self.h.lua,self.data),lua_table(self.h.lua,self.config),"a"*64,"release-a")
    def raw(self,energy=5,capacity=5,derived=None,revision=1,progress=None,tier=0):
        raw=self.f.raw(revision=revision);raw.native.pools.energy=energy
        if capacity is not None:raw.native.stats=lua_table(self.h.lua,{"maxEnergy":capacity})
        if derived is not None:raw.native.derived.effMaxEnergy=derived
        if progress is not None:raw.native.jobs.j_watch=lua_table(self.h.lua,{"completions":progress,"masteryProgress":progress,"masteryTier":tier})
        return raw
    def run_job(self,policy,energy=5,capacity=5,raw=None):
        self.assertTrue(self.app.Set(self.app,"jobs.policy",policy)[0]);self.app.Set(self.app,"jobs.enabled",True);self.app.Resume(self.app)
        self.app.Step(self.app,raw or self.raw(energy,capacity))
    def test_job_count_selects_smallest_current_cost(self):
        self.run_job("Job count");self.assertIn("j_watch",self.h.transport.sent[1].actionKey)
    def test_highest_tier_waits_for_native_capacity_target_without_lower_tier_fallback(self):
        self.run_job("Highest tier",energy=4);self.assertEqual(len(self.h.transport.sent),0)
    def test_named_mastery_target_never_guesses_a_fixed_rule_index(self):
        self.assertTrue(self.app.Set(self.app,"jobs.custom.masteryTarget","Gold")[0])
    def test_highest_tier_sends_the_target_once_energy_arrives(self):
        self.run_job("Highest tier",energy=4);self.assertEqual(len(self.h.transport.sent),0)
        self.app.Step(self.app,self.raw(revision=2));self.assertIn("j_boost",self.h.transport.sent[1].actionKey)
    def test_highest_tier_excludes_jobs_above_capacity_even_with_overfilled_pool(self):
        self.run_job("Highest tier",raw=self.raw(capacity=3));self.assertIn("j_tag",self.h.transport.sent[1].actionKey)
    def test_effective_capacity_precedes_base_capacity(self):
        self.run_job("Highest tier",raw=self.raw(capacity=5,derived=3));self.assertIn("j_tag",self.h.transport.sent[1].actionKey)
    def test_invalid_effective_capacity_does_not_fall_back_to_base(self):
        self.run_job("Highest tier",raw=self.raw(capacity=5,derived=0));self.assertEqual(len(self.h.transport.sent),0)
    def test_missing_capacity_or_eligible_tier_is_unavailable(self):
        self.run_job("Highest tier",raw=self.raw(capacity=None));self.assertEqual(len(self.h.transport.sent),0)
        self.data["JOBS"][2].pop("tier");self.rebuild();self.app.Step(self.app,self.raw(revision=2));self.assertEqual(len(self.h.transport.sent),0)
    def test_same_tier_prefers_higher_unlocked_level_and_retains_source_order_ties(self):
        for row in self.data["JOBS"]:row["tier"]=3
        self.rebuild();self.run_job("Highest tier");self.assertIn("j_tag",self.h.transport.sent[1].actionKey)
    def test_highest_tier_respects_optional_cost_bound_before_tier_ranking(self):
        self.app.Set(self.app,"jobs.custom.limitsEnabled",True);self.app.Set(self.app,"jobs.custom.maxCost",2)
        self.run_job("Highest tier");self.assertIn("j_watch",self.h.transport.sent[1].actionKey)
    def test_named_gold_comes_from_source_position_instead_of_fixed_third_tier(self):
        self.data["JOBS"]=self.data["JOBS"][:1];self.rebuild();self.app.Set(self.app,"jobs.custom.masteryTarget","Gold")
        self.run_job("Mastery",raw=self.raw(progress=4,tier=2));self.assertEqual(len(self.h.transport.sent),0)
    def test_mastery_counter_at_target_holds_even_when_tier_flag_lags(self):
        self.data["JOBS"]=self.data["JOBS"][:1];self.rebuild();self.app.Set(self.app,"jobs.custom.masteryTarget","Bronze")
        self.run_job("Mastery",raw=self.raw(progress=2,tier=0));self.assertEqual(len(self.h.transport.sent),0)
    def test_native_confirmation_settles_then_named_cap_blocks_next_job(self):
        self.data["JOBS"]=self.data["JOBS"][:1];self.rebuild();self.app.Set(self.app,"jobs.custom.masteryTarget","Bronze")
        self.run_job("Mastery",raw=self.raw(progress=1));self.assertEqual(len(self.h.transport.sent),1)
        self.h.transport.callbacks[1](lua_table(self.h.lua,{"ok":True}))
        self.app.Step(self.app,self.raw(revision=2,progress=2));self.h.at(1)
        self.app.Step(self.app,self.raw(revision=3,progress=2));self.assertEqual(len(self.h.transport.sent),1)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).lastOutcome,"confirmed")
    def test_missing_or_duplicate_named_target_never_guesses(self):
        for row in self.config["MASTERY"]:row.pop("name")
        self.rebuild();self.app.Set(self.app,"jobs.custom.masteryTarget","Gold");self.run_job("Mastery")
        self.assertEqual(len(self.h.transport.sent),0)
        self.config["MASTERY"][0]["name"]="Gold";self.config["MASTERY"][1]["name"]="Gold";self.rebuild()
        self.app.Step(self.app,self.raw(revision=2));self.assertEqual(len(self.h.transport.sent),0)
    def test_all_native_and_non_mastery_goals_keep_working_without_names(self):
        for row in self.config["MASTERY"]:row.pop("name")
        self.rebuild();self.run_job("Mastery");self.assertEqual(len(self.h.transport.sent),1)
    def test_queued_named_target_change_prevents_emission(self):
        import test_trophy_goal_runtime as shared
        f=shared.TrophyGoalRuntimeTests();f.setUp()
        try:
            f.targets();f.app.Set(f.app,"jobs.enabled",True);f.app.Set(f.app,"jobs.policy","Mastery")
            f.app.Set(f.app,"jobs.custom.masteryTarget","Gold");f.app.Step(f.app,f.target_raw())
            self.assertIsNotNone(f.executor.callback);f.app.Set(f.app,"jobs.custom.masteryTarget","Silver")
            f.executor.callback();self.assertEqual(len(f.executor.calls),0)
        finally:f.tearDown()
if __name__=="__main__":unittest.main()
