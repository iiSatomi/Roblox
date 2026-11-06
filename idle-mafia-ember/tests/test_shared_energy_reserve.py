"""One shared floor protects energy planning without enabling blocked activities."""
import unittest
import test_jobs_flow as job_fixture
import test_trophy_goal_runtime as shared_fixture
import test_heist_start as heist_fixture
import test_favor_help as favor_fixture
import test_sabotage as sabotage_fixture
from engine_harness import Harness,lua_table
class SharedEnergyReserveTests(unittest.TestCase):
    def setUp(self):self.f=job_fixture.JobsFlowTests();self.f.setUp();self.app=self.f.app;self.h=self.f.h
    def tearDown(self):self.f.tearDown()
    def run_job(self):self.app.Set(self.app,"jobs.enabled",True);self.app.Resume(self.app);self.app.Step(self.app,self.f.raw())
    def test_shared_floor_is_inclusive_and_does_not_enable_jobs(self):
        self.assertTrue(self.app.Set(self.app,"shared.energyReserve",4)[0]);self.assertFalse(self.app.model["values"]["jobs.enabled"])
        self.run_job();self.assertEqual(len(self.h.transport.sent),1)
    def test_floor_can_hold_jobs_without_silently_clamping_to_current_capacity(self):
        self.assertTrue(self.app.Set(self.app,"shared.energyReserve",5)[0]);self.run_job();self.assertEqual(len(self.h.transport.sent),0)
    def test_invalid_shared_floor_never_coerces_or_changes_current_choice(self):
        for value in (-1,True,1.5,float("nan")):
            self.assertFalse(self.app.Set(self.app,"shared.energyReserve",value)[0])
        self.assertEqual(self.app.model["values"]["shared.energyReserve"],0)
    def test_shared_reserve_change_before_native_emission_invalidates_energy_request(self):
        f=shared_fixture.TrophyGoalRuntimeTests();f.setUp()
        try:
            f.app.Set(f.app,"jobs.enabled",True);f.app.Step(f.app,f.raw());self.assertIsNotNone(f.executor.callback)
            self.assertTrue(f.app.Set(f.app,"shared.energyReserve",1000000)[0]);f.executor.callback();self.assertEqual(len(f.executor.calls),0)
        finally:f.tearDown()
    def test_trophy_borrowing_respects_shared_floor(self):
        f=shared_fixture.TrophyGoalRuntimeTests();f.setUp()
        try:
            f.targets()
            for key,value in (("jobs.enabled",True),("shared.energyReserve",1000000),("trophyFocus.enabled",True),
                ("trophyFocus.custom.goalId","t_ashportkey"),("trophyFocus.custom.borrowJobs",True)):
                self.assertTrue(f.app.Set(f.app,key,value)[0])
            f.app.Step(f.app,f.target_raw());self.assertIsNone(f.executor.callback)
        finally:f.tearDown()
    def test_settings_input_uses_the_existing_typed_preference_binding(self):
        h=Harness();ember=h.load("tests/ember_double.lua")()
        app=h.load("src/App.luau").start(lua_table(h.lua,{"Ember":ember,"Catalog":h.load("src/ui/Catalog.luau"),
            "Settings":h.load("src/storage/Settings.luau"),"EmberAdapter":h.load("src/ui/EmberAdapter.luau"),"SettingsTab":h.load("src/tabs/settings/Module.luau")}))
        try:
            control=app.ui.handles["shared.energyReserve"];control.Set(control,"4");ember.Flush()
            self.assertEqual(app.model["values"]["shared.energyReserve"],4)
        finally:app.Destroy(app)
    def test_pure_heist_selection_keeps_floor_without_changing_native_blocker(self):
        f=heist_fixture.HeistStartTests();f.setUp();view=f.view(f.raw())[0];settings=f.settings();settings.energyReserve=8
        proposal,reason=f.planner.propose(view,settings,f.reserves());self.assertIsNotNone(proposal);self.assertEqual(proposal.intent.heistId,"h_low")
        settings.energyReserve=9;self.assertIsNone(f.planner.propose(view,settings,f.reserves())[0])
    def test_pure_favor_uses_larger_feature_or_shared_floor_not_the_sum(self):
        f=favor_fixture.FavorHelpTests();f.setUp();view=f.view(f.raw())[0];settings=f.settings();settings.energyReserve=view.energy-view.energyCost
        proposal,reason=f.planner.propose(view,settings,f.reserve());self.assertIsNotNone(proposal)
        self.assertEqual(proposal.intent.minEnergyReserve,settings.energyReserve)
        settings.energyReserve=view.energy;self.assertIsNone(f.planner.propose(view,settings,f.reserve())[0])
    def test_pure_sabotage_also_keeps_shared_floor(self):
        f=sabotage_fixture.SabotageTests();f.setUp();raw=f.raw();context=f.context.Read(f.context,raw,lua_table(f.h.lua,f.h.session),0,2)[0]
        view=f.reader.read(raw,context)[0];settings=lua_table(f.h.lua,{"enabled":True,"energyReserve":18})
        self.assertIsNone(f.planner.propose(view,settings,lua_table(f.h.lua,{}))[0])
    def test_highest_tier_uses_capacity_after_shared_floor(self):
        import test_job_policies_app as policy_fixture
        f=policy_fixture.JobPoliciesAppTests();f.setUp()
        try:
            f.app.Set(f.app,"shared.energyReserve",2);f.run_job("Highest tier")
            self.assertIn("j_tag",f.h.transport.sent[1].actionKey)
        finally:f.tearDown()
    def test_held_uncertain_energy_and_floor_both_remain_reserved(self):
        self.run_job();self.h.at(45);self.app.Step(self.app,self.f.raw(revision=2))
        self.assertEqual(self.f.runtime.Status(self.f.runtime).uncertainCount,1)
        self.app.Set(self.app,"shared.energyReserve",4);self.h.at(90)
        self.app.Step(self.app,self.f.raw(revision=3));self.assertEqual(len(self.h.transport.sent),1)
        self.app.Set(self.app,"shared.energyReserve",3);self.app.Step(self.app,self.f.raw(revision=4))
        self.assertEqual(len(self.h.transport.sent),1)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).uncertainCount,1)
        raw=self.f.raw(revision=5);raw.capturedAt=90
        enriched=self.f.runtime.tab.Enrich(self.f.runtime.tab,raw)[0]
        context=self.f.runtime.context.Read(self.f.runtime.context,enriched,lua_table(self.h.lua,self.h.session),90,2)[0]
        view=self.f.runtime.jobsState.read(enriched,context)[0]
        settings=lua_table(self.h.lua,{"enabled":True,"policy":"Balanced","energyReserve":3})
        reserved=lua_table(self.h.lua,{"uncertainEnergy":1})
        self.assertIsNotNone(self.f.runtime.jobs.propose(view,settings,reserved)[0])
        settings.energyReserve=4;self.assertIsNone(self.f.runtime.jobs.propose(view,settings,reserved)[0])
    def test_changing_energy_floor_does_not_invalidate_queued_cash_operation(self):
        f=shared_fixture.TrophyGoalRuntimeTests();f.setUp()
        try:
            f.app.Set(f.app,"operations.policy","Highest tier");f.app.Set(f.app,"operations.enabled",True);f.app.Step(f.app,f.raw())
            self.assertIsNotNone(f.executor.callback)
            self.assertEqual(f.runtime.session.broker.active.proposal.feature,"operations")
            f.app.Set(f.app,"shared.energyReserve",1000000);f.executor.callback();self.assertEqual(len(f.executor.calls),1)
        finally:f.tearDown()
    def test_sent_job_can_confirm_after_floor_is_increased(self):
        self.run_job();self.app.Set(self.app,"shared.energyReserve",5)
        self.h.transport.callbacks[1](lua_table(self.h.lua,{"ok":True}))
        self.app.Step(self.app,self.f.raw(revision=2,completions=1))
        self.assertEqual(self.f.runtime.Status(self.f.runtime).lastOutcome,"confirmed");self.assertEqual(len(self.h.transport.sent),1)
    def test_favor_larger_feature_floor_still_wins_and_large_floor_is_recoverable(self):
        f=favor_fixture.FavorHelpTests();f.setUp();view=f.view(f.raw())[0];settings=f.settings(minEnergyReserve=15);settings.energyReserve=5
        proposal,_=f.planner.propose(view,settings,f.reserve());self.assertIsNotNone(proposal);self.assertEqual(proposal.intent.minEnergyReserve,15)
        raw=f.raw();raw.native.pools.energy=2000002;view=f.view(raw)[0];settings.energyReserve=2000000
        proposal,_=f.planner.propose(view,settings,f.reserve());self.assertIsNotNone(proposal)
        self.assertIsNotNone(f.evidence.capture(proposal,raw)[0])
    def test_shared_floor_preserves_native_heist_cash_and_energy_custody(self):
        f=heist_fixture.HeistStartTests();f.setUp();view=f.view(f.raw())[0];settings=f.settings();settings.energyReserve=6
        proposal,_=f.planner.propose(view,settings,f.reserves(energy=2));self.assertIsNotNone(proposal);self.assertEqual(proposal.intent.heistId,"h_low")
        self.assertIsNone(f.planner.propose(view,settings,f.reserves(energy=3))[0])
if __name__=="__main__":unittest.main()
