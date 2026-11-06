"""Code upgrades must keep native proposals in their durable data identity."""
import unittest

from engine_harness import lua_table
import test_runtime_host as host_fixture
import test_fresh_execution_owner as owner_fixture
import test_runtime_entry_integration as entry_fixture


class StorageLineageRuntimeTests(unittest.TestCase):
    def setUp(self):
        f = host_fixture.RuntimeHostTests(); f.setUp()
        self.f, self.h, self.deps = f, f.h, f.deps
        self.deps.release = 'code-new'
        self.deps.expectedCommit = 'code-new'
        self.deps.identity.release = 'code-new'
        self.h.lua.execute("""
            lineageAssemblyCalls=0
            lineageAssembly={new=function(deps)
                lineageAssemblyCalls=lineageAssemblyCalls+1
                local id={}
                for k,v in pairs(deps.identity) do id[k]=v end
                id.release='data-original'
                return {identity=id,sourceRelease='code-new',storage={},ProfileStorage={}},nil
            end}
            lineageApp={start=function(deps)
                lineageSeen=deps
                return {alive=true,Step=function() return true end,
                    Destroy=function(s) s.alive=false;deps.onAppClosed();return true end}
            end}
        """)
        self.deps.StorageAssembly = self.h.lua.globals().lineageAssembly
        self.deps.App = self.h.lua.globals().lineageApp

    def test_storage_identity_is_selected_before_reader_and_app_construction(self):
        host, reason = self.f.host_module.start(self.deps)
        self.assertIsNone(reason)
        self.assertEqual(self.h.lua.globals().lineageAssemblyCalls, 1)
        seen = self.h.lua.globals().lineageSeen
        self.assertEqual(seen.identity.release, 'data-original')
        self.assertEqual(seen.release, 'data-original')
        self.assertEqual(seen.expectedCommit, 'code-new')
        self.assertEqual(seen.sourceRelease, 'code-new')
        self.assertIsNotNone(seen.preparedStorage)
        host.driver.reader.ObserveSync(host.driver.reader, lua_table(self.h.lua, {'cash': 9}))
        captured = host.driver.reader.Capture(host.driver.reader)[0]
        self.assertEqual(captured.release, 'data-original')
        self.assertEqual(self.deps.identity.release, 'code-new', 'Do not mutate the caller code identity')
        host.Destroy(host)

    def test_refused_storage_upgrade_never_constructs_the_app_or_subscribes(self):
        self.deps.StorageAssembly.new = self.h.lua.eval("function() return nil,'Unresolved upgrade review' end")
        host, reason = self.f.host_module.start(self.deps)
        self.assertIsNone(host)
        self.assertIn('Unresolved upgrade review', reason)
        self.assertIsNone(self.h.lua.globals().lineageSeen)
        self.assertIsNone(self.f.events.sync)
        self.assertIsNone(self.f.timer.callback)
        self.assertEqual(len(self.deps.remotesFolder.calls), 0)

    def test_storage_cannot_change_account_session_or_authorized_code_release(self):
        for field in ('account', 'place', 'session', 'sourceRelease'):
            with self.subTest(field=field):
                self.setUp()
                self.h.lua.globals().lineageBadField = field
                self.h.lua.execute("""local original=lineageAssembly.new
                    lineageAssembly.new=function(deps)
                        local stores=original(deps)
                        if lineageBadField=='sourceRelease' then stores.sourceRelease='another-code'
                        else stores.identity[lineageBadField]='another-scope' end
                        return stores,nil
                    end""")
                host, reason = self.f.host_module.start(self.deps)
                self.assertIsNone(host)
                self.assertIn('identity', reason)
                self.assertIsNone(self.h.lua.globals().lineageSeen)


