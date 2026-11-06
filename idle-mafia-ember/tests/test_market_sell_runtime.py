"""Real MarketSell tab/App/broker/store/native adapter; no live client."""
import unittest
from engine_harness import lua_table
from test_market_payout_runtime import MarketPayoutRuntimeFixture

class MarketSellRuntimeTests(MarketPayoutRuntimeFixture, unittest.TestCase):
    feature_id = "marketSell"

    def start(self):
        self.deps.update(clock=self.h.clock, gameData={"ITEMS_BY_ID": {
            "w_baton": {"id":"w_baton","kind":"weapon","rarity":5,"tradable":True,"atk":1,"def":1}}},
            marketPresence=self.h.lua.execute("local gate={allowed=true}; gate.check=function() return gate.allowed end; gate.handle=function() return true end; return gate"))
        self.deps["NativeCollectionCatalog"]=self.h.load('src/tabs/collection/NativeCollectionCatalog.luau')
        self.deps['config']['COLLECTION']={'bonusByRarity':[1,2,3,4,5],
            'tiers':[{'count':count,'mult':i+1} for i,count in enumerate((1,10,100,1000,5000))]}
        super().start()

    def raw(self, revision=1, loose=2, listed=False, collected=0):
        listing = {"L1":{"state":"live","item":"w_baton","indexed":1,"price":14,
            "qty":1,"left":1,"createdAt":1002,"itemOrigin":{"total":1,"free":0}}} if listed else {}
        return self.h.snapshot(revision=revision, captured_at=revision, native={
            "fullSync":True,"serverNow":1000+revision,"market":{"extraSlots":0,"shopUntil":2000,"listings":listing},
            "inventory":{"w_baton":loose},"inventoryBound":{},"collection":{"w_baton":collected},"collectionBound":{},
            "crew":[{}],"derived":{"marketShop":False}})

    def choose(self):
        for key,value in {"enabled":True,"custom.scope":"Selected item","custom.selectedItemId":"w_baton",
            "custom.maxListings":1,"custom.maxListAttempts":1,"custom.keepLoose":1,"custom.maxQuantity":1,
            "custom.minNet":1,"custom.likelyOnly":False,"custom.undercutGold":0,"custom.floorPct":90}.items():
            self.assertTrue(self.app.Set(self.app,"marketSell."+key,value)[0])
        self.app.Resume(self.app)

    def warm(self, raw, metadata=None):
        self.h.at(raw.capturedAt)
        custom = {key.removeprefix("marketSell.custom."):value for key,value in self.app.model["values"].items()
            if key.startswith("marketSell.custom.")}
        settings = lua_table(self.h.lua,{"marketSell":{"enabled":True,"custom":custom},"marketWatch":{"enabled":False}})
        for source in self.tab.ReadSources(self.tab).values():
            if not source.id.startswith("marketSell") or not source.enabled(settings): continue
            request = source.prepare(raw)
            if source.id.endswith("Browse"):
                reply={"ok":True,"pages":1,"more":False,"rows":[{"id":"other","item":"w_baton","qty":1,"price":14,"mine":False}]}
                reply.update(metadata or {})
            elif source.id.endswith("Rap"):
                reply={"ok":True,"values":{"w_baton":{"sales":15,"quantity":30,"average":14,"available":True}}}
            else: reply={"ok":True,"item":"w_baton","recent":[{"price":14},{"price":15},{"price":16}],"days":[]}
            staged = source.accept(raw,request,lua_table(self.h.lua,reply))
            if isinstance(staged,tuple): staged=staged[0]
            self.assertIsNotNone(staged)
            self.assertTrue(source.commit(staged))

    def test_actual_app_lists_only_after_opt_in_and_confirms_exact_effect(self):
        raw=self.raw()
        self.h.at(1)
        self.app.Step(self.app,raw)
        self.assertEqual(len(self.executor.calls),0)
        self.choose(); self.warm(raw)
        self.assertTrue(self.app.Step(self.app,raw)[0])
        self.executor.Drain(self.executor)
        self.assertEqual(len(self.executor.calls),1)
        call=self.executor.calls[1]
        self.assertEqual(call.remote,"MarketAction")
        self.assertEqual([call.args[i] for i in range(1,5)],["list","w_baton",1,14])
        after=self.raw(2,1,True);self.h.at(2);self.app.Step(self.app,after)
        self.assertEqual(self.runtime.Status(self.runtime).outcomes.marketSell,"confirmed")
        self.assertIsNone(self.tab.transactions.Active(self.tab.transactions))
        self.assertEqual(self.tab.transactions.ListingAttempts(self.tab.transactions)[0],1)

    def test_opted_in_collection_withdrawal_then_exact_listing_preserves_checkpoint(self):
        self.choose()
        for key,value in {'fromCollection':True,'maxWithdraw':1,'maxWithdrawAttempts':1}.items():
            self.assertTrue(self.app.Set(self.app,'marketSell.custom.'+key,value)[0])
        raw=self.raw(loose=1,collected=2);self.warm(raw);self.app.Step(self.app,raw)
        self.executor.reply=lua_table(self.h.lua,{'ok':True,'moved':1});self.executor.Drain(self.executor)
        self.assertEqual(len(self.executor.calls),1)
        first=self.executor.calls[1]
        self.assertEqual(first.remote,'CollectionAction')
        self.assertEqual([first.args[i] for i in range(1,4)],['withdraw','w_baton',1])
        after=self.raw(2,loose=2,collected=1);self.h.at(2);self.app.Step(self.app,after)
        self.executor.reply=lua_table(self.h.lua,{'ok':True});self.executor.Drain(self.executor)
        self.assertEqual(len(self.executor.calls),2,str(dict(self.runtime.Status(self.runtime).reasons.items()))+str(dict(self.runtime.session.Status(self.runtime.session).items())))
        second=self.executor.calls[2]
        self.assertEqual(second.remote,'MarketAction')
        self.assertEqual([second.args[i] for i in range(1,5)],['list','w_baton',1,14])
        after=self.raw(3,loose=1,collected=1,listed=True);self.h.at(3);self.app.Step(self.app,after)
        self.assertEqual(self.runtime.Status(self.runtime).outcomes.marketSell,'confirmed')
        self.assertIsNone(self.tab.transactions.Active(self.tab.transactions))
        self.assertEqual(self.tab.transactions.ListingAttempts(self.tab.transactions)[0],1)
        self.assertEqual(self.tab.transactions.WithdrawAttempts(self.tab.transactions)[0],1)
        self.assertEqual(after.native.collection.w_baton,1)

    def withdraw(self, reply=None):
        self.choose()
        for key,value in {'fromCollection':True,'maxWithdraw':1,'maxWithdrawAttempts':1}.items():
            self.app.Set(self.app,'marketSell.custom.'+key,value)
        raw=self.raw(loose=1,collected=2);self.warm(raw);self.app.Step(self.app,raw)
        self.executor.reply=lua_table(self.h.lua,reply or {'ok':True,'moved':1})
        self.executor.Drain(self.executor)

    def test_restart_recovers_exact_withdrawal_and_keeps_continuation_owned(self):
        self.withdraw();self.restart()
        after=self.raw(0,loose=2,collected=1);after.native.serverNow=1005
        self.app.Step(self.app,after)
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.marketSell,'confirmed')
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),0)
        self.assertEqual(self.tab.transactions.Active(self.tab.transactions).stage,'observed')
        self.assertEqual(self.tab.transactions.WithdrawAttempts(self.tab.transactions)[0],1)
        self.assertEqual(len(self.executor.calls),1)
        self.assertFalse(self.app.model['values']['marketSell.enabled'])

    def test_withdrawal_unknown_wrong_effect_and_pending_replies_stay_held_on_restart(self):
        self.withdraw({'ok':True,'pending':True,'moved':1});self.restart()
        after=self.raw(0,loose=2,collected=1);after.native.serverNow=1005
        self.app.Step(self.app,after)
        self.assertIsNone(self.runtime.Status(self.runtime).recoveries.marketSell)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),1)
        self.assertIsNotNone(self.tab.transactions.Active(self.tab.transactions))
        self.assertEqual(len(self.executor.calls),1)

    def test_withdrawal_bound_change_cannot_confirm_saved_transfer(self):
        self.withdraw();self.restart()
        after=self.raw(0,loose=2,collected=1);after.native.serverNow=1005
        after.native.inventoryBound.w_baton=1
        self.app.Step(self.app,after)
        self.assertIsNone(self.runtime.Status(self.runtime).recoveries.marketSell)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),1)
        self.assertEqual(len(self.executor.calls),1)

    def test_exact_rejected_withdrawal_recovers_without_refunding_attempt(self):
        self.withdraw({'ok':False});self.restart()
        after=self.raw(0,loose=1,collected=2);after.native.serverNow=1005
        self.app.Step(self.app,after)
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.marketSell,'rejected')
        self.assertIsNone(self.tab.transactions.Active(self.tab.transactions))
        self.assertEqual(self.tab.transactions.WithdrawAttempts(self.tab.transactions)[0],1)
        self.assertEqual(self.tab.transactions.ListingAttempts(self.tab.transactions)[0],0)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),0)
        self.assertEqual(len(self.executor.calls),1)

    def test_disable_queued_withdrawal_refunds_only_unsent_withdrawal(self):
        self.choose()
        for key,value in {'fromCollection':True,'maxWithdraw':1,'maxWithdrawAttempts':1}.items():
            self.app.Set(self.app,'marketSell.custom.'+key,value)
        raw=self.raw(loose=1,collected=2);self.warm(raw);self.app.Step(self.app,raw)
        self.app.Set(self.app,'marketSell.enabled',False);self.executor.Drain(self.executor)
        self.assertEqual(len(self.executor.calls),0)
        self.assertIsNone(self.tab.transactions.Active(self.tab.transactions))
        self.assertEqual(self.tab.transactions.WithdrawAttempts(self.tab.transactions)[0],0)
        self.assertEqual(self.tab.transactions.ListingAttempts(self.tab.transactions)[0],0)

    def test_unload_before_withdrawal_dispatch_recovers_exact_unsent_fact(self):
        self.choose()
        for key,value in {'fromCollection':True,'maxWithdraw':1,'maxWithdrawAttempts':1}.items():
            self.app.Set(self.app,'marketSell.custom.'+key,value)
        raw=self.raw(loose=1,collected=2);self.warm(raw);self.app.Step(self.app,raw)
        self.app.Destroy(self.app);self.executor.Drain(self.executor);self.restart()
        after=self.raw(0,loose=1,collected=2);after.native.serverNow=1005
        self.app.Step(self.app,after)
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.marketSell,'known_unsent')
        self.assertIsNone(self.tab.transactions.Active(self.tab.transactions))
        self.assertEqual(self.tab.transactions.WithdrawAttempts(self.tab.transactions)[0],0)
        self.assertEqual(len(self.executor.calls),0)

    def test_changed_collection_after_rejection_remains_uncertain(self):
        self.withdraw({'ok':False});self.restart()
        after=self.raw(0,loose=1,collected=1);after.native.serverNow=1005
        self.app.Step(self.app,after)
        self.assertIsNone(self.runtime.Status(self.runtime).recoveries.marketSell)
        self.assertIsNotNone(self.tab.transactions.Active(self.tab.transactions))
        self.assertEqual(self.tab.transactions.WithdrawAttempts(self.tab.transactions)[0],1)
        self.assertEqual(len(self.executor.calls),1)

    def test_disable_queued_followup_keeps_withdrawn_item_custody(self):
        self.withdraw()
        after=self.raw(2,loose=2,collected=1);self.h.at(2);self.app.Step(self.app,after)
        self.app.Set(self.app,'marketSell.enabled',False);self.executor.Drain(self.executor)
        active=self.tab.transactions.Active(self.tab.transactions)
        self.assertIsNotNone(active)
        self.assertEqual(active.kind,'withdraw');self.assertEqual(active.stage,'observed')
        self.assertEqual(self.tab.transactions.ListingAttempts(self.tab.transactions)[0],0)
        self.assertEqual(self.tab.transactions.WithdrawAttempts(self.tab.transactions)[0],1)
        self.assertEqual(len(self.executor.calls),1)

    def test_prepared_withdrawal_can_be_reviewed_paused_without_game_call(self):
        self.choose()
        for key,value in {'fromCollection':True,'maxWithdraw':1,'maxWithdrawAttempts':1}.items():
            self.app.Set(self.app,'marketSell.custom.'+key,value)
        raw=self.raw(loose=1,collected=2);self.warm(raw);self.app.Step(self.app,raw)
        self.restart();after=self.raw(0,loose=1,collected=2);after.native.serverNow=1005
        self.app.Step(self.app,after);self.app.Pause(self.app)
        preview,why=self.app.PreviewFeatureRecovery(self.app,'marketSell')
        self.assertIsNotNone(preview,why)
        self.assertTrue(self.app.ConfirmFeatureRecovery(self.app,'marketSell')[0])
        self.assertIsNone(self.tab.transactions.Active(self.tab.transactions))
        self.assertEqual(self.tab.transactions.WithdrawAttempts(self.tab.transactions)[0],0)
        self.executor.Drain(self.executor)
        self.assertEqual(len(self.executor.calls),0)

    def test_withdrawal_attempt_cap_blocks_second_transfer_after_rejection(self):
        self.withdraw({'ok':False})
        after=self.raw(2,loose=1,collected=2);self.h.at(2);self.app.Step(self.app,after)
        self.assertIsNone(self.tab.transactions.Active(self.tab.transactions))
        self.app.Step(self.app,after);self.executor.Drain(self.executor)
        self.assertEqual(len(self.executor.calls),1)
        self.assertEqual(self.tab.transactions.WithdrawAttempts(self.tab.transactions)[0],1)
        self.assertEqual(self.tab.transactions.ListingAttempts(self.tab.transactions)[0],0)

    def test_failed_withdrawal_observation_write_recovers_on_restart(self):
        self.withdraw()
        self.storage.Write=self.h.lua.eval("function(self,key,value) if value.transaction and value.transaction.stage=='observed' then return false end self.data[key]=value return true end")
        after=self.raw(2,loose=2,collected=1);self.h.at(2);self.app.Step(self.app,after)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),1)
        self.storage.Write=self.h.lua.eval('function(self,key,value) self.data[key]=value return true end')
        self.restart();after=self.raw(0,loose=2,collected=1);after.native.serverNow=1005
        self.app.Step(self.app,after)
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.marketSell,'confirmed')
        self.assertEqual(self.tab.transactions.Active(self.tab.transactions).stage,'observed')
        self.assertEqual(len(self.executor.calls),1)

    def test_followup_restart_confirms_listing_and_preserves_separate_caps(self):
        self.withdraw()
        after=self.raw(2,loose=2,collected=1);self.h.at(2);self.app.Step(self.app,after)
        self.executor.reply=lua_table(self.h.lua,{'ok':True});self.executor.Drain(self.executor)
        self.restart();after=self.raw(0,loose=1,collected=1,listed=True);after.native.serverNow=1005
        self.app.Step(self.app,after)
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.marketSell,'confirmed')
        self.assertIsNone(self.tab.transactions.Active(self.tab.transactions))
        self.assertEqual(self.tab.transactions.WithdrawAttempts(self.tab.transactions)[0],1)
        self.assertEqual(self.tab.transactions.ListingAttempts(self.tab.transactions)[0],1)
        self.assertEqual(len(self.executor.calls),2)

    def test_wrong_withdrawal_reply_quantity_cannot_confirm_exact_transfer(self):
        self.withdraw({'ok':True,'moved':2});self.restart()
        after=self.raw(0,loose=2,collected=1);after.native.serverNow=1005
        self.app.Step(self.app,after)
        self.assertIsNone(self.runtime.Status(self.runtime).recoveries.marketSell)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),1)
        self.assertEqual(len(self.executor.calls),1)

    def test_followup_rejection_retains_owned_items_and_exhausted_listing_cap(self):
        self.withdraw()
        after=self.raw(2,loose=2,collected=1);self.h.at(2);self.app.Step(self.app,after)
        self.executor.reply=lua_table(self.h.lua,{'ok':False});self.executor.Drain(self.executor)
        after=self.raw(3,loose=2,collected=1);self.h.at(3);self.app.Step(self.app,after)
        active=self.tab.transactions.Active(self.tab.transactions)
        self.assertIsNotNone(active);self.assertEqual(active.kind,'withdraw')
        self.assertEqual(self.tab.transactions.ListingAttempts(self.tab.transactions)[0],1)
        self.assertEqual(self.tab.transactions.WithdrawAttempts(self.tab.transactions)[0],1)
        self.app.Step(self.app,after);self.executor.Drain(self.executor)
        self.assertEqual(len(self.executor.calls),2)

    def test_rejected_followup_checkpoint_failure_recovers_without_losing_withdrawal(self):
        self.withdraw()
        after=self.raw(2,loose=2,collected=1);self.h.at(2);self.app.Step(self.app,after)
        self.executor.reply=lua_table(self.h.lua,{'ok':False});self.executor.Drain(self.executor)
        self.storage.Write=self.h.lua.eval("function(self,key,value) if key:find(':checkpoint:',1,true) and #value.records==0 then return false end self.data[key]=value return true end")
        after=self.raw(3,loose=2,collected=1);self.h.at(3);self.app.Step(self.app,after)
        self.storage.Write=self.h.lua.eval('function(self,key,value) self.data[key]=value return true end')
        self.restart();after=self.raw(0,loose=2,collected=1);after.native.serverNow=1005
        after.capturedAt=3;self.h.at(3)
        self.app.Step(self.app,after)
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.marketSell,'rejected')
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),0)
        self.assertEqual(self.tab.transactions.Active(self.tab.transactions).kind,'withdraw')
        self.assertEqual(self.tab.transactions.ListingAttempts(self.tab.transactions)[0],1)
        self.assertEqual(len(self.executor.calls),2)

    def test_observed_withdrawal_paused_review_releases_only_local_hold(self):
        self.withdraw();self.app.Set(self.app,'marketSell.enabled',False)
        after=self.raw(2,loose=2,collected=1);self.h.at(2);self.app.Step(self.app,after)
        self.app.Pause(self.app)
        preview,why=self.app.PreviewFeatureRecovery(self.app,'marketSell')
        self.assertIsNotNone(preview,why);self.assertEqual(preview.kind,'observed')
        self.assertTrue(self.app.ConfirmFeatureRecovery(self.app,'marketSell')[0])
        self.assertIsNone(self.tab.transactions.Active(self.tab.transactions))
        self.assertEqual(self.tab.transactions.WithdrawAttempts(self.tab.transactions)[0],1)
        self.assertEqual(self.tab.transactions.ListingAttempts(self.tab.transactions)[0],0)
        self.assertEqual(after.native.inventory.w_baton,2)
        self.assertEqual(after.native.collection.w_baton,1)
        self.assertEqual(len(self.executor.calls),1)

    def test_observed_review_rechecks_inventory_before_releasing_hold(self):
        self.withdraw();self.app.Set(self.app,'marketSell.enabled',False)
        after=self.raw(2,loose=2,collected=1);self.h.at(2);self.app.Step(self.app,after);self.app.Pause(self.app)
        self.assertIsNotNone(self.app.PreviewFeatureRecovery(self.app,'marketSell')[0])
        after=self.raw(3,loose=1,collected=1);self.h.at(3);self.app.Step(self.app,after)
        self.assertFalse(self.app.ConfirmFeatureRecovery(self.app,'marketSell')[0])
        self.assertIsNotNone(self.tab.transactions.Active(self.tab.transactions))
        self.assertEqual(len(self.executor.calls),1)

    def test_unsent_followup_checkpoint_failure_restores_origin_once_on_restart(self):
        self.withdraw()
        after=self.raw(2,loose=2,collected=1);self.h.at(2);self.app.Step(self.app,after)
        self.storage.Write=self.h.lua.eval("function(self,key,value) if key:find(':checkpoint:',1,true) and #value.records==0 then return false end self.data[key]=value return true end")
        self.app.Set(self.app,'marketSell.enabled',False);self.executor.Drain(self.executor)
        self.storage.Write=self.h.lua.eval('function(self,key,value) self.data[key]=value return true end')
        self.restart();after=self.raw(0,loose=2,collected=1);after.native.serverNow=1005
        self.app.Step(self.app,after)
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.marketSell,'known_unsent')
        self.assertEqual(self.tab.transactions.Active(self.tab.transactions).kind,'withdraw')
        self.assertEqual(self.tab.transactions.WithdrawAttempts(self.tab.transactions)[0],1)
        self.assertEqual(self.tab.transactions.ListingAttempts(self.tab.transactions)[0],0)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),0)
        self.assertEqual(len(self.executor.calls),1)

    def rejected_followup_interruption(self):
        self.withdraw()
        after=self.raw(2,loose=2,collected=1);self.h.at(2);self.app.Step(self.app,after)
        self.executor.reply=lua_table(self.h.lua,{'ok':False});self.executor.Drain(self.executor)
        self.storage.Write=self.h.lua.eval("function(self,key,value) if key:find(':checkpoint:',1,true) and #value.records==0 then return false end self.data[key]=value return true end")
        after=self.raw(3,loose=2,collected=1);self.h.at(3);self.app.Step(self.app,after)
        self.storage.Write=self.h.lua.eval('function(self,key,value) self.data[key]=value return true end')
        return next(v for k,v in self.storage.data.items() if ':rejected:' in k)

    def test_tampered_receipt_baseline_cannot_confirm_different_inventory(self):
        receipt=self.rejected_followup_interruption();receipt.transaction.loose=3
        self.restart();after=self.raw(0,loose=3,collected=1);after.native.serverNow=1005
        after.capturedAt=3;self.h.at(3);self.app.Step(self.app,after)
        self.assertIsNone(self.runtime.Status(self.runtime).recoveries.marketSell)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),1)
        self.assertEqual(self.tab.transactions.Active(self.tab.transactions).kind,'withdraw')
        self.assertEqual(len(self.executor.calls),2)

    def test_stale_receipt_generation_cannot_clear_checkpoint(self):
        receipt=self.rejected_followup_interruption();receipt.generation-=1
        self.restart();after=self.raw(0,loose=2,collected=1);after.native.serverNow=1005
        after.capturedAt=3;self.h.at(3);self.app.Step(self.app,after)
        self.assertIsNone(self.runtime.Status(self.runtime).recoveries.marketSell)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),1)
        self.assertEqual(len(self.executor.calls),2)

    def test_changed_keep_limit_blocks_queued_followup_and_keeps_owned_items(self):
        self.withdraw()
        after=self.raw(2,loose=2,collected=1);self.h.at(2);self.app.Step(self.app,after)
        self.app.Set(self.app,'marketSell.custom.keepLoose',2);self.executor.Drain(self.executor)
        self.assertEqual(len(self.executor.calls),1)
        self.assertEqual(self.tab.transactions.Active(self.tab.transactions).kind,'withdraw')
        self.assertEqual(self.tab.transactions.ListingAttempts(self.tab.transactions)[0],0)
        self.assertEqual(self.tab.transactions.WithdrawAttempts(self.tab.transactions)[0],1)

    def test_observed_release_ticket_expires_without_resetting_usage(self):
        self.withdraw();self.app.Set(self.app,'marketSell.enabled',False)
        after=self.raw(2,loose=2,collected=1);self.h.at(2);self.app.Step(self.app,after);self.app.Pause(self.app)
        self.assertIsNotNone(self.app.PreviewFeatureRecovery(self.app,'marketSell')[0])
        after=self.raw(33,loose=2,collected=1);self.h.at(33);self.app.Step(self.app,after)
        self.assertFalse(self.app.ConfirmFeatureRecovery(self.app,'marketSell')[0])
        self.assertIsNotNone(self.tab.transactions.Active(self.tab.transactions))
        self.assertEqual(self.tab.transactions.WithdrawAttempts(self.tab.transactions)[0],1)
        self.assertEqual(len(self.executor.calls),1)

    def test_expired_listing_window_still_allows_exact_paused_local_release(self):
        self.withdraw();self.app.Set(self.app,'marketSell.enabled',False)
        after=self.raw(2,loose=2,collected=1);self.h.at(2);self.app.Step(self.app,after);self.app.Pause(self.app)
        after=self.raw(3605,loose=2,collected=1);self.h.at(3605);self.app.Step(self.app,after)
        preview,why=self.app.PreviewFeatureRecovery(self.app,'marketSell')
        self.assertIsNotNone(preview,why)
        self.assertTrue(self.app.ConfirmFeatureRecovery(self.app,'marketSell')[0])
        self.assertIsNone(self.tab.transactions.Active(self.tab.transactions))
        self.assertEqual(self.tab.transactions.WithdrawAttempts(self.tab.transactions)[0],1)
        self.assertEqual(len(self.executor.calls),1)

    def test_disable_queued_listing_is_unsent_and_does_not_spend_allowance(self):
        raw=self.raw();self.choose();self.warm(raw);self.app.Step(self.app,raw)
        self.app.Set(self.app,"marketSell.enabled",False)
        self.executor.Drain(self.executor)
        self.assertEqual(len(self.executor.calls),0)
        self.assertIsNone(self.tab.transactions.Active(self.tab.transactions))
        self.assertEqual(self.tab.transactions.ListingAttempts(self.tab.transactions)[0],0)

    def test_native_presence_reply_without_ok_is_saved_and_never_confirms(self):
        self.executor.reply=lua_table(self.h.lua,{"code":"presence","presence":{"id":"native-check"}})
        self.deps["marketPresence"].handle=self.h.lua.eval("function(reply) seenPresence=reply.code; return false end")
        raw=self.raw();self.choose();self.warm(raw);self.app.Step(self.app,raw)
        self.executor.Drain(self.executor)
        after=self.raw(2);self.h.at(2);self.app.Step(self.app,after)
        self.assertIsNone(self.runtime.session.storageFault)
        self.assertEqual(self.h.lua.globals().seenPresence,"presence")
        self.assertEqual(self.tab.transactions.Active(self.tab.transactions).reply.code,"presence")
        self.assertEqual(self.tab.transactions.ListingAttempts(self.tab.transactions)[0],1)
        self.assertIsNone(self.runtime.Status(self.runtime).outcomes.marketSell)
        self.assertEqual(len(self.executor.calls),1)

    def test_all_off_restart_observes_saved_exact_listing_without_replay(self):
        raw=self.raw();self.choose();self.warm(raw);self.app.Step(self.app,raw)
        self.executor.Drain(self.executor)
        self.restart()
        after=self.raw(0,1,True);after.native.serverNow=1005;self.h.at(0)
        self.app.Step(self.app,after)
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.marketSell,"confirmed")
        self.assertEqual(len(self.executor.calls),1)
        self.assertIsNone(self.tab.transactions.Active(self.tab.transactions))
        self.assertEqual(self.tab.transactions.ListingAttempts(self.tab.transactions)[0],1)

    def test_saved_negative_reply_reconciles_on_fresh_session_without_replay(self):
        self.executor.reply=lua_table(self.h.lua,{'ok':False})
        raw=self.raw();self.choose();self.warm(raw);self.app.Step(self.app,raw);self.executor.Drain(self.executor)
        self.restart();after=self.raw(0);after.native.serverNow=1005;self.h.at(0);self.app.Step(self.app,after)
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.marketSell,'rejected')
        self.assertIsNone(self.tab.transactions.Active(self.tab.transactions))
        self.assertEqual(self.tab.transactions.ListingAttempts(self.tab.transactions)[0],1)
        self.assertEqual(len(self.executor.calls),1)

    def test_unknown_reply_keeps_owned_copy_and_attempt_across_restart(self):
        self.executor.reply=lua_table(self.h.lua,{"ok":True,"pending":True})
        raw=self.raw();self.choose();self.warm(raw);self.app.Step(self.app,raw)
        self.executor.Drain(self.executor)
        self.restart()
        after=self.raw(0,1,True);after.native.serverNow=1005;self.h.at(0)
        self.app.Step(self.app,after)
        self.assertIsNotNone(self.tab.transactions.Active(self.tab.transactions))
        self.assertEqual(self.tab.transactions.ListingAttempts(self.tab.transactions)[0],1)
        self.assertEqual(len(self.executor.calls),1)

    def test_old_queued_callback_records_unsent_fact_for_new_owner_only(self):
        raw=self.raw();self.choose();self.warm(raw);self.app.Step(self.app,raw)
        self.restart()
        self.executor.Drain(self.executor)
        after=self.raw(0);after.native.serverNow=1005;self.h.at(0)
        self.app.Step(self.app,after)
        self.assertEqual(len(self.executor.calls),0)
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.marketSell,"known_unsent")
        self.assertIsNone(self.tab.transactions.Active(self.tab.transactions))
        self.assertEqual(self.tab.transactions.ListingAttempts(self.tab.transactions)[0],0)

    def test_unsent_store_cleanup_recovers_after_generic_checkpoint_clear_failure(self):
        raw=self.raw();self.choose();self.warm(raw);self.app.Step(self.app,raw)
        self.storage.Write=self.h.lua.eval("""function(self,key,value)
            if key:find(':checkpoint:',1,true) and #value.records==0 then return false end
            self.data[key]=value return true end""")
        self.app.Set(self.app,'marketSell.enabled',False);self.executor.Drain(self.executor)
        self.assertIsNone(self.tab.transactions.Active(self.tab.transactions))
        self.storage.Write=self.h.lua.eval('function(self,key,value) self.data[key]=value return true end')
        self.restart();after=self.raw(0);after.native.serverNow=1005;self.h.at(0);self.app.Step(self.app,after)
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.marketSell,'known_unsent')
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),0)
        self.assertEqual(self.tab.transactions.ListingAttempts(self.tab.transactions)[0],0)
        self.assertEqual(len(self.executor.calls),0)

    def test_rejected_store_cleanup_recovers_after_generic_checkpoint_clear_failure(self):
        self.executor.reply=lua_table(self.h.lua,{'ok':False})
        raw=self.raw();self.choose();self.warm(raw);self.app.Step(self.app,raw);self.executor.Drain(self.executor)
        self.storage.Write=self.h.lua.eval("""function(self,key,value)
            if key:find(':checkpoint:',1,true) and #value.records==0 then return false end
            self.data[key]=value return true end""")
        after=self.raw(2);self.h.at(2);self.app.Step(self.app,after)
        self.assertIsNone(self.tab.transactions.Active(self.tab.transactions))
        self.storage.Write=self.h.lua.eval('function(self,key,value) self.data[key]=value return true end')
        self.restart();after=self.raw(0);after.native.serverNow=1005;self.h.at(0);self.app.Step(self.app,after)
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.marketSell,'rejected')
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),0)
        self.assertEqual(self.tab.transactions.ListingAttempts(self.tab.transactions)[0],1)
        self.assertEqual(len(self.executor.calls),1)

    def prepare_saved_listing_review(self):
        raw=self.raw();self.choose();self.warm(raw);self.app.Step(self.app,raw)
        self.restart()
        current=self.raw(0);current.native.serverNow=1005;self.h.at(0);self.app.Step(self.app,current)
        return current

    def test_paused_review_discards_prepared_listing_without_call_or_budget_reset(self):
        self.prepare_saved_listing_review()
        self.assertIsNone(self.app.PreviewFeatureRecovery(self.app,'marketSell')[0])
        self.app.Pause(self.app)
        preview,why=self.app.PreviewFeatureRecovery(self.app,'marketSell')
        self.assertIsNone(why)
        self.assertEqual(preview.kind,'prepared')
        self.assertTrue(self.app.ConfirmFeatureRecovery(self.app,'marketSell')[0])
        self.assertFalse(self.app.ConfirmFeatureRecovery(self.app,'marketSell')[0])
        self.assertIsNone(self.tab.transactions.Active(self.tab.transactions))
        self.assertEqual(self.tab.transactions.ListingAttempts(self.tab.transactions)[0],0)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),0)
        self.executor.Drain(self.executor)
        self.assertEqual(len(self.executor.calls),0)
        self.assertTrue(self.app.model.paused)

    def test_prepared_review_ticket_expires_and_requires_a_fresh_review(self):
        self.prepare_saved_listing_review();self.app.Pause(self.app)
        self.assertIsNotNone(self.app.PreviewFeatureRecovery(self.app,'marketSell')[0])
        current=self.raw(32);current.native.serverNow=1032;self.h.at(32);self.app.Step(self.app,current)
        self.assertFalse(self.app.ConfirmFeatureRecovery(self.app,'marketSell')[0])
        self.assertIsNotNone(self.tab.transactions.Active(self.tab.transactions))
        self.assertIsNotNone(self.app.PreviewFeatureRecovery(self.app,'marketSell')[0])
        self.assertTrue(self.app.ConfirmFeatureRecovery(self.app,'marketSell')[0])
        self.assertEqual(len(self.executor.calls),0)

    def test_recovery_buttons_ignore_restore_events_and_require_user_review(self):
        self.prepare_saved_listing_review();self.app.Pause(self.app)
        row=self.app.ui.features.marketSell
        self.assertIsNotNone(row.recoveryReview)
        row.recoveryReview.options.Callback(None,None,lua_table(self.h.lua,{'initial':True}))
        row.recoveryConfirm.options.Callback(None,None,None)
        self.assertIsNotNone(self.tab.transactions.Active(self.tab.transactions))
        row.recoveryReview.options.Callback(None,None,None)
        self.assertIn('w_baton',row.recoveryStatus.value)
        row.recoveryConfirm.options.Callback(None,None,lua_table(self.h.lua,{'restored':True}))
        self.assertIsNotNone(self.tab.transactions.Active(self.tab.transactions))
        row.recoveryConfirm.options.Callback(None,None,None)
        self.assertIsNone(self.tab.transactions.Active(self.tab.transactions))
        self.assertTrue(self.app.model.paused)
        self.assertEqual(len(self.executor.calls),0)

    def test_recovery_requires_a_finite_fresh_snapshot(self):
        self.prepare_saved_listing_review();self.app.Pause(self.app)
        current=self.raw(0);current.capturedAt=float('nan')
        self.app.Step(self.app,current)
        self.assertIsNone(self.app.PreviewFeatureRecovery(self.app,'marketSell')[0])
        self.assertIsNotNone(self.tab.transactions.Active(self.tab.transactions))
        self.assertEqual(len(self.executor.calls),0)

    def test_recovery_rechecks_freshness_after_delayed_storage_read(self):
        self.prepare_saved_listing_review();self.app.Pause(self.app)
        self.storage.Read=self.h.lua.eval("""function(self,key)
            if key:find(':unsent:',1,true) then testNow=4 end
            return self.data[key] end""")
        self.assertIsNone(self.app.PreviewFeatureRecovery(self.app,'marketSell')[0])
        self.assertIsNotNone(self.tab.transactions.Active(self.tab.transactions))
        self.assertEqual(len(self.executor.calls),0)

    def test_native_check_appearing_before_dispatch_is_known_unsent(self):
        raw=self.raw();self.choose();self.warm(raw);self.app.Step(self.app,raw)
        self.deps["marketPresence"].allowed=False
        self.executor.Drain(self.executor)
        self.assertEqual(len(self.executor.calls),0)
        self.assertIsNone(self.tab.transactions.Active(self.tab.transactions))
        self.assertEqual(self.tab.transactions.ListingAttempts(self.tab.transactions)[0],0)

    def test_disable_during_authorization_write_refunds_definitely_unsent_attempt(self):
        raw=self.raw();self.choose();self.warm(raw);self.app.Step(self.app,raw)
        self.h.lua.globals().listingApp=self.app
        self.storage.Write=self.h.lua.eval("""function(self,key,value)
            self.data[key]=value
            if not self.disabled and value.transaction and value.transaction.stage=='sent' then
                self.disabled=true; listingApp:Set('marketSell.enabled',false)
            end
            return true end""")
        self.executor.Drain(self.executor)
        self.assertEqual(len(self.executor.calls),0)
        self.assertIsNone(self.tab.transactions.Active(self.tab.transactions))
        self.assertEqual(self.tab.transactions.ListingAttempts(self.tab.transactions)[0],0)

if __name__ == "__main__": unittest.main()
