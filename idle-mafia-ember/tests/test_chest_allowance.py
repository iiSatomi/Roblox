"""Owned chest totals through the actual Inventory/App/native adapter path."""
import hashlib
import unittest
import test_automation_runtime as runtime_fixture
from test_inventory_restoratives import ITEMS
from engine_harness import lua_table

class ChestAllowanceTests(unittest.TestCase):
    def setUp(self):
        self.base = runtime_fixture.AutomationRuntimeTests(); self.base.setUp()
        self.base.runtime.Close(self.base.runtime)
        self.h = self.base.h
        self.base.storage.Write = self.h.lua.eval("function(self,k,v) self.data[k]=v return true end")
        self.h.lua.globals().chestHash = lambda value: hashlib.sha256(value.encode()).hexdigest()
        self.base.storage.hash = self.h.lua.eval("function(v) return chestHash(v) end")
        self.modules = self.base.runtime.modules
        names = ('Chests','Restoratives','NativeCrateCatalog','NativeRestorativeCatalog','Cosmetics','CrateLuckProducer')
        for name in names: self.modules[name] = self.h.load('src/tabs/inventory/'+name+'.luau')
        self.modules.crateLuckSource = self.h.load('src/tabs/inventory/NativeCrateLuckSource.luau').new(
            self.h.lua.execute('return {crateLuck=function(native) return native.luckBonus end}'), 'release-a')[0]
        self.build()

    def build(self):
        data={i:{'id':i,'kind':'consumable','restore':{'pool':pool,'percent':pct}} for i,pool,pct in ITEMS}
        data['crate_a']={'id':'crate_a','kind':'crate'}
        deps={name:self.modules[name] for name in ('Chests','Restoratives','NativeCrateCatalog','NativeRestorativeCatalog','Cosmetics')}
        deps.update(gameData={'ITEMS_BY_ID':data},config={'CONSUMABLES':{'cooldownSeconds':3},'CRATE_BATCH_MAX':10},fingerprint='a'*64,release='release-a')
        tab_module=self.h.load('src/tabs/inventory/Module.luau')
        tab=tab_module.new(lua_table(self.h.lua,deps))
        self.executor=self.base.install_native_adapter()
        plan=self.h.load('src/transport/NativeCallPlan.luau')
        plan=plan.withInventory(plan,self.h.load('src/tabs/inventory/InventoryCallPlan.luau'))
        adapter=self.h.load('src/transport/NativeDispatchAdapter.luau').new(plan,self.executor)
        self.runtime=self.h.load('src/engine/AutomationRuntime.luau').new(lua_table(self.h.lua,{
            'clock':self.h.clock,'transport':adapter,'storage':self.base.storage,'identity':self.h.session,
            'modules':self.modules,'features':tab.Descriptors(tab),'tabInstances':[tab],
            'featurePages':{'chests':'inventory','restoratives':'inventory','cosmetics':'inventory'},
            'snapshotAssembler':self.h.load('src/tabs/TabSnapshotAssembler.luau').new(lua_table(self.h.lua,[tab]))}))
        self.app=self.h.load('src/App.luau').start(lua_table(self.h.lua,{
            'Ember':self.h.load('tests/ember_double.lua')(),'Catalog':self.h.load('src/ui/Catalog.luau'),
            'Settings':self.h.load('src/storage/Settings.luau'),'EmberAdapter':self.h.load('src/ui/EmberAdapter.luau'),
            'InventoryTab':tab_module,'SettingsTab':self.h.load('src/tabs/settings/Module.luau'),
            'automationRuntimeInstance':self.runtime}))

    def tearDown(self): self.app.Destroy(self.app)
    def raw(self,revision=1,crates=10,prizes=0):
        return self.h.snapshot(revision=revision,native={'fullSync':True,'serverNow':1000+revision,
            'inventory':{'crate_a':crates,'prize_a':prizes},'inventoryBound':{'crate_a':2},'luckBonus':0.25})
    def enable(self,limit=3,batch=2):
        for key,value in [('enabled',True),('policy','Largest stack'),('custom.maxBatch',batch),
                ('custom.totalLimitEnabled',True),('custom.totalLimit',limit)]:
            self.assertTrue(self.app.Set(self.app,'chests.'+key,value)[0],key)
        self.app.Resume(self.app)
    def send(self,amount=2,raw=None,reply=None):
        self.app.Step(self.app,raw or self.raw())
        self.executor.reply=lua_table(self.h.lua,reply or {'ok':True,'opened':amount,'itemIds':['prize_a']*amount})
        self.executor.Drain(self.executor)
    def usage(self): return self.runtime.checkpoint.Allowance(self.runtime.checkpoint,'chests')[0]
    def restart(self):
        self.app.Destroy(self.app); self.build()

    def test_actual_app_final_partial_batch_and_persistent_total(self):
        self.enable(); self.send()
        self.assertEqual(self.executor.calls[1].args[3],2)
        self.assertEqual(self.usage().spent,2)
        self.h.at(1); self.send(amount=1,raw=self.raw(2,8,2))
        self.assertEqual(self.executor.calls[2].args[3],1)
        self.h.at(2); self.app.Step(self.app,self.raw(3,7,3))
        self.executor.Drain(self.executor)
        self.assertEqual(len(self.executor.calls),2)
        self.assertEqual(self.usage().spent,3)
        self.restart(); self.enable(); self.app.Step(self.app,self.raw(4,7,3)); self.executor.Drain(self.executor)
        self.assertEqual(len(self.executor.calls),0)
        self.assertEqual(self.usage().spent,3)

    def test_queued_limit_change_is_definitely_unsent_and_refunds(self):
        self.enable(); self.app.Step(self.app,self.raw())
        self.assertEqual(self.usage().spent,2)
        self.app.Set(self.app,'chests.custom.totalLimit',1)
        self.executor.Drain(self.executor)
        self.h.at(1); self.app.Pause(self.app); self.app.Step(self.app,self.raw(2))
        self.assertEqual(len(self.executor.calls),0)
        self.assertEqual(self.usage().spent,0)

    def test_defaults_off_and_unlimited_mode_still_counts_attempted_crates(self):
        self.assertFalse(self.app.model['values']['chests.enabled'])
        self.assertFalse(self.app.model['values']['chests.custom.totalLimitEnabled'])
        self.enable(limit=1)
        self.app.Set(self.app,'chests.custom.totalLimitEnabled',False)
        self.send(); self.assertEqual(self.executor.calls[1].args[3],2)
        self.h.at(1); self.app.Set(self.app,'chests.custom.totalLimitEnabled',True)
        self.app.Step(self.app,self.raw(2,8,2)); self.executor.Drain(self.executor)
        self.assertEqual(len(self.executor.calls),1)
        self.assertEqual(self.usage().spent,2)

    def test_rejection_keeps_charge_and_profile_apply_does_not_clear_it(self):
        self.enable(limit=2); self.send(reply={'ok':False})
        self.h.at(1); self.app.Step(self.app,self.raw(2))
        self.assertEqual(self.runtime.Status(self.runtime).outcomes.chests,'rejected')
        profile=self.app.model.Snapshot(self.app.model)
        self.assertTrue(self.app.ApplyProfile(self.app,profile)[0])
        self.app.Set(self.app,'chests.enabled',False);self.app.Set(self.app,'chests.enabled',True)
        self.app.Resume(self.app);self.h.at(2);self.app.Step(self.app,self.raw(3));self.executor.Drain(self.executor)
        self.assertEqual(len(self.executor.calls),1)
        self.assertEqual(self.usage().spent,2)

    def test_queued_disable_and_batch_change_refund_once(self):
        self.enable();self.app.Step(self.app,self.raw())
        callback=self.executor.queued[1]
        self.app.Set(self.app,'chests.enabled',False);self.executor.Drain(self.executor)
        self.h.at(1);self.app.Step(self.app,self.raw(2));callback()
        self.assertEqual(len(self.executor.calls),0);self.assertEqual(self.usage().spent,0)
        self.app.Set(self.app,'chests.enabled',True);self.h.at(2);self.app.Step(self.app,self.raw(3))
        self.app.Set(self.app,'chests.custom.maxBatch',1);self.executor.Drain(self.executor)
        self.h.at(3);self.app.Pause(self.app);self.app.Step(self.app,self.raw(4))
        self.assertEqual(len(self.executor.calls),0);self.assertEqual(self.usage().spent,0)

    def test_unload_before_dispatch_recovers_definite_unsent_once(self):
        self.enable();self.app.Step(self.app,self.raw());old=self.executor
        self.app.Destroy(self.app);old.Drain(old);self.build()
        self.h.at(1);self.app.Step(self.app,self.raw(2))
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.chests,'known_unsent')
        self.assertEqual(self.usage().spent,0);self.assertEqual(len(old.calls),0)
        self.restart();self.h.at(2);self.app.Step(self.app,self.raw(3));self.assertEqual(self.usage().spent,0)

    def test_skip_retains_exposure_and_pending_custody_blocks_reset(self):
        self.enable(limit=2);self.send(reply={'ok':True,'pending':True})
        self.h.at(45);self.app.Step(self.app,self.raw(2))
        self.assertEqual(self.runtime.Status(self.runtime).outcomes.chests,'skipped_unconfirmed')
        self.assertEqual(self.usage().spent,2);self.app.Pause(self.app)
        self.assertIsNone(self.app.PreviewAllowance(self.app,'chests')[0])
        self.restart();self.h.at(46);self.app.Step(self.app,self.raw(3))
        self.assertEqual(self.usage().spent,2);self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),1)

    def test_explicit_paused_reset_keeps_config_and_requires_preview(self):
        self.enable(limit=2);self.send()
        self.h.at(1);self.app.Step(self.app,self.raw(2,8,2))
        self.assertIsNone(self.app.PreviewAllowance(self.app,'chests')[0])
        self.app.Pause(self.app)
        self.assertFalse(self.app.ConfirmAllowance(self.app,'chests')[0])
        preview,reason=self.app.PreviewAllowance(self.app,'chests');self.assertIsNone(reason)
        self.assertEqual((preview.attempted,preview.spent),(1,2))
        self.assertTrue(self.app.ConfirmAllowance(self.app,'chests')[0])
        self.assertEqual(self.usage().spent,0);self.assertTrue(self.app.model.paused)
        self.assertEqual(self.app.model['values']['chests.custom.totalLimit'],2)
        self.assertFalse(self.app.ConfirmAllowance(self.app,'chests')[0])
        self.assertEqual(len(self.executor.calls),1)

    def test_saved_exact_outcome_recovers_without_replay_and_keeps_charge(self):
        self.enable();self.send();self.restart();self.h.at(1)
        self.app.Step(self.app,self.raw(2,8,2))
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.chests,'confirmed')
        self.assertEqual(self.usage().spent,2);self.assertEqual(len(self.executor.calls),0)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),0)

    def test_saved_rejection_keeps_charge(self):
        self.enable();self.send(reply={'ok':False});self.restart();self.h.at(1)
        self.app.Step(self.app,self.raw(2))
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.chests,'rejected')
        self.assertEqual(self.usage().spent,2)

    def test_negative_reply_with_changed_inventory_keeps_custody_after_timeout_and_restart(self):
        self.enable(limit=2);self.send(reply={'ok':False});self.app.Pause(self.app)
        self.h.at(1);self.app.Step(self.app,self.raw(2,8,2))
        self.assertIsNone(self.runtime.Status(self.runtime).outcomes.chests)
        self.h.at(46);self.app.Step(self.app,self.raw(3,8,2))
        records=self.runtime.checkpoint.Records(self.runtime.checkpoint)
        self.assertEqual(len(records),1)
        self.assertEqual(records[1].custody['items']['L:crate_a'],2)
        self.assertEqual(self.usage().spent,2)
        self.assertEqual(len(self.executor.calls),1)
        self.restart();self.enable(limit=2);self.h.at(47)
        self.app.Step(self.app,self.raw(4,8,2));self.executor.Drain(self.executor)
        self.assertIsNone(self.runtime.Status(self.runtime).recoveries.chests)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),1)
        self.assertEqual(self.usage().spent,2)
        self.assertEqual(len(self.executor.calls),0)

    def test_unknown_reply_exact_delta_does_not_confirm_or_refund(self):
        self.enable();self.app.Step(self.app,self.raw())
        self.executor.Invoke=self.h.lua.eval("function() error('lost connection') end")
        self.executor.Drain(self.executor);self.restart();self.h.at(1)
        self.app.Step(self.app,self.raw(2,8,2))
        self.assertIsNone(self.runtime.Status(self.runtime).recoveries.chests)
        self.assertEqual(self.usage().spent,2);self.assertEqual(len(self.executor.calls),0)

    def test_saved_partial_extra_or_wrong_origin_outcomes_stay_pending(self):
        self.enable();self.send();self.restart()
        for revision,crates,prizes,bound in [(2,8,1,2),(3,8,3,2),(4,8,2,1)]:
            self.h.at(revision);raw=self.raw(revision,crates,prizes);raw.native.inventoryBound.crate_a=bound
            self.app.Step(self.app,raw)
            self.assertIsNone(self.runtime.Status(self.runtime).recoveries.chests)
            self.assertEqual(self.usage().spent,2)

    def test_cross_session_recovery_needs_newer_native_clock(self):
        self.enable();self.send();self.app.Destroy(self.app)
        self.h.session['session']='next-run';self.build();self.h.at(1)
        raw=self.raw(0,8,2);raw.native.serverNow=1001
        self.app.Step(self.app,raw);self.assertIsNone(self.runtime.Status(self.runtime).recoveries.chests)
        self.h.at(2);raw=self.raw(1,8,2);raw.native.serverNow=1002
        self.app.Step(self.app,raw)
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.chests,'confirmed')
        self.assertEqual(self.usage().spent,2);self.assertEqual(len(self.executor.calls),0)

    def test_pending_negative_reply_never_confirms_or_rejects(self):
        self.enable();self.send(reply={'ok':False,'pending':True});self.h.at(1)
        self.app.Step(self.app,self.raw(2));self.assertIsNone(self.runtime.Status(self.runtime).outcomes.chests)
        self.restart();self.h.at(2);self.app.Step(self.app,self.raw(3))
        self.assertIsNone(self.runtime.Status(self.runtime).recoveries.chests)
        self.assertEqual(self.usage().spent,2)

    def test_invalid_limits_and_independent_native_batch_cap(self):
        for key,bad in [('totalLimit',0),('totalLimit',1001),('totalLimit',1.5),('totalLimit',True),
                ('totalLimitEnabled','true'),('maxBatch',1.5)]:
            self.assertFalse(self.app.Set(self.app,'chests.custom.'+key,bad)[0])
        self.enable(limit=9,batch=10)
        # The composed catalog is an independent native cap, retained in the tab source.
        self.runtime.tabInstances[1].crateCatalog.batchMax=3
        self.send(amount=3)
        self.assertEqual(self.executor.calls[1].args[3],3)
        self.assertEqual(self.usage().spent,3)

    def test_missing_or_altered_persisted_usage_or_charge_fails_closed(self):
        self.enable();self.send()
        key=self.runtime.checkpoint.ScopeKey(self.runtime.checkpoint)
        envelope=self.base.storage.data[key]
        original=self.h.lua.eval('function(v) local r={} for k,x in pairs(v) do r[k]=x end return r end')(envelope)
        for change in ('missing_usage','lower_usage','missing_charge','wrong_charge'):
            with self.subTest(change=change):
                self.base.storage.data[key]=self.h.lua.eval('function(v) local r={} for k,x in pairs(v) do r[k]=x end return r end')(original)
                current=self.base.storage.data[key]
                records=self.h.lua.table();records[1]=self.h.lua.eval('function(v) local r={} for k,x in pairs(v) do r[k]=x end return r end')(original.records[1]);current.records=records
                if change=='missing_usage':current.chestUsage=None
                elif change=='lower_usage':current.chestUsage=lua_table(self.h.lua,{'version':1,'attempted':0,'spent':0})
                elif change=='missing_charge':records[1].chestCharge=None
                else:records[1].chestCharge=lua_table(self.h.lua,{'itemId':'crate_a','amount':2,'attemptedBefore':1,'spentBefore':2})
                cp=self.modules.Checkpoint.new(self.base.storage,self.modules.FamilyContributionUsage,self.modules.ResourceReservations,
                    self.modules.PendingAction,self.modules.EventShopUsage,self.modules.MarketRentUsage,self.modules.CrewHireUsage,self.modules.PlayerFightUsage,self.modules.Chests)
                self.assertIsNone(cp.Load(cp,'user-a',self.h.session['place'],'release-a')[0])
        self.base.storage.data[key]=original

    def test_failed_usage_write_cannot_dispatch(self):
        self.enable();self.base.storage.Write=self.h.lua.eval('function() return false end')
        self.app.Step(self.app,self.raw());self.executor.Drain(self.executor)
        self.assertEqual(len(self.executor.calls),0)
        self.assertTrue(self.runtime.Status(self.runtime).storageFault)

    def test_saved_baseline_tampering_or_new_catalog_does_not_recover(self):
        self.enable();self.send()
        record=self.runtime.checkpoint.Records(self.runtime.checkpoint)[1]
        data=self.runtime.checkpoint.Recovery(self.runtime.checkpoint,record.actionKey)[0]
        after=self.runtime.snapshotAssembler.Enrich(self.runtime.snapshotAssembler,self.raw(2,8,2))[0]
        data.baseline.count=99
        self.assertIsNone(self.modules.Chests.recoverSaved(data,after))
        data.baseline.count=10;after.ownedCrateCatalog.catalogKey='b'*64
        self.assertIsNone(self.modules.Chests.recoverSaved(data,after))

    def test_stale_runtime_cannot_overwrite_consumed_allowance(self):
        self.enable(limit=2);self.send();self.h.at(1);self.app.Step(self.app,self.raw(2,8,2))
        old=self.runtime;self.restart()
        cp=self.runtime.checkpoint;expected=cp.Allowance(cp,'chests')[0]
        self.assertTrue(cp.ResetAllowance(cp,expected)[0])
        oldExpected=old.checkpoint.Allowance(old.checkpoint,'chests')[0]
        self.assertFalse(old.checkpoint.ResetAllowance(old.checkpoint,oldExpected)[0])
        self.assertEqual(cp.Allowance(cp,'chests')[0].spent,0)

    def test_new_stock_revision_before_queued_dispatch_refunds(self):
        self.enable();self.app.Step(self.app,self.raw())
        self.h.at(0.5);self.app.Step(self.app,self.raw(2,1,0))
        self.executor.Drain(self.executor);self.app.Pause(self.app)
        self.h.at(1);self.app.Step(self.app,self.raw(3,1,0))
        self.assertEqual(len(self.executor.calls),0)
        self.assertEqual(self.usage().spent,0)

    def test_current_luck_or_native_cap_change_invalidates_queued_dispatch(self):
        self.enable();self.app.Step(self.app,self.raw())
        self.runtime.tabInstances[1].crateCatalog.batchMax=1
        self.h.at(0.5);raw=self.raw(2);raw.native.luckBonus=0.5
        self.app.Step(self.app,raw);self.executor.Drain(self.executor);self.app.Pause(self.app)
        self.h.at(1);self.app.Step(self.app,self.raw(3))
        self.assertEqual(len(self.executor.calls),0);self.assertEqual(self.usage().spent,0)

    def test_caller_usage_proof_cannot_renew_consumed_allowance(self):
        self.enable(limit=2);self.send();self.h.at(1);self.app.Step(self.app,self.raw(2,8,2))
        self.h.at(2);raw=self.raw(3,8,2)
        raw.chestUsageProof=lua_table(self.h.lua,{**self.h.session,'revision':3,'capturedAt':2,'attempted':0,'spent':0})
        self.app.Step(self.app,raw);self.executor.Drain(self.executor)
        self.assertEqual(len(self.executor.calls),1);self.assertEqual(self.usage().spent,2)

    def test_unknown_legacy_pending_custody_does_not_assume_zero(self):
        self.enable();self.send()
        key=self.runtime.checkpoint.ScopeKey(self.runtime.checkpoint)
        envelope=self.base.storage.data[key]
        envelope.chestUsage=None;envelope.chestUsageInitialized=None;envelope.records[1].chestCharge=None;envelope.records[1].recovery=None
        self.restart();self.h.at(1);self.app.Step(self.app,self.raw(2))
        self.assertIsNone(self.runtime.checkpoint.ChestUsage(self.runtime.checkpoint,self.raw(2))[0])
        self.assertIsNone(self.app.PreviewAllowance(self.app,'chests')[0])
        self.assertEqual(len(self.executor.calls),0)

    def test_settled_missing_usage_is_corrupt_not_a_fresh_allowance(self):
        self.enable(limit=2);self.send();self.h.at(1);self.app.Step(self.app,self.raw(2,8,2))
        cp=self.runtime.checkpoint;key=cp.ScopeKey(cp)
        self.assertEqual(len(cp.Records(cp)),0)
        self.base.storage.data[key].chestUsage=None
        self.restart();self.enable(limit=2);self.h.at(2);self.send(raw=self.raw(3,8,2))
        self.assertEqual(len(self.executor.calls),0)
        self.assertIsNotNone(self.runtime.checkpoint.fault)
        self.app.Pause(self.app)
        self.assertIsNone(self.app.PreviewAllowance(self.app,'chests')[0])
        self.assertFalse(self.app.ConfirmAllowance(self.app,'chests')[0])

    def legacy_pending(self,reply=None):
        self.enable(limit=2);self.send(reply=reply)
        cp=self.runtime.checkpoint;key=cp.ScopeKey(cp)
        envelope=self.base.storage.data[key];record=envelope.records[1]
        data=cp.Recovery(cp,record.actionKey)[0]
        for field in ('attemptedBefore','spentBefore','totalLimitEnabled','totalLimit'):
            data.proposal.intent[field]=None
        data.before.chestUsageProof=None
        record.chestCharge=None;envelope.chestUsage=None;envelope.chestUsageInitialized=None
        record.recovery=self.modules.PendingAction.Capture(data.proposal,data.before,data.baseline,data.reply)[0]
        self.restart()

    def test_legacy_exact_settlement_retains_unknown_until_explicit_reviewed_reset(self):
        self.legacy_pending();self.h.at(1);self.app.Step(self.app,self.raw(2,8,2))
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.chests,'confirmed')
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),0)
        self.assertTrue(self.usage().unknown)
        self.restart();self.enable(limit=2);self.h.at(2);self.send(raw=self.raw(3,8,2))
        self.assertEqual(len(self.executor.calls),0)
        self.assertTrue(self.usage().unknown)
        self.app.Pause(self.app)
        preview,reason=self.app.PreviewAllowance(self.app,'chests');self.assertIsNone(reason)
        self.assertTrue(preview.unknown)
        self.assertTrue(self.app.ConfirmAllowance(self.app,'chests')[0])
        self.assertFalse(bool(self.usage().unknown));self.assertEqual(self.usage().spent,0)
        self.restart();self.enable(limit=2);self.h.at(3);self.send(raw=self.raw(4,8,2))
        self.assertEqual(len(self.executor.calls),1)
        self.assertEqual(self.usage().spent,2)

    def test_legacy_rejected_settlement_retains_unknown_and_pending_disallows_reset(self):
        self.legacy_pending(reply={'ok':False})
        self.h.at(1);self.app.Step(self.app,self.raw(1))
        self.assertIsNone(self.app.PreviewAllowance(self.app,'chests')[0])
        self.h.at(2);self.app.Step(self.app,self.raw(2))
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.chests,'rejected')
        self.assertTrue(self.usage().unknown)
        self.restart();self.h.at(3);self.app.Step(self.app,self.raw(3))
        self.assertTrue(self.usage().unknown);self.assertEqual(len(self.executor.calls),0)

    def test_legacy_checkpoint_without_chest_accounting_preserves_unrelated_usage(self):
        self.enable(limit=2);self.send();self.h.at(1);self.app.Step(self.app,self.raw(2,8,2))
        cp=self.runtime.checkpoint;key=cp.ScopeKey(cp);envelope=self.base.storage.data[key]
        envelope.chestUsage=None;envelope.chestUsageInitialized=None;envelope.stationAttempts=2
        self.restart();self.enable(limit=2);self.h.at(2);self.send(raw=self.raw(3,8,2))
        self.assertIsNone(self.runtime.checkpoint.fault)
        self.assertEqual(self.runtime.checkpoint.stationAttempts,2)
        self.assertEqual(len(self.executor.calls),1);self.assertEqual(self.usage().spent,2)

    def test_unknown_legacy_allowance_is_explicit_in_actual_settings_review(self):
        self.legacy_pending();self.h.at(1);self.app.Step(self.app,self.raw(2,8,2))
        self.app.Pause(self.app)
        selection=self.app.ui.settings.allowanceSelection
        self.assertIn('Owned chests',list(selection.options.Options.values()))
        selection.Set(selection,'Owned chests',True)
        buttons={handle.options.Text:handle for handle in self.app.ui.window.handles.values() if handle.kind=='Button'}
        buttons['Review allowance'].options.Callback(None,None,None)
        status=self.app.ui.settings.allowanceStatus.Get(self.app.ui.settings.allowanceStatus)
        self.assertIn('Previous chest use is unknown',status)
        self.assertNotIn('0 counted',status)
        self.assertTrue(self.usage().unknown)
        buttons['Confirm allowance reset'].options.Callback(None,None,None)
        self.assertFalse(bool(self.usage().unknown));self.assertTrue(self.app.model.paused)
        self.assertEqual(len(self.executor.calls),0)

    def test_existing_count_without_new_marker_is_preserved_on_upgrade(self):
        self.enable(limit=2);self.send();self.h.at(1);self.app.Step(self.app,self.raw(2,8,2))
        cp=self.runtime.checkpoint;key=cp.ScopeKey(cp)
        self.base.storage.data[key].chestUsageInitialized=None
        self.restart();self.enable(limit=2);self.h.at(2);self.send(raw=self.raw(3,8,2))
        self.assertIsNone(self.runtime.checkpoint.fault)
        self.assertEqual(self.usage().spent,2);self.assertEqual(len(self.executor.calls),0)

if __name__=='__main__': unittest.main()
