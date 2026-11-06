"""Real Heists catalog -> tab assembler -> Favor reader/planner -> protocol gate."""
import unittest
import test_automation_runtime as runtime_fixture
from engine_harness import lua_table

class HeistFavorCatalogAppTests(unittest.TestCase):
    def setUp(self):
        self.base=runtime_fixture.AutomationRuntimeTests();self.base.setUp();self.h=self.base.h
        self.base.runtime.Close(self.base.runtime)
        h=self.h
        self.data=lua_table(h.lua,{'HEISTS':[{'id':'h_a','level':10,'stake':100,'energy':2,'crateCount':1,'helpCash':1000,'helpXp':50,'crate':'crate_a','crateChance':.25,'duration':3600,'cash':500,'xp':100,'helpGoal':3},{'id':'h_b','level':20,'stake':200,'energy':5,'crateCount':1,'helpCash':100,'helpXp':100,'crate':'crate_b','crateChance':.5,'duration':1200,'cash':700,'xp':300,'helpGoal':6}],'ITEMS_BY_ID':{'crate_a':{'rarity':3},'crate_b':{'rarity':5}}})
        deps={'identity':h.session,'fingerprint':'a'*64,'release':'release-a','gameData':self.data}
        for name,path in [('NativeHeistCatalog','tabs/heists/NativeHeistCatalog'),('SequenceRecovery','tabs/heists/SequenceRecovery'),('BoardQuery','tabs/heists/BoardQuery'),('BoardReadRuntime','tabs/heists/BoardReadRuntime')]:deps[name]=h.load('src/'+path+'.luau')
        for name in ('HeistBoardState','SabotageState','FavorsState'):deps[name]=h.load('src/game/'+name+'.luau')
        for name in ('HeistStart','HeistStartEvidence','HeistCollect','HeistCollectEvidence','Sabotage','SabotageEvidence','FavorHelp','FavorHelpEvidence'):deps[name]=h.load('src/features/'+name+'.luau')
        self.heists=h.load('src/tabs/heists/Module.luau').new(lua_table(h.lua,deps))
        self.favors=h.load('src/tabs/favors/Module.luau').new(lua_table(h.lua,deps))
        self.tabs=lua_table(h.lua,[self.heists,self.favors])
        composed,why=h.load('src/tabs/TabComposition.luau').build(self.tabs,h.load('src/ui/Catalog.luau'),h.load('src/engine/FeatureRegistry.luau'),h.load('src/tabs/TabSnapshotAssembler.luau'))
        self.assertIsNone(why)
        self.executor=h.lua.execute("return {calls=0,Invoke=function(self) self.calls=self.calls+1;error('No native Heist mutation allowed') end,Schedule=function(self,fn) fn();return true end}")
        h.lua.globals().actualNativePlan=h.load('src/transport/NativeCallPlan.luau')
        self.plan=h.lua.execute('local result={proposals={}};function result.describe(p) result.proposals[#result.proposals+1]=p;return actualNativePlan.describe(p) end;return result')
        transport=h.load('src/transport/NativeDispatchAdapter.luau').new(self.plan,self.executor)
        self.runtime=h.load('src/engine/AutomationRuntime.luau').new(lua_table(h.lua,{'clock':h.clock,'transport':transport,'storage':self.base.storage,'identity':h.session,'modules':self.base.runtime.modules,'features':composed.features,'featurePages':composed.featurePages,'tabInstances':self.tabs,'snapshotAssembler':composed.snapshotAssembler}))
        self.app=h.load('src/App.luau').start(lua_table(h.lua,{'Ember':h.load('tests/ember_double.lua')(),'Catalog':h.load('src/ui/Catalog.luau'),'Settings':h.load('src/storage/Settings.luau'),'EmberAdapter':h.load('src/ui/EmberAdapter.luau'),'HeistsTab':h.load('src/tabs/heists/Module.luau'),'FavorsTab':h.load('src/tabs/favors/Module.luau'),'automationRuntimeInstance':self.runtime}))
        self.raw=h.snapshot(native={'fullSync':True,'serverNow':2000000,'level':20,'cash':1000,'pools':{'energy':20}},heistBoardProof={'account':'user-a','capturedAt':0,'board':{'ok':True,'serverNow':2000000,'rows':[{'id':'run-1','ownerId':42,'heistId':'h_a','endsAt':2000300,'friend':True,'helpsUsed':0,'sabosUsed':0}],'startsLeft':1,'bustWait':0,'favorsLeft':12,'helpFavorCost':1,'helpEnergyCost':2,'helpMaxPerHeist':5,'helpCashCap':500}})
    def test_native_help_quotes_reach_actual_app_and_stop_at_the_sequence_gate(self):
        self.assertTrue(self.app.ui.features.heists.tabOwned);self.assertTrue(self.app.ui.features.favors.tabOwned);self.assertFalse(self.app.ui.degraded)
        self.assertTrue(self.app.Set(self.app,'favors.enabled',True)[0]);self.app.Resume(self.app)
        self.app.Step(self.app,self.raw)
        self.assertEqual(self.runtime.latestOutcomeSnapshot.heistCatalog[1].helpCash,1000)
        self.assertEqual(self.runtime.latestOutcomeSnapshot.heistCatalog[1].helpXp,50)
        self.assertEqual(self.runtime.Status(self.runtime).reasons.favors,'transport_blocked')
        self.assertEqual(self.executor.calls,0)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),0)
    def test_all_heist_goals_and_selected_bounds_reach_real_app_without_a_send(self):
        self.assertTrue(self.app.Set(self.app,'heists.enabled',True)[0]);self.app.Resume(self.app)
        for index,mode in enumerate(('Best chest','Balanced','Highest tier','Lowest stake','XP / hour','Profit / hour','Custom')):
            self.assertTrue(self.app.Set(self.app,'heists.policy',mode)[0])
            self.h.at(index*.25);self.raw.revision=index+1;self.raw.capturedAt=index*.25;self.raw.heistBoardProof.capturedAt=index*.25
            self.app.Step(self.app,self.raw)
            p=self.plan.proposals[len(self.plan.proposals)]
            self.assertEqual(p.intent.heistId,'h_a' if mode=='Lowest stake' else 'h_b',mode)
            self.assertEqual(self.runtime.Status(self.runtime).reasons.heists,'transport_blocked')
        for key,value in {'selection':'Only selected','selectedIds':'h_a','limitsEnabled':True,'minLevel':9.5,'maxLevel':10,'maxHours':1,'maxHelps':3}.items():
            self.assertTrue(self.app.Set(self.app,'heists.custom.'+key,value)[0])
        self.h.at(1.75);self.raw.revision=8;self.raw.capturedAt=1.75;self.raw.heistBoardProof.capturedAt=1.75;self.app.Step(self.app,self.raw)
        self.assertEqual(self.plan.proposals[len(self.plan.proposals)].intent.heistId,'h_a')
        self.assertEqual(self.executor.calls,0);self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),0)
    def test_favor_threshold_applies_to_native_capped_reward_and_import_never_enables(self):
        self.assertTrue(self.app.Set(self.app,'favors.enabled',True)[0]);self.app.Resume(self.app)
        self.assertTrue(self.app.Set(self.app,'favors.policy','Balanced')[0]);self.assertTrue(self.app.Set(self.app,'favors.custom.minRewardCash',500.5)[0]);self.app.Step(self.app,self.raw)
        self.assertEqual(len(self.plan.proposals),0)
        self.assertTrue(self.app.Set(self.app,'favors.custom.minRewardCash',500)[0]);self.h.at(.25);self.raw.revision=2;self.raw.capturedAt=.25;self.raw.heistBoardProof.capturedAt=.25;self.app.Step(self.app,self.raw)
        self.assertEqual(self.plan.proposals[1].intent.rewardCash,500);self.assertEqual(self.plan.proposals[1].intent.rewardXp,50)
        self.assertEqual(self.executor.calls,0)
    def test_unload_retires_own_catalog_and_cannot_generate_more_proposals(self):
        self.app.Destroy(self.app)
        self.assertIsNone(self.heists.Enrich(self.heists,self.raw)[0])
        self.app.Step(self.app,self.raw);self.assertEqual(self.executor.calls,0);self.assertEqual(len(self.plan.proposals),0)
    def test_missing_owner_quote_does_not_hide_valid_favor_rewards(self):
        self.data.HEISTS[1].duration=None
        self.heists.catalog=self.h.load('src/tabs/heists/NativeHeistCatalog.luau').new(self.data,'a'*64,'release-a')
        for feature in ('heists','favors'):self.assertTrue(self.app.Set(self.app,feature+'.enabled',True)[0])
        self.app.Resume(self.app);self.app.Step(self.app,self.raw)
        reasons=self.runtime.Status(self.runtime).reasons
        self.assertIn('quotes required',reasons.heists);self.assertEqual(reasons.favors,'transport_blocked')
        self.assertEqual(self.executor.calls,0)
    def test_missing_help_quote_is_unknown_and_does_not_hide_owner_selection(self):
        self.data.HEISTS[1].helpXp=None
        self.heists.catalog=self.h.load('src/tabs/heists/NativeHeistCatalog.luau').new(self.data,'a'*64,'release-a')
        for feature in ('heists','favors'):self.assertTrue(self.app.Set(self.app,feature+'.enabled',True)[0])
        self.app.Resume(self.app);self.app.Step(self.app,self.raw)
        reasons=self.runtime.Status(self.runtime).reasons
        self.assertEqual(reasons.heists,'transport_blocked');self.assertEqual(reasons.favors,'Invalid Favor catalog')
        self.assertIsNone(self.runtime.latestOutcomeSnapshot.heistCatalog[1].helpCash)
        self.assertEqual(self.executor.calls,0)
    def tearDown(self):self.app.Destroy(self.app)