class ClosedExecutionUpgradeTests(unittest.TestCase):
    def test_upgrade_commit_liveness_retires_with_its_bootstrap_owner(self):
        f = owner_fixture.FreshExecutionOwnerTests(); f.setUp()
        try:
            f.h.lua.globals().lineageOriginalLoader = f.adapters.Loader.start
            f.adapters.Loader.start = f.h.lua.eval("""function(fetch,cache,compile,manifest,deps)
                lineageUpgradeGate=deps.storageUpgradeCurrent
                return lineageOriginalLoader(fetch,cache,compile,manifest,deps)
            end""")
            f.start()
            gate = f.h.lua.globals().lineageUpgradeGate
            self.assertIsNotNone(gate, 'Durable migration needs an execution-owner check')
            self.assertTrue(gate())
            f.start()
            self.assertFalse(gate())
            current = f.h.lua.globals().lineageUpgradeGate
            self.assertTrue(current())
            f.adapters.executionRegistry['__IDLE_MAFIA_EMBER_EXECUTION_V1'].phase = 'closed'
            self.assertFalse(current())
        finally:
            f.tearDown()

    def test_closed_owner_allows_new_code_to_reach_durable_migration_gate(self):
        f = owner_fixture.FreshExecutionOwnerTests(); f.setUp()
        try:
            old = f.start()[0]
            old.Destroy(old)
            record = f.adapters.executionRegistry['__IDLE_MAFIA_EMBER_EXECUTION_V1']
            self.assertFalse(old.alive)
            f.release.commit = 'c' * 40
            f.release.manifest.releaseCommit = 'c' * 40
            f.adapters.Loader.start = f.h.lua.eval("function() return nil,'Durable upgrade review required' end")
            new, reason = f.start()
            self.assertIsNone(new)
            self.assertEqual(reason, 'Durable upgrade review required')
            with self.assertRaisesRegex(Exception, 'Execution owner'):
                f.envs[0].writefile('checkpoint', 'late')
            self.assertEqual(len(f.h.lua.globals().freshWrites), 0)
        finally:
            f.tearDown()

    def test_unloaded_cross_code_owner_still_respects_original_pending_send_gate(self):
        f = owner_fixture.FreshExecutionOwnerTests(); f.setUp()
        try:
            old = f.start()[0]
            f.f.select(); old.Step(old, f.f.raw()); old.Destroy(old)
            f.release.commit = 'c' * 40
            f.release.manifest.releaseCommit = 'c' * 40
            f.adapters.Loader.start = f.h.lua.eval("function() return nil,'Durable upgrade review required' end")
            new, reason = f.start()
            self.assertIsNone(new)
            self.assertIn('45', reason)
            f.h.at(45)
            new, reason = f.start()
            self.assertIsNone(new)
            self.assertEqual(reason, 'Durable upgrade review required')
        finally:
            f.tearDown()


