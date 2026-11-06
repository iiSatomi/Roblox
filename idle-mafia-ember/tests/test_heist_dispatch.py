"""Native Heist act owns dispatch; durable replies precede broker delivery."""
import unittest

from engine_harness import Harness, lua_table


class HeistDispatchTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        base = self.h.load("tests/fixtures/prestige-client.lua")
        self.client = self.h.load("tests/fixtures/heist-client.lua")(base)
        self.controller = self.h.load("src/tabs/heists/NativeHeistController.luau").bind(
            self.client.game, self.client.requireModule, self.client.readUpvalues)
        self.executor = self.h.lua.execute("""return {queued = {}, rawCalls = 0,
            Schedule = function(self, fn) self.queued[#self.queued+1] = fn end,
            Invoke = function(self) self.rawCalls = self.rawCalls+1; error('Raw Heist mutation forbidden') end,
            InvokeOwned = function(self) self.rawCalls = self.rawCalls+1; error('Raw Heist mutation forbidden') end,
            Drain = function(self) local q=self.queued; self.queued={}; for _, fn in ipairs(q) do fn() end end}
        """)
        self.plan = self.h.load("src/tabs/heists/HeistCallPlan.luau")
        self.lane = self.h.load("src/engine/RequestLane.luau").new(self.h.clock)
        self.adapter = self.h.load("src/transport/NativeDispatchAdapter.luau").new(
            self.plan, self.executor, self.lane, self.h.clock, None, self.controller)
        self.proposal = lua_table(self.h.lua, {"feature": "heists", "actionKey": "heists:h_a",
            "resources": {"cash": 10, "energy": 2}, "intent": {"kind": "heistStart",
            "heistId": "h_a", "expectedStake": 10, "expectedEnergy": 2, "needsSequence": True}})
        self.state = self.h.lua.table(recorded=0, delivered=0, unsent=0)
        self.returned = self.h.lua.eval("function(s) return function() assert(s.recorded==1); s.delivered=s.delivered+1 end end")(self.state)
        self.unsent = self.h.lua.eval("function(s) return function() s.unsent=s.unsent+1 end end")(self.state)
        self.allowed = self.h.lua.eval("function() return true end")
        self.authorize = self.h.lua.eval("""function(plan,p,s) return function()
            local call=plan.describe(p); call.nativeSequence=8
            call.recordHeistReturn=function() s.recorded=s.recorded+1; return true end
            return call
        end end""")(self.plan, self.proposal, self.state)

    def send(self, authorize):
        return self.adapter.Send(self.adapter, self.proposal, self.returned,
                                 self.allowed, None, self.unsent, authorize)

    def test_shared_native_act_dispatches_once_and_persists_before_delivery(self):
        self.assertTrue(self.send(self.authorize))
        self.executor.Drain(self.executor)
        self.assertEqual(len(self.client.heistCalls), 1)
        self.assertEqual(self.executor.rawCalls, 0)
        self.client.finishHeist(lua_table(self.h.lua, {"ok": True, "runId": "run-a"}))
        self.assertEqual((self.state.recorded, self.state.delivered), (1, 1))

    def test_native_queue_stays_globally_busy_past_logical_lease_deadline(self):
        self.send(self.authorize)
        self.executor.Drain(self.executor)
        self.h.at(46)
        self.assertTrue(self.adapter.InFlight(self.adapter))
        self.client.finishHeist(lua_table(self.h.lua, {"ok": True, "runId": "run-a"}))
        self.assertEqual(self.state.recorded, 1)
        self.assertEqual(self.state.delivered, 0)
        self.assertFalse(self.adapter.InFlight(self.adapter))

    def test_missing_durable_authorization_never_queues_or_calls_native_act(self):
        self.assertFalse(self.send(None))
        self.executor.Drain(self.executor)
        self.assertEqual(len(self.client.heistCalls), 0)
        self.assertEqual(self.executor.rawCalls, 0)


if __name__ == "__main__":
    unittest.main()
