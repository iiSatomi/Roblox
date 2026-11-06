"""Actual native training App path, current catalog, shared funds and recovery."""
import unittest
import test_crew_equip_runtime as equip_fixture
from engine_harness import lua_table
class CrewTrainRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.e=equip_fixture.CrewEquipRuntimeTests();self.e.setUp();self.f=self.e.f;self.h=self.e.h
        self.f.app.Destroy(self.f.app);self.f.feature_id='crewTrain'
        self.f.tab_dependencies['CrewTrain']=self.h.load('src/tabs/crew/CrewTrain.luau')
        self.f.tab_dependencies['NativeTrainingCatalog']=self.h.load('src/tabs/crew/NativeTrainingCatalog.luau')
        self.f.tab_dependencies['config'].CREW.training=lua_table(self.h.lua,{'minRarity':4,'maxLevel':1,'maxConcurrent':1,
            'cost':{i:[100] for i in range(4,9)},'minutes':{i:[5] for i in range(4,9)}})
        self.f.start_current()
    def tearDown(self):self.f.tearDown()
    def raw(self,revision=1,cash=500,training=False):
        raw=self.f.f.raw(revision=revision,cash=cash)
        raw.native.crew=lua_table(self.h.lua,[{'name':'Player'},
            {'name':'Trainer','rarity':5,'healId':'member-a','train':0},
            {'name':'Reserve','rarity':4,'healId':'member-b','train':0}])
        if training:raw.native.crew[2].training=lua_table(self.h.lua,{'to':1,'endsAt':1301})
        return raw
    def step(self,revision=1,cash=500,training=False):
        raw=self.raw(revision,cash,training);self.h.at(raw.capturedAt);self.f.app.Step(self.f.app,raw);return raw
    def choose(self):
        for key,value in {'enabled':True,'custom.minRarity':5,'custom.targetLevel':1,'custom.maxCost':100,
            'custom.maxConcurrent':1,'custom.cashReserve':300}.items():self.f.app.Set(self.f.app,'crewTrain.'+key,value)
        self.f.app.Resume(self.f.app)
    def begin(self):self.choose();self.step();self.f.drain()
    def test_actual_training_requires_exact_cash_debit_and_timer(self):
        self.begin();call=self.f.executor.calls[1]
        self.assertEqual(call.remote,'CrewAction');self.assertEqual((call.args[1],call.args[2]),('train',2))
        self.step(2,400,True);self.assertEqual(self.f.runtime.Status(self.f.runtime).outcomes.crewTrain,'confirmed')
    def test_wrong_timer_without_cash_debit_cannot_confirm(self):
        self.begin();after=self.raw(2,500,True)
        after.native.crew[2].training.endsAt=1100
        self.h.at(after.capturedAt);self.f.app.Step(self.f.app,after)
        self.assertIsNone(self.f.runtime.Status(self.f.runtime).outcomes.crewTrain)
    def test_wrong_training_duration_cannot_confirm(self):
        self.begin();after=self.raw(2,400,True);after.native.crew[2].training.endsAt=1100
        self.h.at(2);self.f.app.Step(self.f.app,after)
        self.assertIsNone(self.f.runtime.Status(self.f.runtime).outcomes.crewTrain)
    def test_same_name_replacement_cannot_confirm_original_training(self):
        self.begin();after=self.raw(2,400,True);after.native.crew[2].healId='replacement'
        self.h.at(2);self.f.app.Step(self.f.app,after)
        self.assertIsNone(self.f.runtime.Status(self.f.runtime).outcomes.crewTrain)
    def test_restart_observes_exact_saved_training_without_replay(self):
        self.begin();self.f.restart();after=self.raw(0,400,True);after.native.serverNow=1005
        self.f.app.Step(self.f.app,after)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).recoveries.crewTrain,'confirmed')
        self.assertEqual(len(self.f.executor.calls),1)
    def test_other_cash_custody_cannot_consume_training_reserve(self):
        self.h.lua.globals().crewExternalHold=lua_table(self.h.lua,{
            'account':self.h.session['account'],'place':self.h.session['place'],'release':self.h.session['release'],
            'feature':'crewRoll','actionKey':'funded-hire','claims':{'allCrew':False,'allItems':False,
                'members':{},'items':{},'funds':{'cash':200}}})
        self.choose();self.step();self.f.drain();self.assertEqual(len(self.f.executor.calls),0)

    def test_reserved_home_member_is_not_counted_as_available_training_backup(self):
        self.e.hold(members={'id:member-b':True});self.choose();self.step();self.f.drain()
        self.assertEqual(len(self.f.executor.calls),0)

    def test_completed_training_after_restart_recovers_without_replay(self):
        self.begin();self.f.restart();after=self.raw(0,400,False)
        after.native.serverNow=1405;after.native.crew[2].train=1;self.f.app.Step(self.f.app,after)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).recoveries.crewTrain,'confirmed')
        self.assertEqual(len(self.f.executor.calls),1)
    def test_queued_cost_limit_change_blocks_training(self):
        self.choose();self.step()
        self.f.app.Set(self.f.app,'crewTrain.custom.maxCost',99);self.f.drain()
        self.assertEqual(len(self.f.executor.calls),0)
    def test_exact_negative_reply_without_start_releases_checkpoint(self):
        self.f.executor.reply=lua_table(self.h.lua,{'ok':False})
        self.begin();self.step(2)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).outcomes.crewTrain,'rejected')
        self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)),0)
    def test_pending_negative_reply_never_releases_training_custody(self):
        self.f.executor.reply=lua_table(self.h.lua,{'ok':False,'pending':True})
        self.begin();self.step(2)
        self.assertIsNone(self.f.runtime.Status(self.f.runtime).outcomes.crewTrain)
        self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)),1)
    def test_queued_member_replacement_blocks_training(self):
        self.choose();self.step();after=self.raw(2);after.native.crew[2].healId='replacement'
        self.h.at(2);self.f.app.Step(self.f.app,after);self.f.drain()
        self.assertEqual(len(self.f.executor.calls),0)
    def test_unload_queued_training_does_not_invoke(self):
        self.choose();self.step();self.f.app.Destroy(self.f.app);self.f.drain()
        self.assertEqual(len(self.f.executor.calls),0)