class RealEntryStorageStartupTests(unittest.TestCase):
    def import_fixture(self, floor=19):
        f = entry_fixture.RuntimeEntryIntegrationTests(); f.setUp()
        f.h.lua.globals().importFloor = floor
        f.h.lua.execute('''
            importGuard={bindings=0,checks=0,
                BindCheckpoint=function(self,cp)
                    assert(cp:ScopeKey(),'Checkpoint must be loaded before binding')
                    self.bindings=self.bindings+1; self.cp=cp; return true,nil
                end,
                Check=function(self,proposal,raw)
                    assert(self.bindings==1,'Imported usage was never bound')
                    self.checks=self.checks+1; return false,'Imported allowance exhausted'
                end}
            local compile=loadstring
            loadstring=function(bytes,name)
                local chunk=compile(bytes,name)
                if name=='src/storage/StorageAssembly.luau' or name=='@src/storage/StorageAssembly.luau' then
                    return function()
                        local assembly=chunk();local create=assembly.new
                        assembly.new=function(deps)
                            local stores,why=create(deps)
                            if stores then
                                stores.usageCarryGuard=importGuard
                                stores.requestHighwaterFloor=importFloor
                            end
                            return stores,why
                        end
                        return assembly
                    end
                end
                return chunk
            end
        ''')
        return f

    def test_prepared_import_guard_binds_loaded_checkpoint_before_runtime_is_exposed(self):
        f = self.import_fixture()
        host = f.start()
        runtime = host.app.automationRuntime
        guard = f.h.lua.globals().importGuard
        self.assertEqual(guard.bindings,1)
        self.assertEqual(runtime.checkpoint.requestHighwater,19)
        self.assertIsNone(runtime.checkpoint.expectedEnvelope)
        raw = f.h.snapshot(native={'fullSync':True,'pools':{'energy':5}})
        for key in ('account','place','release','session'):
            raw[key] = runtime.identity[key]
        proposal = f.h.proposal()
        for key in ('account','place','release','session'):
            proposal[key] = runtime.identity[key]
        denied,reason = runtime.reservationOwner.Check(runtime.reservationOwner,proposal,raw)
        self.assertIsNone(denied)
        self.assertIn('Imported allowance',reason)
        self.assertEqual(guard.checks,1)
        self.assertEqual(f.h.lua.globals().nativeCalls,0)
        host.Destroy(host)

    def test_native_carry_sources_bind_before_checkpoint_activation_even_when_unavailable(self):
        f = self.import_fixture()
        f.h.lua.execute('''
            importGuard.nativeBindings=0
            function importGuard:BindNativeSources(sources)
                assert(type(sources)=='table')
                self.nativeBindings=self.nativeBindings+1
                self.nativeSources=sources
                return true,nil
            end
            local bind=importGuard.BindCheckpoint
            function importGuard:BindCheckpoint(cp)
                assert(self.nativeBindings==1,'Native sources must bind before checkpoint activation')
                return bind(self,cp)
            end
        ''')
        host = f.start()
        runtime = host.app.automationRuntime
        self.assertIsNone(runtime.session.storageFault)
        self.assertEqual(f.h.lua.globals().importGuard.nativeBindings, 1)
        self.assertEqual(f.h.lua.globals().nativeCalls, 0)
        host.Destroy(host)

    def test_refused_native_source_binding_cannot_expose_a_running_host(self):
        f = self.import_fixture()
        f.h.lua.globals().importGuard.BindNativeSources = f.h.lua.eval(
            "function() return false,'Native source binding changed' end")
        with self.assertRaisesRegex(Exception, 'Native source binding changed'):
            f.start()
        self.assertEqual(f.h.lua.globals().nativeCalls, 0)

    def test_import_binding_failure_keeps_the_actual_runtime_unable_to_send(self):
        for body in ("return false,'Changed import source'", "error('Changed import source')"):
            with self.subTest(body=body):
                f = self.import_fixture()
                f.h.lua.globals().importGuard.BindCheckpoint = f.h.lua.eval('function() '+body+' end')
                host = f.start()
                runtime = host.app.automationRuntime
                self.assertIsNotNone(runtime.session.storageFault)
                self.assertEqual(runtime.checkpoint.requestHighwater,0)
                self.assertFalse(runtime.session.broker.policy.canOffer())
                self.assertFalse(runtime.session.broker.policy.canSend())
                self.assertEqual(f.h.lua.globals().nativeCalls,0)
                host.Destroy(host)

    def test_import_guard_without_its_reviewed_request_floor_refuses_startup(self):
        f = self.import_fixture(floor=None)
        with self.assertRaisesRegex(Exception,'Imported request floor'):
            f.start()
        self.assertEqual(f.h.lua.globals().nativeCalls,0)

    def test_real_host_and_app_reuse_one_prepared_storage_assembly(self):
        f = entry_fixture.RuntimeEntryIntegrationTests(); f.setUp()
        f.h.lua.execute("""
            storageConstructionCount=0
            local compile=loadstring
            loadstring=function(bytes,name)
                local chunk=compile(bytes,name)
                if name=='src/storage/StorageAssembly.luau' or name=='@src/storage/StorageAssembly.luau' then
                    return function()
                        local assembly=chunk()
                        local create=assembly.new
                        assembly.new=function(deps)
                            storageConstructionCount=storageConstructionCount+1
                            assert(storageConstructionCount==1,'Storage was assembled twice')
                            return create(deps)
                        end
                        return assembly
                    end
                end
                return chunk
            end
        """)
        host = f.start()
        self.assertTrue(host.alive)
        self.assertIsNotNone(host.app.automationRuntime)
        self.assertEqual(f.h.lua.globals().storageConstructionCount, 1)
        self.assertEqual(f.h.lua.globals().nativeCalls, 0)
        host.Destroy(host)
