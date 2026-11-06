"""Snapshot-bound reads share mutation ownership and fence late/disabled work."""
import unittest

from engine_harness import Harness, lua_table


class ReadCoordinatorTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.lane = self.h.load("src/engine/RequestLane.luau").new(self.h.clock)
        self.budget = self.h.load("src/engine/ReadBudget.luau").new(self.h.clock,
            lua_table(self.h.lua, [{"id": "family", "interval": 1}, {"id": "heists", "interval": 1}]), 5, 60)
        self.h.lua.globals().current = self.h.snapshot(native={"fullSync": True, "serverNow": 1000})
        self.executor = self.h.lua.execute("""return {queued={},calls=0,
            Schedule=function(self,fn) self.queued[#self.queued+1]=fn; return true end,
            InvokeOwned=function(self,token,remote,method,...)
                self.calls=self.calls+1
                if self.hang then coroutine.yield('held') end
                return {ok=self.fail~=true,value=1}
            end}""")
        self.h.lua.globals().commits = self.h.lua.table()
        self.sources = self.h.lua.execute("""return {
            {id='family',prepare=function() return {remote='FamilyBossAction',method='InvokeServer',arity=2,args={'state'}} end,
                accept=function(raw,call,reply) if reply.ok then return {value=reply.value} end end,
                commit=function(value) commits[#commits+1]='family'; return true end},
            {id='heists',prepare=function() return {remote='HeistAction',method='InvokeServer',arity=1,args={'board'}} end,
                accept=function(raw,call,reply) if reply.ok then return {value=reply.value} end end,
                commit=function(value) commits[#commits+1]='heists'; return true end}
        }""")
        self.coordinator = self.h.load("src/transport/ReadCoordinator.luau").new(lua_table(self.h.lua, {
            "clock": self.h.clock, "lane": self.lane, "budget": self.budget, "executor": self.executor,
            "sources": self.sources, "currentSnapshot": self.h.lua.eval("function() return current end")}))

    def step(self, family=True, heists=True):
        return self.coordinator.Step(self.coordinator, self.h.lua.globals().current,
            lua_table(self.h.lua, {"family": family, "heists": heists}))

    def test_territory_map_uses_exact_four_arguments_with_nil_trailing_slots(self):
        self.coordinator.Close(self.coordinator)
        for arity, third, fourth, expected in ((2, None, None, "blocked"), (4, None, None, "queued"),
                (4, "unexpected", None, "blocked"), (4, None, 1, "blocked")):
            with self.subTest(arity=arity, third=third, fourth=fourth):
                self.h.lua.globals().mapReadCall = lua_table(self.h.lua, {"remote": "TerritoryView", "method": "InvokeServer",
                    "arity": arity, "args": {1: "map", 2: "jade_harbor", 3: third, 4: fourth}})
                self.sources[1].prepare = self.h.lua.eval("function() return mapReadCall end")
                self.budget = self.h.load("src/engine/ReadBudget.luau").new(self.h.clock,
                    lua_table(self.h.lua, [{"id": "family", "interval": 1}]), 5, 60)
                self.coordinator = self.h.load("src/transport/ReadCoordinator.luau").new(lua_table(self.h.lua, {
                    "clock": self.h.clock, "lane": self.lane, "budget": self.budget, "executor": self.executor,
                    "sources": [self.sources[1]], "currentSnapshot": self.h.lua.eval("function() return current end")}))
                actual = self.step()
                if expected == "queued" and actual == "queued": self.executor.queued[len(self.executor.queued)]()
                self.coordinator.Close(self.coordinator)
                self.assertEqual(actual, expected)

    def test_reserves_before_defer_and_releases_after_accepted_commit(self):
        self.assertEqual(self.step(), "queued")
        self.assertEqual(self.lane.Status(self.lane).active.kind, "read")
        self.assertIsNone(self.lane.TryAcquire(self.lane, "mutation", "jobs:one", 45)[0])
        self.executor.queued[1]()
        self.assertEqual((self.executor.calls, len(self.h.lua.globals().commits)), (1, 1))
        self.assertIsNone(self.coordinator.Status(self.coordinator).reasons.family)
        self.assertIsNone(self.lane.Status(self.lane).active)
        self.assertEqual(self.step(), "queued")
        self.executor.queued[2]()
        self.assertEqual(self.h.lua.globals().commits[2], "heists")

    def test_changed_full_sync_or_disabled_queue_cannot_invoke(self):
        self.step()
        self.h.lua.globals().current.revision = 2
        self.executor.queued[1]()
        self.assertEqual(self.executor.calls, 0)
        self.step(False, True)
        self.step(False, False)
        self.executor.queued[2]()
        self.assertEqual(self.executor.calls, 0)

    def test_timeout_of_hung_read_allows_another_source_and_ignores_old_return(self):
        self.executor.hang = True
        self.step()
        self.h.lua.globals().queuedRead = self.executor.queued[1]
        self.h.lua.execute("oldRead=coroutine.create(queuedRead); assert(coroutine.resume(oldRead))")
        self.h.at(5)
        self.h.lua.globals().current = self.h.snapshot(revision=2, native={"fullSync": True, "serverNow": 1005})
        self.assertEqual(self.step(), "queued")
        self.assertEqual(self.budget.Status(self.budget).family.failures, 1)
        self.h.lua.execute("assert(coroutine.resume(oldRead))")
        self.assertEqual(len(self.h.lua.globals().commits), 0)
        self.assertIsNotNone(self.lane.Status(self.lane).active)
        self.executor.hang = False
        self.executor.queued[2]()
        self.assertEqual(self.h.lua.globals().commits[1], "heists")

    def test_mutation_commands_are_refused_even_if_source_calls_them_reads(self):
        self.sources[1].prepare = self.h.lua.eval("function() return {remote='FamilyBossAction',method='InvokeServer',arity=1,args={'attack'},kind='readOnly'} end")
        # Build again so the constructor sees the deliberately invalid source.
        self.coordinator.Close(self.coordinator)
        self.budget = self.h.load("src/engine/ReadBudget.luau").new(self.h.clock,
            lua_table(self.h.lua, [{"id": "family", "interval": 1}]), 5, 60)
        self.coordinator = self.h.load("src/transport/ReadCoordinator.luau").new(lua_table(self.h.lua, {
            "clock": self.h.clock, "lane": self.lane, "budget": self.budget, "executor": self.executor,
            "sources": [self.sources[1]], "currentSnapshot": self.h.lua.eval("function() return current end")}))
        self.assertEqual(self.step(), "blocked")
        self.assertEqual(self.executor.calls, 0)
        self.assertEqual(len(self.executor.queued), 0)

    def test_close_fences_queued_work_and_does_not_close_shared_lane(self):
        self.step()
        self.coordinator.Close(self.coordinator)
        self.executor.queued[1]()
        self.assertEqual(self.executor.calls, 0)
        self.assertIsNotNone(self.lane.TryAcquire(self.lane, "mutation", "jobs:one", 45)[0])

    def test_failure_backs_off_only_that_source(self):
        self.executor.fail = True
        self.step()
        self.executor.queued[1]()
        self.assertEqual(self.budget.Status(self.budget).family.failures, 1)
        self.executor.fail = False
        self.assertEqual(self.step(), "queued")
        self.executor.queued[2]()
        self.assertEqual(self.h.lua.globals().commits[1], "heists")

    def with_confirmation_source(self):
        self.coordinator.Close(self.coordinator)
        self.sources[1].confirmFeatures = lua_table(self.h.lua, {"familyBossClaims": True})
        self.budget = self.h.load("src/engine/ReadBudget.luau").new(self.h.clock,
            lua_table(self.h.lua, [{"id": "family", "interval": 1}, {"id": "heists", "interval": 1}]), 5, 60)
        self.coordinator = self.h.load("src/transport/ReadCoordinator.luau").new(lua_table(self.h.lua, {
            "clock": self.h.clock, "lane": self.lane, "budget": self.budget, "executor": self.executor,
            "sources": self.sources, "currentSnapshot": self.h.lua.eval("function() return current end"),
            "borrowLease": self.h.lua.eval("function(feature) if feature=='familyBossClaims' then return heldMutation end end")}))
        token, _ = self.lane.TryAcquire(self.lane, "mutation", "family:claim:one", 45)
        self.h.lua.globals().heldMutation = token
        return token

    def test_exact_confirmation_read_keeps_mutation_owner_until_broker_resolves(self):
        token = self.with_confirmation_source()
        self.assertEqual(self.step(), "queued")
        self.executor.queued[1]()
        self.assertTrue(self.lane.Owns(self.lane, token))
        self.assertEqual(self.h.lua.globals().commits[1], "family")
        self.assertEqual(self.step(False, True), "busy")
        self.assertEqual(len(self.executor.queued), 1)

    def test_confirmation_timeout_or_close_never_releases_the_mutation(self):
        token = self.with_confirmation_source()
        self.executor.hang = True
        self.step()
        self.h.lua.globals().queuedRead = self.executor.queued[1]
        self.h.lua.execute("oldRead=coroutine.create(queuedRead); assert(coroutine.resume(oldRead))")
        self.h.at(5)
        self.h.lua.globals().current = self.h.snapshot(2, native={"fullSync": True, "serverNow": 1005})
        self.assertEqual(self.step(), "idle")
        self.assertTrue(self.lane.Owns(self.lane, token))
        self.coordinator.Close(self.coordinator)
        self.h.lua.execute("assert(coroutine.resume(oldRead))")
        self.assertEqual(len(self.h.lua.globals().commits), 0)
        self.assertTrue(self.lane.Owns(self.lane, token))



    def test_player_profile_read_requires_exact_positive_integral_target(self):
        for target in (None,0,-1,1.5,'42',float('inf'),float('nan')):
            with self.subTest(target=target):
                self.setUp();self.h.lua.globals().profileReadCall=lua_table(self.h.lua,{'remote':'PlayerProfile',
                    'method':'InvokeServer','arity':1,'args':{1:target} if target is not None else {}})
                self.sources[1].prepare=self.h.lua.eval('function() return profileReadCall end')
                self.coordinator=self.h.load('src/transport/ReadCoordinator.luau').new(lua_table(self.h.lua,{
                    'clock':self.h.clock,'lane':self.lane,'budget':self.budget,'executor':self.executor,
                    'sources':self.sources,'currentSnapshot':self.h.lua.eval('function() return current end')}))
                self.assertEqual(self.step(True,False),'blocked');self.assertEqual(len(self.executor.queued),0)
        self.setUp();self.sources[1].prepare=self.h.lua.eval("function() return {remote='PlayerProfile',method='InvokeServer',arity=1,args={42}} end")
        self.coordinator=self.h.load('src/transport/ReadCoordinator.luau').new(lua_table(self.h.lua,{
            'clock':self.h.clock,'lane':self.lane,'budget':self.budget,'executor':self.executor,
            'sources':self.sources,'currentSnapshot':self.h.lua.eval('function() return current end')}))
        self.assertEqual(self.step(True,False),'queued');self.executor.queued[1]();self.assertEqual(self.executor.calls,1)

if __name__ == "__main__":
    unittest.main()
