"""Actual Contract tab and App arbitrate existing enabled ordinary planners."""
import unittest
import test_automation_runtime as fixture
from engine_harness import lua_table
class ContractGoalRuntimeTests(unittest.TestCase):
    def setUp(self): self.setup_goal("jobs")
    def setup_goal(self, goal_key):
        self.f=fixture.AutomationRuntimeTests();self.f.setUp();self.h=self.f.h
        self.f.runtime.Close(self.f.runtime)
        deps={"config":{"CONTRACTS":{"DAILY_TIERS":[1,1,2,2,3],"WEEKLY_TIERS":[4,4,4,4,4],
            "TEMPLATES":[{"id":"c_goal","key":goal_key}],"BONUS":{"seals":2,"energyRefill":True},
            "WEEKLY_BONUS":{"seals":12,"crate":"crate_fixervault"}}},"fingerprint":"a"*64,"release":"release-a"}
        for name,folder in (("ContractEntriesState","game"),("ContractEntries","features"),("ContractEntriesEvidence","features"),
            ("ContractBonusesState","game"),("ContractBonuses","features"),("ContractBonusesEvidence","features")):
            deps[name]=self.h.load("src/"+folder+"/"+name+".luau")
        for name in ("ContractGoalState","ContractGoalBlocked","ContractGoalRequests","ContractCashQuote","NativeContractCatalog"):
            deps[name]=self.h.load("src/tabs/contracts/"+name+".luau")
        entry=self.h.load("src/tabs/contracts/Module.luau");self.tab=entry.new(lua_table(self.h.lua,deps))
        goals=self.tab.Descriptors(self.tab)[3]
        features=[self.f.runtime.features.jobs,self.f.runtime.features.operations,self.f.runtime.features.collect,goals]
        self.executor=self.h.lua.execute("return {calls={},Schedule=function(self,fn) self.callback=fn return true end,Invoke=function(self,remote,method,...) self.calls[#self.calls+1]={remote=remote,args=table.pack(...)} return {ok=true} end}")
        adapter=self.h.load("src/transport/NativeDispatchAdapter.luau").new(self.h.load("src/transport/NativeCallPlan.luau"),self.executor)
        self.runtime=self.h.load("src/engine/AutomationRuntime.luau").new(lua_table(self.h.lua,{
            "clock":self.h.clock,"transport":adapter,"storage":self.f.storage,"identity":self.h.session,"modules":self.f.runtime.modules,
            "features":features,"tabInstances":[self.tab],"featurePages":{"jobs":"jobs","operations":"operations","collect":"operations","autoContracts":"contracts"},
            "snapshotAssembler":self.h.load("src/tabs/TabSnapshotAssembler.luau").new(lua_table(self.h.lua,[self.tab]))}))
        self.app=self.h.load("src/App.luau").start(lua_table(self.h.lua,{"Ember":self.h.load("tests/ember_double.lua")(),
            "Catalog":self.h.load("src/ui/Catalog.luau"),"Settings":self.h.load("src/storage/Settings.luau"),
            "EmberAdapter":self.h.load("src/ui/EmberAdapter.luau"),"ContractsTab":entry,"automationRuntimeInstance":self.runtime}))
    def tearDown(self):self.app.Destroy(self.app)
    def raw(self,revision=1,progress=0,done=False,completions=0):
        raw=self.f.raw(revision=revision,active=[],completions=completions);raw.catalogKey="a"*64
        raw.contractConfig=raw.contractBonusConfig=raw.contractTemplates=None
        n=raw.native;n.derived.contractDayReset=n.serverNow+1000;n.derived.contractWeekReset=n.serverNow+10000
        n.contracts.daily[1]=lua_table(self.h.lua,{"id":"c_goal","done":done,"claimed":False,"progress":progress,"goal":2})
        for index in range(2,6):n.contracts.daily[index].claimed=True
        for row in n.contracts.weekly.values():row.claimed=True
        return raw
    def select(self,jobs=True,goal=True,borrow=True):
        for key,value in (("jobs.enabled",jobs),("operations.enabled",True),("operations.policy","Highest tier"),("autoContracts.enabled",goal),
            ("autoContracts.custom.borrowJobs",borrow)):
            self.assertTrue(self.app.Set(self.app,key,value)[0])
        self.app.Resume(self.app)
    def test_actual_goal_prioritizes_existing_jobs_over_operation_start(self):
        self.select();self.app.Step(self.app,self.raw())
        self.executor.callback();self.assertEqual(self.executor.calls[1].remote,"DoJob")
        self.assertEqual(len(self.executor.calls),1)
    def test_no_borrow_or_disabled_goal_preserves_ordinary_priority(self):
        self.select(borrow=False);self.app.Step(self.app,self.raw());self.executor.callback()
        self.assertEqual(self.executor.calls[1].remote,"StartOperation")
    def test_borrow_never_enables_an_off_ordinary_feature(self):
        self.select(jobs=False);self.app.Step(self.app,self.raw());self.executor.callback()
        self.assertEqual(self.executor.calls[1].remote,"StartOperation")
        self.assertFalse(self.app.model["values"]["jobs.enabled"])
    def test_successful_job_is_not_objective_completion_without_native_progress(self):
        self.select();self.app.Step(self.app,self.raw());self.executor.callback();self.h.at(1)
        self.app.Step(self.app,self.raw(2,completions=1))
        self.assertEqual(self.runtime.Status(self.runtime).outcomes.jobs,"confirmed")
        self.assertEqual(self.runtime.Status(self.runtime).goals.autoContracts.state,"waiting")
    def test_native_goal_progress_and_completion_stop_goal_priority(self):
        self.select();self.app.Step(self.app,self.raw());self.executor.callback();self.h.at(1)
        self.app.Step(self.app,self.raw(2,progress=1,completions=1))
        self.assertEqual(self.runtime.Status(self.runtime).goals.autoContracts.state,"progressed")
        self.executor.callback();self.h.at(2);self.app.Step(self.app,self.raw(3,progress=2,done=True,completions=2))
        self.assertEqual(self.runtime.Status(self.runtime).goals.autoContracts.state,"complete")
        self.executor.callback();self.assertEqual(self.executor.calls[len(self.executor.calls)].remote,"StartOperation")
    def test_completed_native_goal_stays_complete_in_later_snapshots(self):
        self.select();self.app.Step(self.app,self.raw());self.executor.callback();self.h.at(1)
        self.app.Step(self.app,self.raw(2,progress=2,done=True,completions=1))
        self.assertEqual(self.runtime.Status(self.runtime).goals.autoContracts.state,"complete")
        self.app.Pause(self.app);self.h.at(2)
        # A fresh request remains the ordinary Operation's own authorization.
        self.executor.callback();self.app.Resume(self.app)
        self.app.Step(self.app,self.raw(3,progress=2,done=True,completions=1))
        self.assertEqual(self.runtime.Status(self.runtime).goals.autoContracts.state,"complete")
    def test_changed_native_reset_identity_never_counts_as_progress(self):
        self.select();self.app.Step(self.app,self.raw());self.executor.callback();self.h.at(1)
        after=self.raw(2,progress=2,done=True,completions=1);after.native.derived.contractDayReset+=86400
        self.app.Step(self.app,after)
        self.assertNotEqual(self.runtime.Status(self.runtime).goals.autoContracts.state,"complete")
    def test_goal_disable_does_not_cancel_independently_enabled_jobs(self):
        self.select();self.app.Step(self.app,self.raw());self.app.Set(self.app,"autoContracts.enabled",False)
        self.executor.callback();self.assertEqual(self.executor.calls[1].remote,"DoJob")
        self.h.at(1);self.app.Step(self.app,self.raw(2,completions=1))
        self.assertIsNone(self.runtime.Status(self.runtime).goals.autoContracts)
    def test_disabling_borrowed_feature_before_invoke_refuses_it(self):
        self.select();self.app.Step(self.app,self.raw());self.app.Set(self.app,"jobs.enabled",False)
        self.executor.callback();self.assertEqual(len(self.executor.calls),0)
    def test_unknown_outcome_does_not_claim_goal_progress_or_start_another_job(self):
        self.select();self.app.Step(self.app,self.raw());self.executor.callback();self.h.at(45)
        self.app.Step(self.app,self.raw(2))
        self.assertEqual(self.runtime.Status(self.runtime).outcomes.jobs,"skipped_unconfirmed")
        self.assertEqual(self.runtime.Status(self.runtime).goals.autoContracts.state,"waiting")
        self.assertEqual(len(self.executor.calls),1)
    def test_unload_fences_queued_ordinary_job(self):
        self.select();self.app.Step(self.app,self.raw());self.app.Destroy(self.app);self.executor.callback()
        self.assertEqual(len(self.executor.calls),0)
    def test_operation_goal_requires_both_explicit_borrow_permissions_and_enabled_switches(self):
        self.app.Destroy(self.app);self.setup_goal("ops");self.select(jobs=False)
        self.app.Set(self.app,"autoContracts.custom.borrowOperations",True)
        self.app.Set(self.app,"collect.enabled",True)
        self.app.Step(self.app,self.raw())
        self.assertFalse(self.runtime.Status(self.runtime).goals.autoContracts.routed)
    def test_operation_start_and_collection_use_existing_calls_and_only_native_goal_progress(self):
        self.app.Destroy(self.app);self.setup_goal("ops");self.select(jobs=False)
        for key in ("autoContracts.custom.borrowOperations","autoContracts.custom.borrowCollect","collect.enabled"):
            self.app.Set(self.app,key,True)
        self.app.Step(self.app,self.raw());self.executor.callback()
        self.assertEqual(self.executor.calls[1].remote,"StartOperation")
        self.h.at(1);after=self.raw(2)
        after.native.operations.active=lua_table(self.h.lua,[{"opId":"op_fence","remaining":0,"slot":1}]);after.native.cash=800
        self.app.Step(self.app,after)
        self.assertEqual(self.runtime.Status(self.runtime).outcomes.operations,"confirmed")
        self.assertEqual(self.runtime.Status(self.runtime).goals.autoContracts.state,"waiting")
        self.executor.callback();self.assertEqual(self.executor.calls[2].remote,"CollectOperation")
        self.h.at(2);self.app.Step(self.app,self.raw(3,progress=1))
        self.assertEqual(self.runtime.Status(self.runtime).outcomes.collect,"confirmed")
        self.assertEqual(self.runtime.Status(self.runtime).goals.autoContracts.state,"progressed")
    def test_energy_objective_uses_same_job_custody_and_native_progress(self):
        self.app.Destroy(self.app);self.setup_goal("energy");self.select()
        self.app.Step(self.app,self.raw());self.executor.callback();self.h.at(1)
        self.app.Step(self.app,self.raw(2,progress=1,completions=1))
        self.assertEqual(self.runtime.Status(self.runtime).outcomes.jobs,"confirmed")
        self.assertEqual(self.runtime.Status(self.runtime).goals.autoContracts.state,"progressed")
    def test_backward_native_clock_does_not_claim_objective_progress(self):
        self.select();self.app.Step(self.app,self.raw());self.executor.callback();self.h.at(1)
        after=self.raw(2,progress=1,completions=1);after.native.serverNow-=10
        self.app.Step(self.app,after)
        self.assertEqual(self.runtime.Status(self.runtime).goals.autoContracts.state,"waiting")
if __name__=="__main__":unittest.main()
