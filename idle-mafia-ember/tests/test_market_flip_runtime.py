"""Actual Flip tab/App/broker/native adapter; no live client or spending."""
import unittest
from engine_harness import lua_table
from test_market_payout_runtime import MarketPayoutRuntimeFixture

class MarketFlipRuntimeTests(MarketPayoutRuntimeFixture,unittest.TestCase):
    feature_id='marketFlip'
    def start(self):
        self.deps.update(clock=self.h.clock,gameData={'ITEMS_BY_ID':{'w_baton':{
            'id':'w_baton','kind':'weapon','rarity':5,'tradable':True,'atk':1,'def':1}}},
            marketPresence=self.h.lua.execute('local g={allowed=true};g.check=function() return g.allowed end;g.handle=function() return true end;return g'))
        super().start()
    def raw(self,revision=1,gold=20,loose=1):
        return self.h.snapshot(revision=revision,captured_at=revision,native={
            'fullSync':True,'serverNow':1000+revision,'level':50,
            'market':{'extraSlots':0,'shopUntil':2000,'listings':{}},
            'inventory':{'gold_bar':gold,'w_baton':loose},'inventoryBound':{},
            'collection':{},'collectionBound':{},'crew':[{}],'derived':{'marketShop':False}})
    def choose(self):
        for key,value in {'enabled':True,'custom.scope':'Selected item','custom.selectedItemId':'w_baton',
            'custom.maxBuy':8,'custom.sessionBudget':8,'custom.goldReserve':5,'custom.maxAttempts':1,
            'custom.maxListAttempts':1,'custom.minMargin':1,'custom.minMarginPct':0,
            'custom.undercutGold':0,'custom.floorPct':90,'custom.requireCoverage':True}.items():
            self.assertTrue(self.app.Set(self.app,'marketFlip.'+key,value)[0])
        self.app.Resume(self.app)
    def warm(self,raw,metadata=None):
        self.h.at(raw.capturedAt)
        custom={k.removeprefix('marketFlip.custom.'):v for k,v in self.app.model['values'].items() if k.startswith('marketFlip.custom.')}
        settings=lua_table(self.h.lua,{'marketFlip':{'enabled':True,'custom':custom},'marketWatch':{'enabled':False}})
        for source in self.tab.ReadSources(self.tab).values():
            if not source.id.startswith('marketFlip') or not source.enabled(settings):continue
            request=source.prepare(raw)
            if isinstance(request,tuple):request=request[0]
            if request is None:continue
            if source.id.endswith('Browse'):
                reply={'ok':True,'pages':1,'more':False,'rows':[
                    {'id':'cheap','item':'w_baton','qty':1,'price':8,'mine':False},
                    {'id':'other','item':'w_baton','qty':1,'price':14,'mine':False}]}
                if source.id.startswith('marketFlipList'):reply['rows']=reply['rows'][1:]
                reply.update(metadata or {})
            elif source.id.endswith('Rap'):reply={'ok':True,'values':{'w_baton':{'sales':15,'quantity':30,'average':14,'available':True}}}
            else:reply={'ok':True,'item':'w_baton','recent':[{'price':14},{'price':15},{'price':16}],'days':[]}
            staged=source.accept(raw,request,lua_table(self.h.lua,reply))
            if isinstance(staged,tuple):staged=staged[0]
            self.assertIsNotNone(staged,source.id);self.assertTrue(source.commit(staged))
    def test_actual_app_buy_requires_opt_in_and_confirms_exact_gold_item_effect(self):
        raw=self.raw();self.h.at(1);self.app.Step(self.app,raw)
        self.assertEqual(len(self.executor.calls),0)
        self.choose();self.warm(raw);self.app.Step(self.app,raw);self.executor.Drain(self.executor)
        self.assertEqual(len(self.executor.calls),1,str(dict(self.runtime.Status(self.runtime).reasons.items()))+str(dict(self.runtime.session.Status(self.runtime.session).items())))
        call=self.executor.calls[1]
        self.assertEqual(call.remote,'MarketAction')
        self.assertEqual([call.args[i] for i in range(1,5)],['buy','cheap',1,8])
        after=self.raw(2,gold=12,loose=2);self.h.at(2);self.app.Step(self.app,after)
        self.assertEqual(self.runtime.Status(self.runtime).outcomes.marketFlip,'confirmed')
        self.assertEqual(self.tab.transactions.BuyUsage(self.tab.transactions).spent,8)
        self.assertFalse(self.app.model['values']['marketWatch.enabled'])

    def test_confirmed_buy_then_owned_listing_uses_independent_limits(self):
        self.choose();raw=self.raw();self.warm(raw);self.app.Step(self.app,raw);self.executor.Drain(self.executor)
        after=self.raw(2,gold=12,loose=2);self.h.at(2);self.app.Step(self.app,after)
        self.warm(after);self.app.Step(self.app,after);self.executor.Drain(self.executor)
        self.assertEqual(len(self.executor.calls),2,str(dict(self.runtime.Status(self.runtime).reasons.items())))
        call=self.executor.calls[2]
        self.assertEqual([call.args[i] for i in range(1,5)],['list','w_baton',1,14])
        after=self.raw(3,gold=12,loose=1)
        after.native.market.listings=lua_table(self.h.lua,{'listed':{'state':'live','item':'w_baton','indexed':1,
            'price':14,'qty':1,'left':1,'createdAt':1002,'itemOrigin':{'total':1,'free':0}}})
        self.h.at(3);self.app.Step(self.app,after)
        self.assertIsNone(self.tab.transactions.Active(self.tab.transactions))
        self.assertEqual(self.tab.transactions.BuyUsage(self.tab.transactions).spent,8)
        self.assertEqual(self.tab.transactions.ListingAttempts(self.tab.transactions,"marketFlip")[0],1)

    def begin_buy(self,reply=None):
        self.choose();raw=self.raw();self.warm(raw);self.app.Step(self.app,raw)
        self.executor.reply=lua_table(self.h.lua,reply or {'ok':True});self.executor.Drain(self.executor)

    def test_restart_confirms_exact_saved_buy_without_replay(self):
        self.begin_buy();self.restart()
        after=self.raw(0,gold=12,loose=2);after.native.serverNow=1005;self.app.Step(self.app,after)
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.marketFlip,'confirmed')
        self.assertEqual(self.tab.transactions.Active(self.tab.transactions).stage,'observed')
        self.assertEqual(self.tab.transactions.BuyUsage(self.tab.transactions).spent,8)
        self.assertEqual(len(self.executor.calls),1)
        self.assertFalse(self.app.model['values']['marketFlip.enabled'])

    def test_exact_buy_rejection_retains_charged_attempt(self):
        self.begin_buy({'ok':False})
        after=self.raw(2);self.h.at(2);self.app.Step(self.app,after)
        self.assertEqual(self.runtime.Status(self.runtime).outcomes.marketFlip,'rejected')
        self.assertIsNone(self.tab.transactions.Active(self.tab.transactions))
        self.assertEqual(self.tab.transactions.BuyUsage(self.tab.transactions).spent,8)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),0)
        self.assertEqual(len(self.executor.calls),1)

    def test_pending_buy_reply_never_confirms_exact_item_effect(self):
        self.begin_buy({'ok':True,'pending':True});self.restart()
        after=self.raw(0,gold=12,loose=2);after.native.serverNow=1005;self.app.Step(self.app,after)
        self.assertIsNone(self.runtime.Status(self.runtime).recoveries.marketFlip)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),1)
        self.assertEqual(len(self.executor.calls),1)

    def test_disable_before_buy_dispatch_does_not_charge_gold_allowance(self):
        self.choose();raw=self.raw();self.warm(raw);self.app.Step(self.app,raw)
        self.app.Set(self.app,'marketFlip.enabled',False);self.executor.Drain(self.executor)
        self.assertEqual(len(self.executor.calls),0)
        self.assertIsNone(self.tab.transactions.Active(self.tab.transactions))
        self.assertEqual(self.tab.transactions.BuyUsage(self.tab.transactions).spent,0)

    def test_queued_budget_change_blocks_buy_and_releases_only_unsent_hold(self):
        self.choose();raw=self.raw();self.warm(raw);self.app.Step(self.app,raw)
        self.app.Set(self.app,'marketFlip.custom.sessionBudget',7);self.executor.Drain(self.executor)
        self.assertEqual(len(self.executor.calls),0)
        self.assertIsNone(self.tab.transactions.Active(self.tab.transactions))
        self.assertEqual(self.tab.transactions.BuyUsage(self.tab.transactions).spent,0)

    def test_bound_origin_change_cannot_confirm_saved_buy(self):
        self.begin_buy();self.restart()
        after=self.raw(0,gold=12,loose=2);after.native.serverNow=1005
        after.native.inventoryBound.gold_bar=1;self.app.Step(self.app,after)
        self.assertIsNone(self.runtime.Status(self.runtime).recoveries.marketFlip)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),1)

    def test_native_presence_reply_stays_owned_and_is_delegated(self):
        self.begin_buy({'code':'presence'})
        after=self.raw(2);self.h.at(2);self.app.Step(self.app,after)
        self.assertIsNone(self.runtime.Status(self.runtime).outcomes.marketFlip)
        self.assertEqual(self.tab.transactions.Active(self.tab.transactions).reply.code,'presence')
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),1)

    def test_restart_confirms_exact_followup_listing_without_replay(self):
        self.begin_buy();after=self.raw(2,gold=12,loose=2);self.h.at(2);self.app.Step(self.app,after)
        self.warm(after);self.app.Step(self.app,after);self.executor.Drain(self.executor);self.restart()
        after=self.raw(0,gold=12,loose=1);after.native.serverNow=1005
        after.native.market.listings=lua_table(self.h.lua,{'listed':{'state':'live','item':'w_baton','indexed':1,
            'price':14,'qty':1,'left':1,'createdAt':1002,'itemOrigin':{'total':1,'free':0}}})
        self.app.Step(self.app,after)
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.marketFlip,'confirmed')
        self.assertIsNone(self.tab.transactions.Active(self.tab.transactions))
        self.assertEqual(len(self.executor.calls),2)

    def test_paused_prepared_buy_review_clears_without_call_or_budget_reset(self):
        self.choose();raw=self.raw();self.warm(raw);self.app.Step(self.app,raw);self.restart()
        after=self.raw(0);after.native.serverNow=1005;self.app.Step(self.app,after);self.app.Pause(self.app)
        preview,why=self.app.PreviewFeatureRecovery(self.app,'marketFlip')
        self.assertIsNotNone(preview,why)
        self.assertTrue(self.app.ConfirmFeatureRecovery(self.app,'marketFlip')[0])
        self.assertIsNone(self.tab.transactions.Active(self.tab.transactions))
        self.assertEqual(self.tab.transactions.BuyUsage(self.tab.transactions).spent,0)
        self.executor.Drain(self.executor);self.assertEqual(len(self.executor.calls),0)

    def test_paused_observed_purchase_release_keeps_item_and_charged_budget(self):
        self.begin_buy();self.app.Set(self.app,'marketFlip.enabled',False)
        after=self.raw(2,gold=12,loose=2);self.h.at(2);self.app.Step(self.app,after);self.app.Pause(self.app)
        preview,why=self.app.PreviewFeatureRecovery(self.app,'marketFlip')
        self.assertIsNotNone(preview,why);self.assertEqual(preview.kind,'observed')
        self.assertTrue(self.app.ConfirmFeatureRecovery(self.app,'marketFlip')[0])
        self.assertIsNone(self.tab.transactions.Active(self.tab.transactions))
        self.assertEqual(self.tab.transactions.BuyUsage(self.tab.transactions).spent,8)
        self.assertEqual(after.native.inventory.w_baton,2)
        self.assertEqual(len(self.executor.calls),1)

    def test_disable_followup_keeps_purchased_item_hold_and_does_not_refund_buy(self):
        self.begin_buy();after=self.raw(2,gold=12,loose=2);self.h.at(2);self.app.Step(self.app,after)
        self.warm(after);self.app.Step(self.app,after)
        self.app.Set(self.app,'marketFlip.enabled',False);self.executor.Drain(self.executor)
        self.assertEqual(self.tab.transactions.Active(self.tab.transactions).kind,'buy')
        self.assertEqual(self.tab.transactions.BuyUsage(self.tab.transactions).spent,8)
        self.assertEqual(self.tab.transactions.ListingAttempts(self.tab.transactions,"marketFlip")[0],0)
        self.assertEqual(len(self.executor.calls),1)

    def test_unload_before_buy_dispatch_recovers_only_exact_unsent_fact(self):
        self.choose();raw=self.raw();self.warm(raw);self.app.Step(self.app,raw)
        self.app.Destroy(self.app);self.executor.Drain(self.executor);self.restart()
        after=self.raw(0);after.native.serverNow=1005;self.app.Step(self.app,after)
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.marketFlip,'known_unsent')
        self.assertIsNone(self.tab.transactions.Active(self.tab.transactions))
        self.assertEqual(self.tab.transactions.BuyUsage(self.tab.transactions).spent,0)
        self.assertEqual(len(self.executor.calls),0)

    def test_disable_during_buy_authorization_write_refunds_definitely_unsent_charge(self):
        self.choose();raw=self.raw();self.warm(raw);self.app.Step(self.app,raw)
        self.h.lua.globals().flipApp=self.app
        self.storage.Write=self.h.lua.eval("function(self,key,value) self.data[key]=value;if not self.disabled and value.transaction and value.transaction.kind=='buy' and value.transaction.stage=='sent' then self.disabled=true;flipApp:Set('marketFlip.enabled',false) end return true end")
        self.executor.Drain(self.executor)
        self.assertEqual(len(self.executor.calls),0)
        self.assertEqual(self.tab.transactions.BuyUsage(self.tab.transactions).spent,0)
        self.assertIsNone(self.tab.transactions.Active(self.tab.transactions))

    def test_45_second_skip_keeps_uncertain_buy_custody_and_does_not_replay(self):
        self.begin_buy({'ok':True})
        after=self.raw(46);self.h.at(46);self.app.Step(self.app,after);self.executor.Drain(self.executor)
        self.assertEqual(self.runtime.Status(self.runtime).outcomes.marketFlip,'skipped_unconfirmed')
        self.assertIsNotNone(self.tab.transactions.Active(self.tab.transactions))
        self.assertEqual(self.tab.transactions.BuyUsage(self.tab.transactions).spent,8)
        self.assertEqual(len(self.executor.calls),1)
        self.app.Pause(self.app)
        self.assertIsNone(self.app.PreviewFeatureRecovery(self.app,'marketFlip')[0])

    def test_buy_observation_write_failure_recovers_without_double_charging(self):
        self.begin_buy()
        self.storage.Write=self.h.lua.eval("function(self,key,value) if value.transaction and value.transaction.stage=='observed' then return false end self.data[key]=value return true end")
        after=self.raw(2,gold=12,loose=2);self.h.at(2);self.app.Step(self.app,after)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),1)
        self.storage.Write=self.h.lua.eval('function(self,key,value) self.data[key]=value return true end')
        self.restart();after=self.raw(0,gold=12,loose=2);after.native.serverNow=1005;self.app.Step(self.app,after)
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.marketFlip,'confirmed')
        self.assertEqual(self.tab.transactions.BuyUsage(self.tab.transactions).spent,8)
        self.assertEqual(len(self.executor.calls),1)

    def test_rejected_buy_checkpoint_cleanup_failure_recovers_exact_receipt(self):
        self.begin_buy({'ok':False})
        self.storage.Write=self.h.lua.eval("function(self,key,value) if key:find(':checkpoint:',1,true) and #value.records==0 then return false end self.data[key]=value return true end")
        after=self.raw(2);self.h.at(2);self.app.Step(self.app,after)
        self.storage.Write=self.h.lua.eval('function(self,key,value) self.data[key]=value return true end')
        self.restart();after=self.raw(0);after.native.serverNow=1005;self.app.Step(self.app,after)
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.marketFlip,'rejected')
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),0)
        self.assertEqual(self.tab.transactions.BuyUsage(self.tab.transactions).spent,8)
        self.assertEqual(len(self.executor.calls),1)

    def test_rejected_followup_restores_bought_item_and_exhausts_only_listing_cap(self):
        self.begin_buy();after=self.raw(2,gold=12,loose=2);self.h.at(2);self.app.Step(self.app,after)
        self.warm(after);self.app.Step(self.app,after)
        self.executor.reply=lua_table(self.h.lua,{'ok':False});self.executor.Drain(self.executor)
        after=self.raw(3,gold=12,loose=2);self.h.at(3);self.app.Step(self.app,after)
        self.assertEqual(self.tab.transactions.Active(self.tab.transactions).kind,'buy')
        self.assertEqual(self.tab.transactions.ListingAttempts(self.tab.transactions,"marketFlip")[0],1)
        self.assertEqual(self.tab.transactions.BuyUsage(self.tab.transactions).spent,8)
        self.app.Step(self.app,after);self.executor.Drain(self.executor)
        self.assertEqual(len(self.executor.calls),2)

    def test_listing_limit_applies_per_copy_and_is_independent_from_market_sell(self):
        self.choose()
        self.app.Set(self.app,'marketFlip.custom.sessionBudget',16)
        self.app.Set(self.app,'marketFlip.custom.maxAttempts',2)
        self.app.Set(self.app,'marketFlip.custom.goldReserve',0)
        raw=self.raw();self.warm(raw);self.app.Step(self.app,raw);self.executor.Drain(self.executor)
        after=self.raw(2,gold=12,loose=2);self.h.at(2);self.app.Step(self.app,after)
        self.warm(after);self.app.Step(self.app,after);self.executor.Drain(self.executor)
        listings=lua_table(self.h.lua,{'first':{'state':'live','item':'w_baton','indexed':1,
            'price':14,'qty':1,'left':1,'createdAt':1002,'itemOrigin':{'total':1,'free':0}}})
        after=self.raw(3,gold=12,loose=1);after.native.market.listings=listings
        self.h.at(3);self.app.Step(self.app,after);self.warm(after);self.app.Step(self.app,after);self.executor.Drain(self.executor)
        self.assertEqual(len(self.executor.calls),3,str(dict(self.runtime.Status(self.runtime).reasons.items())))
        after=self.raw(4,gold=4,loose=2);after.native.market.listings=listings
        self.h.at(4);self.app.Step(self.app,after);self.warm(after);self.app.Step(self.app,after);self.executor.Drain(self.executor)
        self.assertEqual(len(self.executor.calls),4,str(dict(self.runtime.Status(self.runtime).reasons.items())))
        self.assertEqual(self.tab.transactions.BuyUsage(self.tab.transactions).spent,16)
        self.assertEqual(self.tab.transactions.ListingAttempts(self.tab.transactions,'marketFlip')[0],2)
        self.assertEqual(self.tab.transactions.ListingAttempts(self.tab.transactions)[0],0)

    def test_same_copy_listing_retries_stop_at_its_own_cap(self):
        self.choose();self.app.Set(self.app,'marketFlip.custom.maxListAttempts',2)
        raw=self.raw();self.warm(raw);self.app.Step(self.app,raw);self.executor.Drain(self.executor)
        after=self.raw(2,gold=12,loose=2);self.h.at(2);self.app.Step(self.app,after)
        self.warm(after);self.app.Step(self.app,after)
        self.executor.reply=lua_table(self.h.lua,{'ok':False});self.executor.Drain(self.executor)
        after=self.raw(3,gold=12,loose=2);self.h.at(3);self.app.Step(self.app,after);self.executor.Drain(self.executor)
        self.assertEqual(len(self.executor.calls),3,str(dict(self.runtime.Status(self.runtime).reasons.items())))
        after=self.raw(4,gold=12,loose=2);self.h.at(4);self.app.Step(self.app,after);self.executor.Drain(self.executor)
        self.assertEqual(len(self.executor.calls),3)
        self.assertEqual(self.tab.transactions.Active(self.tab.transactions).listAttempts,2)
        self.assertEqual(self.tab.transactions.ListingAttempts(self.tab.transactions,'marketFlip')[0],2)
        self.assertEqual(self.tab.transactions.ListingAttempts(self.tab.transactions)[0],0)
        self.assertEqual(self.tab.transactions.BuyUsage(self.tab.transactions).spent,8)

    def test_corrupt_flip_listing_usage_blocks_store_reload(self):
        self.begin_buy();after=self.raw(2,gold=12,loose=2);self.h.at(2);self.app.Step(self.app,after)
        self.warm(after);self.app.Step(self.app,after);self.executor.Drain(self.executor)
        self.storage.data[self.tab.transactions.key].flipListingAttempts=0
        owner,why=self.tab.NewTransactions(self.tab,self.storage,lua_table(self.h.lua,self.h.session))
        self.assertIsNone(owner);self.assertIn('Corrupt',why)

    def test_native_check_appearing_before_buy_dispatch_is_definitely_unsent(self):
        self.choose();raw=self.raw();self.warm(raw);self.app.Step(self.app,raw)
        self.deps['marketPresence'].allowed=False;self.executor.Drain(self.executor)
        self.assertEqual(len(self.executor.calls),0)
        self.assertIsNone(self.tab.transactions.Active(self.tab.transactions))
        self.assertEqual(self.tab.transactions.BuyUsage(self.tab.transactions).spent,0)

    def test_observed_purchase_review_expires_and_rechecks_item_custody(self):
        self.begin_buy();self.app.Set(self.app,'marketFlip.enabled',False)
        after=self.raw(2,gold=12,loose=2);self.h.at(2);self.app.Step(self.app,after);self.app.Pause(self.app)
        self.assertIsNotNone(self.app.PreviewFeatureRecovery(self.app,'marketFlip')[0])
        after=self.raw(33,gold=12,loose=2);self.h.at(33);self.app.Step(self.app,after)
        self.assertFalse(self.app.ConfirmFeatureRecovery(self.app,'marketFlip')[0])
        self.assertIsNotNone(self.app.PreviewFeatureRecovery(self.app,'marketFlip')[0])
        after=self.raw(34,gold=12,loose=1);self.h.at(34);self.app.Step(self.app,after)
        self.assertFalse(self.app.ConfirmFeatureRecovery(self.app,'marketFlip')[0])
        self.assertIsNotNone(self.tab.transactions.Active(self.tab.transactions))
        self.assertEqual(len(self.executor.calls),1)

    def test_unload_queued_followup_restores_purchase_and_listing_usage_once(self):
        self.begin_buy();after=self.raw(2,gold=12,loose=2);self.h.at(2);self.app.Step(self.app,after)
        self.warm(after);self.app.Step(self.app,after)
        self.app.Destroy(self.app);self.executor.Drain(self.executor);self.restart()
        after=self.raw(0,gold=12,loose=2);after.native.serverNow=1005;self.app.Step(self.app,after)
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.marketFlip,'known_unsent')
        self.assertEqual(self.tab.transactions.Active(self.tab.transactions).kind,'buy')
        self.assertEqual(self.tab.transactions.ListingAttempts(self.tab.transactions,'marketFlip')[0],0)
        self.assertEqual(self.tab.transactions.BuyUsage(self.tab.transactions).spent,8)
        self.assertEqual(len(self.executor.calls),1)

    def test_rejected_followup_checkpoint_failure_recovers_exact_charged_origin(self):
        self.begin_buy();after=self.raw(2,gold=12,loose=2);self.h.at(2);self.app.Step(self.app,after)
        self.warm(after);self.app.Step(self.app,after)
        self.executor.reply=lua_table(self.h.lua,{'ok':False});self.executor.Drain(self.executor)
        self.storage.Write=self.h.lua.eval("function(self,key,value) if key:find(':checkpoint:',1,true) and #value.records==0 then return false end self.data[key]=value return true end")
        after=self.raw(3,gold=12,loose=2);self.h.at(3);self.app.Step(self.app,after)
        self.storage.Write=self.h.lua.eval('function(self,key,value) self.data[key]=value return true end')
        self.restart();after=self.raw(0,gold=12,loose=2);after.native.serverNow=1005;after.capturedAt=3;self.h.at(3)
        self.app.Step(self.app,after)
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.marketFlip,'rejected')
        self.assertEqual(self.tab.transactions.Active(self.tab.transactions).listAttempts,1)
        self.assertEqual(self.tab.transactions.ListingAttempts(self.tab.transactions,'marketFlip')[0],1)
        self.assertEqual(self.tab.transactions.BuyUsage(self.tab.transactions).spent,8)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),0)
        self.assertEqual(len(self.executor.calls),2)
