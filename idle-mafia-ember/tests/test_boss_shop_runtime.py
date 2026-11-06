"""Selected Boss reward purchase through actual App, source and native adapter."""
import unittest
import test_bosses_runtime as fixture
from engine_harness import lua_table

class BossShopRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.BossesRuntimeTests();self.f.setUp();self.f.app.Destroy(self.f.app)
        self.f.feature_id='bossShop';self.f.start_current();self.h=self.f.h
    def tearDown(self): self.f.tearDown()
    def raw(self,revision=1,tokens=3000,owned=2,bound=0):
        raw=self.f.raw(revision)
        raw.native.inventory=lua_table(self.h.lua,{'boss_token':tokens,'crate_loot':owned,'w_policebaton':0})
        raw.native.inventoryBound=lua_table(self.h.lua,{'boss_token':bound})
        return raw
    def step(self,revision=1,**kwargs):
        raw=self.raw(revision,**kwargs);self.h.at(raw.capturedAt);self.f.app.Step(self.f.app,raw);return raw
    def choose(self,item='crate_loot',quantity=1,reserve=0,cap=1):
        for key,value in {'enabled':True,'custom.itemId':item,'custom.crateQuantity':quantity,
                'custom.tokenReserve':reserve,'custom.maxSends':cap}.items():
            self.assertTrue(self.f.app.Set(self.f.app,'bossShop.'+key,value)[0],key)
        self.f.app.Resume(self.f.app)
    def begin(self,**kw):
        self.choose(**kw);self.step();self.f.drain()
        self.assertEqual(len(self.f.executor.calls),1,str(dict(self.f.runtime.Status(self.f.runtime).reasons.items())))
    def test_exact_crate_quantity_and_token_effect(self):
        self.begin(quantity=10);call=self.f.executor.calls[1]
        self.assertEqual(call.remote,'BossAction');self.assertEqual(call.args.n,3)
        self.assertEqual([call.args[i] for i in (1,2,3)],['shopBuy','crate_loot',10])
        self.step(2,tokens=2860,owned=12)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).outcomes.bossShop,'confirmed')
    def test_gear_uses_one_and_preserves_nil_native_argument(self):
        self.begin(item='w_policebaton',quantity=10);call=self.f.executor.calls[1]
        self.assertEqual(call.args.n,3);self.assertEqual(call.args[2],'w_policebaton');self.assertIsNone(call.args[3])
    def test_caller_counter_does_not_bypass_same_session_cap(self):
        self.begin();self.step(2,tokens=2986,owned=3)
        self.h.at(2);raw=self.raw(3,tokens=2986,owned=3)
        raw.bossShopUsageProof=lua_table(self.h.lua,{'account':'user-a','session':'run-a','capturedAt':2,'attempts':0})
        self.f.app.Step(self.f.app,raw);self.f.drain();self.assertEqual(len(self.f.executor.calls),1)
    def test_saved_exact_purchase_recovers_without_replay(self):
        self.begin();self.f.restart();after=self.raw(0,tokens=2986,owned=3);after.native.serverNow=2000005
        self.f.app.Step(self.f.app,after)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).recoveries.bossShop,'confirmed')
        self.assertEqual(len(self.f.executor.calls),1)
    def test_pending_reply_with_effect_stays_uncertain(self):
        self.f.executor.reply=lua_table(self.h.lua,{'ok':True,'pending':True});self.begin();self.step(2,tokens=2986,owned=3)
        self.assertIsNone(self.f.runtime.Status(self.f.runtime).outcomes.bossShop)
    def test_partial_effect_cannot_be_rejected(self):
        self.f.executor.reply=lua_table(self.h.lua,{'ok':False});self.begin();self.step(2,tokens=2986)
        self.assertIsNone(self.f.runtime.Status(self.f.runtime).outcomes.bossShop)
    def test_overdebit_cannot_be_confirmed(self):
        self.begin();self.step(2,tokens=2900,owned=3)
        self.assertIsNone(self.f.runtime.Status(self.f.runtime).outcomes.bossShop)
    def test_extra_items_cannot_be_confirmed(self):
        self.begin();self.step(2,tokens=2986,owned=4)
        self.assertIsNone(self.f.runtime.Status(self.f.runtime).outcomes.bossShop)
    def test_current_quote_change_after_queue_blocks_emit(self):
        self.choose();self.step();self.f.source.SHOP.crates[1].price=15;self.f.drain()
        self.assertEqual(len(self.f.executor.calls),0)
    def test_shared_token_funding_and_reserve_guard(self):
        self.choose(reserve=100);self.step(tokens=150);self.f.hold({'boss_token':50});self.f.drain()
        self.assertEqual(len(self.f.executor.calls),0)
    def test_queued_disable_never_invokes_or_uses_send_cap(self):
        self.choose();self.step();self.f.app.Set(self.f.app,'bossShop.enabled',False);self.f.drain()
        self.assertEqual(len(self.f.executor.calls),0)
        self.assertEqual(self.f.runtime.checkpoint.bossShopUsage.attempts,0)
    def test_changed_bound_and_loose_origin_with_same_total_is_not_exact(self):
        self.begin();after=self.raw(2,tokens=2986,owned=2)
        after.native.inventoryBound.crate_loot=2;after.native.inventory.crate_loot=1
        self.f.app.Step(self.f.app,after)
        self.assertIsNone(self.f.runtime.Status(self.f.runtime).outcomes.bossShop)

    def test_exact_bound_award_is_observed_without_inventing_output_origin(self):
        self.begin();after=self.raw(2,tokens=2986);after.native.inventoryBound.crate_loot=1
        self.f.app.Step(self.f.app,after)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).outcomes.bossShop,'confirmed')
    def test_saved_negative_requires_fresh_unchanged_inventory(self):
        self.f.executor.reply=lua_table(self.h.lua,{'ok':False});self.begin();self.f.restart()
        after=self.raw(0);after.native.serverNow=2000005;self.f.app.Step(self.f.app,after)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).recoveries.bossShop,'rejected')
        self.assertEqual(len(self.f.executor.calls),1)
    def test_missing_unlock_and_zero_reserve_funding_do_not_emit(self):
        self.f.source.crateUnlocked=self.h.lua.eval('function() return false end')
        self.choose();self.step();self.f.drain();self.assertEqual(len(self.f.executor.calls),0)
    def test_unload_before_invocation_recovers_only_exact_unsent_send(self):
        self.choose();self.step();self.f.app.Destroy(self.f.app);self.f.drain();self.f.restart()
        after=self.raw(0);after.native.serverNow=2000005;self.f.app.Step(self.f.app,after)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).recoveries.bossShop,'known_unsent')
        self.assertEqual(self.f.runtime.checkpoint.bossShopUsage.attempts,0)
        self.assertEqual(len(self.f.executor.calls),0)
    def test_timeout_holds_reward_inventory_and_keeps_attempt(self):
        self.f.executor.reply=lua_table(self.h.lua,{'ok':True,'pending':True});self.begin()
        self.h.at(45);after=self.raw(2,tokens=2986,owned=3);self.f.app.Step(self.f.app,after)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).outcomes.bossShop,'skipped_unconfirmed')
        self.assertEqual(self.f.runtime.checkpoint.bossShopUsage.attempts,1)
        proposal=lua_table(self.h.lua,{**self.h.session,'revision':2,'feature':'other','actionKey':'other-use',
            'intent':{'kind':'consume'},'resources':{'crate_loot':1}})
        self.assertIsNone(self.f.runtime.reservationOwner.Check(self.f.runtime.reservationOwner,proposal,after)[0])
    def test_selected_reward_change_after_queue_blocks_native_call(self):
        self.choose();self.step();self.f.app.Set(self.f.app,'bossShop.custom.itemId','w_policebaton');self.f.drain()
        self.assertEqual(len(self.f.executor.calls),0)
    def test_stale_negative_reply_never_resolves_same_revision(self):
        self.f.executor.reply=lua_table(self.h.lua,{'ok':False});self.begin();self.step(1)
        self.assertIsNone(self.f.runtime.Status(self.f.runtime).outcomes.bossShop)
        self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)),1)
    def test_tokens_transferred_between_origins_cannot_prove_debit(self):
        self.begin();self.step(2,tokens=2980,bound=6,owned=3)
        self.assertIsNone(self.f.runtime.Status(self.f.runtime).outcomes.bossShop)
