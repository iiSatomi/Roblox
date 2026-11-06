"""Actual Trophy tab uses the shared arbiter and separate earned claims."""
import unittest
import test_contract_goal_runtime as fixture
from engine_harness import lua_table
class TrophyGoalRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.ContractGoalRuntimeTests();self.f.setUp();self.f.app.Destroy(self.f.app)
        self.h=self.f.h;self.base=self.f.f
        self.start_app()
    def start_app(self, game_data=None):
        deps={"config":{"MASTERY":[{"name":"Bronze","completions":25,"energyDiscount":0},{"name":"Silver","completions":50,"energyDiscount":.05},{"name":"Gold","completions":100,"energyDiscount":.05}]},"fingerprint":"a"*64,"release":"release-a","gameData":{"ITEMS":[{"id":id,"kind":"trophy"}
            for id in ("t_streetname","t_ashportkey","t_manifest","t_vaultdial","t_deedbook","t_brasskeys","t_vesperacase")],"TROPHY_TRADE_INS":{}}}
        if game_data: deps["gameData"].update(game_data)
        self.config=deps["config"]
        deps["NativeJobCatalog"]=self.h.load("src/tabs/jobs/NativeJobCatalog.luau")
        for name,folder in (("EarnedTrophiesState","game"),("EarnedTrophies","features"),("EarnedTrophiesEvidence","features")):
            deps[name]=self.h.load("src/"+folder+"/"+name+".luau")
        for name in ("NativeTrophyCatalog","TrophyFocusState","TrophyFocusBlocked","TrophyGoalRequests"):
            deps[name]=self.h.load("src/tabs/trophies/"+name+".luau")
        entry=self.h.load("src/tabs/trophies/Module.luau");self.tab=entry.new(lua_table(self.h.lua,deps))
        features=[self.base.runtime.features[id] for id in ("jobs","operations","collect","bank","properties")]
        features.extend(self.tab.Descriptors(self.tab).values())
        self.executor=self.h.lua.execute("return {calls={},Schedule=function(self,fn) self.callback=fn return true end,Invoke=function(self,remote,method,...) self.calls[#self.calls+1]={remote=remote,args=table.pack(...)} return self.reply or {ok=true} end}")
        transport=self.h.load("src/transport/NativeDispatchAdapter.luau").new(self.h.load("src/transport/NativeCallPlan.luau"),self.executor)
        self.runtime=self.h.load("src/engine/AutomationRuntime.luau").new(lua_table(self.h.lua,{
            "clock":self.h.clock,"transport":transport,"storage":self.base.storage,"identity":self.h.session,"modules":self.base.runtime.modules,
            "features":features,"tabInstances":[self.tab],"featurePages":{f.id:"trophies" if f.id in ("trophies","trophyFocus") else f.id for f in features},
            "snapshotAssembler":self.h.load("src/tabs/TabSnapshotAssembler.luau").new(lua_table(self.h.lua,[self.tab]))}))
        self.app=self.h.load("src/App.luau").start(lua_table(self.h.lua,{"Ember":self.h.load("tests/ember_double.lua")(),
            "Catalog":self.h.load("src/ui/Catalog.luau"),"Settings":self.h.load("src/storage/Settings.luau"),
            "EmberAdapter":self.h.load("src/ui/EmberAdapter.luau"),"TrophiesTab":entry,"automationRuntimeInstance":self.runtime}))
    def tearDown(self):self.app.Destroy(self.app)
    def raw(self,revision=1,ready=False,owned=False,completions=0):
        raw=self.base.raw(revision=revision,active=[],completions=completions);raw.catalogKey="a"*64;raw.trophyCatalog=None
        raw.native.derived.trophyReady=lua_table(self.h.lua,["t_streetname"] if ready else [])
        if owned:raw.native.inventoryBound.t_streetname=1
        if getattr(self,"native_jobs",None): raw=self.native_jobs.Enrich(self.native_jobs,raw)[0]
        if getattr(self,"native_properties",None): raw=self.native_properties.Enrich(self.native_properties,raw)[0]
        return raw
    def targets(self):
        self.app.Destroy(self.app)
        data={"CITIES":[{"id":"city_ashport","firstTier":1},{"id":"city_caldera","firstTier":4}],
            "JOBS":[{"id":"j_watch","tier":1,"level":1,"energy":1,"cash":10,"xp":1},
                    {"id":"j_ash","tier":2,"level":1,"energy":1,"cash":20,"xp":2},
                    {"id":"j_other","tier":4,"level":1,"energy":1,"cash":100,"xp":10}],
            "PROPERTIES":[{"id":"p_owned","level":1,"baseCost":10,"incomePerHour":20},
                          {"id":"p_city","level":1,"baseCost":100,"incomePerHour":10},
                          {"id":"p_other","level":1,"baseCost":1,"incomePerHour":100}],
            "CITY_PROPERTIES":{"city_ashport":["p_owned","p_city"],"city_caldera":["p_other"]}}
        self.start_app(data)
        self.native_jobs=self.h.load("src/tabs/jobs/NativeJobCatalog.luau").new(lua_table(self.h.lua,data),lua_table(self.h.lua,self.config),"a"*64,"release-a")
        self.native_properties=self.h.load("src/tabs/property/NativePropertyCatalog.luau").new(lua_table(self.h.lua,data),lua_table(self.h.lua,{"PROPERTY":{"costGrowth":1.18,"maxOwned":20}}),"a"*64,"release-a")
    def target_raw(self,revision=1):
        raw=self.base.raw(revision=revision,active=[]);raw.catalogKey="a"*64;raw.trophyCatalog=None
        raw.native.derived.trophyReady=self.h.lua.table()
        raw.native.jobs=lua_table(self.h.lua,{"j_watch":{"masteryTier":3,"completions":100},"j_ash":{"masteryTier":2,"completions":90}})
        raw.native.properties=lua_table(self.h.lua,{"p_owned":{"owned":1}})
        raw.native.derived.territoryBonuses=lua_table(self.h.lua,{"buildDiscount":0})
        raw=self.native_jobs.Enrich(self.native_jobs,raw)[0]
        return self.native_properties.Enrich(self.native_properties,raw)[0]
    def select(self,target="t_streetname",jobs=True,borrow=True,claims=False):
        for key,value in (("jobs.enabled",jobs),("operations.enabled",True),("operations.policy","Highest tier"),
            ("trophyFocus.enabled",True),("trophyFocus.custom.goalId",target),("trophyFocus.custom.borrowJobs",borrow),("trophies.enabled",claims)):
            self.assertTrue(self.app.Set(self.app,key,value)[0])
        self.app.Resume(self.app)
    def test_level_goal_prioritizes_enabled_positive_xp_job(self):
        self.select();self.app.Step(self.app,self.raw());self.executor.callback()
        self.assertEqual(self.executor.calls[1].remote,"DoJob")
        self.assertTrue(self.runtime.Status(self.runtime).goals.trophyFocus.routed)
    def test_ready_goal_routes_only_separately_enabled_nonconsuming_claim(self):
        self.select(claims=True);self.app.Step(self.app,self.raw());self.executor.callback();self.h.at(1)
        self.app.Step(self.app,self.raw(2,ready=True,completions=1))
        self.assertEqual(self.runtime.Status(self.runtime).goals.trophyFocus.state,"ready")
        self.executor.callback();self.assertEqual(self.runtime.session.broker.active.proposal.feature,"trophies")
        self.h.at(2);self.app.Step(self.app,self.raw(3,owned=True,completions=1))
        self.assertEqual(self.runtime.Status(self.runtime).outcomes.trophies,"confirmed")
        self.assertEqual(self.runtime.Status(self.runtime).goals.trophyFocus.state,"owned")
    def test_native_ready_is_never_reported_as_owned_without_award(self):
        self.select(claims=False);self.app.Step(self.app,self.raw(ready=True))
        self.assertEqual(self.runtime.Status(self.runtime).goals.trophyFocus.state,"ready")
        self.executor.callback();self.assertEqual(self.executor.calls[1].remote,"StartOperation")
    def test_owned_goal_does_not_prioritize_jobs(self):
        self.select();self.app.Step(self.app,self.raw(owned=True));self.executor.callback()
        self.assertEqual(self.runtime.Status(self.runtime).goals.trophyFocus.state,"owned")
        self.assertEqual(self.executor.calls[1].remote,"StartOperation")
    def test_disabled_ordinary_jobs_or_missing_borrow_permission_never_loan(self):
        self.select(jobs=False);self.app.Step(self.app,self.raw());self.executor.callback()
        self.assertEqual(self.executor.calls[1].remote,"StartOperation")
        self.assertFalse(self.runtime.Status(self.runtime).goals.trophyFocus.routed)
    def test_mastery_and_city_property_targets_remain_explicitly_unrouted(self):
        self.select("t_ashportkey");self.app.Step(self.app,self.raw())
        self.assertFalse(self.runtime.Status(self.runtime).goals.trophyFocus.routed)
        self.assertIn("Target-specific",self.runtime.Status(self.runtime).reasons.trophyFocus)
    def test_zero_xp_job_cannot_be_favored_as_a_level_goal(self):
        self.select();raw=self.raw();raw.jobCatalog[1].xp=0;self.app.Step(self.app,raw)
        self.assertFalse(self.runtime.Status(self.runtime).goals.trophyFocus.routed)
    def test_item_consuming_goal_never_gets_an_ordinary_route(self):
        self.select("t_vesperacase");self.app.Step(self.app,self.raw())
        self.assertEqual(self.runtime.Status(self.runtime).goals.trophyFocus.state,"manualTradeIn")
        self.assertFalse(self.runtime.Status(self.runtime).goals.trophyFocus.routed)
    def test_banking_goal_uses_actual_enabled_bank_feature_identity(self):
        self.select("t_vaultdial",jobs=False)
        for key,value in (("trophyFocus.custom.borrowBanking",True),("bank.enabled",True),("bank.custom.depositThreshold",1),("bank.custom.cashToKeep",0)):
            self.assertTrue(self.app.Set(self.app,key,value)[0])
        self.app.Step(self.app,self.raw())
        self.assertEqual(self.runtime.session.broker.active.proposal.feature,"bank")
        self.executor.callback();self.assertEqual(len(self.executor.calls),1)
    def test_operation_goal_uses_both_enabled_stages_and_native_readiness(self):
        self.select("t_manifest",jobs=False)
        self.app.Set(self.app,"trophyFocus.custom.borrowOperations",True);self.app.Set(self.app,"collect.enabled",True)
        self.app.Step(self.app,self.raw());self.executor.callback()
        self.assertEqual(self.runtime.session.broker.active.proposal.feature,"operations")
        self.h.at(1);after=self.raw(2)
        after.native.operations.active=lua_table(self.h.lua,[{"opId":"op_fence","remaining":0,"slot":1}]);after.native.cash=800
        self.app.Step(self.app,after);self.executor.callback()
        self.assertEqual(self.runtime.session.broker.active.proposal.feature,"collect")
        self.h.at(2);after=self.raw(3);after.native.derived.trophyReady=lua_table(self.h.lua,["t_manifest"])
        self.app.Step(self.app,after)
        self.assertEqual(self.runtime.Status(self.runtime).goals.trophyFocus.state,"ready")
        self.assertNotEqual(self.runtime.Status(self.runtime).goals.trophyFocus.state,"owned")
    def test_city_mastery_selects_remaining_city_job_instead_of_better_unrelated_job(self):
        self.targets();self.select("t_ashportkey");self.app.Step(self.app,self.target_raw())
        active=self.runtime.session.broker.active
        self.assertEqual(active.proposal.feature,"jobs")
        self.assertEqual(active.proposal.intent.targetId,"j_ash")
        self.executor.callback();self.assertEqual(self.executor.calls[1].args[1],"j_ash")
    def test_city_property_selects_missing_city_property_without_rebuying_owned_copy(self):
        self.targets();self.select("t_brasskeys",jobs=False)
        for key,value in (("trophyFocus.custom.borrowProperties",True),("properties.enabled",True),
            ("properties.custom.cashReserve",0),("properties.custom.purchaseCap",1000),("properties.custom.ownedLimit",10)):
            self.assertTrue(self.app.Set(self.app,key,value)[0])
        self.app.Step(self.app,self.target_raw())
        active=self.runtime.session.broker.active
        self.assertEqual(active.proposal.feature,"properties")
        self.assertEqual(active.proposal.intent.propId,"p_city")
    def test_ready_goal_selects_its_own_claim_instead_of_another_ready_trophy(self):
        self.select("t_manifest",jobs=False,claims=True)
        raw=self.raw();raw.native.derived.trophyReady=lua_table(self.h.lua,["t_streetname","t_manifest"])
        self.app.Step(self.app,raw)
        active=self.runtime.session.broker.active
        self.assertEqual(active.proposal.feature,"trophies")
        self.assertEqual(active.proposal.intent.targetId,"t_manifest")
    def enable_properties(self):
        for key,value in (("trophyFocus.custom.borrowProperties",True),("properties.enabled",True),
            ("properties.custom.cashReserve",0),("properties.custom.purchaseCap",1000),("properties.custom.ownedLimit",10)):
            self.assertTrue(self.app.Set(self.app,key,value)[0])
    def test_filtered_mastery_keeps_selected_job_policy_and_disabled_borrowing(self):
        self.targets();self.select("t_ashportkey")
        self.app.Set(self.app,"jobs.policy","Selected job");self.app.Set(self.app,"jobs.custom.selectedJobId","j_other")
        self.app.Step(self.app,self.target_raw())
        self.assertFalse(self.runtime.Status(self.runtime).goals.trophyFocus.routed)
        self.assertEqual(self.runtime.session.broker.active.proposal.feature,"operations")
    def test_city_job_loan_does_not_enable_disabled_jobs(self):
        self.targets();self.select("t_ashportkey",jobs=False);self.app.Step(self.app,self.target_raw())
        self.assertFalse(self.runtime.Status(self.runtime).goals.trophyFocus.routed)
        self.assertEqual(self.runtime.session.broker.active.proposal.feature,"operations")
    def test_gold_city_waits_for_native_readiness_instead_of_favoring_extra_job(self):
        self.targets();self.select("t_ashportkey");raw=self.target_raw()
        raw.native.jobs.j_ash.masteryTier=3
        self.app.Step(self.app,raw)
        self.assertFalse(self.runtime.Status(self.runtime).goals.trophyFocus.routed)
        self.assertEqual(self.runtime.Status(self.runtime).goals.trophyFocus.state,"waiting")
        self.assertEqual(self.runtime.session.broker.active.proposal.feature,"operations")
    def test_filtered_job_unload_fences_the_queued_call(self):
        self.targets();self.select("t_ashportkey");self.app.Step(self.app,self.target_raw())
        self.app.Destroy(self.app);self.executor.callback()
        self.assertEqual(len(self.executor.calls),0)
    def test_filtered_job_disable_refuses_queued_invocation(self):
        self.targets();self.select("t_ashportkey");self.app.Step(self.app,self.target_raw())
        self.app.Set(self.app,"jobs.enabled",False);self.executor.callback()
        self.assertEqual(len(self.executor.calls),0)
    def test_filtered_job_unknown_outcome_does_not_prove_trophy_owned(self):
        self.targets();self.select("t_ashportkey");self.app.Step(self.app,self.target_raw());self.executor.callback()
        self.h.at(45);self.app.Step(self.app,self.target_raw(2))
        self.assertEqual(self.runtime.Status(self.runtime).outcomes.jobs,"skipped_unconfirmed")
        self.assertNotEqual(self.runtime.Status(self.runtime).goals.trophyFocus.state,"owned")
        self.assertEqual(len(self.executor.calls),1)
    def test_city_property_preserves_reserve_and_purchase_cap(self):
        self.targets();self.select("t_brasskeys",jobs=False);self.enable_properties()
        self.app.Set(self.app,"properties.custom.purchaseCap",99)
        self.app.Step(self.app,self.target_raw())
        self.assertFalse(self.runtime.Status(self.runtime).goals.trophyFocus.routed)
        self.assertEqual(self.runtime.session.broker.active.proposal.feature,"operations")
    def test_owned_city_properties_wait_for_native_ready_without_rebuying(self):
        self.targets();self.select("t_brasskeys",jobs=False);self.enable_properties();raw=self.target_raw()
        raw.native.properties.p_city=lua_table(self.h.lua,{"owned":1})
        raw=self.native_properties.Enrich(self.native_properties,raw)[0]
        self.app.Step(self.app,raw)
        self.assertFalse(self.runtime.Status(self.runtime).goals.trophyFocus.routed)
        self.assertNotEqual(self.runtime.Status(self.runtime).goals.trophyFocus.state,"owned")
    def test_city_property_exact_purchase_then_native_ready_and_ownership(self):
        self.targets();self.select("t_brasskeys",jobs=False,claims=True);self.enable_properties()
        self.app.Step(self.app,self.target_raw());self.executor.callback();self.app.Pause(self.app)
        self.h.at(1);after=self.target_raw(2);after.native.cash=900
        after.native.properties.p_city=lua_table(self.h.lua,{"owned":1})
        after=self.native_properties.Enrich(self.native_properties,after)[0]
        self.app.Step(self.app,after)
        self.assertEqual(self.runtime.Status(self.runtime).outcomes.properties,"confirmed")
        self.app.Resume(self.app);after.native.derived.trophyReady=lua_table(self.h.lua,["t_brasskeys"])
        self.app.Step(self.app,after);self.executor.callback()
        self.assertEqual(self.runtime.session.broker.active.proposal.feature,"trophies")
        self.h.at(2);final=self.target_raw(3);final.native.cash=900
        final.native.properties.p_city=lua_table(self.h.lua,{"owned":1});final.native.inventoryBound.t_brasskeys=1
        final=self.native_properties.Enrich(self.native_properties,final)[0]
        self.app.Step(self.app,final)
        self.assertEqual(self.runtime.Status(self.runtime).goals.trophyFocus.state,"owned")
    def test_deedbook_routes_existing_best_value_property_planner(self):
        self.targets();self.select("t_deedbook",jobs=False);self.enable_properties()
        self.app.Step(self.app,self.target_raw())
        self.assertEqual(self.runtime.session.broker.active.proposal.feature,"properties")
        self.assertEqual(self.runtime.session.broker.active.proposal.intent.propId,"p_other")
    def test_deedbook_ten_owned_waits_for_native_readiness(self):
        self.targets();self.select("t_deedbook",jobs=False);self.enable_properties();raw=self.target_raw()
        raw.native.properties.p_owned.owned=10;raw=self.native_properties.Enrich(self.native_properties,raw)[0]
        self.app.Step(self.app,raw)
        self.assertFalse(self.runtime.Status(self.runtime).goals.trophyFocus.routed)
        self.assertEqual(self.runtime.Status(self.runtime).goals.trophyFocus.state,"waiting")
    def test_filtered_job_rejection_never_marks_trophy_progress_or_ownership(self):
        self.targets();self.select("t_ashportkey");self.app.Step(self.app,self.target_raw())
        self.executor.reply=lua_table(self.h.lua,{"ok":False});self.executor.callback();self.h.at(1)
        self.app.Step(self.app,self.target_raw(2))
        self.assertEqual(self.runtime.Status(self.runtime).outcomes.jobs,"rejected")
        self.assertEqual(self.runtime.Status(self.runtime).goals.trophyFocus.state,"waiting")
if __name__=="__main__":unittest.main()
