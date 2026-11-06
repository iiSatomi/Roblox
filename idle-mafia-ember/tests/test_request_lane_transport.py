"""Queued mutation custody, 45s expiry and old coroutine returns share one owner."""
import unittest

from engine_harness import Harness, lua_table


class RequestLaneTransportTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.lane = self.h.load("src/engine/RequestLane.luau").new(self.h.clock)
        self.executor = self.h.lua.execute("""return {queued={},calls={},
            Schedule=function(self,fn) self.queued[#self.queued+1]=fn; return true end,
            Invoke=function() error('Unowned invocation') end,
            InvokeOwned=function(self,token,remote,method,...)
                self.calls[#self.calls+1]={token=token,remote=remote,args={...}}
                return {ok=true}
            end}""")
        self.adapter = self.h.load("src/transport/NativeDispatchAdapter.luau").new(
            self.h.load("src/transport/NativeCallPlan.luau"), self.executor, self.lane, self.h.clock)
        self.broker = self.h.load("src/engine/Broker.luau").new(self.h.clock,
            self.adapter, self.h.journal, self.h.policy)

    def proposal(self, key="jobs:one"):
        proposal = self.h.proposal(key=key)
        proposal.intent = lua_table(self.h.lua, {"kind": "job", "targetId": "j_watch"})
        return proposal

    def test_queued_mutation_reserves_lane_before_callback_and_holds_until_proof(self):
        proposal, before = self.proposal(), self.h.snapshot()
        self.broker.Offer(self.broker, proposal, before)
        self.broker.Tick(self.broker, before)
        self.assertIsNone(self.adapter.ReadLease(self.adapter, "jobs"))
        self.assertIsNone(self.adapter.ReadLease(self.adapter, "familyBossClaims"))
        self.assertEqual(self.lane.Status(self.lane).active.kind, "mutation")
        self.assertIsNone(self.lane.TryAcquire(self.lane, "read", "heists:board", 5)[0])
        self.executor.queued[1]()
        self.assertEqual(len(self.executor.calls), 1)
        self.assertIsNotNone(self.adapter.ReadLease(self.adapter, "jobs"))
        self.assertIsNotNone(self.lane.Status(self.lane).active)
        self.h.at(1)
        after = self.h.snapshot(revision=2, proofKey=proposal.actionKey)
        self.assertEqual(self.broker.Observe(self.broker, after), "confirmed")
        self.assertIsNone(self.lane.Status(self.lane).active)

    def test_busy_read_blocks_admission_and_expired_queued_mutation_does_not_invoke(self):
        read, _ = self.lane.TryAcquire(self.lane, "read", "market:browse", 5)
        self.assertEqual(self.broker.Offer(self.broker, self.proposal(), self.h.snapshot())[0], "wait")
        self.lane.Release(self.lane, read, "returned")
        self.broker.Offer(self.broker, self.proposal(), self.h.snapshot())
        self.broker.Tick(self.broker, self.h.snapshot())
        self.h.at(45)
        self.assertEqual(self.broker.Tick(self.broker, self.h.snapshot(2)), "skipped_unconfirmed")
        newer, _ = self.lane.TryAcquire(self.lane, "read", "family:state", 50)
        self.executor.queued[1]()
        self.assertEqual(len(self.executor.calls), 0)
        self.assertTrue(self.lane.Owns(self.lane, newer))

    def test_resolver_expired_physical_call_does_not_block_or_clear_new_owner(self):
        self.h.lua.globals().lane = self.lane
        self.h.lua.globals().resolverModule = self.h.load("src/transport/NativeRemoteResolver.luau")
        state = self.h.lua.execute("""
            local folder={}; local remote={Parent=folder}
            function folder:FindFirstChild() return remote end
            function remote:IsA(kind) return kind=='RemoteFunction' end
            function remote:InvokeServer(...) coroutine.yield('held'); return {ok=true} end
            local resolver=resolverModule.new(folder,lane)
            local old=lane:TryAcquire('mutation','old',45)
            local co=coroutine.create(function() return resolver:InvokeOwned(old,'DoJob') end)
            assert(coroutine.resume(co))
            return {resolver=resolver,old=old,co=co}
        """)
        self.assertTrue(state.resolver.InFlight(state.resolver))
        self.h.at(45)
        self.assertFalse(state.resolver.InFlight(state.resolver))
        self.h.lua.globals().held = state
        self.h.lua.execute("""
            held.new=lane:TryAcquire('read','new',50)
            held.second=coroutine.create(function() return held.resolver:InvokeOwned(held.new,'DoJob') end)
            assert(coroutine.resume(held.second))
            assert(coroutine.resume(held.co))
        """)
        self.assertTrue(state.resolver.InFlight(state.resolver))
        self.assertTrue(self.lane.Owns(self.lane, state.new))
        with self.assertRaises(Exception): state.resolver.Invoke(state.resolver, "DoJob")
        self.h.lua.execute("assert(coroutine.resume(held.second))")
        self.assertFalse(state.resolver.InFlight(state.resolver))

    def test_schedule_refusal_releases_known_unsent_lease(self):
        self.executor.Schedule = self.h.lua.eval("function() return false end")
        self.broker.Offer(self.broker, self.proposal(), self.h.snapshot())
        self.broker.Tick(self.broker, self.h.snapshot())
        self.assertIsNone(self.lane.Status(self.lane).active)
        self.assertEqual(len(self.executor.calls), 0)


if __name__ == "__main__":
    unittest.main()
