"""Actual Prestige tab/App uses owned native preflight plus durable reset attempts."""
import unittest
import hashlib
import test_automation_runtime as fixture
from engine_harness import lua_table

class PrestigeOwnedAppTests(unittest.TestCase):
    def setUp(self):
        self.base=fixture.AutomationRuntimeTests();self.base.setUp();self.h=self.base.h;self.base.runtime.Close(self.base.runtime)
        self.h.lua.globals().prestigeHash=lambda value:hashlib.sha256(value.encode()).hexdigest()
        self.base.storage.hash=self.h.lua.eval('function(value) return prestigeHash(value) end')
        self.config=lua_table(self.h.lua,{'PRESTIGE':{'maxRank':6,'levelByRank':[200,200,200,210,220,230]}})
        self.start()
    def start(self, allowed=None):
        h=self.h
        self.controller=h.lua.execute("""return {valid=true,frame={rank=0,level=200,xp=1234,ready=true,controllersClear=true},
            Current=function(self) return self.valid and not self.closed end,
            Read=function(self) self.readCalls=(self.readCalls or 0)+1;if self.yieldRead then coroutine.yield('controller-read') end;if not self:Current() then return nil end;local r={};for k,v in pairs(self.frame) do r[k]=v end;return r end,
            Close=function(self) self.closed=true end}""")
        deps={'PrestigeState':h.load('src/game/PrestigeState.luau'),'PrestigeBlocked':h.load('src/features/PrestigeBlocked.luau'),
            'PrestigeReset':h.load('src/tabs/prestige/PrestigeReset.luau'),'config':self.config,'fingerprint':'a'*64,'release':'release-a',
            'identity':h.session,'nativePrestigeController':self.controller}
        self.tab=h.load('src/tabs/prestige/Module.luau').new(lua_table(h.lua,deps));self.spec=self.tab.Descriptors(self.tab)[1]
        self.base.runtime.modules.nativePrestigeController=self.controller
        self.lane=h.load('src/engine/RequestLane.luau').new(h.clock);h.lua.globals().prestigeLane=self.lane
        self.executor=h.lua.execute("""return {queued={},calls=0,apply=true,reply={ok=true,rank=1},
            Schedule=function(self,fn) self.queued[#self.queued+1]=fn;return true end,
            Invoke=function() error('Unowned reset') end,
            InvokeOwned=function(self,token,remote,method,arg)
                assert(prestigeLane:Owns(token));assert(remote=='PrestigeAction' and method=='InvokeServer' and arg=='prestige')
                self.calls=self.calls+1
                if self.apply then self.source.frame.rank=self.source.frame.rank+1;self.source.frame.level=1;self.source.frame.xp=0;self.source.frame.ready=false end
                if self.fail then error('Interrupted reset response') end
                return self.reply
            end}""")
        self.executor.source=self.controller
        native=h.load('src/transport/NativeCallPlan.luau');plan=native.withPrestige(native,deps['PrestigeReset'])
        self.adapter=h.load('src/transport/NativeDispatchAdapter.luau').new(plan,self.executor,self.lane,h.clock)
        self.runtime=h.load('src/engine/AutomationRuntime.luau').new(lua_table(h.lua,{'clock':h.clock,'transport':self.adapter,
            'storage':self.base.storage,'identity':h.session,'modules':self.base.runtime.modules,'features':[self.spec],
            'tabInstances':[self.tab],'featurePages':{'prestige':'prestige'},
            'snapshotAssembler':h.load('src/tabs/TabSnapshotAssembler.luau').new(lua_table(h.lua,[self.tab]))}))
        self.app=h.load('src/App.luau').start(lua_table(h.lua,{'Ember':h.load('tests/ember_double.lua')(),
            'Catalog':h.load('src/ui/Catalog.luau'),'Settings':h.load('src/storage/Settings.luau'),
            'EmberAdapter':h.load('src/ui/EmberAdapter.luau'),'PrestigeTab':h.load('src/tabs/prestige/Module.luau'),
            'automationRuntimeInstance':self.runtime,'allowedFeatures':allowed}))
    def test_owned_ui_shows_runtime_status_without_polling_or_enabling_reset(self):
        self.assertIsNone(self.app.ui.features.prestige.blockedReason)
        self.assertNotIn('Blocked',self.app.ui.features.prestige.status.Get(self.app.ui.features.prestige.status))
        self.assertTrue(self.runtime.SupportsPrestigeReset(self.runtime))
        self.assertIsNone(self.controller.readCalls)
        self.assertFalse(self.app.model["values"]['prestige.enabled'])
        self.assertFalse(self.app.model["values"]['prestige.custom.allowReset'])
        self.assertEqual(self.app.model["values"]['prestige.custom.maxResets'],0)
    def test_entry_exclusion_retains_prestige_unavailable_warning(self):
        self.app.Destroy(self.app);self.start(lua_table(self.h.lua,{'jobs':True}))
        self.assertIn('native controller',self.app.ui.features.prestige.blockedReason)
        self.assertIsNone(self.controller.readCalls)
    def test_missing_or_replaced_source_cannot_advertise_reset_capability(self):
        self.runtime.nativePrestigeController=None
        self.assertFalse(self.runtime.SupportsPrestigeReset(self.runtime))
        self.runtime.nativePrestigeController=self.controller
        self.controller.Read=self.h.lua.eval('function() return nil end')
        self.assertFalse(self.runtime.SupportsPrestigeReset(self.runtime))
    def raw(self,rank=0,level=200,xp=1234,revision=1,at=0):
        return self.h.snapshot(revision=revision,capturedAt=at,native={'fullSync':True,'serverNow':1000+at,'prestige':rank,'level':level,'xp':xp})
    def enable(self,cap=1):
        for key,value in (('prestige.enabled',True),('prestige.custom.allowReset',True),('prestige.custom.maxResets',cap)):
            self.assertTrue(self.app.Set(self.app,key,value)[0])
        self.app.Resume(self.app)
    def begin(self):
        self.enable();self.app.Step(self.app,self.raw())
        self.assertEqual(len(self.executor.queued),1,str(dict(self.runtime.Status(self.runtime).reasons.items())))
    def send(self):self.executor.queued[1]();self.assertEqual(self.executor.calls,1)
    def test_default_off_and_zero_cap_do_not_invoke_or_charge(self):
        self.app.Step(self.app,self.raw());self.assertEqual(len(self.executor.queued),0)
        self.enable(cap=0);self.app.Step(self.app,self.raw());self.assertEqual(len(self.executor.queued),0)
        self.assertEqual(self.runtime.checkpoint.PrestigeUsage(self.runtime.checkpoint,self.raw())[0].attempted,0)
    def test_each_native_rank_threshold_resets_once_and_confirms_exact_next_rank(self):
        for rank,threshold in enumerate((200,200,200,210,220,230)):
            self.tearDown();self.setUp();self.controller.frame.rank=rank;self.controller.frame.level=threshold
            self.enable();self.app.Step(self.app,self.raw(rank=rank,level=threshold-1))
            self.assertEqual(len(self.executor.queued),0)
            self.app.Step(self.app,self.raw(rank=rank,level=threshold))
            self.assertEqual(len(self.executor.queued),1)
            self.executor.reply.rank=rank+1;self.send();self.h.at(.25)
            self.app.Step(self.app,self.raw(rank=rank+1,level=1,xp=0,revision=2,at=.25))
            self.assertEqual(self.runtime.Status(self.runtime).outcomes.prestige,'confirmed')
            self.assertEqual(self.runtime.checkpoint.PrestigeUsage(self.runtime.checkpoint,self.raw())[0].attempted,1)
    def test_target_rank_is_independent_of_remaining_owned_attempts(self):
        self.enable(cap=6);self.app.Set(self.app,'prestige.custom.targetRank',1)
        self.controller.frame.rank=1
        self.app.Step(self.app,self.raw(rank=1));self.assertEqual(len(self.executor.queued),0)
        self.assertEqual(self.runtime.checkpoint.PrestigeUsage(self.runtime.checkpoint,self.raw())[0].attempted,0)
    def test_saved_rejection_recovers_but_saved_challenge_remains_held_without_refund(self):
        for uncertain in (False,True):
            self.tearDown();self.setUp();self.begin();self.executor.apply=False
            self.executor.reply=lua_table(self.h.lua,{'ok':False,'code':'presence' if uncertain else 'requirements'})
            self.send();self.restart_all_off();self.app.Step(self.app,self.raw())
            self.assertEqual(self.runtime.Status(self.runtime).recoveries.prestige,None if uncertain else 'rejected')
            self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),1 if uncertain else 0)
            self.assertEqual(self.runtime.checkpoint.PrestigeUsage(self.runtime.checkpoint,self.raw())[0].attempted,1)
            self.assertEqual(self.executor.calls,0)
    def test_exact_owned_reset_confirms_only_after_new_sync_and_retains_attempt(self):
        self.begin();self.send();self.h.at(.25);self.app.Step(self.app,self.raw(rank=1,level=1,xp=0,revision=2,at=.25))
        self.assertEqual(self.runtime.Status(self.runtime).outcomes.prestige,'confirmed')
        self.assertEqual(self.runtime.checkpoint.PrestigeUsage(self.runtime.checkpoint,self.raw())[0].attempted,1)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),0)
    def test_changed_native_modal_or_rank_before_queue_refuses_without_rpc_and_refunds_unsent(self):
        for field,value in (('controllersClear',False),('rank',1),('xp',1235)):
            self.tearDown();self.setUp();self.begin();self.controller.frame[field]=value
            self.executor.queued[1]();self.assertEqual(self.executor.calls,0)
            self.assertEqual(self.runtime.checkpoint.PrestigeUsage(self.runtime.checkpoint,self.raw())[0].attempted,0)
    def test_disable_or_unload_before_queue_never_resets(self):
        for unload in (False,True):
            self.tearDown();self.setUp();self.begin()
            if unload:self.app.Destroy(self.app)
            else:self.app.Set(self.app,'prestige.enabled',False);self.app.Step(self.app,self.raw())
            self.executor.queued[1]();self.assertEqual(self.executor.calls,0)
    def test_native_rejection_keeps_attempt_charge_and_no_success(self):
        self.begin();self.executor.apply=False;self.executor.reply=lua_table(self.h.lua,{'ok':False,'code':'requirements'})
        self.send();self.h.at(.25);self.app.Step(self.app,self.raw(revision=2,at=.25))
        self.assertEqual(self.runtime.Status(self.runtime).outcomes.prestige,'rejected')
        self.assertEqual(self.runtime.checkpoint.PrestigeUsage(self.runtime.checkpoint,self.raw())[0].attempted,1)
    def test_interrupted_response_remains_unknown_even_if_rank_changed(self):
        self.begin();self.executor.fail=True;self.send();self.h.at(45)
        self.app.Step(self.app,self.raw(rank=1,level=1,xp=0,revision=2,at=45))
        self.assertEqual(self.runtime.Status(self.runtime).outcomes.prestige,'skipped_unconfirmed')
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),1)
        self.assertEqual(self.runtime.checkpoint.PrestigeUsage(self.runtime.checkpoint,self.raw())[0].attempted,1)
    def test_caller_zero_count_and_clear_flags_cannot_replace_native_owner(self):
        self.controller.valid=False;self.enable(cap=6);raw=self.raw()
        raw.prestigeUsageProof=lua_table(self.h.lua,{**self.h.session,'revision':1,'capturedAt':0,'attempted':0,'controllersClear':True})
        self.app.Step(self.app,raw);self.assertEqual(len(self.executor.queued),0)
    def restart_all_off(self):
        self.app.Destroy(self.app);self.h.session['session']='fresh-prestige-session';self.start()
    def test_sent_disable_still_observes_exact_returned_effect_without_another_reset(self):
        self.begin();self.send();self.app.Set(self.app,'prestige.enabled',False);self.h.at(.25)
        self.app.Step(self.app,self.raw(rank=1,level=1,xp=0,revision=2,at=.25))
        self.assertEqual(self.runtime.Status(self.runtime).outcomes.prestige,'confirmed');self.assertEqual(self.executor.calls,1)
    def test_pending_busy_rate_or_challenge_reply_stays_held_until_skip(self):
        for reply in ({'ok':False,'pending':True},{'ok':False,'code':'busy'},
                      {'ok':False,'code':'rate_limited'},{'ok':False,'code':'presence'}):
            self.tearDown();self.setUp();self.begin();self.executor.apply=False;self.executor.reply=lua_table(self.h.lua,reply)
            self.send();self.h.at(.25);self.app.Step(self.app,self.raw(revision=2,at=.25))
            self.assertIsNone(self.runtime.Status(self.runtime).outcomes.prestige)
            self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),1)
            self.h.at(45);self.app.Step(self.app,self.raw(revision=3,at=45))
            self.assertEqual(self.runtime.Status(self.runtime).outcomes.prestige,'skipped_unconfirmed')
            self.assertEqual(self.executor.calls,1)
    def test_positive_saved_reply_recovers_after_reload_all_off_without_replay(self):
        self.begin();self.send();self.restart_all_off()
        self.controller.frame.rank=1;self.controller.frame.level=1;self.controller.frame.xp=0;self.controller.frame.ready=False
        self.app.Step(self.app,self.raw(rank=1,level=1,xp=0,revision=1))
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.prestige,'confirmed')
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),0)
        self.assertEqual(self.runtime.checkpoint.PrestigeUsage(self.runtime.checkpoint,self.raw())[0].attempted,1)
        self.assertEqual(self.executor.calls,0)
    def test_unknown_changed_rank_after_reload_never_replays_or_refunds(self):
        self.begin();self.executor.fail=True;self.send();self.restart_all_off()
        self.app.Step(self.app,self.raw(rank=1,level=1,xp=0,revision=1))
        self.assertIsNone(self.runtime.Status(self.runtime).recoveries.prestige)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),1)
        self.assertEqual(self.runtime.checkpoint.PrestigeUsage(self.runtime.checkpoint,self.raw())[0].attempted,1)
        self.assertEqual(self.executor.calls,0)
    def test_unload_before_send_recovers_only_exact_adapter_unsent_fact(self):
        self.begin();old=self.executor;self.app.Destroy(self.app);old.queued[1]();self.restart_all_off()
        self.app.Step(self.app,self.raw())
        self.assertEqual(self.executor.calls,0);self.assertEqual(old.calls,0)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),0)
        self.assertEqual(self.runtime.checkpoint.PrestigeUsage(self.runtime.checkpoint,self.raw())[0].attempted,0)
    def test_reply_persistence_failure_keeps_unknown_custody_and_charge_after_reload(self):
        self.begin();self.h.lua.globals().prestigeExecutor=self.executor
        original=self.base.storage.Write
        self.base.storage.Write=self.h.lua.eval('function(self,k,v) if k:find(":checkpoint:",1,true) and prestigeExecutor.calls>0 then return false end;self.data[k]=v;return true end')
        self.send();self.assertTrue(self.runtime.Status(self.runtime).storageFault)
        self.base.storage.Write=original;self.restart_all_off()
        self.app.Step(self.app,self.raw(rank=1,level=1,xp=0))
        self.assertIsNone(self.runtime.Status(self.runtime).recoveries.prestige)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),1)
        self.assertEqual(self.runtime.checkpoint.PrestigeUsage(self.runtime.checkpoint,self.raw())[0].attempted,1)
        self.assertEqual(self.executor.calls,0)
    def test_confirmed_cleanup_failure_recovers_durable_reply_without_another_rpc(self):
        self.begin();self.send();original=self.base.storage.Write
        self.base.storage.Write=self.h.lua.eval('function(self,k,v) if k:find(":checkpoint:",1,true) and #v.records==0 then return false end;self.data[k]=v;return true end')
        self.h.at(.25);self.app.Step(self.app,self.raw(rank=1,level=1,xp=0,revision=2,at=.25))
        self.assertTrue(self.runtime.Status(self.runtime).storageFault)
        self.base.storage.Write=original;self.restart_all_off()
        self.app.Step(self.app,self.raw(rank=1,level=1,xp=0,revision=1,at=.25))
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.prestige,'confirmed')
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),0);self.assertEqual(self.executor.calls,0)
    def test_wrong_saved_reply_or_nonexact_effect_never_confirms_on_reload(self):
        for change in ('reply','xp','level'):
            self.tearDown();self.setUp();self.begin()
            if change=='reply':self.executor.reply.rank=2
            self.send();self.restart_all_off()
            after=self.raw(rank=1,level=2 if change=='level' else 1,xp=1 if change=='xp' else 0)
            self.app.Step(self.app,after)
            self.assertIsNone(self.runtime.Status(self.runtime).recoveries.prestige)
            self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),1);self.assertEqual(self.executor.calls,0)
    def test_changed_opt_in_or_controller_method_cancels_queued_reset_as_unsent(self):
        for change in ('optin','method'):
            self.tearDown();self.setUp();self.begin()
            if change=='optin':
                self.app.Set(self.app,'prestige.custom.allowReset',False);self.app.Step(self.app,self.raw())
            else:self.controller.Read=self.h.lua.eval('function() return {controllersClear=true,ready=true,rank=0,level=200,xp=1234} end')
            self.executor.queued[1]();self.assertEqual(self.executor.calls,0)
            self.assertEqual(self.runtime.checkpoint.PrestigeUsage(self.runtime.checkpoint,self.raw())[0].attempted,0)
    def test_exhausted_owned_budget_cannot_be_reset_by_caller_zero_proof(self):
        self.begin();self.executor.apply=False;self.executor.reply=lua_table(self.h.lua,{'ok':False,'code':'requirements'});self.send()
        self.h.at(.25);self.app.Step(self.app,self.raw(revision=2,at=.25));self.h.at(1)
        raw=self.raw(revision=3,at=1);raw.prestigeUsageProof=lua_table(self.h.lua,{**self.h.session,'revision':3,'capturedAt':1,'attempted':0,'controllersClear':True})
        self.app.Step(self.app,raw);self.assertEqual(len(self.executor.queued),1);self.assertEqual(self.executor.calls,1)
    def test_native_controller_is_not_polled_while_all_off_or_paused(self):
        self.app.Step(self.app,self.raw());self.assertIsNone(self.controller.readCalls)
        self.enable();self.app.Pause(self.app);self.app.Step(self.app,self.raw())
        self.assertIsNone(self.controller.readCalls)
    def begin_yielded_controller(self):
        self.enable();self.controller.yieldRead=True
        self.h.lua.globals().prestigeYieldApp=self.app;self.h.lua.globals().prestigeYieldRaw=self.raw()
        value=self.h.lua.execute('prestigeStepThread=coroutine.create(function() return prestigeYieldApp:Step(prestigeYieldRaw) end);local ok,value=coroutine.resume(prestigeStepThread);assert(ok);return value')
        self.assertEqual(value,'controller-read')
    def test_unload_during_native_preflight_does_not_republish_closed_snapshot(self):
        self.begin_yielded_controller();self.app.Destroy(self.app)
        self.h.lua.execute('assert(coroutine.resume(prestigeStepThread))')
        self.assertEqual(self.executor.calls,0);self.assertEqual(len(self.executor.queued),0)
        self.assertIsNone(self.runtime.allowanceSnapshot);self.assertIsNone(self.runtime.latestOutcomeSnapshot)
    def test_disable_during_native_preflight_cannot_be_overwritten_by_older_step(self):
        self.begin_yielded_controller();self.controller.yieldRead=False
        self.app.Set(self.app,'prestige.enabled',False);self.app.Step(self.app,self.raw())
        self.h.lua.execute('assert(coroutine.resume(prestigeStepThread))')
        self.assertEqual(len(self.executor.queued),0);self.assertEqual(self.executor.calls,0)
        self.assertEqual(self.runtime.checkpoint.PrestigeUsage(self.runtime.checkpoint,self.raw())[0].attempted,0)
    def test_disable_during_yielding_attempt_save_refunds_only_uninvoked_reset(self):
        self.enable();original=self.base.storage.Write
        self.base.storage.Write=self.h.lua.eval('function(self,k,v) if k:find(":checkpoint:",1,true) and #v.records>0 then coroutine.yield("attempt-write") end;self.data[k]=v;return true end')
        self.h.lua.globals().prestigeWriteApp=self.app;self.h.lua.globals().prestigeWriteRaw=self.raw()
        self.assertEqual(self.h.lua.execute('prestigeWriteThread=coroutine.create(function() return prestigeWriteApp:Step(prestigeWriteRaw) end);local ok,value=coroutine.resume(prestigeWriteThread);assert(ok);return value'),'attempt-write')
        self.app.Set(self.app,'prestige.enabled',False);self.app.Step(self.app,self.raw())
        self.base.storage.Write=original;self.h.lua.execute('assert(coroutine.resume(prestigeWriteThread))')
        for _,callback in self.executor.queued.items():callback()
        self.assertEqual(self.executor.calls,0)
        self.assertEqual(self.runtime.checkpoint.PrestigeUsage(self.runtime.checkpoint,self.raw())[0].attempted,0)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),0)
    def test_unload_during_attempt_save_leaves_only_exact_unsent_recovery(self):
        self.enable();original=self.base.storage.Write
        self.base.storage.Write=self.h.lua.eval('function(self,k,v) if k:find(":checkpoint:",1,true) and #v.records>0 then coroutine.yield("attempt-write") end;self.data[k]=v;return true end')
        self.h.lua.globals().prestigeWriteApp=self.app;self.h.lua.globals().prestigeWriteRaw=self.raw()
        self.assertEqual(self.h.lua.execute('prestigeWriteThread=coroutine.create(function() return prestigeWriteApp:Step(prestigeWriteRaw) end);local ok,value=coroutine.resume(prestigeWriteThread);assert(ok);return value'),'attempt-write')
        self.app.Destroy(self.app);self.base.storage.Write=original
        self.h.lua.execute('assert(coroutine.resume(prestigeWriteThread))')
        old=self.executor
        for _,callback in old.queued.items():callback()
        self.restart_all_off();self.app.Step(self.app,self.raw())
        self.assertEqual(old.calls,0);self.assertEqual(self.executor.calls,0)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),0)
        self.assertEqual(self.runtime.checkpoint.PrestigeUsage(self.runtime.checkpoint,self.raw())[0].attempted,0)
    def test_ambiguous_successful_attempt_write_never_invokes_and_recovers_unsent(self):
        original=self.base.storage.Write
        self.base.storage.Write=self.h.lua.eval('function(self,k,v) self.data[k]=v;if k:find(":checkpoint:",1,true) and #v.records>0 then return false end;return true end')
        self.enable();self.app.Step(self.app,self.raw());self.assertEqual(self.executor.calls,0)
        self.base.storage.Write=original;self.restart_all_off();self.app.Step(self.app,self.raw())
        self.assertEqual(self.executor.calls,0);self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),0)
        self.assertEqual(self.runtime.checkpoint.PrestigeUsage(self.runtime.checkpoint,self.raw())[0].attempted,0)
    def tearDown(self):
        if hasattr(self,'app'):self.app.Destroy(self.app)
