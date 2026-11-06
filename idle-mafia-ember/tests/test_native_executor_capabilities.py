"""The live bootstrap must provide explicit timer, file, JSON and SHA capabilities."""
import unittest

from engine_harness import Harness


class NativeExecutorCapabilitiesTests(unittest.TestCase):
    def setUp(self):
        h = Harness()
        env, scheduler, http = h.lua.execute("""local env = {
            writes = 0,
            isfolder = function() return true end,
            makefolder = function() env.writes = env.writes + 1 end,
            isfile = function() return false end,
            readfile = function() return nil end,
            writefile = function() env.writes = env.writes + 1 end,
            crypt = { hash = function(value, algorithm)
                if value == 'abc' and algorithm == 'sha256' then
                    return 'ba7816bf8f01cfea414140de5dae2223b00361a396'
                        .. '177a9cb410ff61f20015ad'
                end
            end },
        }
        local scheduler = {
            delay = function(_, callback) return { callback = callback } end,
            cancel = function(handle) handle.cancelled = true end,
            defer = function(callback) return callback() end,
            spawn = function(callback)
                local thread = coroutine.create(callback)
                assert(coroutine.resume(thread))
                return thread
            end,
        }
        local http = {
            JSONEncode = function(_, value) return tostring(value.x) end,
            JSONDecode = function(_, value) return { x = tonumber(value) } end,
        }
        return env, scheduler, http""")
        module = h.load("src/transport/NativeExecutorCapabilities.luau")
        caps, reason = module.new(env, scheduler, http)
        self.h, self.env, self.scheduler, self.caps, self.reason = h, env, scheduler, caps, reason

    def test_adapts_capabilities_without_file_side_effects(self):
        h, env, caps, reason = self.h, self.env, self.caps, self.reason
        self.assertIsNone(reason)
        self.assertEqual(env.writes, 0)
        self.assertEqual(caps.executorStorageApi.hash("abc"),
            "ba7816bf8f01cfea414140de5dae2223b00361a396"
            "177a9cb410ff61f20015ad")
        self.assertEqual(caps.executorStorageApi.jsonEncode(
            h.lua.table_from({"x": 5})), "5")
        self.assertEqual(caps.executorStorageApi.jsonDecode("7").x, 7)
        self.assertTrue(callable(caps.executorRuntimeApi.after))
        self.assertTrue(callable(caps.executorRuntimeApi.defer))

    def test_native_read_runs_in_owned_spawn_and_preserves_nil_returns(self):
        self.h.lua.globals().readCaller = self.h.lua.eval("coroutine.running()")
        fn = self.h.lua.eval("function() assert(coroutine.running() ~= readCaller);return 7,nil,9 end")
        self.assertEqual(self.caps.executorRuntimeApi.readNative(fn), (True, 7, None, 9))
        self.assertEqual(self.env.writes, 0)

    def test_yielding_native_read_is_cancelled_and_never_accepted(self):
        self.scheduler.cancel = self.h.lua.eval("function(thread) cancelledRead=thread;coroutine.close(thread) end")
        fn = self.h.lua.eval("function() coroutine.yield('not a completed quote');return 99 end")
        accepted, reason = self.caps.executorRuntimeApi.readNative(fn)
        self.assertFalse(accepted)
        self.assertIn("yield", reason.lower())
        self.assertEqual(self.h.lua.eval("coroutine.status(cancelledRead)"), "dead")

    def test_native_read_errors_or_spawn_failure_do_not_become_results(self):
        fn = self.h.lua.eval("function() error('native calculation failed',0) end")
        self.assertEqual(self.caps.executorRuntimeApi.readNative(fn), (False, "native calculation failed"))
        self.scheduler.spawn = self.h.lua.eval("function() error('scheduler unavailable',0) end")
        self.assertEqual(self.caps.executorRuntimeApi.readNative(fn), (False, "scheduler unavailable"))

    def test_missing_sha_fails_closed(self):
        h = Harness()
        module = h.load("src/transport/NativeExecutorCapabilities.luau")
        caps, _ = module.new(h.lua.table(), h.lua.table(), h.lua.table())
        self.assertIsNone(caps)


if __name__ == "__main__":
    unittest.main()
