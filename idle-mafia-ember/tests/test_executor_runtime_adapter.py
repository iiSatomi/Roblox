"""Timer and native invocation wrappers preserve exact arguments."""
import unittest

from engine_harness import Harness


class ExecutorRuntimeAdapterTests(unittest.TestCase):
    def test_exact_nil_argument_and_timer_capabilities(self):
        h = Harness()
        api = h.lua.execute("""return {
            calls = {},
            after = function(delay, callback)
                return { delay = delay, callback = callback }
            end,
            cancel = function(handle) handle.cancelled = true end,
            defer = function(callback) api.pending = callback end,
            invoke = function(remote, ...)
                api.calls[#api.calls + 1] = {
                    remote = remote, args = table.pack(...),
                }
                return { ok = true }
            end,
        }""")
        h.lua.globals().api = api
        adapter = h.load(
            "src/transport/ExecutorRuntimeAdapter.luau")
        caps, reason = adapter.new(api)
        self.assertIsNone(reason)
        timer, executor = caps["timer"], caps["nativeExecutor"]
        handle = timer.After(timer, 0.25,
            h.lua.eval("function() end"))
        self.assertEqual(handle["delay"], 0.25)
        timer.Cancel(timer, handle)
        self.assertTrue(handle["cancelled"])
        executor.Invoke(executor, "BossAction", "InvokeServer",
                        "shopBuy", "w_policebaton", None)
        call = api.calls[1]
        self.assertEqual(call["remote"], "BossAction")
        self.assertEqual(call["args"]["n"], 3)
        self.assertIsNone(call["args"][3])
        with self.assertRaises(Exception):
            executor.Invoke(executor, "BossAction", "FireServer")

    def test_synchronous_scheduler_is_rejected(self):
        h = Harness()
        api = h.lua.execute("""return {
            after = function(_, callback) callback(); return 1 end,
            cancel = function() end,
            defer = function(callback) callback() end,
            invoke = function() return { ok = true } end,
        }""")
        adapter = h.load(
            "src/transport/ExecutorRuntimeAdapter.luau")
        caps, _ = adapter.new(api)
        with self.assertRaises(Exception):
            caps["timer"].After(caps["timer"], 0.25,
                h.lua.eval("function() end"))
        with self.assertRaises(Exception):
            caps["nativeExecutor"].Schedule(
                caps["nativeExecutor"], h.lua.eval("function() end"))


if __name__ == "__main__":
    unittest.main()
