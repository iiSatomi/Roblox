"""Actual selected Crew gear swaps preserve stable member and origin custody."""
import unittest
from engine_harness import lua_table
import test_crew_equip_runtime as equip_fixture
class CrewGearRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.e=equip_fixture.CrewEquipRuntimeTests();self.e.setUp();self.f=self.e.f;self.h=self.e.h
        self.f.app.Destroy(self.f.app);self.f.feature_id='crewGear'
        self.f.tab_dependencies.update(CrewGear=self.h.load('src/tabs/crew/CrewGear.luau'),
            gearSets=self.h.lua.eval('{slotBonus=function() return 0,0 end}'),
            gameData={'ITEMS_BY_ID':{'old_w':{'id':'old_w','kind':'weapon','atk':1,'def':1},
                'new_w':{'id':'new_w','kind':'weapon','atk':8,'def':3}}})
        self.f.start_current()
    def tearDown(self):self.f.tearDown()
    def raw(self,revision=1,changed=False,target=1):
        raw=self.f.f.raw(revision=revision)
        raw.native.inventory=lua_table(self.h.lua,{'new_w':0 if changed else 1,'old_w':1 if changed else 0})
        raw.native.inventoryBound=self.h.lua.table()
        raw.native.crew=lua_table(self.h.lua,[{'name':'Player','weapon':'new_w' if changed and target==1 else 'old_w','weaponBound':target==2},
            {'name':'Ally','rarity':4,'healId':'member-a','weapon':'new_w' if changed and target==2 else 'old_w'}])
        return raw
    def step(self,revision=1,changed=False,target=1):
        raw=self.raw(revision,changed,target);self.h.at(raw.capturedAt);self.f.app.Step(self.f.app,raw);return raw
    def choose(self):
        self.f.app.Set(self.f.app,'crewGear.enabled',True);self.f.app.Set(self.f.app,'crewGear.policy','Attack');self.f.app.Resume(self.f.app)
    def test_actual_native_swap_confirms_exact_loose_debit_and_returned_old_item(self):
        self.choose();self.step();self.f.drain();call=self.f.executor.calls[1]
        self.assertEqual(call.remote,'CrewEquip');self.assertEqual([call.args[i] for i in range(1,4)],[1,'weapon','new_w'])
        self.step(2,True);self.assertEqual(self.f.runtime.Status(self.f.runtime).outcomes.crewGear,'confirmed')
    def test_wrong_bound_origin_change_stays_uncertain(self):
        self.choose();self.step();self.f.drain();after=self.raw(2,True)
        after.native.inventoryBound.new_w=1;self.h.at(2);self.f.app.Step(self.f.app,after)
        self.assertIsNone(self.f.runtime.Status(self.f.runtime).outcomes.crewGear)
    def test_same_name_replacement_identity_cannot_confirm_old_member_swap(self):
        self.choose();self.step(target=2);self.f.drain();after=self.raw(2,True,2)
        after.native.crew[2].healId='replacement-a';self.h.at(2);self.f.app.Step(self.f.app,after)
        self.assertIsNone(self.f.runtime.Status(self.f.runtime).outcomes.crewGear)
    def test_missing_old_item_return_stays_uncertain(self):
        self.choose();self.step();self.f.drain();after=self.raw(2,True)
        after.native.inventory.old_w=0;self.h.at(2);self.f.app.Step(self.f.app,after)
        self.assertIsNone(self.f.runtime.Status(self.f.runtime).outcomes.crewGear)
    def test_restart_confirms_exact_saved_gear_swap_without_replay(self):
        self.choose();self.step();self.f.drain();self.f.restart()
        after=self.raw(0,True);after.native.serverNow=1005;self.f.app.Step(self.f.app,after)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).recoveries.crewGear,'confirmed')
        self.assertEqual(len(self.f.executor.calls),1)

    def test_pending_swap_holds_returned_item_against_collection_consumption(self):
        self.f.executor.reply=lua_table(self.h.lua,{'ok':True,'pending':True})
        self.choose();self.step();self.f.drain();after=self.step(2,True)
        p=lua_table(self.h.lua,{**self.h.session,'revision':2,'feature':'collectionDonate','actionKey':'deposit-returned',
            'resources':{'old_w':1},'intent':{'kind':'collectionDonate','itemId':'old_w','amount':1}})
        claims,why=self.f.runtime.reservationOwner.Check(self.f.runtime.reservationOwner,p,after)
        self.assertIsNone(claims,why)

    def test_saved_market_copy_is_never_equipped(self):
        self.e.hold_market('new_w');self.choose();self.step();self.f.drain()
        self.assertEqual(len(self.f.executor.calls),0)
    def test_queued_member_replacement_blocks_native_swap(self):
        self.choose();self.step(target=2)
        after=self.raw(2,False,2);after.native.crew[2].healId='replacement-a'
        self.h.at(2);self.f.app.Step(self.f.app,after);self.f.drain()
        self.assertEqual(len(self.f.executor.calls),0)
        self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)),0)
    def test_queued_disable_and_unload_cannot_emit_swap(self):
        self.choose();self.step();self.f.app.Set(self.f.app,'crewGear.enabled',False);self.f.app.Destroy(self.f.app);self.f.drain()
        self.assertEqual(len(self.f.executor.calls),0)
    def test_negative_reply_with_applied_swap_keeps_pending_custody(self):
        self.f.executor.reply=lua_table(self.h.lua,{'ok':False})
        self.choose();self.step();self.f.drain();self.step(2,True)
        self.assertIsNone(self.f.runtime.Status(self.f.runtime).outcomes.crewGear)
        self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)),1)
    def test_unidentified_non_player_member_is_not_automatically_targeted(self):
        self.choose();raw=self.raw(target=2);raw.native.crew[2].healId=None
        self.h.at(1);self.f.app.Step(self.f.app,raw);self.f.drain()
        self.assertEqual(len(self.f.executor.calls),0)
