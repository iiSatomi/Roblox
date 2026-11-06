"""Actual native Auto Equip App path and shared custody; no live client."""
import unittest
import test_crew_runtime as fixture
from engine_harness import lua_table

class CrewEquipRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.CrewRuntimeTests();self.f.setUp();self.f.app.Destroy(self.f.app)
        self.h=self.f.h;self.f.feature_id='crew'
        self.f.tab_dependencies['AutoEquipCrew']=self.h.load('src/tabs/crew/AutoEquipCrew.luau')
        self.f.executor.Invoke=self.h.lua.eval("function(self,remote,method,...) self.calls[#self.calls+1]={remote=remote,args=table.pack(...)} return self.reply or {ok=true,changed=true} end")
        self.h.lua.globals().crewExternalHold=None
        self.h.lua.globals().crewMarketOwner=None
        self.f.additional_reservation_sources=[self.h.lua.execute("return {id='externalTrade',read=function() if crewMarketOwner then return crewMarketOwner:ReservationClaims() end return crewExternalHold end}")]
        self.f.start_current()
    def tearDown(self):self.f.tearDown()
    def raw(self,revision=1,weapon='old'):
        raw=self.f.f.raw(revision=revision)
        raw.native.inventory=lua_table(self.h.lua,{'w_baton':1});raw.native.inventoryBound=self.h.lua.table()
        raw.native.crew[1].weapon=weapon
        raw.native.crew[2].healId='member-a';raw.native.crew[3].healId='member-b'
        return raw
    def step(self,revision=1,weapon='old'):
        raw=self.raw(revision,weapon);self.h.at(raw.capturedAt);self.f.app.Step(self.f.app,raw);return raw
    def choose(self):self.f.app.Set(self.f.app,'crew.enabled',True);self.f.app.Resume(self.f.app)
    def test_actual_zero_argument_native_call_requires_exact_newer_roster_effect(self):
        self.step();self.assertEqual(len(self.f.executor.calls),0)
        self.choose();self.step();self.f.drain()
        self.assertEqual(len(self.f.executor.calls),1)
        call=self.f.executor.calls[1];self.assertEqual(call.remote,'AutoEquipCrew');self.assertEqual(call.args.n,0)
        self.step(2,'w_baton')
        self.assertEqual(self.f.runtime.Status(self.f.runtime).outcomes.crew,'confirmed')
    def test_restart_observes_saved_native_reply_and_gear_effect_without_replay(self):
        self.choose();self.step();self.f.drain();self.f.restart()
        raw=self.raw(0,'w_baton');raw.native.serverNow=1005;self.f.app.Step(self.f.app,raw)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).recoveries.crew,'confirmed')
        self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)),0)
        self.assertEqual(len(self.f.executor.calls),1)
    def test_negative_reply_with_changed_gear_stays_uncertain(self):
        self.f.executor.reply=lua_table(self.h.lua,{'ok':False})
        self.choose();self.step();self.f.drain();self.step(2,'w_baton')
        self.assertIsNone(self.f.runtime.Status(self.f.runtime).outcomes.crew)
        self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)),1)

    def hold(self,items=None,members=None):
        self.h.lua.globals().crewExternalHold=lua_table(self.h.lua,{
            'account':self.h.session['account'],'place':self.h.session['place'],'release':self.h.session['release'],
            'feature':'marketSell' if items else 'crewRoll','actionKey':'saved-other',
            'claims':{'allCrew':False,'allItems':False,'members':members or {},'items':items or {},'funds':{}}})
    def hold_market(self,item="w_baton"):
        raw=self.raw();raw.native.inventory[item]=1;raw.native.market=lua_table(self.h.lua,{'shopUntil':2000,'listings':{}})
        evidence=self.h.load('src/tabs/blackMarket/MarketListEvidence.luau')
        owner,why=self.h.load('src/tabs/blackMarket/MarketTransactions.luau').new(
            self.f.storage,lua_table(self.h.lua,self.h.session),evidence)
        self.assertIsNone(why)
        p=lua_table(self.h.lua,{**self.h.session,'revision':1,'feature':'marketSell','preflightOnly':True,
            'intent':{'kind':'marketList','itemId':item,'quantity':1,'ask':14}})
        self.assertTrue(owner.PrepareOwnedList(owner,p,raw)[0])
        self.h.lua.globals().crewMarketOwner=owner
    def test_saved_market_item_hold_blocks_bulk_auto_equip(self):
        self.hold_market();self.choose();self.step();self.f.drain()
        self.assertEqual(len(self.f.executor.calls),0)
    def test_replacement_member_hold_blocks_bulk_auto_equip(self):
        self.hold(members={'id:member-a':True});self.choose();self.step();self.f.drain()
        self.assertEqual(len(self.f.executor.calls),0)
    def test_item_hold_appearing_after_queue_blocks_direct_emission(self):
        self.choose();self.step();self.hold_market();self.f.drain()
        self.assertEqual(len(self.f.executor.calls),0)
        self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)),0)
    def test_queued_disable_prevents_native_call(self):
        self.choose();self.step();self.f.app.Set(self.f.app,'crew.enabled',False);self.f.drain()
        self.assertEqual(len(self.f.executor.calls),0)
        self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)),0)
    def test_restarted_pending_reply_and_changed_stable_member_stay_held(self):
        self.f.executor.reply=lua_table(self.h.lua,{'ok':True,'changed':True,'pending':True})
        self.choose();self.step();self.f.drain();self.f.restart()
        raw=self.raw(0,'w_baton');raw.native.serverNow=1005;self.f.app.Step(self.f.app,raw)
        self.assertIsNone(self.f.runtime.Status(self.f.runtime).recoveries.crew)
        self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)),1)
    def test_changed_member_identity_cannot_confirm_gear_change(self):
        self.choose();self.step();self.f.drain()
        raw=self.raw(2,'w_baton');raw.native.crew[2].healId='replacement-a';self.h.at(2)
        self.f.app.Step(self.f.app,raw)
        self.assertIsNone(self.f.runtime.Status(self.f.runtime).outcomes.crew)
        self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)),1)
    def test_unload_queued_callback_does_not_invoke(self):
        self.choose();self.step();self.f.app.Destroy(self.f.app);self.f.drain()
        self.assertEqual(len(self.f.executor.calls),0)
