"""Actual App/broker lifecycle with a bounded fixture planner; production PvP remains blocked."""
import unittest
import test_family_claim_read_pipeline as app_fixture
import test_player_fight_evidence as result_fixture
from engine_harness import lua_table

class PlayerFightAppTests(unittest.TestCase):
    def setUp(self):
        self.f=app_fixture.FamilyClaimReadPipelineTests();self.f.setUp();self.h=self.f.h
        self.f.app.Destroy(self.f.app)
        self.result=result_fixture.PlayerFightEvidenceTests();self.result.provided_h=self.h;self.result.setUp()
        self.start()
    def start(self):
        f,h=self.f,self.h
        self.lane=h.load('src/engine/RequestLane.luau').new(h.clock)
        self.source=h.lua.execute("""return {Current=function() return true end,CanAttack=function() return true end,
            Subscribe=function(self,cb) self.callback=cb;return {Disconnect=function() self.disconnected=true end} end}""")
        self.receipts=h.load('src/tabs/combat/FightReceipts.luau')
        self.owner=self.receipts.new(lua_table(h.lua,h.session),h.clock,self.lane,self.source,'a'*64)
        self.e=h.load('src/tabs/combat/PlayerFightEvidence.luau').new(self.receipts)
        self.ledger=h.load('src/tabs/combat/PlayerFightLedger.luau').new(f.base.storage,lua_table(h.lua,h.session),self.e)[0]
        self.tab=self.tab_factory(self) if hasattr(self,"tab_factory") else f.tab
        self.tab.closed=False;self.tab.fightReceipts=self.owner;self.tab.playerEvidence=self.e
        if not hasattr(self,'tab_factory'):
            self.tab.hitListQuery=h.load('src/tabs/combat/HitListQuery.luau').new(lua_table(h.lua,h.session),'a'*64)
        self.tab.playerLedger=self.ledger
        # Seed the actual query owner through its response acceptance boundary.
        if h.session['session']==self.result.before.session:
            call=self.tab.hitListQuery.Prepare(self.tab.hitListQuery,self.result.before)[0]
            response=lua_table(h.lua,{'ok':True,'list':[{'userId':42,'name':'Target B','level':128,'stamina':1,'shielded':False}]})
            staged=self.tab.hitListQuery.Accept(self.tab.hitListQuery,self.result.before,call,response)[0]
            self.assertTrue(self.tab.hitListQuery.Commit(self.tab.hitListQuery,staged))
        self.spec=next(row for row in self.tab.Descriptors(self.tab).values() if row.id=='combat')
        h.lua.globals().fixtureFightProposal=self.result.p;h.lua.globals().fixtureFightReply=lua_table(h.lua,self.result.initial)
        # Source/planner admission is deliberately frozen here. This exercises the
        # real application, storage, broker and adapter without claiming policy closure.
        fake=h.lua.execute("""return {read=function(raw) return raw end,propose=function(view,settings)
            if settings.enabled then return fixtureFightProposal end
        end}""")
        if not hasattr(self,"tab_factory"): self.spec.reader=fake;self.spec.planner=fake
        self.executor=h.lua.execute("""return {queued={},calls=0,Invoke=function() error('Unowned call') end,Schedule=function(self,fn) self.queued[#self.queued+1]=fn;return true end,
            InvokeOwned=function(self,token,remote,method,target) self.calls=self.calls+1;assert(remote=='Attack' and target==42);return fixtureFightReply end}""")
        plan=h.lua.execute("""return {describe=function(p) return {remote='Attack',method='InvokeServer',arity=1,args={p.intent.target}} end}""")
        if hasattr(self,'plan_factory'): plan=self.plan_factory(self)
        self.transport=h.load('src/transport/NativeDispatchAdapter.luau').new(plan,self.executor,self.lane,h.clock,self.owner)
        f.base.runtime.modules.PlayerFightUsage=h.load('src/tabs/combat/PlayerFightUsage.luau')
        self.runtime=h.load('src/engine/AutomationRuntime.luau').new(lua_table(h.lua,{'clock':h.clock,'transport':self.transport,
            'storage':f.base.storage,'identity':h.session,'modules':f.base.runtime.modules,
            'features':[self.spec]+([next(row for row in self.tab.Descriptors(self.tab).values() if row.id=='warCombat')] if getattr(self,'include_war',False) else []),
            'tabInstances':[self.tab],'featurePages':{'combat':'combat','warCombat':'combat'},
            'snapshotAssembler':h.load('src/tabs/TabSnapshotAssembler.luau').new(lua_table(h.lua,[self.tab]))}))
        self.app=h.load('src/App.luau').start(lua_table(h.lua,{'Ember':h.load('tests/ember_double.lua')(),
            'Catalog':h.load('src/ui/Catalog.luau'),'Settings':h.load('src/storage/Settings.luau'),
            'PlayerTab':h.load('src/tabs/player/Module.luau'),
            'EmberAdapter':h.load('src/ui/EmberAdapter.luau'),'automationRuntimeInstance':self.runtime}))
    def step(self,raw=None):
        return self.app.Step(self.app,raw or self.result.before)
    def begin(self):
        self.app.Set(self.app,'combat.enabled',True);self.app.Resume(self.app);self.step()
        self.assertEqual(len(self.executor.queued),1,str(dict(self.runtime.Status(self.runtime).reasons.items())))
    def send(self):
        self.executor.queued[1]();self.assertEqual(self.executor.calls,1)
    def settle(self):
        self.source.callback('fightcash','',lua_table(self.h.lua,self.result.final))
        self.h.at(.25);self.result.after.capturedAt=.25;self.step(self.result.after)
    def test_exact_fight_settles_and_persists_history_before_clearing_custody(self):
        self.begin();self.send();self.settle()
        self.assertEqual(self.runtime.Status(self.runtime).outcomes.combat,'confirmed')
        self.assertEqual(self.ledger.Summary(self.ledger).fights,1)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),0)
        self.assertEqual(self.runtime.checkpoint.Allowance(self.runtime.checkpoint,'combat')[0].attackSpent,1)
        self.assertTrue(self.source.disconnected)
    def test_disable_while_queued_refunds_only_definitely_unsent_attempt(self):
        self.begin();self.app.Set(self.app,'combat.enabled',False);self.step();self.executor.queued[1]()
        self.assertEqual(self.executor.calls,0);self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),0)
        self.assertEqual(self.runtime.checkpoint.Allowance(self.runtime.checkpoint,'combat')[0].attackSpent,0)
    def test_sent_disable_retains_receipt_observation_and_settles_without_second_send(self):
        self.begin();self.send();self.app.Set(self.app,'combat.enabled',False);self.settle()
        self.assertEqual(self.ledger.Summary(self.ledger).fights,1);self.assertEqual(self.executor.calls,1)
    def test_unknown_or_timeout_keeps_custody_and_charge_without_history_success(self):
        self.begin();self.send();self.h.at(45);raw=self.result.after;raw.capturedAt=45;self.step(raw)
        self.assertEqual(self.runtime.Status(self.runtime).outcomes.combat,'skipped_unconfirmed')
        self.assertEqual(self.ledger.Summary(self.ledger).fights,0)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),1)
        self.assertEqual(self.runtime.checkpoint.Allowance(self.runtime.checkpoint,'combat')[0].attackSpent,1)
    def test_unload_fences_queued_call_and_late_notification(self):
        self.begin();self.send();cb=self.source.callback;self.app.Destroy(self.app)
        cb('fightcash','',lua_table(self.h.lua,self.result.final))
        self.assertEqual(self.ledger.Summary(self.ledger).fights,0)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),1)
    def test_history_save_failure_retains_confirmed_execution_in_unresolved_custody(self):
        self.begin();self.send();self.f.base.storage.Write=self.h.lua.eval('function(self,k,v) if k:find("player-fights",1,true) then return false end self.data[k]=v;return true end')
        self.settle();self.assertEqual(self.runtime.Status(self.runtime).outcomes.combat,'confirmed')
        self.assertTrue(self.runtime.Status(self.runtime).storageFault)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),1)
        self.assertEqual(self.ledger.Summary(self.ledger).fights,0)
    def test_durable_history_recovers_interrupted_generic_cleanup_after_reload_all_off(self):
        self.begin();self.send()
        self.f.base.storage.Write=self.h.lua.eval('function(self,k,v) if k:find(":checkpoint:",1,true) and #v.records==0 then return false end self.data[k]=v;return true end')
        self.settle();self.assertEqual(self.ledger.Summary(self.ledger).fights,1)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),1)
        self.app.Destroy(self.app)
        self.f.base.storage.Write=self.h.lua.eval('function(self,k,v) self.data[k]=v;return true end')
        self.h.session['session']='fresh-session';self.start()
        raw=self.result.after;raw.session='fresh-session';raw.revision=3;raw.capturedAt=.5;self.h.at(.5)
        self.step(raw)
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.combat,'confirmed')
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),0)
        self.assertEqual(self.ledger.Summary(self.ledger).fights,1)
        self.assertEqual(self.executor.calls,0)
    def test_native_rejection_keeps_attempt_charge_but_has_no_success_history(self):
        self.h.lua.globals().fixtureFightReply=lua_table(self.h.lua,{'ok':False,'code':'target_hospitalized'})
        self.begin();self.send();self.h.at(.25)
        raw=self.result.before;raw.revision=2;raw.capturedAt=.25;raw.native.serverNow+=1;self.step(raw)
        self.assertEqual(self.runtime.Status(self.runtime).outcomes.combat,'rejected')
        self.assertEqual(self.ledger.Summary(self.ledger).fights,0)
        self.assertEqual(self.runtime.checkpoint.Allowance(self.runtime.checkpoint,'combat')[0].attackSpent,1)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),0)
    def test_unload_before_queued_send_never_invokes_and_next_owner_refunds_known_unsent(self):
        self.begin();old=self.executor;self.app.Destroy(self.app);old.queued[1]()
        self.assertEqual(old.calls,0)
        self.h.session['session']='fresh-session';self.start()
        raw=self.result.after;raw.session='fresh-session';raw.revision=3;raw.capturedAt=.25;self.h.at(.25);self.step(raw)
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.combat,'known_unsent')
        self.assertEqual(self.runtime.checkpoint.Allowance(self.runtime.checkpoint,'combat')[0].attackSpent,0)
        self.assertEqual(self.executor.calls,0)
    def test_terminal_receipt_before_next_step_survives_graceful_unload_and_recovers_all_off(self):
        self.begin();self.send()
        self.source.callback('fightcash','',lua_table(self.h.lua,self.result.final))
        self.app.Destroy(self.app)
        self.assertEqual(self.ledger.Summary(self.ledger).fights,1)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),1)
        self.h.session['session']='fresh-session';self.start()
        raw=self.result.after;raw.session='fresh-session';raw.revision=3;raw.capturedAt=.25;self.h.at(.25);self.step(raw)
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.combat,'confirmed')
        self.assertEqual(self.executor.calls,0);self.assertEqual(self.ledger.Summary(self.ledger).fights,1)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),0)
    def test_canceled_or_expired_terminal_receipt_is_not_flushed_as_success_on_unload(self):
        self.begin();self.send();bad=lua_table(self.h.lua,self.result.final);bad.ok=False
        self.source.callback('fightcash','',bad);self.app.Destroy(self.app)
        self.assertEqual(self.ledger.Summary(self.ledger).fights,0)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),1)
        self.assertEqual(self.runtime.checkpoint.Allowance(self.runtime.checkpoint,'combat')[0].attackSpent,1)
    def test_failed_close_receipt_save_keeps_unresolved_custody_and_does_not_count_history(self):
        self.begin();self.send()
        self.f.base.storage.Write=self.h.lua.eval('function(self,k,v) if k:find("player-fights",1,true) then return false end self.data[k]=v;return true end')
        self.source.callback('fightcash','',lua_table(self.h.lua,self.result.final))
        self.app.Destroy(self.app)
        self.assertEqual(self.ledger.Summary(self.ledger).fights,0)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),1)
    def test_deadline_receipt_cannot_be_persisted_by_close_after_the_lease_expired(self):
        self.begin();self.send();self.h.at(45)
        self.source.callback('fightcash','',lua_table(self.h.lua,self.result.final));self.app.Destroy(self.app)
        self.assertEqual(self.ledger.Summary(self.ledger).fights,0)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),1)
    def test_close_history_write_can_yield_reentrant_close_and_step_without_another_send(self):
        self.begin();self.send()
        self.h.lua.globals().closingRuntime=self.runtime;self.h.lua.globals().closingRaw=self.result.before
        self.f.base.storage.Write=self.h.lua.eval("function(self,k,v) if k:find('player-fights',1,true) then closingRuntime:Close();closingRuntime:Step(closingRaw,{combat={enabled=true}}) end self.data[k]=v;return true end")
        self.source.callback('fightcash','',lua_table(self.h.lua,self.result.final))
        self.app.Destroy(self.app)
        self.assertEqual(self.ledger.Summary(self.ledger).fights,1);self.assertEqual(self.executor.calls,1)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),1)
    def test_ambiguous_close_write_recovers_only_from_the_actual_durable_history(self):
        self.begin();self.send()
        self.f.base.storage.Write=self.h.lua.eval("function(self,k,v) self.data[k]=v;if k:find('player-fights',1,true) then return false end return true end")
        self.source.callback('fightcash','',lua_table(self.h.lua,self.result.final))
        self.app.Destroy(self.app);self.assertEqual(self.ledger.Summary(self.ledger).fights,0)
        self.f.base.storage.Write=self.h.lua.eval('function(self,k,v) self.data[k]=v;return true end')
        self.h.session['session']='fresh-session';self.start()
        raw=self.result.after;raw.session='fresh-session';raw.revision=3;raw.capturedAt=.25;self.h.at(.25);self.step(raw)
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.combat,'confirmed')
        self.assertEqual(self.ledger.Summary(self.ledger).fights,1);self.assertEqual(self.executor.calls,0)
    def test_terminal_receipt_is_durable_without_tick_or_graceful_close(self):
        self.begin();self.send()
        self.source.callback('fightcash','',lua_table(self.h.lua,self.result.final))
        self.assertEqual(self.ledger.Summary(self.ledger).fights,1)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),1)
        # Simulate a hard interruption: discard observers without App.Destroy's flush.
        self.owner.Close(self.owner);self.ledger.Close(self.ledger);self.runtime.session.Close(self.runtime.session)
        self.h.session['session']='fresh-session';self.start()
        raw=self.result.after;raw.session='fresh-session';raw.revision=3;raw.capturedAt=.25;self.h.at(.25)
        self.step(raw)
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.combat,'confirmed')
        self.assertEqual(self.executor.calls,0)
        self.assertEqual(self.ledger.Summary(self.ledger).fights,1)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),0)

    def test_terminal_notification_before_initial_return_is_persisted_after_reply_save(self):
        self.h.lua.globals().receiptSource=self.source
        self.h.lua.globals().terminalPacket=lua_table(self.h.lua,self.result.final)
        self.executor.InvokeOwned=self.h.lua.eval("function(self) self.calls=self.calls+1;receiptSource.callback('fightcash','',terminalPacket);return fixtureFightReply end")
        self.begin();self.send()
        self.assertEqual(self.ledger.Summary(self.ledger).fights,1)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),1)
        self.assertEqual(self.executor.calls,1)

    def test_duplicate_terminal_notifications_do_not_repeat_durable_writes(self):
        self.h.lua.globals().countedStorage=self.f.base.storage
        self.h.lua.execute("local original=countedStorage.Write;countedStorage.fightWrites=0;countedStorage.Write=function(self,k,v) if k:find('player-fights',1,true) then self.fightWrites=self.fightWrites+1 end return original(self,k,v) end")
        self.begin();self.send()
        for _ in range(3): self.source.callback('fightcash','',lua_table(self.h.lua,self.result.final))
        self.assertEqual(self.f.base.storage.fightWrites,1)
        self.settle()
        self.assertEqual(self.f.base.storage.fightWrites,1)
        self.assertEqual(self.ledger.Summary(self.ledger).fights,1)

    def test_incomplete_receipt_hard_interruption_does_not_invent_a_settlement(self):
        self.begin();self.send()
        partial=lua_table(self.h.lua,self.result.final);partial.cashStage=3;partial.rewardsPending=True
        self.source.callback('fightcash','',partial)
        self.assertEqual(self.ledger.Summary(self.ledger).fights,0)
        self.owner.Close(self.owner);self.ledger.Close(self.ledger);self.runtime.session.Close(self.runtime.session)
        self.h.session['session']='fresh-session';self.start()
        raw=self.result.after;raw.session='fresh-session';raw.revision=3;raw.capturedAt=.25;self.h.at(.25)
        self.step(raw)
        self.assertNotEqual(self.runtime.Status(self.runtime).recoveries.combat,'confirmed')
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),1)
        self.assertEqual(self.executor.calls,0)

    def test_wrong_fight_terminal_receipt_never_writes_history(self):
        self.begin();self.send()
        wrong=lua_table(self.h.lua,self.result.final);wrong.fightId='unrelated-manual-fight'
        self.source.callback('fightcash','',wrong)
        self.assertEqual(self.ledger.Summary(self.ledger).fights,0)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),1)

    def test_initial_checkpoint_reply_write_failure_cannot_persist_buffered_terminal(self):
        self.h.lua.globals().receiptSource=self.source
        self.h.lua.globals().terminalPacket=lua_table(self.h.lua,self.result.final)
        self.executor.InvokeOwned=self.h.lua.eval("function(self) self.calls=self.calls+1;receiptSource.callback('fightcash','',terminalPacket);return fixtureFightReply end")
        self.begin()
        self.f.base.storage.Write=self.h.lua.eval('function(self,k,v) if k:find(":checkpoint:",1,true) then return false end self.data[k]=v;return true end')
        self.send()
        self.assertEqual(self.ledger.Summary(self.ledger).fights,0)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),1)
        self.assertTrue(self.runtime.Status(self.runtime).storageFault)

    def test_conflicting_buffered_terminals_refuse_acceptance_and_remain_held_after_restart(self):
        h=self.h
        h.lua.globals().receiptSource=self.source;h.lua.globals().terminalPacket=lua_table(h.lua,self.result.final)
        other=lua_table(h.lua,self.result.final);other.cashConfirmed+=1;other.stolen+=1;h.lua.globals().conflictingPacket=other
        self.executor.InvokeOwned=h.lua.eval("function(self) self.calls=self.calls+1;receiptSource.callback('fightcash','',terminalPacket);receiptSource.callback('fightcash','',conflictingPacket);return fixtureFightReply end")
        self.begin();self.send()
        self.assertEqual(self.owner.Read(self.owner,self.result.before).attempts[1].status,'ambiguous')
        self.assertEqual(self.ledger.Summary(self.ledger).fights,0)
        self.owner.Close(self.owner);self.ledger.Close(self.ledger);self.runtime.session.Close(self.runtime.session)
        h.session['session']='fresh-session';self.start()
        raw=self.result.after;raw.session='fresh-session';raw.revision=3;raw.capturedAt=.25;h.at(.25);self.step(raw)
        self.assertNotEqual(self.runtime.Status(self.runtime).recoveries.combat,'confirmed')
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),1)
        self.assertEqual(self.executor.calls,0)

    def test_accepted_terminal_seals_listener_before_storage_can_yield(self):
        h=self.h;self.begin();self.send()
        h.lua.globals().receiptSource=self.source
        other=lua_table(h.lua,self.result.final);other.cashConfirmed+=1;other.stolen+=1;h.lua.globals().conflictingPacket=other
        h.lua.globals().testStorage=self.f.base.storage
        h.lua.execute("local original=testStorage.Write;testStorage.Write=function(self,k,v) if k:find('player-fights',1,true) then assert(receiptSource.disconnected);receiptSource.callback('fightcash','',conflictingPacket);coroutine.yield('terminal-write') end return original(self,k,v) end")
        h.lua.globals().terminalPacket=lua_table(h.lua,self.result.final)
        thread=h.lua.eval("coroutine.create(function() receiptSource.callback('fightcash','',terminalPacket) end)").coroutine()
        self.assertEqual(next(thread),'terminal-write')
        self.assertEqual(self.owner.Read(self.owner,self.result.before).attempts[1].status,'settled')
        self.assertRaises(StopIteration,next,thread)
        self.assertEqual(self.ledger.Summary(self.ledger).fights,1)
        self.assertEqual(self.ledger.Summary(self.ledger).cash,self.result.final['cashConfirmed'])
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),1)

    def tearDown(self):
        self.app.Destroy(self.app);self.f.reader.Close(self.f.reader)
