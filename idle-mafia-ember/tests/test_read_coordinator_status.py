"""Owned status recovery and physical native queues share the bounded read lane."""
import unittest

from engine_harness import Harness, lua_table


class ReadCoordinatorStatusTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.raw = self.h.snapshot(native={"fullSync": True, "serverNow": 100})
        self.h.lua.globals().readRaw = self.raw
        self.state = self.h.lua.execute("""return {busy=false, queued={}, calls=0, committed=0,
            reply={ok=false,code='expired'},
            Schedule=function(self,fn) self.queued[#self.queued+1]=fn end,
            InFlight=function(self) return self.busy end,
            InvokeOwned=function(self,token,remote,method,...) self.calls=self.calls+1; return self.reply end,
            Drain=function(self) local q=self.queued; self.queued={}; for _,fn in ipairs(q) do fn() end end}
        """)
        self.call = lua_table(self.h.lua, {"remote": "HeistAction", "method": "InvokeServer",
            "arity": 3, "args": ["status", "h_a", 8], "kind": "statusOnly"})

    def create(self):
        sources = self.h.lua.eval("""function(call,state) return {{id='ownedStatus',
            prepare=function() return call end,
            accept=function(_,_,reply) return {reply=reply} end,
            commit=function(staged) state.committed=state.committed+1; state.accepted=staged.reply; return true end}}
        end""")(self.call, self.state)
        budget = self.h.load("src/engine/ReadBudget.luau").new(self.h.clock,
            lua_table(self.h.lua, [{"id": "ownedStatus", "interval": 3}]), 5, 60)
        lane = self.h.load("src/engine/RequestLane.luau").new(self.h.clock)
        self.reader = self.h.load("src/transport/ReadCoordinator.luau").new(
            lua_table(self.h.lua, {"clock": self.h.clock, "lane": lane, "budget": budget,
                "executor": self.state, "sources": sources,
                "currentSnapshot": self.h.lua.eval("function() return readRaw end")}))

    def step(self):
        return self.reader.Step(self.reader, self.raw,
                                lua_table(self.h.lua, {"ownedStatus": True}))

    def test_owned_status_accepts_exact_terminal_rejection_for_feature_evidence(self):
        self.create()
        self.assertEqual(self.step(), "queued")
        self.state.Drain(self.state)
        self.assertEqual(self.state.committed, 1)
        self.assertFalse(self.state.accepted.ok)

    def test_native_busy_prevents_read_queue_and_is_rechecked_before_invocation(self):
        self.call = lua_table(self.h.lua, {"remote": "HeistAction", "method": "InvokeServer",
                                         "arity": 1, "args": ["board"]})
        self.create()
        self.state.busy = True
        self.assertEqual(self.step(), "busy")
        self.state.busy = False
        self.assertEqual(self.step(), "queued")
        self.state.busy = True
        self.state.Drain(self.state)
        self.assertEqual(self.state.calls, 0)

    def test_recall_status_uses_reviewed_three_argument_shape(self):
        self.call = lua_table(self.h.lua, {"remote": "TerritoryStatus", "method": "InvokeServer",
            "arity": 3, "args": ["recallstatus", "district-a", 8], "kind": "statusOnly"})
        self.state.reply = lua_table(self.h.lua, {"ok": True})
        self.create()
        self.assertEqual(self.step(), "queued")
        self.state.Drain(self.state)
        self.assertEqual(self.state.committed, 1)


if __name__ == "__main__":
    unittest.main()
