"""Actual Recall App, checkpoint, composed transport and shared status reads."""
import unittest
import test_runtime_host as host_fixture
from engine_harness import lua_table,ROOT
from recall_source_fixture import make_recall_client
import test_automation_runtime as base_fixture

class RecallRuntimeAppTests(unittest.TestCase):
    def setUp(self):
        base=base_fixture.AutomationRuntimeTests();base.setUp();self.h=base.h;self.modules=base.runtime.modules;self.storage=base.storage
        base.runtime.Close(base.runtime);self.storage.Write=self.h.lua.eval('function(self,k,v) self.data[k]=v;return true end')
        _,self.native=make_recall_client(self.h)
        self.storage.hash=self.native.env.crypt.hash
        self.lease=self.h.load('src/tabs/territory/NativeRecallLease.luau').bind(lua_table(self.h.lua,{'game':self.native.game,'env':self.native.env,
            'registry':self.native.registry,'requireModule':self.native.requireModule,'clock':self.h.clock,'account':'user-a'}))[0]
        self.assertTrue((ROOT/'src/tabs/territory/RecallRuntime.luau').is_file(),'Recall runtime owner is missing')
        self.recall=self.h.load('src/tabs/territory/RecallRuntime.luau').new(lua_table(self.h.lua,{'lease':self.lease,
            'transactions':self.h.load('src/tabs/territory/RecallTransactions.luau'),'identity':self.h.session,'storage':self.storage,
            'clock':self.h.clock,'cooldownSeconds':600}))[0]
        self.assertIsNotNone(self.recall)
        self.before=self.raw();self.h.lua.globals().recallAppRaw=self.before
        self.executor=self.h.lua.execute('''return {calls={},queued={},reply={ok=true,pending=true},status={ok=true,pending=true},
            Schedule=function(self,fn) self.queued[#self.queued+1]=fn;return true end,Invoke=function()error('unowned')end,
            InvokeOwned=function(self,token,remote,method,command,id,targets)
                self.calls[#self.calls+1]={remote=remote,command=command,id=id,targets=targets}
                if self.yieldInvoke then coroutine.yield('recall-invoke') end
                if remote=='TerritoryStatus' then return self.status end
                assert(remote=='TerritoryAction' and command=='recallcrew' and #targets==1);return self.reply
            end}''')
        self.start()
        for key,value in {'mode':'Recall','districtId':'d1','memberSlot':2,'minGarrison':1,'maxAttempts':2}.items():
            self.assertTrue(self.app.Set(self.app,'station.custom.'+key,value)[0])
    def raw(self,revision=1,home=False,captured=0):
        raw=self.h.snapshot(revision=revision,captured_at=captured,native={'fullSync':True,'userId':42,'serverNow':1000+revision-1,
            'family':{'id':'own-family'},'crew':[{'name':'Player'},
                {'name':'Guard','rarity':4,'train':2,'healId':'guard','duty':None if home else 'd1','dutyToken':None if home else 'deployment-a','dutyAt':None if home else 900},
                {'name':'Medic','rarity':3,'train':1,'healId':'medic'}]})
        query=self.h.load('src/tabs/territory/DistrictQuery.luau').new();request=query.Prepare(query,'d1',raw)[0]
        raw.territoryDistrict=query.Accept(query,request,lua_table(self.h.lua,{'ok':True,'district':{'id':'d1','mine':True,'holderId':'own-family',
            'garrisonCount':3,'garrisonCap':200,'revision':7}}))[0]
        raw.territoryMap=lua_table(self.h.lua,{'header':{**self.h.session,'revision':revision,'capturedAt':captured},'cityId':'vespera','districts':[{'id':'d1','mine':True}]})
        return raw
    def start(self,lazy_recall=False,with_reads=False):
        h=self.h
        deps={name:h.load(path) for name,path in {'TerritoryMapQuery':'src/tabs/territory/TerritoryMapQuery.luau',
            'ResidencyQuery':'src/tabs/territory/ResidencyQuery.luau','TerritoryState':'src/tabs/territory/TerritoryState.luau',
            'ReadAttachment':'src/tabs/territory/ReadAttachment.luau','TerritoryBlocked':'src/tabs/territory/TerritoryBlocked.luau',
            'Stationing':'src/tabs/territory/Stationing.luau'}.items()}
        deps.update({'nativeRecallRuntime':self.recall,'config':{'TERRITORY':{'garrisonCap':200}},'gameData':{'DISTRICTS_BY_ID':{'d1':{'city':'vespera'}}},
            'fingerprint':'a'*64,'release':'release-a'})
        if lazy_recall:
            deps.pop('nativeRecallRuntime',None)
            deps.update({'nativeRecallLease':self.lease,'RecallRuntime':h.load('src/tabs/territory/RecallRuntime.luau'),
                'RecallTransactions':h.load('src/tabs/territory/RecallTransactions.luau'),'storage':self.storage,'clock':h.clock,
                'identity':h.session,'config':{'TERRITORY':{'garrisonCap':200,'recallCooldownSeconds':600}}})
        if with_reads:
            for name in ('TerritoryReadSources','DistrictQuery','FortificationQuery'):
                deps[name]=h.load('src/tabs/territory/'+name+'.luau')
            deps['territoryCitySource']=h.lua.execute("return {Current=function()return true end,Select=function()return {cityId='vespera'}end}")
            self.reader=h.load('src/transport/NativeSnapshotReader.luau').new(lua_table(h.lua,h.session),h.clock,'a'*64)
            self.reader.ObserveSync(self.reader,self.before.native)
            h.lua.globals().recallReadsExecutor=self.executor
            h.lua.execute("""
                local invoke=recallReadsExecutor.InvokeOwned
                recallReadsExecutor.readCalls={}
                function recallReadsExecutor:InvokeOwned(token,remote,method,command,...)
                    if remote~='TerritoryView'then return invoke(self,token,remote,method,command,...)end
                    self.readCalls[#self.readCalls+1]=command
                    if command=='map'then return {ok=true,city='vespera',territoryCapacity={familyId='own-family'},districts={{id='d1',mine=true}}}end
                    assert(command=='district')
                    return {ok=true,district={id='d1',mine=true,holderId='own-family',garrisonCount=3,garrisonCap=200,revision=7}}
                end
            """)
        self.tab=h.load('src/tabs/territory/Module.luau').new(lua_table(h.lua,deps))
        if lazy_recall:
            self.assertIsNotNone(self.tab.recall,'Temporary manual activity must not permanently remove Recall owner')
            self.recall=self.tab.recall
        native=h.load('src/transport/NativeCallPlan.luau');territory=h.load('src/tabs/territory/TerritoryCallPlan.luau')
        self.assertIsNotNone(territory.withRecall,'Bound Recall call-plan composition is missing')
        plan=native.withTerritory(native,territory.withRecall(territory,self.recall))
        self.lane=h.load('src/engine/RequestLane.luau').new(h.clock)
        transport=h.load('src/transport/NativeDispatchAdapter.luau').new(plan,self.executor,self.lane,h.clock)
        self.transport=self.recall.WrapTransport(self.recall,transport)
        self.runtime=h.load('src/engine/AutomationRuntime.luau').new(lua_table(h.lua,{'clock':h.clock,'transport':self.transport,'storage':self.storage,
            'identity':h.session,'modules':self.modules,'features':[self.tab.Descriptors(self.tab)[2]],'tabInstances':[self.tab],'featurePages':{'station':'territory'},
            'snapshotAssembler':h.load('src/tabs/TabSnapshotAssembler.luau').new(lua_table(h.lua,[self.tab])),'reservationSources':self.tab.ReservationSources(self.tab)}))
        self.recall.BindCheckpoint(self.recall,self.runtime.checkpoint,h.lua.eval('function() return recallAppRaw end'))
        sources=self.tab.ReadSources(self.tab,self.reader if with_reads else None)
        specs=[{'id':row.id,'interval':row.interval} for row in sources.values()]
        budget=h.load('src/engine/ReadBudget.luau').new(h.clock,lua_table(h.lua,specs),5,60)
        self.runtime.readSources=sources
        self.runtime.readCoordinator=h.load('src/transport/ReadCoordinator.luau').new(lua_table(h.lua,{'clock':h.clock,'lane':self.lane,'budget':budget,
            'executor':self.executor,'sources':sources,'currentSnapshot':h.lua.eval('function() return recallAppRaw end'),
            'borrowLease':h.lua.eval('function(feature) return recallTransport:ReadLease(feature) end')}))
        h.lua.globals().recallTransport=self.transport
        self.app=h.load('src/App.luau').start(lua_table(h.lua,{'Ember':h.load('tests/ember_double.lua')(),'Catalog':h.load('src/ui/Catalog.luau'),
            'Settings':h.load('src/storage/Settings.luau'),'EmberAdapter':h.load('src/ui/EmberAdapter.luau'),'automationRuntimeInstance':self.runtime}))
    def step(self,raw=None):
        raw=raw or self.before;self.h.lua.globals().recallAppRaw=raw;self.native.ctx.State.data=raw.native
        return self.app.Step(self.app,raw)
    def begin(self):
        self.app.Set(self.app,'station.enabled',True);self.app.Resume(self.app);self.step()
        self.assertEqual(len(self.executor.queued),1,str(dict(self.runtime.Status(self.runtime).reasons.items())))
    def send(self):self.executor.queued[1]();self.assertEqual(len(self.executor.calls),1)
    def settled(self):return lua_table(self.h.lua,{'ok':True,'settled':[self.native.target]})
    def test_station_mode_reports_missing_other_member_identity_without_sending_recall(self):
        self.before.native.crew[2].healId=None
        # A unique deployment token now identifies an unselected legacy member.
        # This case must lack both supported identities to remain ambiguous.
        self.before.native.crew[2].dutyToken=None
        self.app.Set(self.app,'station.custom.mode','Station')
        self.app.Set(self.app,'station.custom.memberSlot',3)
        self.app.Set(self.app,'station.custom.minHome',0)
        self.app.Set(self.app,'station.enabled',True);self.app.Resume(self.app)
        self.step()
        reason=self.runtime.Status(self.runtime).reasons.station
        self.assertIn('Crew slot 2 lacks a stable member identity',reason)
        self.assertEqual(len(self.executor.calls),0);self.assertEqual(len(self.executor.queued),0)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),0)
        self.assertEqual(self.runtime.checkpoint.stationAttempts,0)

    def test_sync_interruption_does_not_backoff_a_district_before_its_map_exists(self):
        self.h.lua.globals().recallReadNativeContext=self.native.ctx
        self.native.clockModule.Value.now=self.h.lua.eval(
            "function() return recallReadNativeContext.State.data.serverNow or 1000 end")
        self.restart(with_reads=True)
        def step_reader():
            return self.step(self.reader.Capture(self.reader)[0])
        def drain():
            while len(self.executor.queued):
                queued=self.executor.queued;self.executor.queued=self.h.lua.table()
                for callback in queued.values():callback()
        def sync(at,revision,home=False):
            self.h.at(at)
            self.reader.ObserveSync(self.reader,self.raw(revision,home,at).native)
        step_reader();drain()
        self.assertIsNotNone(self.reader.Capture(self.reader)[0].territoryMap)
        # Other confirmed work emits fresh Syncs. Map invalidation is expected;
        # waiting for its replacement must not consume district failure backoff.
        sync(.1,2);step_reader();drain()
        sync(10.2,3);step_reader();drain()
        sync(15.1,4);step_reader();drain()
        self.h.at(15.2);step_reader();drain()
        self.assertEqual(list(self.executor.readCalls.values()),['map','map','district'])
        self.assertEqual(len(self.executor.calls),0)
        self.executor.reply=self.settled()
        self.h.at(15.3);step_reader();drain()
        status=self.runtime.Status(self.runtime)
        self.assertEqual(len(self.executor.calls),1,(status.reasons.station,status.globalReason))
        sync(15.4,5,True);step_reader()
        self.assertEqual(self.runtime.Status(self.runtime).outcomes.station,'confirmed')
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),0)

    def test_actual_one_own_recall_sends_exact_target_and_confirms_only_new_member_home(self):
        self.executor.reply=self.settled();self.begin();self.send();self.h.at(.25)
        self.step(self.raw(2,True,.25));self.assertEqual(self.runtime.Status(self.runtime).outcomes.station,'confirmed')
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),0);self.assertEqual(self.recall.owner.Usage(self.recall.owner).attempted,1)
        self.assertEqual((self.executor.calls[1].command,self.executor.calls[1].targets[1].userId,self.executor.calls[1].targets[1].deploymentId),('recallcrew',42,'deployment-a'))
        self.assertEqual(self.native.calls,0)
    def test_pending_then_unknown_request_then_terminal_uses_status_only_without_replay(self):
        self.begin();self.send();self.h.at(.25);self.before.capturedAt=.25;self.before.territoryDistrict.header.capturedAt=.25;self.before.territoryMap.header.capturedAt=.25;self.step()
        self.assertEqual(len(self.executor.queued),2,str(self.runtime.readCoordinator.Status(self.runtime.readCoordinator).reasons['territoryRecallStatus']))
        self.executor.status=lua_table(self.h.lua,{'ok':False,'code':'unknown_request'});self.executor.queued[2]();self.assertEqual(self.executor.calls[2].command,'recallstatus')
        self.h.at(3.5);raw=self.raw(2,False,3.5);self.before=raw;self.step(raw)
        self.assertEqual(len(self.executor.queued),3);self.executor.status=self.settled();self.executor.queued[3]()
        self.h.at(3.75);self.step(self.raw(3,True,3.75));self.assertEqual(self.runtime.Status(self.runtime).outcomes.station,'confirmed')
        self.assertEqual([x.command for x in self.executor.calls.values()],['recallcrew','recallstatus','recallstatus'])
    def test_zero_cap_defender_reserve_foreign_user_and_changed_native_member_never_send(self):
        self.app.Set(self.app,'station.custom.maxAttempts',0);self.app.Set(self.app,'station.enabled',True);self.app.Resume(self.app);self.step()
        self.assertEqual(len(self.executor.queued),0)
        self.app.Set(self.app,'station.custom.maxAttempts',2);self.app.Set(self.app,'station.custom.minGarrison',3);self.step();self.assertEqual(len(self.executor.queued),0)
        self.app.Set(self.app,'station.custom.minGarrison',1);self.step();self.assertEqual(len(self.executor.queued),1)
        self.native.ctx.State.data.crew[2].healId='changed';self.executor.queued[1]();self.assertEqual(len(self.executor.calls),0)
    def test_disable_queued_recall_refunds_only_definitely_unsent_attempt(self):
        self.begin();self.app.Set(self.app,'station.enabled',False);self.step();self.executor.queued[1]()
        self.assertEqual(len(self.executor.calls),0);self.assertEqual(self.recall.owner.Usage(self.recall.owner).attempted,0);self.assertFalse(self.native.api.busy())
    def test_explicit_negative_requires_no_effect_and_retains_attempt(self):
        self.executor.reply=lua_table(self.h.lua,{'ok':False,'code':'deployment_changed'});self.begin();self.send();self.h.at(.25);self.step(self.raw(2,False,.25))
        self.assertEqual(self.runtime.Status(self.runtime).outcomes.station,'rejected');self.assertEqual(self.recall.owner.Usage(self.recall.owner).attempted,1)
    def test_presence_stays_manual_and_45second_skip_retains_member_custody(self):
        self.executor.reply=lua_table(self.h.lua,{'ok':False,'code':'presence'});self.begin();self.send();self.h.at(45)
        self.step(self.raw(2,False,45));self.assertEqual(self.runtime.Status(self.runtime).outcomes.station,'skipped_unconfirmed')
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),1);self.assertEqual(self.recall.owner.Usage(self.recall.owner).attempted,1)
        self.assertFalse(self.native.api.busy())
    def test_unload_before_queued_callback_never_invokes_or_erases_unknown_custody(self):
        self.begin();self.app.Destroy(self.app);self.executor.queued[1]();self.assertEqual(len(self.executor.calls),0);self.assertFalse(self.native.api.busy())
    def restart(self,pristine_registry=False,with_reads=False):
        self.app.Destroy(self.app)
        if pristine_registry:self.native.registry=self.h.lua.table()
        self.lease,why=self.h.load('src/tabs/territory/NativeRecallLease.luau').bind(lua_table(self.h.lua,{'game':self.native.game,'env':self.native.env,
            'registry':self.native.registry,'requireModule':self.native.requireModule,'clock':self.h.clock,'account':'user-a'}))
        self.assertIsNotNone(self.lease,why)
        self.recall,why=self.h.load('src/tabs/territory/RecallRuntime.luau').new(lua_table(self.h.lua,{'lease':self.lease,
            'transactions':self.h.load('src/tabs/territory/RecallTransactions.luau'),'identity':self.h.session,'storage':self.storage,
            'clock':self.h.clock,'cooldownSeconds':600}))
        self.assertIsNotNone(self.recall,why);self.start(with_reads=with_reads)
        for key,value in {'mode':'Recall','districtId':'d1','memberSlot':2,'minGarrison':1,'maxAttempts':2}.items():self.app.Set(self.app,'station.custom.'+key,value)
        self.app.Set(self.app,'station.enabled',True);self.app.Resume(self.app)
    def test_malformed_positive_or_wrong_settlement_stays_pending_without_storage_fault(self):
        for reply in ({'ok':True},{'ok':False},{'ok':True,'settled':[{'districtId':'other','userId':42,'memberIndex':2}]},
                      {'ok':True,'code':'presence','settled':[{'districtId':'d1','userId':42,'memberIndex':2,'deploymentId':'deployment-a'}]}):
            with self.subTest(reply=reply):
                self.setUp();self.executor.reply=lua_table(self.h.lua,reply);self.begin();self.send()
                self.h.at(.25);self.step(self.raw(2,False,.25))
                self.assertFalse(self.runtime.Status(self.runtime).storageFault)
                self.assertIsNone(self.runtime.checkpoint.Recovery(self.runtime.checkpoint,self.recall.owner.Active(self.recall.owner).actionKey)[0].reply)
                self.assertEqual(self.recall.owner.Active(self.recall.owner).stage,'sent');self.app.Destroy(self.app)
    def test_restart_sent_uses_same_epoch_status_only_then_exact_saved_effect(self):
        self.begin();self.send();self.h.at(.25);self.restart();self.before=self.raw(2,False,.25);self.step()
        self.assertEqual(len(self.executor.queued),2);self.executor.status=self.settled();self.executor.queued[2]()
        self.h.at(.5);self.step(self.raw(3,True,.5))
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.station,'confirmed')
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),0)
        self.assertEqual(self.recall.owner.Usage(self.recall.owner).attempted,1)
        self.assertEqual([x.command for x in self.executor.calls.values()],['recallcrew','recallstatus'])
    def test_restart_without_counter_provenance_retains_custody_and_never_queries_or_replays(self):
        self.begin();self.send();self.h.at(.25);self.restart(True);self.before=self.raw(2,False,.25);self.step()
        self.assertEqual(len(self.executor.queued),1);self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),1)
        self.assertEqual(self.recall.owner.Usage(self.recall.owner).attempted,1)
        held=self.recall.Reservations(self.recall);self.assertTrue(held.claims.members['id:guard']);self.assertTrue(held.claims.members['slot:2'])
    def test_reply_saved_before_unload_recovers_on_newer_home_without_another_request(self):
        self.executor.reply=self.settled();self.begin();self.send();self.h.at(.25);self.restart();self.step(self.raw(2,True,.25))
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.station,'confirmed');self.assertEqual(len(self.executor.calls),1)
    def test_unload_during_physical_invoke_late_return_cannot_replace_restarted_status_owner(self):
        self.executor.yieldInvoke=True;self.begin();self.h.lua.globals().recallInvoke=self.executor.queued[1]
        self.assertEqual(self.h.lua.execute('oldRecall=coroutine.create(recallInvoke);local ok,v=coroutine.resume(oldRecall);assert(ok);return v'),'recall-invoke')
        self.h.at(.25);self.restart();self.before=self.raw(2,False,.25);self.step();self.assertTrue(self.native.api.busy())
        self.h.lua.execute('assert(coroutine.resume(oldRecall))');self.assertTrue(self.native.api.busy())
        self.executor.yieldInvoke=False;self.executor.status=self.settled();self.executor.queued[2]()
        self.h.at(.5);self.step(self.raw(3,True,.5));self.assertEqual(self.runtime.Status(self.runtime).recoveries.station,'confirmed')
    def test_manual_modal_or_foreign_snapshot_before_queued_invoke_never_sends(self):
        for blocker in ('modal','foreign'):
            with self.subTest(blocker=blocker):
                self.setUp();self.begin()
                if blocker=='modal':self.native.confirm.Visible=True
                else:self.h.lua.globals().recallAppRaw.native.userId=43
                self.executor.queued[1]();self.assertEqual(len(self.executor.calls),0)
                self.assertFalse(self.native.api.busy());self.assertFalse(self.runtime.Status(self.runtime).storageFault)
                self.assertEqual(self.recall.owner.Usage(self.recall.owner).attempted,0)
                if blocker=='modal':self.assertTrue(self.native.confirm.Visible)
                self.app.Destroy(self.app)
    def test_unload_during_local_prepare_reload_cleans_known_unsent_without_mutation(self):
        self.storage.Write=self.h.lua.eval("""function(self,k,v)
            if self.yieldRecall and k:find('territory%-recall') then coroutine.yield('recall-prepare-save') end
            self.data[k]=v;return true end""")
        self.storage.yieldRecall=True;self.app.Set(self.app,'station.enabled',True);self.app.Resume(self.app)
        self.h.lua.globals().recallApp=self.app;self.h.lua.globals().recallRaw=self.before;self.native.ctx.State.data=self.before.native
        self.assertEqual(self.h.lua.execute('prepareRecall=coroutine.create(function()return recallApp:Step(recallRaw)end);local ok,v=coroutine.resume(prepareRecall);assert(ok);return v'),'recall-prepare-save')
        self.app.Destroy(self.app);self.assertFalse(self.native.api.busy());self.storage.yieldRecall=False
        self.h.lua.execute('assert(coroutine.resume(prepareRecall))');self.restart();self.app.Set(self.app,'station.enabled',False)
        self.step();self.assertEqual(len(self.executor.calls),0);self.assertEqual(self.recall.owner.Usage(self.recall.owner).attempted,0)
        self.assertIsNone(self.recall.owner.Active(self.recall.owner));self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),0)
    def test_durable_observed_outcome_survives_cleanup_failure_and_lost_counter_provenance(self):
        self.executor.reply=self.settled();self.begin();self.send()
        self.storage.Write=self.h.lua.eval("""function(self,k,v)
            if self.failCheckpoint and not k:find('territory%-recall') then return false end
            self.data[k]=v;return true end""")
        self.storage.failCheckpoint=True;self.h.at(.25);self.step(self.raw(2,True,.25))
        self.assertTrue(self.runtime.Status(self.runtime).storageFault);self.assertEqual(self.recall.owner.Active(self.recall.owner).stage,'observed')
        self.storage.failCheckpoint=False;self.restart(True);self.step(self.raw(3,True,.25))
        self.assertFalse(self.runtime.Status(self.runtime).storageFault)
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.station,'confirmed');self.assertEqual(len(self.executor.calls),1)
    def test_local_recall_provider_holds_orphan_member_without_generic_record(self):
        self.begin();self.send()
        self.assertIsNotNone(self.tab.ReservationSources,'Territory Recall reservation providers are missing')
        owner=self.h.load('src/engine/ResourceReservations.luau').new(lua_table(self.h.lua,self.h.session),
            self.h.lua.eval('function()return {} end'),self.tab.ReservationSources(self.tab))
        held,why=owner.Held(owner,self.before);self.assertIsNotNone(held,why)
        self.assertTrue(held.members['id:guard']);self.assertTrue(held.members['slot:2'])
    def test_tab_can_construct_recall_owner_with_actual_storage_and_bind_checkpoint(self):
        self.app.Destroy(self.app)
        lease,why=self.h.load('src/tabs/territory/NativeRecallLease.luau').bind(lua_table(self.h.lua,{'game':self.native.game,'env':self.native.env,
            'registry':self.native.registry,'requireModule':self.native.requireModule,'clock':self.h.clock,'account':'user-a'}))
        self.assertIsNotNone(lease,why);deps=dict(self.tab.deps.items());deps.pop('nativeRecallRuntime',None)
        deps.update({'nativeRecallLease':lease,'storage':self.storage,'clock':self.h.clock,'identity':self.h.session,
            'RecallRuntime':self.h.load('src/tabs/territory/RecallRuntime.luau'),'RecallTransactions':self.h.load('src/tabs/territory/RecallTransactions.luau'),
            'config':{'TERRITORY':{'garrisonCap':200,'recallCooldownSeconds':600}}})
        tab=self.h.load('src/tabs/territory/Module.luau').new(lua_table(self.h.lua,deps))
        self.assertIsNotNone(tab.recall,'Actual guarded App storage did not construct Recall owner')
        self.assertIsNotNone(tab.BindCheckpoint,'Territory checkpoint binding hook is missing')
        tab.BindCheckpoint(tab,self.runtime.checkpoint,self.h.lua.eval('function()return recallAppRaw end'))
        self.assertTrue(tab.recall.Ready(tab.recall));self.assertEqual(len(tab.ReservationSources(tab)),1);tab.Close(tab)
    def test_queued_unload_callback_records_unsent_fact_and_restart_refunds_without_replay(self):
        self.begin();self.app.Destroy(self.app);self.executor.queued[1]()
        self.assertEqual(len(self.executor.calls),0);self.h.at(.25);self.restart();self.step(self.raw(2,False,.25))
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.station,'known_unsent')
        self.assertFalse(self.runtime.Status(self.runtime).storageFault);self.assertEqual(self.recall.owner.Usage(self.recall.owner).attempted,0)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),0);self.assertEqual(len(self.executor.calls),0)
    def test_durable_rejection_with_failed_generic_reply_save_retries_status_only_after_restart(self):
        self.executor.reply=lua_table(self.h.lua,{'ok':False,'code':'deployment_changed'});self.begin()
        self.storage.Write=self.h.lua.eval("""function(self,k,v)
            if self.failReplyCheckpoint and k:find(':checkpoint:') then return false end
            self.data[k]=v;return true end""")
        self.storage.failReplyCheckpoint=True;self.send()
        self.assertEqual(self.recall.owner.Active(self.recall.owner).stage,'rejected')
        self.assertTrue(self.runtime.Status(self.runtime).storageFault)
        self.storage.failReplyCheckpoint=False;self.h.at(.25);self.restart();self.before=self.raw(2,False,.25);self.step()
        self.assertEqual(len(self.executor.queued),2,'Durable rejection with missing generic reply must permit exact status-only recovery')
        self.executor.status=lua_table(self.h.lua,{'ok':False,'code':'deployment_changed'});self.executor.queued[2]()
        self.h.at(.5);self.step(self.raw(3,False,.5))
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.station,'rejected')
        self.assertFalse(self.runtime.Status(self.runtime).storageFault);self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),0)
        self.assertEqual(self.recall.owner.Usage(self.recall.owner).attempted,1)
        self.assertEqual([x.command for x in self.executor.calls.values()],['recallcrew','recallstatus'])
    def test_rejected_status_recovery_refuses_conflicting_positive_or_negative_result(self):
        for code in ('different_rejection','settled'):
            with self.subTest(code=code):
                self.setUp();self.executor.reply=lua_table(self.h.lua,{'ok':False,'code':'deployment_changed'});self.begin()
                self.storage.Write=self.h.lua.eval("""function(self,k,v)
                    if self.failReplyCheckpoint and k:find(':checkpoint:') then return false end
                    self.data[k]=v;return true end""")
                self.storage.failReplyCheckpoint=True;self.send();self.storage.failReplyCheckpoint=False
                self.h.at(.25);self.restart();self.before=self.raw(2,False,.25);self.step()
                self.assertEqual(len(self.executor.queued),2)
                self.executor.status=self.settled() if code=='settled' else lua_table(self.h.lua,{'ok':False,'code':code})
                self.executor.queued[2]();self.h.at(.5);self.step(self.raw(3,False,.5))
                self.assertEqual(self.recall.owner.Active(self.recall.owner).stage,'rejected')
                record=self.runtime.checkpoint.Records(self.runtime.checkpoint)[1]
                self.assertIsNone(self.runtime.checkpoint.Recovery(self.runtime.checkpoint,record.actionKey)[0].reply)
                self.assertTrue(self.recall.Reservations(self.recall).claims.members['id:guard'])
                self.assertEqual(self.recall.owner.Usage(self.recall.owner).attempted,1)
                self.assertFalse(self.runtime.Status(self.runtime).storageFault)
                self.assertEqual([x.command for x in self.executor.calls.values()],['recallcrew','recallstatus']);self.app.Destroy(self.app)
    def test_duplicate_names_with_distinct_stable_ids_confirm_exact_selected_slot_after_restart(self):
        self.before.native.crew[3].name='Guard';self.before.native.crew[3].rarity=4
        self.executor.reply=self.settled();self.begin();self.send()
        self.assertEqual(self.executor.calls[1].targets[1].memberIndex,2)
        self.h.at(.25);self.restart();after=self.raw(2,True,.25);after.native.crew[3].name='Guard';after.native.crew[3].rarity=4
        self.step(after)
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.station,'confirmed')
        self.assertEqual(len(self.executor.calls),1);self.assertEqual(self.recall.owner.Usage(self.recall.owner).attempted,1)
    def test_duplicate_stable_ids_still_refuse_before_any_app_queue(self):
        self.before.native.crew[3].healId='guard';self.app.Set(self.app,'station.enabled',True);self.app.Resume(self.app);self.step()
        self.assertEqual(len(self.executor.queued),0);self.assertEqual(self.recall.owner.Usage(self.recall.owner).attempted,0)
    def test_tab_constructed_during_manual_dialog_or_presence_resumes_after_human_clears_it(self):
        for blocker in ('dialog','presence'):
            with self.subTest(blocker=blocker):
                self.setUp();self.app.Destroy(self.app)
                self.native.confirm.Visible=blocker=='dialog';self.native.presence=blocker=='presence'
                self.lease,why=self.h.load('src/tabs/territory/NativeRecallLease.luau').bind(lua_table(self.h.lua,{'game':self.native.game,'env':self.native.env,
                    'registry':self.native.registry,'requireModule':self.native.requireModule,'clock':self.h.clock,'account':'user-a'}))
                self.assertIsNotNone(self.lease,why);self.start(lazy_recall=True)
                for key,value in {'mode':'Recall','districtId':'d1','memberSlot':2,'minGarrison':1,'maxAttempts':2}.items():self.app.Set(self.app,'station.custom.'+key,value)
                self.app.Set(self.app,'station.enabled',True);self.app.Resume(self.app);self.step()
                self.assertEqual(len(self.executor.queued),0);self.assertEqual(self.native.calls,0);self.assertEqual(self.native.writes,0)
                self.assertEqual(self.native.confirm.Visible,blocker=='dialog');self.assertEqual(self.native.presence,blocker=='presence')
                self.native.confirm.Visible=False;self.native.presence=False;self.step()
                self.assertEqual(len(self.executor.queued),1);self.executor.reply=self.settled();self.send()
                self.h.at(.25);self.step(self.raw(2,True,.25));self.assertEqual(self.runtime.Status(self.runtime).outcomes.station,'confirmed')
                self.app.Destroy(self.app)
    def test_pending_restart_during_manual_presence_holds_custody_without_status_until_cleared(self):
        self.begin();self.send();self.native.presence=True;self.h.at(.25);self.restart();self.before=self.raw(2,False,.25);self.step()
        self.assertEqual(len(self.executor.queued),1);self.assertTrue(self.recall.Reservations(self.recall).claims.members['id:guard'])
        self.assertTrue(self.native.presence);self.assertEqual(len(self.executor.calls),1)
        self.native.presence=False;self.step();self.assertEqual(len(self.executor.queued),2)
        self.executor.status=self.settled();self.executor.queued[2]();self.h.at(.5);self.step(self.raw(3,True,.5))
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.station,'confirmed')
        self.assertEqual([x.command for x in self.executor.calls.values()],['recallcrew','recallstatus'])
    def test_unrelated_missing_native_ids_allow_exact_selected_id_recall(self):
        self.before.native.crew[3].healId=None;self.executor.reply=self.settled();self.begin();self.send()
        self.assertEqual(self.recall.owner.Active(self.recall.owner).memberKey,'id:guard')
        self.assertFalse(self.recall.Reservations(self.recall).claims.allCrew)
        self.h.at(.25);after=self.raw(2,True,.25);after.native.crew[3].healId=None;self.step(after)
        self.assertEqual(self.runtime.Status(self.runtime).outcomes.station,'confirmed');self.assertEqual(len(self.executor.calls),1)
    def test_missing_selected_id_holds_whole_crew_and_restarts_with_status_only(self):
        self.before.native.crew[2].healId=None;self.before.native.crew[3].healId=None;self.begin()
        self.assertEqual(self.recall.owner.Active(self.recall.owner).memberKey,'slot:2')
        self.assertTrue(self.runtime.checkpoint.Records(self.runtime.checkpoint)[1].custody.allCrew)
        self.assertTrue(self.recall.Reservations(self.recall).claims.allCrew);self.send()
        self.h.at(.25);self.restart();self.before=self.raw(2,False,.25);self.before.native.crew[2].healId=None;self.before.native.crew[3].healId=None;self.step()
        self.assertEqual(len(self.executor.queued),2);self.assertTrue(self.recall.Reservations(self.recall).claims.allCrew)
        self.executor.status=self.settled();self.executor.queued[2]();self.h.at(.5);after=self.raw(3,True,.5)
        after.native.crew[2].healId=None;after.native.crew[3].healId=None;self.step(after)
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.station,'confirmed')
        self.assertEqual([x.command for x in self.executor.calls.values()],['recallcrew','recallstatus'])
    def test_weak_selected_identity_rechecks_direct_native_roster_before_invoke(self):
        self.before.native.crew[2].healId=None;self.begin()
        native=self.raw().native;native.crew[2].healId=None;native.crew[3].name='Replacement'
        self.native.ctx.State.data=native;self.executor.queued[1]()
        self.assertEqual(len(self.executor.calls),0);self.assertEqual(self.recall.owner.Usage(self.recall.owner).attempted,0)
    def test_native_32member_roster_with_20_absent_ids_supports_one_exact_recall(self):
        def roster(raw):
            raw.native.crew[3].healId=None
            for slot in range(4,33):
                raw.native.crew[slot]=lua_table(self.h.lua,{'name':'Guard','rarity':4,'train':1,'healId':None if slot<=22 else 'card-'+str(slot)})
            return raw
        self.before=roster(self.before);self.executor.reply=self.settled();self.begin();self.send()
        self.assertEqual(self.recall.owner.Active(self.recall.owner).baseline.size,32)
        self.h.at(.25);self.step(roster(self.raw(2,True,.25)))
        self.assertEqual(self.runtime.Status(self.runtime).outcomes.station,'confirmed');self.assertEqual(len(self.executor.calls),1)
    def test_weak_selected_identity_accepts_only_exact_native_timestamp_fallback(self):
        self.before.native.crew[2].healId=None;self.before.native.crew[2].dutyToken=None
        target=lua_table(self.h.lua,{'districtId':'d1','userId':42,'memberIndex':2,'at':900,'memberName':'Guard','rarity':4})
        self.executor.reply=lua_table(self.h.lua,{'ok':True,'settled':[target]});self.begin();self.send()
        self.assertIsNone(self.executor.calls[1].targets[1].deploymentId);self.assertEqual(self.executor.calls[1].targets[1].at,900)
        self.h.at(.25);after=self.raw(2,True,.25);after.native.crew[2].healId=None;self.step(after)
        self.assertEqual(self.runtime.Status(self.runtime).outcomes.station,'confirmed')
    def transfer_host(self):
        host = host_fixture.RuntimeHostTests(); host.provided_h = self.h; host.setUp()
        self.h.lua.globals().transferRecallApp = self.app
        host.deps.App = self.h.lua.eval('{start=function()return transferRecallApp end}')
        signal = host.teleport_signal(); owner, why = host.host_module.start(host.deps)
        self.assertIsNotNone(owner, why); self.addCleanup(lambda: owner.Destroy(owner))
        return owner, signal

    def test_transfer_before_recall_dispatch_never_sends_and_cleans_native_worker(self):
        owner, signal = self.transfer_host(); self.begin()
        signal.callback(lua_table(self.h.lua, {'Name':'Started'}))
        self.executor.queued[1]()
        self.assertEqual(len(self.executor.calls), 0)
        self.assertFalse(self.native.api.busy()); self.assertFalse(owner.active)
        self.assertFalse(self.app.alive)

    def test_transfer_sent_recall_holds_member_on_new_server_without_replay(self):
        owner, signal = self.transfer_host(); self.begin(); self.send()
        original = self.runtime.checkpoint.Records(self.runtime.checkpoint)[1]
        signal.callback(lua_table(self.h.lua, {'Name':'InProgress'}))
        self.native.game.JobId = 'new-job'; self.h.session['session'] = 'new-session'
        self.h.at(.25); self.restart(True); self.before=self.raw(2,False,.25); self.step()
        self.assertEqual(len(self.executor.calls), 1)
        self.assertEqual(len(self.executor.queued), 1)
        self.assertEqual(self.runtime.checkpoint.Records(self.runtime.checkpoint)[1].actionKey, original.actionKey)
        self.assertEqual(self.recall.owner.Usage(self.recall.owner).attempted, 1)
        self.assertTrue(self.recall.Reservations(self.recall).claims.members['id:guard'])
        self.assertFalse(owner.active)

    def tearDown(self):
        if hasattr(self,'app'):self.app.Destroy(self.app)
