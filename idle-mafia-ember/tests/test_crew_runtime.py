"""Actual tab owns storage/proofs/lifecycle; the fake executor only invokes calls."""
import unittest
import test_automation_runtime as runtime_fixture
import test_crew_replacement as replacement_fixture
from engine_harness import lua_table


class CrewRuntimeTests(unittest.TestCase):
    def setUp(self):
        base = runtime_fixture.AutomationRuntimeTests()
        base.setUp()
        self.h, self.modules, self.storage = base.h, base.runtime.modules, base.storage
        base.runtime.Close(base.runtime)
        self.storage.Write = self.h.lua.eval('function(self,key,value) self.data[key]=value return true end')
        self.f = replacement_fixture.CrewReplacementTests()
        self.f.h = self.h
        self.f.load_components()
        self.f.config.TERRITORY = lua_table(self.h.lua, {'healStaminaCost': 5,'healSeconds': 300})
        catalog = self.h.lua.eval('{new=function() return {Enrich=function(self,raw) return raw end} end}')
        self.h.lua.globals().crewFixtureSource = self.f.source
        deps = {key: self.f.source for key in ('RosterState','AutoEquipCrew','CrewSort','CrewHeal',
            'CrewTrain','CrewHire','CrewHealItems','CrewRollState')}
        deps.update({'NativeTrainingCatalog': catalog,'NativeHireCatalog': catalog,'NativeHealItemCatalog': catalog,
            'CrewGear': self.h.lua.eval('{new=function() return crewFixtureSource end}'),
            'gearSets': {},'gameData': {},'config': self.f.config,'fingerprint': 'a'*64,'release': 'release-a',
            'CrewReplacement': self.f.module,'CrewReplacementTransactions': self.f.tx_module,
            'CrewReplacementRuntime': self.h.load('src/tabs/crew/CrewReplacementRuntime.luau'),
            'CrewRecoveryReview': self.h.load('src/tabs/crew/CrewRecoveryReview.luau'),
            'ResourceReservations': self.modules.ResourceReservations,
            'storage': self.storage,'identity': self.h.session,'clock': self.h.clock})
        self.tab_module = self.h.load('src/tabs/crew/Module.luau')
        self.tab_dependencies = deps
        self.executor = self.h.lua.execute("""return {calls={},queued={},
            Schedule=function(self,fn) self.queued[#self.queued+1]=fn return true end,
            Invoke=function(self,remote,method,...)
                local args=table.pack(...)
                self.calls[#self.calls+1]={remote=remote,method=method,args=args}
                if self.reply then return self.reply end
                return args[1]=='dismiss' and {ok=true} or {ok=true,index=2,
                    member={name='New',rarity=2,atk=5,def=6}} end} """)
        self.start_current()

    def start_current(self):
        self.tab_dependencies['identity'] = self.h.session
        self.tab = self.tab_module.new(lua_table(self.h.lua,self.tab_dependencies))
        self.f.source = self.tab.replacement
        self.owner = self.tab.replacementOwner
        self.assertIsNotNone(self.owner)
        selected = getattr(self,'feature_id','crewRoll')
        self.descriptor = next(row for row in self.tab.Descriptors(self.tab).values() if row.id == selected)
        native = self.h.load('src/transport/NativeCallPlan.luau')
        plan = native.withCrew(self.h.load('src/tabs/crew/CrewCallPlan.luau'), self.f.module)
        self.adapter = self.h.load('src/transport/NativeDispatchAdapter.luau').new(plan, self.executor)
        sources=self.tab.ReservationSources(self.tab)
        for source in getattr(self,"additional_reservation_sources",[]):sources[len(sources)+1]=source
        self.runtime = self.h.load('src/engine/AutomationRuntime.luau').new(lua_table(self.h.lua, {
            'clock': self.h.clock,'transport': self.adapter,'storage': self.storage,'identity': self.h.session,
            'modules': self.modules,'features': [self.descriptor],'featurePages': {selected: 'crew'},
            'tabInstances': [self.tab],'reservationSources': sources,
            'snapshotAssembler': self.h.load('src/tabs/TabSnapshotAssembler.luau').new(lua_table(self.h.lua,[self.tab]))}))
        self.ember = self.h.load('tests/ember_double.lua')()
        self.app = self.h.load('src/App.luau').start(lua_table(self.h.lua, {
            'Ember': self.ember,'Catalog': self.h.load('src/ui/Catalog.luau'),
            'Settings': self.h.load('src/storage/Settings.luau'),'EmberAdapter': self.h.load('src/ui/EmberAdapter.luau'),
            'CrewTab': self.tab_module,'automationRuntimeInstance': self.runtime}))
        if selected == 'crewRoll':
            self.assertTrue(self.runtime.SupportsFeatureRecovery(self.runtime,'crewRoll'))
            self.assertIsNone(self.app.ui.features.crewRoll.blockedReason)

    def restart(self):
        self.app.Destroy(self.app)
        self.h.session['session'] = 'session-reloaded'
        self.h.at(0)
        self.start_current()

    def tearDown(self):
        self.app.Destroy(self.app)

    def choose(self, reserve=0):
        for key, value in (('crewRoll.enabled',True),('crewRoll.policy','Custom'),
            ('crewRoll.custom.allowDismiss',True),('crewRoll.custom.targetRarity',3),
            ('crewRoll.custom.maxDismissRarity',2),('crewRoll.custom.minHome',1),
            ('crewRoll.custom.cashReserve',reserve),('crewRoll.custom.maxCost',10000),
            ('crewRoll.custom.maxSpend',10000),('crewRoll.custom.maxAttempts',1)):
            self.assertTrue(self.app.Set(self.app,key,value)[0],key)
        self.app.Resume(self.app)

    def step(self, **kwargs):
        raw = self.f.raw(**kwargs)
        self.h.at(raw.capturedAt)
        self.assertTrue(self.app.Step(self.app,raw)[0])
        return raw

    def drain(self):
        queued, self.executor.queued = self.executor.queued, self.h.lua.table()
        for callback in queued.values():
            callback()

    def test_actual_owner_drives_two_calls_and_persists_one_cycle_budget(self):
        self.choose()
        self.step()
        self.assertEqual(len(self.executor.queued),1, str(dict(self.runtime.Status(self.runtime).reasons.items())))
        self.assertEqual(self.owner.Active(self.owner).stage,'preparedDismiss')
        self.assertEqual(self.owner.Usage(self.owner).attempted,1)
        self.drain()
        self.assertEqual(self.owner.Active(self.owner).stage,'sentDismiss')
        self.step(revision=2,stage='empty')
        self.assertEqual(self.owner.Active(self.owner).stage,'preparedHire')
        self.drain()
        self.assertEqual(self.owner.Active(self.owner).stage,'sentHire')
        self.assertEqual(self.owner.Usage(self.owner).spent,10000)
        self.step(revision=3,stage='hired',cash=40000)
        self.assertEqual(self.runtime.Status(self.runtime).outcomes.crewRoll,'confirmed')
        self.assertIsNone(self.owner.Active(self.owner))
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),0)
        self.step(revision=4,stage='hired',cash=40000,attempted=0,spent=0)
        self.assertEqual(len(self.executor.calls),2)
        self.assertEqual([call.args[1] for call in self.executor.calls.values()],['dismiss','hire'])
        self.assertEqual((self.owner.Usage(self.owner).attempted,self.owner.Usage(self.owner).spent),(1,10000))

    def test_all_off_and_zero_limits_do_not_prepare_write_or_call(self):
        self.step()
        self.assertEqual(len(self.executor.calls),0)
        self.assertEqual(len(self.executor.queued),0)
        self.assertEqual(len(self.storage.data),0)
        self.app.Set(self.app,'crewRoll.enabled',True)
        self.step(revision=2)
        self.assertEqual(len(self.executor.queued),0)
        self.assertIsNone(self.owner.Active(self.owner))
        self.assertEqual(self.owner.Usage(self.owner).attempted,0)

    def test_inert_entry_retains_warning_and_cannot_expose_recovery(self):
        app = self.h.load('src/App.luau').start(lua_table(self.h.lua, {
            'Ember': self.h.load('tests/ember_double.lua')(),'Catalog': self.h.load('src/ui/Catalog.luau'),
            'Settings': self.h.load('src/storage/Settings.luau'),'EmberAdapter': self.h.load('src/ui/EmberAdapter.luau'),
            'CrewTab': self.tab_module}))
        try:
            self.assertIsNotNone(app.ui.features.crewRoll.blockedReason)
            self.assertIn('unavailable',app.ui.features.crewRoll.recoveryStatus.value)
            self.assertEqual(len(self.executor.calls),0)
            self.assertEqual(len(self.storage.data),0)
        finally:
            app.Destroy(app)

    def test_known_unsent_dismissal_restores_budget_without_a_native_call(self):
        self.choose()
        self.step()
        self.app.Set(self.app,'crewRoll.enabled',False)
        self.drain()
        self.assertEqual(len(self.executor.calls),0)
        self.assertIsNone(self.owner.Active(self.owner))
        self.assertEqual(self.owner.Usage(self.owner).attempted,0)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),0)

    def test_only_the_funded_hire_can_use_all_reserved_cash(self):
        self.choose()
        self.step(cash=10000)
        self.drain()
        self.step(revision=2,stage='empty',cash=10000)
        self.assertEqual(len(self.executor.queued),1,str(dict(self.runtime.Status(self.runtime).reasons.items())))
        self.drain()
        self.step(revision=3,stage='hired',cash=0)
        self.assertEqual(len(self.executor.calls),2)
        self.assertIsNone(self.owner.Active(self.owner))

    def test_unsent_hire_preserves_funding_and_resumes_only_that_cycle(self):
        self.choose()
        self.step(cash=10000)
        self.drain()
        empty = self.step(revision=2,stage='empty',cash=10000)
        self.app.Pause(self.app)
        self.drain()
        self.assertEqual(len(self.executor.calls),1)
        self.assertEqual(self.owner.Active(self.owner).stage,'observedEmpty')
        self.assertEqual((self.owner.Usage(self.owner).attempted,self.owner.Usage(self.owner).spent),(1,0))
        held = self.runtime.reservationOwner.Held(self.runtime.reservationOwner,empty)[0]
        self.assertEqual(held.funds.cash,10000)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),0)
        self.app.Resume(self.app)
        self.step(revision=3,stage='empty',cash=10000)
        self.drain()
        self.step(revision=4,stage='hired',cash=0)
        self.assertEqual(len(self.executor.calls),2)
        self.assertIsNone(self.owner.Active(self.owner))

    def test_pause_inside_sent_write_refunds_only_the_uninvoked_hire(self):
        self.choose()
        self.step()
        self.drain()
        self.step(revision=2,stage='empty')
        self.h.lua.globals().crewWriteApp = self.app
        self.storage.Write = self.h.lua.eval("""function(self,key,value)
            self.data[key]=value
            if value.active and value.active.stage=='sentHire' and not self.interrupted then
                self.interrupted=true; self.hireExposure=value.usage.spent; crewWriteApp:Pause()
            end
            return true end """)
        self.drain()
        self.assertEqual(self.storage.hireExposure,10000)
        self.assertEqual(len(self.executor.calls),1)
        self.assertEqual(self.owner.Active(self.owner).stage,'observedEmpty')
        self.assertEqual(self.owner.Usage(self.owner).spent,0)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),0)

    def test_unload_inside_write_retains_saved_uncertainty_without_invocation(self):
        self.choose()
        self.step()
        self.drain()
        self.step(revision=2,stage='empty')
        self.h.lua.globals().crewWriteApp = self.app
        self.storage.Write = self.h.lua.eval("""function(self,key,value)
            self.data[key]=value
            if value.active and value.active.stage=='sentHire' then crewWriteApp:Destroy() end
            return true end """)
        self.drain()
        self.assertEqual(len(self.executor.calls),1)
        recovered, reason = self.f.tx_module.new(self.storage,self.owner.scope,self.f.source)
        self.assertIsNone(reason)
        self.assertEqual(recovered.Active(recovered).stage,'sentHire')
        self.assertEqual(recovered.Usage(recovered).spent,10000)
        self.assertIsNone(recovered.SubmitCall(recovered,self.f.raw(revision=3,stage='empty'),3)[0])
        self.assertTrue(recovered.KnownUnsent(recovered))
        self.restart()
        self.app.Pause(self.app)
        self.step(revision=4,stage='empty')
        preview, why = self.app.PreviewFeatureRecovery(self.app,'crewRoll')
        self.assertIsNone(why)
        self.assertEqual(preview.kind,'restoreHire')
        self.assertTrue(self.app.ConfirmFeatureRecovery(self.app,'crewRoll')[0])
        self.assertEqual(self.owner.Active(self.owner).stage,'observedEmpty')
        self.assertEqual((self.owner.Usage(self.owner).attempted,self.owner.Usage(self.owner).spent),(1,0))
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),0)
        self.assertEqual(len(self.executor.calls),1)

    def test_paused_restart_observes_saved_dismissal_then_only_user_resume_hires(self):
        self.choose()
        self.step()
        self.drain()
        self.restart()
        self.assertFalse(self.app.model['values']['crewRoll.enabled'])
        self.step(revision=2,stage='empty')
        self.assertEqual(self.runtime.Status(self.runtime).state,'paused')
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.crewRoll,'confirmed')
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),0)
        self.assertEqual(self.owner.Active(self.owner).stage,'observedEmpty')
        self.assertEqual(len(self.executor.calls),1)
        self.choose()
        self.step(revision=3,stage='empty')
        self.drain()
        self.step(revision=4,stage='hired',cash=40000)
        self.assertEqual(len(self.executor.calls),2)
        self.assertIsNone(self.owner.Active(self.owner))

    def test_restart_missing_reply_or_unrelated_change_retains_hold_without_replay(self):
        self.choose()
        self.step()
        callback = self.executor.queued[1]
        self.executor.Invoke = self.h.lua.eval("""function(self,remote,method,...)
            self.calls[#self.calls+1]={remote=remote,args=table.pack(...)}; return nil end """)
        self.drain()
        self.restart()
        self.step(revision=2,stage='empty')
        generation = self.owner.generation
        callback()
        self.assertEqual(self.owner.generation,generation)
        self.assertEqual(self.owner.Active(self.owner).stage,'sentDismiss')
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),1)
        self.assertIsNone(self.runtime.Status(self.runtime).recoveries.crewRoll)
        self.assertEqual(len(self.executor.calls),1)

    def test_restart_wrong_cash_or_other_member_does_not_clear_checkpoint(self):
        self.choose()
        self.step()
        self.drain()
        self.restart()
        self.step(revision=2,stage='empty',cash=49999)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),1)
        raw = self.f.raw(revision=3,stage='empty')
        raw.native.crew[3].atk = 999
        self.h.at(3)
        self.app.Step(self.app,raw)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),1)
        self.assertEqual(self.owner.Active(self.owner).stage,'sentDismiss')
        self.assertEqual(len(self.executor.calls),1)

    def test_terminal_hire_checkpoint_survives_crash_between_two_store_clears(self):
        self.choose()
        self.step()
        self.drain()
        self.step(revision=2,stage='empty')
        self.drain()
        # Simulate the generic checkpoint write failing after the tab's exact
        # observed outcome was saved and its terminal transaction cleared.
        self.storage.Write = self.h.lua.eval("""function(self,key,value)
            if key:find(':checkpoint:',1,true) and #value.records==0 then return false end
            self.data[key]=value; return true end """)
        self.step(revision=3,stage='hired',cash=40000)
        self.assertIsNone(self.owner.Active(self.owner))
        self.assertTrue(self.runtime.Status(self.runtime).storageFault)
        self.storage.Write = self.h.lua.eval('function(self,key,value) self.data[key]=value return true end')
        self.restart()
        self.step(revision=4,stage='hired',cash=40000)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),0)
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.crewRoll,'confirmed')
        self.assertEqual(self.owner.Usage(self.owner).spent,10000)
        self.assertEqual(len(self.executor.calls),2)

    def test_yielding_first_preparation_cannot_be_entered_by_another_tick(self):
        self.choose()
        raw = self.f.raw()
        self.h.at(1)
        self.h.lua.globals().crewTickApp = self.app
        self.h.lua.globals().crewTickRaw = raw
        self.storage.Write = self.h.lua.eval("""function(self,key,value)
            if value.active and value.active.stage=='preparedDismiss' and not self.yielded then
                self.yielded=true; coroutine.yield('preparing') end
            self.data[key]=value; return true end """)
        self.h.lua.execute('crewTick=coroutine.create(function() return crewTickApp:Step(crewTickRaw) end)')
        self.assertTrue(self.h.lua.eval('coroutine.resume(crewTick)')[0])
        self.app.Step(self.app,raw)
        self.assertFalse(self.runtime.Status(self.runtime).storageFault)
        self.assertTrue(self.h.lua.eval('coroutine.resume(crewTick)')[0])
        self.drain()
        self.assertEqual(len(self.executor.calls),1)
        self.assertEqual(self.owner.Usage(self.owner).attempted,1)

    def test_yielding_recovery_cleanup_blocks_another_tick_until_its_save_finishes(self):
        self.choose()
        self.step()
        self.drain()
        self.step(revision=2,stage='empty')
        self.drain()
        self.storage.Write = self.h.lua.eval("""function(self,key,value)
            if key:find(':checkpoint:',1,true) and #value.records==0 then return false end
            self.data[key]=value; return true end """)
        self.step(revision=3,stage='hired',cash=40000)
        self.storage.Write = self.h.lua.eval('function(self,key,value) self.data[key]=value return true end')
        self.restart()
        raw = self.f.raw(revision=4,stage='hired',cash=40000)
        self.h.at(4)
        self.h.lua.globals().crewTickApp = self.app
        self.h.lua.globals().crewTickRaw = raw
        self.storage.Write = self.h.lua.eval("""function(self,key,value)
            if key:find(':checkpoint:',1,true) and #value.records==0 and not self.yielded then
                self.yielded=true; coroutine.yield('recovering') end
            self.data[key]=value; return true end """)
        self.h.lua.execute('crewTick=coroutine.create(function() return crewTickApp:Step(crewTickRaw) end)')
        self.assertTrue(self.h.lua.eval('coroutine.resume(crewTick)')[0])
        newer = self.f.raw(revision=5,stage='hired',cash=40000)
        self.h.at(5)
        self.app.Step(self.app,newer)
        self.assertFalse(self.runtime.Status(self.runtime).storageFault)
        self.assertTrue(self.h.lua.eval('coroutine.resume(crewTick)')[0])
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),0)
        self.assertEqual(len(self.executor.calls),2)

    def test_later_saved_effect_reconciliation_keeps_original_skip_and_cooldown(self):
        self.choose()
        self.step()
        self.drain()
        self.h.at(46)
        self.app.Step(self.app,self.f.raw(revision=2))
        self.assertEqual(self.runtime.Status(self.runtime).outcomes.crewRoll,'skipped_unconfirmed')
        self.assertEqual(self.runtime.Status(self.runtime).cooldownUntil.crewRoll,91)
        current = self.f.raw(revision=3,stage='empty')
        current.capturedAt = 47
        current.economyProof.capturedAt = 47
        self.h.at(47)
        self.app.Step(self.app,current)
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.crewRoll,'confirmed')
        self.assertEqual(self.runtime.Status(self.runtime).outcomes.crewRoll,'skipped_unconfirmed')
        self.assertEqual(self.runtime.Status(self.runtime).cooldownUntil.crewRoll,91)
        self.assertEqual(len(self.executor.calls),1)
        self.assertEqual(len(self.executor.queued),0)
        kinds = [row.kind for row in self.runtime.journal.Events(self.runtime.journal).values()]
        self.assertIn('skipped_unconfirmed',kinds)
        self.assertIn('reconciled_saved',kinds)

    def test_known_unsent_receipt_recovers_if_generic_cleanup_fails(self):
        self.choose()
        self.step()
        self.storage.Write = self.h.lua.eval("""function(self,key,value)
            if key:find(':checkpoint:',1,true) and #value.records==0 then return false end
            self.data[key]=value; return true end """)
        self.app.Set(self.app,'crewRoll.enabled',False)
        self.drain()
        self.assertIsNone(self.owner.Active(self.owner))
        self.storage.Write = self.h.lua.eval('function(self,key,value) self.data[key]=value return true end')
        self.restart()
        self.step(revision=2)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),0)
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.crewRoll,'known_unsent')
        self.assertEqual(self.owner.Usage(self.owner).attempted,0)
        self.assertEqual(len(self.executor.calls),0)
