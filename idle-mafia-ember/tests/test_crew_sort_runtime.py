"""Actual native Crew sorting with complete-member custody and saved results."""
import hashlib
import unittest
import test_crew_equip_runtime as equip_fixture
from engine_harness import lua_table
class CrewSortRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.e=equip_fixture.CrewEquipRuntimeTests();self.e.setUp();self.f=self.e.f;self.h=self.e.h
        self.f.app.Destroy(self.f.app);self.f.feature_id='crewSort'
        self.h.lua.globals().crewRuntimeSortHash=lambda value: hashlib.sha256(value.encode()).hexdigest()
        self.f.tab_dependencies['sha256']=self.h.lua.eval('function(value) return crewRuntimeSortHash(value) end')
        self.f.tab_dependencies['CrewSort']=self.h.load('src/tabs/crew/CrewSort.luau');self.f.start_current()
    def tearDown(self):self.f.tearDown()
    def raw(self,revision=1,sorted=False):
        raw=self.f.f.raw(revision=revision)
        weak={'name':'Weak','rarity':1,'healId':'a','weapon':'wa'}
        strong={'name':'Strong','rarity':5,'healId':'b','weapon':'wb'}
        raw.native.crew=lua_table(self.h.lua,[{'name':'Player'},strong if sorted else weak,weak if sorted else strong,
            {'name':'Guard','rarity':4,'healId':'c','duty':'district'}])
        raw.native.inventory=self.h.lua.table();raw.native.inventoryBound=self.h.lua.table()
        return raw
    def step(self,revision=1,sorted=False):
        raw=self.raw(revision,sorted);self.h.at(raw.capturedAt);self.f.app.Step(self.f.app,raw);return raw
    def choose(self):self.f.app.Set(self.f.app,'crewSort.enabled',True);self.f.app.Resume(self.f.app)
    def test_actual_four_argument_sort_preserves_pinned_member(self):
        self.choose();self.step();self.f.drain();call=self.f.executor.calls[1]
        self.assertEqual(call.remote,'CrewAction');self.assertEqual(call.args.n,4);self.assertEqual(call.args[1],'sort')
        self.step(2,True);self.assertEqual(self.f.runtime.Status(self.f.runtime).outcomes.crewSort,'confirmed')
    def test_wrong_gear_association_cannot_confirm_sort(self):
        self.choose();self.step();self.f.drain();after=self.raw(2,True);after.native.crew[2].weapon='wrong'
        self.h.at(2);self.f.app.Step(self.f.app,after)
        self.assertIsNone(self.f.runtime.Status(self.f.runtime).outcomes.crewSort)
    def test_same_name_replacement_does_not_count_as_original_member(self):
        self.choose();self.step();self.f.drain();after=self.raw(2,True);after.native.crew[3].healId='replacement'
        self.h.at(2);self.f.app.Step(self.f.app,after)
        self.assertIsNone(self.f.runtime.Status(self.f.runtime).outcomes.crewSort)
    def test_negative_reply_with_changed_order_stays_uncertain(self):
        self.f.executor.reply=lua_table(self.h.lua,{'ok':False})
        self.choose();self.step();self.f.drain();self.step(2,True)
        self.assertIsNone(self.f.runtime.Status(self.f.runtime).outcomes.crewSort)
    def test_saved_sort_recovers_only_exact_newer_roster_without_replay(self):
        self.choose();self.step();self.f.drain();self.f.restart()
        after=self.raw(0,True);after.native.serverNow=1005;self.f.app.Step(self.f.app,after)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).recoveries.crewSort,'confirmed')
        self.assertEqual(len(self.f.executor.calls),1)
    def test_shared_member_hold_prevents_sort(self):
        self.e.hold(members={'id:a':True});self.choose();self.step();self.f.drain()
        self.assertEqual(len(self.f.executor.calls),0)

    def test_duplicate_stable_id_blocks_native_sort(self):
        self.choose();raw=self.raw();raw.native.crew[3].healId='a';self.h.at(1);self.f.app.Step(self.f.app,raw);self.f.drain()
        self.assertEqual(len(self.f.executor.calls),0)
    def test_queued_member_hold_blocks_emission(self):
        self.choose();self.step();self.e.hold(members={'id:a':True});self.f.drain()
        self.assertEqual(len(self.f.executor.calls),0)
        self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)),0)
    def test_pinned_member_movement_cannot_confirm(self):
        self.choose();self.step();self.f.drain();after=self.raw(2,True)
        after.native.crew[2],after.native.crew[4]=after.native.crew[4],after.native.crew[2]
        self.h.at(2);self.f.app.Step(self.f.app,after)
        self.assertIsNone(self.f.runtime.Status(self.f.runtime).outcomes.crewSort)
    def test_disable_then_unload_queued_callback_does_not_sort(self):
        self.choose();self.step();self.f.app.Set(self.f.app,'crewSort.enabled',False);self.f.app.Destroy(self.f.app);self.f.drain()
        self.assertEqual(len(self.f.executor.calls),0)
    def test_saved_pending_reply_cannot_confirm_new_order(self):
        self.f.executor.reply=lua_table(self.h.lua,{'ok':True,'changed':True,'pending':True})
        self.choose();self.step();self.f.drain();self.f.restart()
        after=self.raw(0,True);after.native.serverNow=1005;self.f.app.Step(self.f.app,after)
        self.assertIsNone(self.f.runtime.Status(self.f.runtime).recoveries.crewSort)
        self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)),1)

    def test_large_roster_crosses_actual_app_checkpoint_and_exact_native_call(self):
        self.choose()
        raw=self.raw()
        for slot in range(5,34):
            raw.native.crew[slot]=lua_table(self.h.lua,{'name':f'Member {slot} with a long roster name',
                'rarity':4,'healId':f'stable-id-{slot}-abcdefghijklmnopqrstuvwxyz'})
        self.h.at(raw.capturedAt);self.f.app.Step(self.f.app,raw)
        self.f.drain()
        self.assertEqual(len(self.f.executor.calls),1,str(dict(self.f.runtime.Status(self.f.runtime).reasons.items())))
        self.assertEqual(self.f.executor.calls[1].args[1],'sort')
        self.assertFalse(self.f.runtime.Status(self.f.runtime).storageFault)
        self.f.restart()
        after=self.raw(0,True)
        for slot in range(5,34):after.native.crew[slot]=raw.native.crew[slot]
        after.native.serverNow=1005
        self.f.app.Step(self.f.app,after)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).recoveries.crewSort,'confirmed')
        self.assertEqual(len(self.f.executor.calls),1)
