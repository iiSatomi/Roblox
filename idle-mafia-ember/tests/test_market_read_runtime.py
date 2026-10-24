"""Market research shares one bounded read lane without mutating gameplay."""
import unittest

from engine_harness import Harness, lua_table


class MarketReadRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        budget_module = self.h.load("src/engine/ReadBudget.luau")
        self.budget = budget_module.new(self.h.clock,
            lua_table(self.h.lua, [
                {"id": "marketBrowse", "interval": 90},
                {"id": "marketPrices", "interval": 120}]), 8, 300)
        self.browse = self.h.load("src/features/MarketBrowse.luau").new(5)
        self.prices = self.h.load("src/features/MarketPrices.luau").new(
            self.h.clock)
        self.executor = self.h.lua.execute("""return {
            queued = {}, calls = {},
            Schedule = function(self, fn) self.queued[#self.queued + 1] = fn end,
            Invoke = function(self, remote, method, ...)
                self.calls[#self.calls + 1] = {
                    remote = remote, method = method, args = table.pack(...),
                    arity = select('#', ...),
                }
                if select(1, ...) == 'browse' then
                    return { ok = true, rows = {}, pages = 1 }
                end
                return { ok = true, recent = {}, days = {} }
            end,
            Drain = function(self)
                local queued = self.queued
                self.queued = {}
                for _, fn in ipairs(queued) do fn() end
            end,
        }""")
        self.sink = self.h.lua.table_from([])
        self.h.lua.globals().market_sink = self.sink
        callback = self.h.lua.eval("""function(kind, result, reason)
            market_sink[#market_sink + 1] = {
                kind = kind, result = result, reason = reason,
            }
        end""")
        self.runtime = self.h.load("src/features/MarketReadRuntime.luau").new(
            self.budget, self.browse, self.prices, self.executor, callback)

    def test_browse_preserves_four_args_and_copies_result(self):
        self.assertTrue(self.runtime.QueueBrowse(self.runtime,
            lua_table(self.h.lua, {"kind": "all", "page": 1}))[0])
        self.assertEqual(self.runtime.Step(self.runtime), "scheduled")
        self.assertEqual(self.runtime.Step(self.runtime), "Read in flight")
        self.executor.Drain(self.executor)
        call = self.executor["calls"][1]
        self.assertEqual(call["remote"], "MarketAction")
        self.assertEqual(call["arity"], 4)
        self.assertEqual([call["args"][i] for i in range(1, 5)],
                         ["browse", "all", None, 1])
        self.assertEqual(self.sink[1]["kind"], "marketBrowse")
        self.assertIsNotNone(self.sink[1]["result"])

    def test_prices_waits_for_shared_lane_and_cache(self):
        self.assertTrue(self.runtime.QueuePrices(self.runtime, "w_baton")[0])
        self.assertEqual(self.runtime.Step(self.runtime), "scheduled")
        self.executor.Drain(self.executor)
        self.assertEqual(self.executor["calls"][1]["arity"], 4)
        self.assertEqual(self.sink[1]["kind"], "marketPrices")
        self.assertIsNotNone(self.prices.Get(self.prices, "w_baton"))
        self.assertFalse(self.runtime.QueuePrices(self.runtime, "w_baton")[0])

    def test_browse_and_prices_share_one_in_flight_slot(self):
        self.runtime.QueueBrowse(self.runtime,
            lua_table(self.h.lua, {"kind": "all", "page": 1}))
        self.runtime.QueuePrices(self.runtime, "w_baton")
        self.assertEqual(self.runtime.Step(self.runtime), "scheduled")
        self.assertEqual(self.runtime.Step(self.runtime), "Read in flight")
        self.executor.Drain(self.executor)
        self.assertEqual(self.runtime.Step(self.runtime), "scheduled")
        self.executor.Drain(self.executor)
        self.assertEqual([self.sink[i]["kind"] for i in (1, 2)],
                         ["marketBrowse", "marketPrices"])

    def test_close_fences_queued_callback(self):
        self.runtime.QueueBrowse(self.runtime,
            lua_table(self.h.lua, {"kind": "all", "page": 1}))
        self.assertEqual(self.runtime.Step(self.runtime), "scheduled")
        self.runtime.Close(self.runtime)
        self.executor.Drain(self.executor)
        self.assertEqual(len(self.sink), 0)
        self.assertEqual(self.runtime.Step(self.runtime), "closed")

    def test_declined_schedule_releases_market_read_lane(self):
        self.executor["Schedule"] = self.h.lua.eval(
            "function() return false end")
        self.runtime.QueueBrowse(self.runtime,
            lua_table(self.h.lua, {"kind": "all", "page": 1}))
        self.assertEqual(self.runtime.Step(self.runtime), "schedule_failed")
        self.assertIsNone(self.runtime.inFlight)
        self.assertEqual(len(self.executor["queued"]), 0)

    def test_timeout_fences_query_before_delayed_scheduler_runs(self):
        self.runtime.QueueBrowse(self.runtime,
            lua_table(self.h.lua, {"kind": "all", "page": 1}))
        self.assertEqual(self.runtime.Step(self.runtime), "scheduled")
        self.h.at(8)
        self.runtime.Step(self.runtime)
        self.executor.Drain(self.executor)
        self.assertEqual(len(self.executor["calls"]), 0)
        self.assertEqual(len(self.sink), 0)

    def test_timeout_does_not_admit_read_while_invoke_is_running(self):
        self.runtime.QueueBrowse(self.runtime,
            lua_table(self.h.lua, {"kind": "all", "page": 1}))
        self.runtime.QueuePrices(self.runtime, "w_baton")
        self.h.lua.globals().market_runtime = self.runtime
        self.h.lua.globals().advance_read_clock = lambda: self.h.at(8)
        self.executor["Invoke"] = self.h.lua.eval("""function(self, remote, method, ...)
            self.calls[#self.calls + 1] = { remote = remote, method = method }
            advance_read_clock()
            self.nested = market_runtime:Step()
            return { ok = true, rows = {}, pages = 1 }
        end""")
        self.assertEqual(self.runtime.Step(self.runtime), "scheduled")
        self.executor.Drain(self.executor)
        self.assertEqual(self.executor["nested"],
                         "Read invocation still running")
        self.assertEqual(len(self.executor["calls"]), 1)
        self.assertEqual(len(self.sink), 0)
        self.assertEqual(self.runtime.Step(self.runtime), "scheduled")


if __name__ == "__main__":
    unittest.main()
