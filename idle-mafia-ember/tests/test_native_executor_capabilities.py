"""The live bootstrap must provide explicit timer, file, JSON and SHA capabilities."""
import unittest

from engine_harness import Harness


class NativeExecutorCapabilitiesTests(unittest.TestCase):
    def test_adapts_capabilities_without_file_side_effects(self):
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
        }
        local http = {
            JSONEncode = function(_, value) return tostring(value.x) end,
            JSONDecode = function(_, value) return { x = tonumber(value) } end,
        }
        return env, scheduler, http""")
        module = h.load("src/transport/NativeExecutorCapabilities.luau")
        caps, reason = module.new(env, scheduler, http)
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

    def test_missing_sha_fails_closed(self):
        h = Harness()
        module = h.load("src/transport/NativeExecutorCapabilities.luau")
        caps, _ = module.new(h.lua.table(), h.lua.table(), h.lua.table())
        self.assertIsNone(caps)


if __name__ == "__main__":
    unittest.main()
