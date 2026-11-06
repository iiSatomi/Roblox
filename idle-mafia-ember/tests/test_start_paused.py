"""Explicit startup pause keeps authorized autoload choices inert until Resume."""
import unittest

import test_bootstrap as bootstrap_fixture
import test_runtime_entry_integration as entry_fixture
from engine_harness import lua_table


class StartPausedTests(unittest.TestCase):
    def test_bootstrap_forwards_only_an_explicit_true_adapter_flag(self):
        for requested, expected in ((True, True), (False, False), (None, False)):
            with self.subTest(requested=requested):
                f = bootstrap_fixture.BootstrapTests(); f.setUp()
                f.adapters.startPaused = requested
                handle, reason = f.bootstrap.start(f.release, f.adapters, True)
                self.assertIsNone(reason)
                self.assertIs(f.h.lua.globals().seen.dependencies.startPaused, expected)
                handle.Destroy(handle)

    def test_real_entry_autoload_keeps_profile_and_queued_sync_inert_until_resume(self):
        f = entry_fixture.RuntimeEntryIntegrationTests(); f.setUp()
        initial = f.start()
        self.assertTrue(initial.Set(initial, 'jobs.enabled', True)[0])
        self.assertTrue(initial.SaveProfile(initial, 'Chosen')[0])
        self.assertTrue(initial.SetAutoload(initial, 'Chosen')[0])
        self.assertTrue(initial.Destroy(initial))
        profile_bytes = {k: v for k, v in f.h.lua.globals().files.items()
                         if '/profiles/' in k}
        f.entry = f.entry.replace('scheduler = task, Ember = Ember,',
                                 'scheduler = task, Ember = Ember, startPaused = true,')
        f.h.lua.execute("""
            local folder=fixtureBindings.remotesFolder
            local find=folder.FindFirstChild
            local remotes={}
            function folder:FindFirstChild(name)
                if not remotes[name] then
                    remotes[name]=find(self,name)
                    if name=='DoJob' then
                        remotes[name].InvokeServer=function(_,id)
                            assert(id=='j_watch');nativeCalls=nativeCalls+1;return {ok=true}
                        end
                    end
                end
                return remotes[name]
            end
        """)
        host = f.start()
        try:
            self.assertTrue(host.app.model.paused)
            self.assertTrue(host.app.model['values']['jobs.enabled'])
            self.assertEqual(host.app.currentProfile, 'Chosen')
            self.assertFalse(host.app.automationRuntime.requested)
            self.assertEqual(profile_bytes, {k: v for k, v in f.h.lua.globals().files.items()
                                            if '/profiles/' in k})
            raw = lua_table(f.h.lua, {'cash': 100, 'level': 2, 'userId': 123, 'serverNow': 100,
                'pools': {'energy': 10}, 'derived': {'autoJobs': False},
                'jobs': {'j_watch': {'completions': 0, 'masteryTier': 0, 'masteryProgress': 0}},
                'inventory': {}, 'inventoryBound': {}})
            for _ in range(3):
                f.h.lua.globals().fixtureSyncCallback(raw)
                for task in list(f.h.lua.globals().scheduled.values()):
                    if not task.cancelled: task.callback()
            self.assertEqual(f.h.lua.globals().nativeCalls, 0)
            self.assertFalse(host.app.automationRuntime.requested)
            self.assertTrue(host.Resume(host)[0])
            f.h.lua.globals().fixtureSyncCallback(raw)
            for _ in range(2):
                for task in list(f.h.lua.globals().scheduled.values()):
                    if not task.cancelled: task.callback()
            self.assertEqual(f.h.lua.globals().nativeCalls, 1,
                             'The same eligible saved Job must become executable after Resume')
        finally:
            host.Destroy(host)

    def test_pause_is_effective_before_profile_and_yielding_first_ui_construction(self):
        f = entry_fixture.RuntimeEntryIntegrationTests(); f.setUp()
        f.entry = f.entry.replace('scheduler = task, Ember = Ember,',
                                 'scheduler = task, Ember = Ember, startPaused = true,')
        f.h.lua.execute("""
            local compile=loadstring
            loadstring=function(bytes,name)
                local chunk=compile(bytes,name)
                name=type(name)=='string' and name:gsub('^@','') or name
                if name=='src/storage/Settings.luau' then return function()
                    local module=chunk();local create=module.new
                    module.new=function(...)
                        startupModel=create(...);return startupModel
                    end;return module
                end end
                if name=='src/storage/ProfileStore.luau' then return function()
                    local module=chunk();local create=module.new
                    module.new=function(...)
                        assert(startupModel.paused,'Profile setup observed running model')
                        return create(...)
                    end;return module
                end end
                if name=='src/ui/EmberAdapter.luau' then return function()
                    local module=chunk();local create=module.new
                    module.new=function(...)
                        assert(startupModel.paused,'First UI construction observed running model')
                        coroutine.yield('startup-ui')
                        return create(...)
                    end;return module
                end end
                return chunk
            end
        """)
        f.h.lua.globals().startupEntry = f.entry
        f.h.lua.execute("""
            startupThread=coroutine.create(function() startupHost=assert(loadstring(startupEntry))() end)
            startupFirst=table.pack(coroutine.resume(startupThread))
        """)
        first = f.h.lua.globals().startupFirst
        self.assertTrue(first[1], first[2])
        self.assertEqual(first[2], 'startup-ui')
        self.assertTrue(f.h.lua.globals().startupModel.paused)
        self.assertEqual(f.h.lua.globals().nativeCalls, 0)
        f.h.lua.execute('assert(coroutine.resume(startupThread))')
        host = f.h.lua.globals().startupHost
        self.assertTrue(host.app.model.paused)
        host.Destroy(host)


if __name__ == '__main__': unittest.main()
