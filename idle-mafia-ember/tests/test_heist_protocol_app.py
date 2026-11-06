"""Actual App -> tab -> broker -> owned native transport, without Roblox."""
import unittest
import hashlib
import test_heist_favor_catalog_app as fixture
import test_runtime_host as host_fixture
from engine_harness import lua_table

class HeistProtocolAppTests(unittest.TestCase):
    def setUp(self):
        self.base=fixture.HeistFavorCatalogAppTests();self.base.setUp();self.h=self.base.h;h=self.h
        deps=self.base.heists.deps;self.base.app.Destroy(self.base.app)
        self.port=h.lua.execute("return {counter=0,running=false,Current=function() return true end,Read=function(s) return {counter=s.counter,pending=s.pending,running=s.running} end,Write=function(s,k,v) s[k]=v end}")
        lease=h.load('src/tabs/heists/NativeHeistLease.luau').new(self.port,h.clock,lua_table(h.lua,{'account':'user-a','place':h.session['place'],'jobId':'job-a','sourceKey':'a'*64}),lua_table(h.lua,{'id':'epoch-a','counterSeen':0}))[0]
        h.lua.globals().heistTestHash=lambda text: hashlib.sha256(text.encode()).hexdigest()
        self.base.base.storage.hash=h.lua.eval('function(text) return heistTestHash(text) end')
        self.protocol=h.load('src/tabs/heists/HeistProtocol.luau').new(lua_table(h.lua,{'lease':lease,'clock':h.clock,'identity':h.session,'hash':h.lua.eval('function(text) return heistTestHash(text) end'),'config':{'xpForLevel':h.lua.eval('function() return 100 end')}}))
        deps.heistProtocol=self.protocol
        self.heists=h.load('src/tabs/heists/Module.luau').new(deps);self.favors=h.load('src/tabs/favors/Module.luau').new(deps)
        self.tabs=lua_table(h.lua,[self.heists,self.favors]);composed,why=h.load('src/tabs/TabComposition.luau').build(self.tabs,h.load('src/ui/Catalog.luau'),h.load('src/engine/FeatureRegistry.luau'),h.load('src/tabs/TabSnapshotAssembler.luau'));self.assertIsNone(why)
        self.lane=h.load('src/engine/RequestLane.luau').new(h.clock)
        self.executor=h.lua.execute("return {calls={},queued={},reply={pending=true},Invoke=function() error('unowned invocation') end,Schedule=function(s,fn) s.queued[#s.queued+1]=fn;return true end,InvokeOwned=function(s,token,remote,method,...) s.calls[#s.calls+1]={remote=remote,args=table.pack(...)};if s.fail then error('lost') end;return s.reply end,Drain=function(s) local q=s.queued;s.queued={};for _,f in ipairs(q) do f() end end}")
        self.adapter=h.load('src/transport/NativeDispatchAdapter.luau').new(h.load('src/transport/NativeCallPlan.luau'),self.executor,self.lane,h.clock,None,self.protocol)
        self.runtime=h.load('src/engine/AutomationRuntime.luau').new(lua_table(h.lua,{'clock':h.clock,'transport':self.adapter,'storage':self.base.base.storage,'identity':h.session,'modules':self.base.runtime.modules,'features':composed.features,'featurePages':composed.featurePages,'tabInstances':self.tabs,'snapshotAssembler':composed.snapshotAssembler}))
        self.app=h.load('src/App.luau').start(lua_table(h.lua,{'Ember':h.load('tests/ember_double.lua')(),'Catalog':h.load('src/ui/Catalog.luau'),'Settings':h.load('src/storage/Settings.luau'),'EmberAdapter':h.load('src/ui/EmberAdapter.luau'),'HeistsTab':h.load('src/tabs/heists/Module.luau'),'FavorsTab':h.load('src/tabs/favors/Module.luau'),'automationRuntimeInstance':self.runtime}))
        self.raw=self.base.raw
    def test_authoritative_reader_keeps_actual_sync_through_income_projection_before_heist(self):
        reader=self.h.load('src/transport/NativeSnapshotReader.luau').new(
            lua_table(self.h.lua,self.h.session),self.h.clock,'a'*64,True)
        self.addCleanup(lambda:reader.Close(reader))
        reader.ObserveSync(reader,self.raw.native)
        projected=lua_table(self.h.lua,{k:v for k,v in self.raw.native.items()})
        projected.cash=self.raw.native.cash+123.5
        projected.serverNow=self.raw.native.serverNow+.25
        reader.ObserveChanged(reader,projected)
        current=reader.Capture(reader)[0]
        self.assertTrue(current.native.fullSync)
        self.assertEqual(current.native.cash,self.raw.native.cash)
        staged=self.heists.StageBoard(self.heists,current,self.raw.heistBoardProof.board)[0]
        self.assertTrue(reader.AttachHeistBoard(reader,staged))
        self.app.Set(self.app,'heists.enabled',True);self.app.Resume(self.app)
        self.app.Step(self.app,reader.Capture(reader)[0]);self.executor.Drain(self.executor)
        self.assertEqual(len(self.executor.calls),1)
        self.assertEqual(self.executor.calls[1].args[1],'start')

    def start(self,feature='heists'):
        self.assertTrue(self.app.Set(self.app,feature+'.enabled',True)[0]);self.app.Resume(self.app);self.app.Step(self.app,self.raw)
    def later(self,t=1,run=True):
        self.h.at(t);self.raw.revision=self.raw.revision+1;self.raw.capturedAt=t;self.raw.native.serverNow=2000000+t
        self.raw.heistBoardProof.capturedAt=t;self.raw.heistBoardProof.board.serverNow=2000000+t
        if run:self.raw.heistBoardProof.board.mine=lua_table(self.h.lua,{'id':'run-a','heistId':'h_b','endsAt':2001000});self.raw.heistBoardProof.board.startsLeft=0
    def test_pending_status_then_terminal_is_one_mutation_and_one_checkpoint_reply(self):
        self.start();self.executor.Drain(self.executor)
        self.assertEqual(len(self.executor.calls),1);self.assertEqual(self.executor.calls[1].args[1],'start')
        records=self.runtime.checkpoint.Records(self.runtime.checkpoint);self.assertEqual(len(records),1)
        data=self.runtime.checkpoint.Recovery(self.runtime.checkpoint,records[1].actionKey)[0];self.assertIsNone(data.reply)
        call,_=self.protocol.StatusCall(self.protocol)
        self.protocol.AcceptStatus(self.protocol,call,lua_table(self.h.lua,{'ok':False,'code':'no_pending'}));self.assertEqual(len(self.executor.calls),1)
        self.protocol.AcceptStatus(self.protocol,call,lua_table(self.h.lua,{'ok':True,'runId':'run-a'}))
        self.later();self.app.Step(self.app,self.raw)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),0);self.assertIsNone(self.port.pending);self.assertEqual(self.port.counter,1)
    def test_queued_disable_is_definitely_unsent_and_cleans_native_lease(self):
        self.start();self.assertIsNotNone(self.port.pending);self.app.Set(self.app,'heists.enabled',False);self.executor.Drain(self.executor)
        self.assertEqual(len(self.executor.calls),0);self.assertIsNone(self.port.pending);self.assertFalse(self.runtime.session.Status(self.runtime.session).storageFault)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),0)
    def test_unload_during_queue_keeps_no_worker_or_late_send(self):
        self.start();self.app.Destroy(self.app);self.executor.Drain(self.executor)
        self.assertEqual(len(self.executor.calls),0);self.assertIsNone(self.port.pending);self.assertFalse(self.port.running)
    def test_unknown_reply_expires_at_45_without_refund_or_replay(self):
        self.start();self.executor.Drain(self.executor);self.later(45,False);self.app.Step(self.app,self.raw)
        self.assertEqual(len(self.executor.calls),1);self.assertIsNone(self.port.pending);self.assertEqual(self.port.counter,1)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),1)
        self.later(46,False);self.app.Step(self.app,self.raw);self.assertEqual(len(self.executor.calls),1)
    def test_favor_uses_same_native_counter_and_numeric_or_string_row_identity(self):
        self.start('favors');self.executor.Drain(self.executor)
        self.assertEqual(len(self.executor.calls),1);self.assertEqual(self.executor.calls[1].args[1],'help');self.assertEqual(self.executor.calls[1].args[2],'run-1');self.assertEqual(self.executor.calls[1].args[3],1)
    def test_native_ui_race_is_not_a_storage_fault(self):
        original=self.protocol.lease.Acquire
        self.h.lua.globals().originalAcquire=original;self.h.lua.globals().nativePort=self.port
        self.protocol.lease.Acquire=self.h.lua.eval('function(s,p,d) nativePort.counter=nativePort.counter+1;return originalAcquire(s,p,d) end')
        self.start();self.executor.Drain(self.executor)
        self.assertEqual(len(self.executor.calls),0);self.assertFalse(self.runtime.session.Status(self.runtime.session).storageFault)
    def collect_result(self):
        self.raw.native.xp=90;self.raw.native.maxLevel=20;self.raw.native.prestige=0
        self.raw.native.inventory=lua_table(self.h.lua,{'crate_a':2,'gold_bar':1});self.raw.native.inventoryBound=lua_table(self.h.lua,{'crate_a':3})
        self.raw.heistBoardProof.board.result=lua_table(self.h.lua,{'heistId':'h_a','ok':True,'cash':100,'xp':30,'gold':1,'crateId':'crate_a','crates':1,'bonusCrates':0})
        self.raw=self.heists.StageBoard(self.heists,self.raw,self.raw.heistBoardProof.board)[0]
        self.executor.reply=lua_table(self.h.lua,{'ok':True,'collected':True,'cash':100,'xp':30})
    def collected(self):
        self.later(1,False);self.raw.heistBoardProof.board.result=None
        self.raw.native.cash=1100;self.raw.native.xp=20;self.raw.native.level=21;self.raw.native.maxLevel=21
        self.raw.native.inventory.crate_a=3;self.raw.native.inventory.gold_bar=2
        self.raw=self.heists.StageBoard(self.heists,self.raw,self.raw.heistBoardProof.board)[0]
    def test_terminal_bonus_xp_is_confirmed_from_owned_reply_and_exact_effect(self):
        self.collect_result();self.executor.reply.xp=46;self.executor.reply.xpEventMultiplier=1
        self.start('heistCollect');self.executor.Drain(self.executor)
        self.collected();self.raw.native.xp=36
        self.app.Step(self.app,self.raw)
        self.assertEqual(self.runtime.outcomes.heistCollect,'confirmed')
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),0)
    def test_native_result_heist_id_is_original_run_not_catalog_template(self):
        self.collect_result()
        self.raw.heistBoardProof.board.result.heistId='original-run-guid'
        self.raw=self.heists.StageBoard(self.heists,self.raw,self.raw.heistBoardProof.board)[0]
        self.start('heistCollect');self.executor.Drain(self.executor)
        self.assertEqual(len(self.executor.calls),1)
        self.assertEqual(self.executor.calls[1].args[1],'collect')
        self.assertIsNone(self.executor.calls[1].args[2])
        records=self.runtime.checkpoint.Records(self.runtime.checkpoint)
        saved=self.runtime.checkpoint.Recovery(self.runtime.checkpoint,records[1].actionKey)[0]
        self.assertEqual(saved.before.heistBoardProof.board.result.heistId,'original-run-guid')
        self.collected();self.app.Step(self.app,self.raw)
        self.assertEqual(self.runtime.outcomes.heistCollect,'confirmed')
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),0)
    def test_collect_nil_target_closes_only_after_complete_reward_and_level_effect(self):
        self.collect_result();self.start('heistCollect');self.executor.Drain(self.executor)
        self.assertEqual(len(self.executor.calls),1);self.assertEqual(self.executor.calls[1].args[1],'collect');self.assertIsNone(self.executor.calls[1].args[2]);self.assertEqual(self.executor.calls[1].args[3],1)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),1)
        self.collected();self.app.Step(self.app,self.raw)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),0);self.assertIsNone(self.port.pending)
    def test_partial_collection_award_and_disable_keep_original_custody(self):
        self.collect_result();self.start('heistCollect');self.executor.Drain(self.executor);self.app.Set(self.app,'heistCollect.enabled',False)
        self.collected();self.raw.native.inventory.crate_a=2;self.app.Step(self.app,self.raw)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),1)
        self.assertEqual(len(self.executor.calls),1);self.assertIsNotNone(self.port.pending)
    def test_physical_initial_invocation_blocks_status_and_board_borrowing(self):
        self.executor.InvokeOwned=self.h.lua.eval("function(s,token,remote,method,...) s.calls[#s.calls+1]={remote=remote,args=table.pack(...)};coroutine.yield('native_wait');return {pending=true} end")
        self.start();self.h.lua.globals().initialInvocation=self.executor.queued[1]
        self.h.lua.execute('initialThread=coroutine.create(initialInvocation);assert(coroutine.resume(initialThread))')
        self.assertIsNone(self.adapter.ReadLease(self.adapter,'heists'));self.assertIsNone(self.protocol.StatusCall(self.protocol)[0])
        self.h.lua.execute('assert(coroutine.resume(initialThread))');self.assertIsNotNone(self.adapter.ReadLease(self.adapter,'heists'));self.assertIsNotNone(self.protocol.StatusCall(self.protocol)[0])

    def test_generic_text_controls_use_inputs_and_owned_heist_controls_are_available(self):
        self.assertEqual(self.app.ui.handles['familyStamina.custom.selectedPerks'].kind,'Input')
        for feature in ('heists','heistCollect','sabotage','favors'):
            self.assertIsNone(self.app.ui.features[feature].blockedReason,feature)

    def test_native_message_only_start_accepts_owned_run_despite_passive_income(self):
        self.executor.reply=lua_table(self.h.lua,{'ok':True,'msg':'started'})
        self.start();self.executor.Drain(self.executor);self.later()
        self.raw.native.cash=50000.25;self.app.Step(self.app,self.raw)
        self.assertEqual(self.runtime.outcomes.heists,'confirmed');self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),0)
        self.assertEqual(len(self.executor.calls),1)

    def tearDown(self):self.app.Destroy(self.app)


