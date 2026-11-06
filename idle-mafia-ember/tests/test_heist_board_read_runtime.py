"""A read-only Heist board reply belongs to its originating full Sync."""
import unittest

from engine_harness import Harness, lua_table


class HeistBoardReadRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.snapshot = self.h.snapshot(native={"fullSync": True})
        self.h.lua.globals().current_heist_snapshot = self.snapshot
        budget = self.h.load("src/engine/ReadBudget.luau").new(
            self.h.clock, lua_table(self.h.lua, [
                {"id": "heistBoard", "interval": 15}]), 8, 120)
        query = self.h.load("src/tabs/heists/BoardQuery.luau").new(
            lua_table(self.h.lua, self.h.session))
        self.executor = self.h.lua.execute("""return {
            queued = {}, calls = {},
            Schedule = function(self, fn)
                self.queued[#self.queued + 1] = fn
            end,
            Invoke = function(self, remote, method, ...)
                self.calls[#self.calls + 1] = {
                    remote = remote, method = method,
                    args = table.pack(...), arity = select('#', ...),
                }
                return { ok = true, serverNow = 2000000,
                    rows = { { id = 'run-1', heistId = 'h_a',
                        ownerId = 123 } }, startsLeft = 1 }
            end,
            Drain = function(self)
                local queued = self.queued
                self.queued = {}
                for _, fn in ipairs(queued) do fn() end
            end,
        }""")
        self.sink = self.h.lua.table_from([])
        self.h.lua.globals().heist_sink = self.sink
        current = self.h.lua.eval(
            "function() return current_heist_snapshot end")
        callback = self.h.lua.eval("""function(result, reason)
            heist_sink[#heist_sink + 1] = {
                result = result, reason = reason }
        end""")
        self.runtime = self.h.load(
            "src/tabs/heists/BoardReadRuntime.luau").new(
                budget, query, self.executor, current, callback)

    def test_exact_board_read_attaches_to_current_full_sync(self):
        self.assertTrue(self.runtime.Queue(self.runtime, self.snapshot)[0])
        self.assertEqual(self.runtime.Step(self.runtime), "scheduled")
        self.executor.Drain(self.executor)
        call = self.executor["calls"][1]
        self.assertEqual(call["remote"], "HeistAction")
        self.assertEqual(call["method"], "InvokeServer")
        self.assertEqual(call["arity"], 1)
        self.assertEqual(call["args"][1], "board")
        self.assertEqual(self.sink[1]["result"]["heistBoardProof"]
                         ["board"]["rows"][1]["id"], "run-1")

    def test_newer_sync_fences_queued_read_and_releases_lane(self):
        self.runtime.Queue(self.runtime, self.snapshot)
        self.assertEqual(self.runtime.Step(self.runtime), "scheduled")
        self.h.lua.globals().current_heist_snapshot = self.h.snapshot(
            revision=2, native={"fullSync": True})
        self.executor.Drain(self.executor)
        self.assertEqual(len(self.executor["calls"]), 0)
        self.assertEqual(len(self.sink), 0)
        self.assertIsNone(self.runtime.inFlight)

    def test_changed_sync_during_invocation_discards_reply(self):
        self.runtime.Queue(self.runtime, self.snapshot)
        self.assertEqual(self.runtime.Step(self.runtime), "scheduled")
        self.h.lua.globals().replace_heist_snapshot = lambda: setattr(
            self.h.lua.globals(), "current_heist_snapshot",
            self.h.snapshot(revision=2, native={"fullSync": True}))
        self.executor["Invoke"] = self.h.lua.eval("""function(self)
            replace_heist_snapshot()
            return { ok = true, rows = {} }
        end""")
        self.executor.Drain(self.executor)
        self.assertEqual(len(self.sink), 0)

    def test_invalid_snapshot_or_schedule_refusal_fails_closed(self):
        invalid = self.h.snapshot(native={"fullSync": False})
        self.assertFalse(self.runtime.Queue(self.runtime, invalid)[0])
        missing_session = self.h.snapshot(native={"fullSync": True})
        missing_session["session"] = None
        self.assertFalse(self.runtime.Queue(self.runtime, missing_session)[0])
        invalid_revision = self.h.snapshot(
            revision=-1, native={"fullSync": True})
        self.assertFalse(self.runtime.Queue(self.runtime, invalid_revision)[0])
        self.executor["Schedule"] = self.h.lua.eval(
            "function() return false end")
        self.assertTrue(self.runtime.Queue(self.runtime, self.snapshot)[0])
        self.assertEqual(self.runtime.Step(self.runtime), "schedule_failed")
        self.assertIsNone(self.runtime.inFlight)
        self.assertEqual(len(self.executor["calls"]), 0)

    def test_close_fences_queued_read(self):
        self.runtime.Queue(self.runtime, self.snapshot)
        self.assertEqual(self.runtime.Step(self.runtime), "scheduled")
        self.runtime.Close(self.runtime)
        self.executor.Drain(self.executor)
        self.assertEqual(len(self.executor["calls"]), 0)
        self.assertEqual(self.runtime.Step(self.runtime), "closed")

    def test_rejected_board_reply_is_reported_without_proof(self):
        self.executor["Invoke"] = self.h.lua.eval(
            "function() return { ok = false, rows = {} } end")
        self.runtime.Queue(self.runtime, self.snapshot)
        self.assertEqual(self.runtime.Step(self.runtime), "scheduled")
        self.executor.Drain(self.executor)
        self.assertIsNone(self.sink[1]["result"])
        self.assertEqual(self.sink[1]["reason"],
                         "Current personal Heist board reply required")

    def test_timed_out_board_reply_is_discarded(self):
        self.h.lua.globals().advance_heist_clock = lambda: self.h.at(8)
        self.executor["Invoke"] = self.h.lua.eval("""function()
            advance_heist_clock()
            return { ok = true, rows = {} }
        end""")
        self.runtime.Queue(self.runtime, self.snapshot)
        self.assertEqual(self.runtime.Step(self.runtime), "scheduled")
        self.executor.Drain(self.executor)
        self.assertEqual(len(self.sink), 0)
        self.assertIsNone(self.runtime.inFlight)


if __name__ == "__main__":
    unittest.main()
