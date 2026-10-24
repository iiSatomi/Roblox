"""Territory read lane binds accepted replies to one full Sync."""
import unittest

from engine_harness import Harness, lua_table


class TerritoryReadRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.snapshot = self.h.snapshot(native={"fullSync": True,
            "family": {"id": "fam-a"}})
        self.h.lua.globals().current_territory_snapshot = self.snapshot
        budget = self.h.load("src/engine/ReadBudget.luau").new(
            self.h.clock, lua_table(self.h.lua, [
                {"id": "territoryMap", "interval": 30},
                {"id": "residencyView", "interval": 30}]), 8, 120)
        map_query = self.h.load(
            "src/tabs/territory/TerritoryMapQuery.luau").new()
        residency_query = self.h.load(
            "src/tabs/territory/ResidencyQuery.luau").new()
        attachment = self.h.load(
            "src/tabs/territory/ReadAttachment.luau")
        self.executor = self.h.lua.execute("""return {
            queued = {}, calls = {},
            Schedule = function(self, fn)
                self.queued[#self.queued + 1] = fn
            end,
            Invoke = function(self, remote, method, ...)
                self.calls[#self.calls + 1] = {
                    remote = remote, args = table.pack(...),
                    arity = select('#', ...),
                }
                if remote == 'TerritoryView' then
                    return { ok = true, city = 'vespera',
                        territoryCapacity = { familyId = 'fam-a' },
                        districts = { { id = 'd1', mine = true } } }
                end
                return { ok = true, districtId = 'd1',
                    admission = 'open', kind = 'landlord', rent = 3 }
            end,
            Drain = function(self)
                local queued = self.queued
                self.queued = {}
                for _, fn in ipairs(queued) do fn() end
            end,
        }""")
        self.sink = self.h.lua.table_from([])
        self.h.lua.globals().territory_sink = self.sink
        current = self.h.lua.eval(
            "function() return current_territory_snapshot end")
        callback = self.h.lua.eval("""function(kind, result, reason)
            territory_sink[#territory_sink + 1] = {
                kind = kind, result = result, reason = reason }
        end""")
        self.runtime = self.h.load(
            "src/tabs/territory/TerritoryReadRuntime.luau").new(
                budget, map_query, residency_query, attachment,
                self.executor, current, callback)

    def test_map_then_residency_attach_to_same_sync(self):
        self.assertTrue(self.runtime.QueueMap(self.runtime,
            "vespera", self.snapshot)[0])
        self.assertEqual(self.runtime.Step(self.runtime), "scheduled")
        self.executor.Drain(self.executor)
        self.assertEqual(self.executor["calls"][1]["arity"], 2)
        self.assertEqual(self.executor["calls"][1]["args"][1], "map")
        self.assertEqual(self.sink[1]["kind"], "territoryMap")
        self.assertEqual(self.sink[1]["result"]["territoryMap"]
                         ["districts"][1]["id"], "d1")
        self.assertTrue(self.runtime.QueueResidency(self.runtime,
            "d1", self.snapshot)[0])
        self.assertEqual(self.runtime.Step(self.runtime), "scheduled")
        self.executor.Drain(self.executor)
        self.assertEqual(self.executor["calls"][2]["arity"], 3)
        self.assertEqual(self.sink[2]["kind"], "residencyView")
        self.assertEqual(self.sink[2]["result"]["residencyView"]
                         ["districtId"], "d1")

    def test_newer_sync_fences_scheduled_read(self):
        self.runtime.QueueMap(self.runtime, "vespera", self.snapshot)
        self.assertEqual(self.runtime.Step(self.runtime), "scheduled")
        self.h.lua.globals().current_territory_snapshot = self.h.snapshot(
            revision=2, native={"fullSync": True,
                "family": {"id": "fam-a"}})
        self.executor.Drain(self.executor)
        self.assertEqual(len(self.executor["calls"]), 0)
        self.assertEqual(len(self.sink), 0)

    def test_attachment_uses_current_matching_snapshot(self):
        self.runtime.QueueMap(self.runtime, "vespera", self.snapshot)
        self.assertEqual(self.runtime.Step(self.runtime), "scheduled")
        self.h.lua.globals().current_territory_snapshot = self.h.snapshot(
            native={"fullSync": True, "cash": 42,
                "family": {"id": "fam-a"}})
        self.executor.Drain(self.executor)
        self.assertEqual(self.sink[1]["result"]["native"]["cash"], 42)

    def test_close_fences_queued_read(self):
        self.runtime.QueueMap(self.runtime, "vespera", self.snapshot)
        self.assertEqual(self.runtime.Step(self.runtime), "scheduled")
        self.runtime.Close(self.runtime)
        self.executor.Drain(self.executor)
        self.assertEqual(len(self.executor["calls"]), 0)
        self.assertEqual(self.runtime.Step(self.runtime), "closed")

    def test_timeout_and_new_sync_during_invoke_discard_result(self):
        self.runtime.QueueMap(self.runtime, "vespera", self.snapshot)
        self.assertEqual(self.runtime.Step(self.runtime), "scheduled")
        self.h.lua.globals().advance_territory_clock = lambda: self.h.at(8)
        self.executor["Invoke"] = self.h.lua.eval("""function(self)
            advance_territory_clock()
            return { ok = true, city = 'vespera',
                territoryCapacity = { familyId = 'fam-a' },
                districts = { { id = 'd1', mine = true } } }
        end""")
        self.executor.Drain(self.executor)
        self.assertEqual(len(self.sink), 0)
        self.assertFalse(self.runtime.QueueResidency(self.runtime,
            "d1", self.snapshot)[0])


if __name__ == "__main__":
    unittest.main()