class HeistServerTransferAppTests(unittest.TestCase):
    def fresh(self):
        f = HeistProtocolAppTests(); f.setUp(); self.addCleanup(f.tearDown)
        host = host_fixture.RuntimeHostTests(); host.provided_h = f.h; host.setUp()
        f.h.lua.globals().transferApp = f.app
        host.deps.App = f.h.lua.eval("{start=function()return transferApp end}")
        signal = host.teleport_signal()
        owner, reason = host.host_module.start(host.deps)
        self.assertIsNotNone(owner, reason); self.addCleanup(lambda: owner.Destroy(owner))
        self.assertIsNotNone(signal.callback, "Actual App needs its owned transfer subscription")
        return f, owner, signal

    def test_transfer_before_queued_heist_emission_is_known_unsent(self):
        f, owner, signal = self.fresh()
        f.start()
        self.assertEqual(len(f.executor.queued), 1)
        signal.callback(lua_table(f.h.lua, {"Name": "Started"}))
        f.executor.Drain(f.executor)
        self.assertFalse(f.app.alive)
        self.assertFalse(owner.active)
        self.assertEqual(len(f.executor.calls), 0)
        records = f.runtime.checkpoint.Records(f.runtime.checkpoint)
        for _, record in records.items():
            self.assertTrue(f.runtime.checkpoint.KnownUnsent(f.runtime.checkpoint, record))

    def test_transfer_unsent_fact_recovers_in_new_server_without_counter_adoption(self):
        f, owner, signal = self.fresh()
        f.start()
        signal.callback(lua_table(f.h.lua, {"Name": "Started"}))
        f.executor.Drain(f.executor)
        self.assertEqual(len(f.executor.calls), 0)
        HeistCompletedReceiptAppTests.restart(self, f)
        f.app.Step(f.app, f.raw)
        f.executor.Drain(f.executor)
        self.assertEqual(f.runtime.Status(f.runtime).recoveries.heists, "known_unsent")
        self.assertEqual(len(f.runtime.checkpoint.Records(f.runtime.checkpoint)), 0)
        self.assertEqual((f.port.counter, f.port.writes, len(f.executor.calls)), (0, 0, 0))

    def test_transfer_after_sent_unknown_keeps_exact_checkpoint_without_replay(self):
        f, owner, signal = self.fresh()
        f.start(); f.executor.Drain(f.executor)
        original = f.runtime.checkpoint.Records(f.runtime.checkpoint)[1]
        signal.callback(lua_table(f.h.lua, {"Name": "InProgress"}))
        f.executor.Drain(f.executor)
        records = f.runtime.checkpoint.Records(f.runtime.checkpoint)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[1].actionKey, original.actionKey)
        self.assertFalse(f.runtime.checkpoint.KnownUnsent(f.runtime.checkpoint, records[1]))
        self.assertEqual(len(f.executor.calls), 1)
        self.assertFalse(owner.active)
        self.assertFalse(f.app.alive)


    def test_transfer_during_physical_invocation_never_marks_unsent_or_replays_on_new_server(self):
        f, owner, signal = self.fresh()
        f.executor.InvokeOwned = f.h.lua.eval("""function(s,token,remote,method,...)
            s.calls[#s.calls+1]={remote=remote,args=table.pack(...)}
            coroutine.yield('native_wait');return {ok=true,runId='old-run'} end""")
        f.start()
        f.h.lua.globals().transferInvocation = f.executor.queued[1]
        f.h.lua.execute('transferThread=coroutine.create(transferInvocation);assert(coroutine.resume(transferThread))')
        signal.callback(lua_table(f.h.lua, {"Name": "RequestedFromServer"}))
        f.h.lua.execute('assert(coroutine.resume(transferThread))')
        f.executor.queued = f.h.lua.table()
        original = f.runtime.checkpoint.Records(f.runtime.checkpoint)[1]
        self.assertFalse(f.runtime.checkpoint.KnownUnsent(f.runtime.checkpoint, original))
        HeistCompletedReceiptAppTests.restart(self, f)
        f.app.Set(f.app, 'heists.enabled', True)
        f.app.Resume(f.app)
        f.app.Step(f.app, f.raw); f.executor.Drain(f.executor)
        self.assertEqual(len(f.executor.calls), 1)
        self.assertEqual((f.port.counter, f.port.writes), (0, 0))
        self.assertEqual(f.runtime.checkpoint.Records(f.runtime.checkpoint)[1].actionKey, original.actionKey)
        self.assertIsNone(f.runtime.Status(f.runtime).recoveries.heists)

    def test_transfer_unknown_survives_restart_with_feature_explicitly_enabled(self):
        f, owner, signal = self.fresh()
        f.start(); f.executor.Drain(f.executor)
        original = f.runtime.checkpoint.Records(f.runtime.checkpoint)[1]
        signal.callback(lua_table(f.h.lua, {"Name": "WaitingForServer"}))
        HeistCompletedReceiptAppTests.restart(self, f)
        f.app.Set(f.app, 'heists.enabled', True); f.app.Resume(f.app)
        f.app.Step(f.app, f.raw); f.executor.Drain(f.executor)
        self.assertEqual((len(f.executor.calls), f.port.counter, f.port.writes), (1, 0, 0))
        self.assertEqual(f.runtime.checkpoint.Records(f.runtime.checkpoint)[1].actionKey, original.actionKey)
        self.assertIsNone(f.runtime.Status(f.runtime).recoveries.heists)


