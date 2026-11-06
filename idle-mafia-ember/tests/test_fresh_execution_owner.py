"""Fresh Bootstrap chunks share ownership before actual App construction."""
import unittest,hashlib
import test_trophy_goal_runtime as fixture
from engine_harness import lua_table
class FreshExecutionOwnerTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.TrophyGoalRuntimeTests();self.f.setUp();self.f.app.Destroy(self.f.app)
        self.h=self.f.h;self.apps=[];self.envs=[];self.previous_alive=[]
        self.h.lua.globals().freshMakeApp=self.make_app
        self.h.lua.globals().freshHash=lambda value:hashlib.sha256(value.encode()).hexdigest()
        self.h.lua.execute("freshWrites={};freshGame={PlaceId=73897506680154};function freshGame:GetService(name) if name=='Players' then return {LocalPlayer={Name='user-a'}} end;if name=='HttpService' then return {GenerateGUID=function() freshGuid=(freshGuid or 0)+1;return 'fresh-guid-'..freshGuid end} end end")
        self.adapters=lua_table(self.h.lua,{"Loader":{"start":self.h.lua.eval("function(fetch,cache,compile,manifest,deps) return freshMakeApp(deps) end")},
            "Manifest":{},"fetch":self.h.lua.eval("function() end"),"cache":{},"compile":self.h.lua.eval("function() end"),
            "clientGame":self.h.lua.globals().freshGame,"clientRequire":self.h.lua.eval("function() end"),
            "clientHash":self.h.lua.eval("function(value) return freshHash(value) end"),"executionRegistry":{},
            "executorEnv":{"writefile":self.h.lua.eval("function(path,value) freshWrites[#freshWrites+1]={path=path,value=value} end")},"scheduler":{},"Ember":{}})
        self.release=lua_table(self.h.lua,{"commit":"a"*40,"fingerprint":"b"*64,"place":"73897506680154","gameVersion":"0.26.530",
            "directory":"IdleMafiaEmber","manifest":{"releaseCommit":"a"*40},"allowedFeatures":{"jobs":True,"bosses":True}})
    def tearDown(self):
        for app in self.apps:app.Destroy(app)
    def make_app(self,deps):
        if self.apps:self.previous_alive.append(self.apps[-1].alive)
        self.h.session["session"]=deps.identity.session
        # A loadstring execution reloads modules; the old Session's local registry is not shared.
        self.f.base.runtime.modules.Session=self.h.load("src/engine/Session.luau")
        self.f.base.runtime.modules.Checkpoint=self.h.load("src/storage/Checkpoint.luau")
        self.f.start_app();self.apps.append(self.f.app);self.envs.append(deps.executorEnv)
        return self.f.app,None
    def start(self):return self.h.load("Bootstrap.luau").start(self.release,self.adapters,True)
    def test_legacy_fluent_owner_is_not_unloaded_or_ignored(self):
        for record in ({"Running":True},{"Running":False,"Pending":{"kind":"withdraw"}},False):
            self.adapters.executionRegistry.IdleMafiaFluentHub=lua_table(self.h.lua,record)
            app,reason=self.start();self.assertIsNone(app);self.assertIn("Fluent",reason)
            self.assertEqual(len(self.apps),0);self.assertEqual(len(self.h.lua.globals().freshWrites),0)
    def test_separate_executor_legacy_registry_also_refuses_activation(self):
        self.adapters.legacyRegistry=lua_table(self.h.lua,{"IdleMafiaFluentHub":{"Running":True}})
        app,reason=self.start();self.assertIsNone(app);self.assertIn("Fluent",reason)
        self.assertEqual(len(self.apps),0)
    def test_new_chunk_closes_old_actual_app_before_constructing_another(self):
        old=self.start()[0];new,reason=self.start()
        self.assertIsNone(reason);self.assertFalse(old.alive);self.assertTrue(new.alive)
        self.assertEqual(self.previous_alive,[False])
    def test_fresh_entry_does_not_bypass_first_send_45_second_gate(self):
        old=self.start()[0];self.f.select();old.Step(old,self.f.raw());queued=self.f.executor
        new,reason=self.start();self.assertIsNone(new);self.assertTrue(old.alive)
        self.assertIn("45",reason)
        self.h.at(45);new,reason=self.start()
        self.assertIsNone(reason);self.assertFalse(old.alive)
        queued.callback();self.assertEqual(len(queued.calls),0)
    def test_retired_file_writer_cannot_write_through_a_new_owner(self):
        self.start();old=self.envs[-1];old.writefile("a","before")
        self.start()
        with self.assertRaisesRegex(Exception,"Execution owner"):old.writefile("a","late")
        self.envs[-1].writefile("a","current")
        self.assertEqual(len(self.h.lua.globals().freshWrites),2)
    def test_corrupt_existing_registry_refuses_without_starting_an_app(self):
        self.adapters.executionRegistry["__IDLE_MAFIA_EMBER_EXECUTION_V1"]=lua_table(self.h.lua,{"version":99})
        app,reason=self.start();self.assertIsNone(app);self.assertIn("ownership",reason)
        self.assertEqual(len(self.apps),0)
    def test_release_change_requires_migration_instead_of_hiding_old_scope(self):
        old=self.start()[0];self.release.commit="c"*40;self.release.manifest.releaseCommit="c"*40
        app,reason=self.start();self.assertIsNone(app);self.assertIn("migration",reason)
        self.assertTrue(old.alive)
    def test_yielding_file_write_keeps_old_owner_until_io_finishes(self):
        self.start();env=self.envs[-1]
        # The underlying write yields, so a second loaded Bootstrap must refuse replacement.
        self.adapters.executorEnv.writefile=self.h.lua.eval("function() coroutine.yield('writing') end")
        self.start();env=self.envs[-1]
        self.h.lua.globals().freshEnv=env
        self.h.lua.execute("freshWriter=coroutine.create(function() freshEnv.writefile('x','y') end);assert(select(2,coroutine.resume(freshWriter))=='writing')")
        app,reason=self.start();self.assertIsNone(app);self.assertIn("writing",reason)
        self.h.lua.execute("assert(coroutine.resume(freshWriter))")
        self.assertIsNotNone(self.start()[0])
    def test_startup_gate_is_shared_while_loader_yields(self):
        regular=self.adapters.Loader.start
        self.adapters.Loader.start=self.h.lua.eval("function(fetch,cache,compile,manifest,deps) coroutine.yield('loading');return {alive=true,CanReplace=function() return true end,Destroy=function(self) self.alive=false end} end")
        self.h.lua.globals().freshBootstrap=self.h.load("Bootstrap.luau")
        self.h.lua.globals().freshRelease,self.h.lua.globals().freshAdapters=self.release,self.adapters
        self.h.lua.execute("freshStartup=coroutine.create(function() return freshBootstrap.start(freshRelease,freshAdapters,true) end);assert(select(2,coroutine.resume(freshStartup))=='loading')")
        self.adapters.Loader.start=regular
        app,reason=self.start();self.assertIsNone(app);self.assertIn("in progress",reason)
        self.h.lua.execute("assert(coroutine.resume(freshStartup))")
        record=self.adapters.executionRegistry["__IDLE_MAFIA_EMBER_EXECUTION_V1"]
        self.assertEqual(record.phase,"active");record.handle.Destroy(record.handle)
    def test_failed_loader_can_retry_but_its_file_writer_is_retired(self):
        regular=self.adapters.Loader.start
        self.adapters.Loader.start=self.h.lua.eval("function(fetch,cache,compile,manifest,deps) failedEnv=deps.executorEnv;return nil,'load failed' end")
        app,reason=self.start();self.assertIsNone(app);self.assertEqual(reason,"load failed")
        with self.assertRaisesRegex(Exception,"Execution owner"):self.h.lua.globals().failedEnv.writefile("x","late")
        self.adapters.Loader.start=regular;self.assertIsNotNone(self.start()[0])
    def test_missing_registry_does_not_start_a_runtime(self):
        self.adapters.executionRegistry=None
        app,reason=self.start();self.assertIsNone(app);self.assertIn("registry",reason)
        self.assertEqual(len(self.apps),0)
    def test_bad_write_counter_does_not_grant_replacement(self):
        self.start();record=self.adapters.executionRegistry["__IDLE_MAFIA_EMBER_EXECUTION_V1"]
        record.writes=float('nan')
        app,reason=self.start();self.assertIsNone(app);self.assertIn("ownership",reason)
    def test_io_started_during_a_yielding_replacement_check_refuses_handoff(self):
        old=self.start()[0]
        old.CanReplace=self.h.lua.eval("function() coroutine.yield('checking');return true end")
        self.h.lua.globals().freshBootstrap=self.h.load("Bootstrap.luau")
        self.h.lua.globals().freshRelease,self.h.lua.globals().freshAdapters=self.release,self.adapters
        self.h.lua.execute("freshReplacement=coroutine.create(function() return freshBootstrap.start(freshRelease,freshAdapters,true) end);assert(select(2,coroutine.resume(freshReplacement))=='checking')")
        self.adapters.executionRegistry["__IDLE_MAFIA_EMBER_EXECUTION_V1"].writes=1
        self.h.lua.execute("freshResult=table.pack(coroutine.resume(freshReplacement))")
        result=self.h.lua.globals().freshResult
        self.assertIsNone(result[2]);self.assertIn("writing",result[3]);self.assertTrue(old.alive)
    def test_manual_unload_does_not_erase_pending_first_send_gate(self):
        app=self.start()[0];self.f.select();app.Step(app,self.f.raw());app.Destroy(app)
        replacement,reason=self.start()
        self.assertIsNone(replacement);self.assertIn("45",reason)
        self.h.at(45);self.assertIsNotNone(self.start()[0])
    def test_write_failure_releases_only_io_lock_and_preserves_original_error(self):
        self.adapters.executorEnv.writefile=self.h.lua.eval("function() error('disk failed') end")
        self.start()
        with self.assertRaisesRegex(Exception,"disk failed"):self.envs[-1].writefile("x","y")
        record=self.adapters.executionRegistry["__IDLE_MAFIA_EMBER_EXECUTION_V1"]
        self.assertEqual(record.writes,0)
        self.assertIsNotNone(self.start()[0])
if __name__=="__main__":unittest.main()