class HeistCompletedReceiptAppTests(unittest.TestCase):
    def fresh_case(self, reply="positive", feature="heistCollect"):
        f = HeistProtocolAppTests()
        f.setUp()
        self.addCleanup(f.tearDown)
        if feature == "heistCollect":
            f.collect_result()
            f.raw.heistBoardProof.board.result.heistId = "original-run-guid"
            if reply == "positive": f.executor.reply.xp = 46
            elif reply == "pending": f.executor.reply = lua_table(f.h.lua, {"pending": True})
            elif reply == "rejected": f.executor.reply = lua_table(f.h.lua, {"ok": False, "collected": False})
            elif reply == "dismissal":
                result = f.raw.heistBoardProof.board.result
                result.ok = False
                for field in ("cash", "xp", "gold", "crates", "bonusCrates", "crateId", "bonusCrateId"):
                    result[field] = None
                f.executor.reply = lua_table(f.h.lua, {"ok": True, "collected": False})
            f.raw = f.heists.StageBoard(f.heists, f.raw, f.raw.heistBoardProof.board)[0]
        f.start(feature)
        f.executor.Drain(f.executor)
        self.assertEqual(len(f.executor.calls), 1)
        self.assertEqual(len(f.runtime.checkpoint.Records(f.runtime.checkpoint)), 1)
        if feature == "heistCollect":
            if reply == "dismissal":
                f.later(1, False)
                f.raw.heistBoardProof.board.result = None
            else:
                f.collected()
                f.raw.native.xp = 36
        else: f.later(1, True)
        return f

    def restart(self, f):
        f.app.Destroy(f.app)
        h, deps = f.h, f.heists.deps
        h.at(1)
        h.session["session"] = "new-session"
        deps.identity = lua_table(h.lua, h.session)
        f.raw.session, f.raw.revision, f.raw.capturedAt = "new-session", 0, 1
        f.port = h.lua.execute("return {counter=0,writes=0,running=false,Current=function() return true end,Read=function(s) return {counter=s.counter,pending=s.pending,running=s.running} end,Write=function(s,k,v) s.writes=s.writes+1;s[k]=v end}")
        lease = h.load("src/tabs/heists/NativeHeistLease.luau").new(f.port, h.clock,
            lua_table(h.lua, {"account": "user-a", "place": h.session["place"], "jobId": "new-job", "sourceKey": "a" * 64}),
            lua_table(h.lua, {"id": "new-epoch", "counterSeen": 0}))[0]
        f.protocol = h.load("src/tabs/heists/HeistProtocol.luau").new(lua_table(h.lua, {
            "lease": lease, "clock": h.clock, "identity": h.session,
            "hash": h.lua.eval("function(text) return heistTestHash(text) end"),
            "config": {"xpForLevel": h.lua.eval("function() return 100 end")}}))
        deps.heistProtocol = f.protocol
        f.heists = h.load("src/tabs/heists/Module.luau").new(deps)
        f.favors = h.load("src/tabs/favors/Module.luau").new(deps)
        f.tabs = lua_table(h.lua, [f.heists, f.favors])
        composed, why = h.load("src/tabs/TabComposition.luau").build(f.tabs, h.load("src/ui/Catalog.luau"),
            h.load("src/engine/FeatureRegistry.luau"), h.load("src/tabs/TabSnapshotAssembler.luau"))
        self.assertIsNone(why)
        f.lane = h.load("src/engine/RequestLane.luau").new(h.clock)
        f.adapter = h.load("src/transport/NativeDispatchAdapter.luau").new(
            h.load("src/transport/NativeCallPlan.luau"), f.executor, f.lane, h.clock, None, f.protocol)
        f.runtime = h.load("src/engine/AutomationRuntime.luau").new(lua_table(h.lua, {
            "clock": h.clock, "transport": f.adapter, "storage": f.base.base.storage, "identity": h.session,
            "modules": f.runtime.modules, "features": composed.features, "featurePages": composed.featurePages,
            "tabInstances": f.tabs, "snapshotAssembler": composed.snapshotAssembler}))
        f.app = h.load("src/App.luau").start(lua_table(h.lua, {"Ember": h.load("tests/ember_double.lua")(),
            "Catalog": h.load("src/ui/Catalog.luau"), "Settings": h.load("src/storage/Settings.luau"),
            "EmberAdapter": h.load("src/ui/EmberAdapter.luau"), "HeistsTab": h.load("src/tabs/heists/Module.luau"),
            "FavorsTab": h.load("src/tabs/favors/Module.luau"), "automationRuntimeInstance": f.runtime}))
        f.raw = f.heists.StageBoard(f.heists, f.raw, f.raw.heistBoardProof.board)[0]
        self.assertEqual(len(f.runtime.checkpoint.Records(f.runtime.checkpoint)), 1)
        self.assertIsNone(f.protocol.StatusCall(f.protocol)[0])

    def test_completed_receipt_recovers_through_new_app_without_status_or_counter_write_or_replay(self):
        f = self.fresh_case()
        original = f.runtime.checkpoint.Records(f.runtime.checkpoint)[1]
        saved = f.runtime.checkpoint.Recovery(f.runtime.checkpoint, original.actionKey)[0]
        self.assertEqual(saved.reply.xp, 46)
        self.assertEqual(saved.before.heistBoardProof.board.result.heistId, "original-run-guid")
        self.restart(f)
        f.app.Step(f.app, f.raw)
        f.executor.Drain(f.executor)
        self.assertEqual(f.runtime.Status(f.runtime).recoveries.heistCollect, "confirmed")
        self.assertEqual(len(f.runtime.checkpoint.Records(f.runtime.checkpoint)), 0)
        self.assertEqual((f.port.counter, f.port.writes, len(f.executor.calls)), (0, 0, 1))
        self.assertEqual((saved.proposal.intent.nativeJob, saved.proposal.intent.nativeEpoch), ("job-a", "epoch-a"))
        f.h.at(1.25)
        f.app.Step(f.app, f.raw)
        f.executor.Drain(f.executor)
        self.assertEqual((f.port.counter, f.port.writes, len(f.executor.calls)), (0, 0, 1))

    def test_completed_receipt_rechecks_when_board_read_arrives_for_same_sync(self):
        f = self.fresh_case()
        self.restart(f)
        board = f.raw.heistBoardProof
        f.raw.heistBoardProof = None
        f.app.Step(f.app, f.raw)
        self.assertEqual(len(f.runtime.checkpoint.Records(f.runtime.checkpoint)), 1)
        self.assertIsNone(f.runtime.recoveries.heistCollect)
        # The owned read is attached after the first paused step, without a new Sync.
        f.raw.heistBoardProof = board
        f.app.Step(f.app, f.raw)
        self.assertEqual(f.runtime.recoveries.heistCollect, "confirmed")
        self.assertEqual(len(f.runtime.checkpoint.Records(f.runtime.checkpoint)), 0)
        f.app.Step(f.app, f.raw)
        self.assertEqual((f.port.counter, f.port.writes, len(f.executor.calls)), (0, 0, 1))

    def test_new_app_holds_pending_rejected_and_failed_result_dismissal(self):
        for reply in ("pending", "rejected", "dismissal"):
            with self.subTest(reply=reply):
                f = self.fresh_case(reply=reply)
                self.restart(f)
                f.app.Step(f.app, f.raw)
                f.executor.Drain(f.executor)
                self.assertEqual(len(f.runtime.checkpoint.Records(f.runtime.checkpoint)), 1)
                self.assertIsNone(f.runtime.Status(f.runtime).recoveries.heistCollect)
                self.assertEqual((f.port.counter, f.port.writes, len(f.executor.calls)), (0, 0, 1))

    def test_new_app_keeps_partial_or_unrelated_rewards_and_changed_source_held(self):
        for change in ("partial-item", "missing-origin", "origin-transfer", "unrelated-item", "partial-xp", "extra-xp",
                       "cash", "maxLevel", "prestige", "source", "native-source", "new-mine"):
            with self.subTest(change=change):
                f = self.fresh_case()
                self.restart(f)
                if change == "partial-item": f.raw.native.inventory.crate_a = 2
                elif change == "missing-origin": f.raw.native.inventoryBound = None
                elif change == "origin-transfer":
                    f.raw.native.inventory.crate_a -= 2
                    f.raw.native.inventoryBound.crate_a += 2
                elif change == "unrelated-item": f.raw.native.inventory.unrelated = 1
                elif change == "partial-xp": f.raw.native.xp = 35
                elif change == "extra-xp": f.raw.native.xp = 37
                elif change == "cash": f.raw.native.cash = 1099
                elif change == "maxLevel": f.raw.native.maxLevel = 22
                elif change == "prestige": f.raw.native.prestige = 1
                elif change == "source": f.raw.heistBoardProof.sourceKey = "b" * 64
                elif change == "native-source": f.protocol.lease.scope.sourceKey = "b" * 64
                else: f.raw.heistBoardProof.board.mine = lua_table(f.h.lua, {"id": "other-run", "heistId": "h_a", "endsAt": 2001000})
                f.app.Step(f.app, f.raw)
                f.executor.Drain(f.executor)
                self.assertEqual(len(f.runtime.checkpoint.Records(f.runtime.checkpoint)), 1)
                self.assertEqual((f.port.counter, f.port.writes, len(f.executor.calls)), (0, 0, 1))

    def test_new_app_keeps_changed_scope_and_release_held(self):
        for field in ("account", "place", "release"):
            with self.subTest(field=field):
                f = self.fresh_case()
                self.restart(f)
                f.raw[field] = f.raw.heistBoardProof.header[field] = "changed"
                if field == "account": f.raw.heistBoardProof.account = "changed"
                f.app.Step(f.app, f.raw)
                f.executor.Drain(f.executor)
                self.assertEqual(len(f.runtime.checkpoint.Records(f.runtime.checkpoint)), 1)
                self.assertIsNone(f.runtime.Status(f.runtime).recoveries.heistCollect)
                self.assertEqual((f.port.counter, f.port.writes, len(f.executor.calls)), (0, 0, 1))

    def test_new_app_revalidates_original_baseline_in_decodable_saved_record(self):
        f = self.fresh_case()
        self.restart(f)
        checkpoint = f.runtime.checkpoint
        record = checkpoint.records[1]
        data = checkpoint.Recovery(checkpoint, record.actionKey)[0]
        data.baseline.cash -= 1
        # A structurally valid historical envelope still cannot substitute a
        # baseline that does not recapture exactly from its original before.
        encoded, why = checkpoint.pendingModule.Capture(data.proposal, data.before, data.baseline, data.reply)
        self.assertIsNone(why)
        record.recovery = encoded
        self.assertIsNotNone(checkpoint.Recovery(checkpoint, record.actionKey)[0])
        f.app.Step(f.app, f.raw)
        f.executor.Drain(f.executor)
        self.assertEqual(len(checkpoint.Records(checkpoint)), 1)
        self.assertIsNone(f.runtime.Status(f.runtime).recoveries.heistCollect)
        self.assertEqual((f.port.counter, f.port.writes, len(f.executor.calls)), (0, 0, 1))

    def test_older_unknown_start_stays_held_in_new_app(self):
        f = self.fresh_case(feature="heists")
        key = f.runtime.checkpoint.Records(f.runtime.checkpoint)[1].actionKey
        self.restart(f)
        f.app.Step(f.app, f.raw)
        f.executor.Drain(f.executor)
        self.assertEqual(len(f.runtime.checkpoint.Records(f.runtime.checkpoint)), 1)
        self.assertEqual(f.runtime.checkpoint.Records(f.runtime.checkpoint)[1].actionKey, key)
        self.assertIsNone(f.runtime.Status(f.runtime).recoveries.heists)
        self.assertEqual((f.port.counter, f.port.writes, len(f.executor.calls)), (0, 0, 1))
