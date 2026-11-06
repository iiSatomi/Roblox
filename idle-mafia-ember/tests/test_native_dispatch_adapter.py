"""Injected dispatch is gated before write-ahead recording and never touches Roblox."""
import unittest

from engine_harness import Harness, lua_table


class NativeDispatchAdapterTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.executor = self.h.lua.execute("""return {
            queued = {}, calls = {}, reply = { ok = true }, fail = false,
            Schedule = function(self, fn)
                self.queued[#self.queued + 1] = fn
            end,
            Invoke = function(self, remote, method, ...)
                self.calls[#self.calls + 1] = {
                    remote = remote, method = method,
                    arity = select('#', ...), args = table.pack(...),
                }
                if self.fail then error('interrupted') end
                return self.reply
            end,
            Drain = function(self)
                local queued = self.queued
                self.queued = {}
                for _, fn in ipairs(queued) do fn() end
            end,
        }""")
        plan = self.h.load("src/transport/NativeCallPlan.luau")
        adapter = self.h.load("src/transport/NativeDispatchAdapter.luau")
        self.transport = adapter.new(plan, self.executor)
        broker = self.h.load("src/engine/Broker.luau")
        self.broker = broker.new(self.h.clock, self.transport,
            self.h.journal, self.h.policy)
        store = self.h.lua.execute("""return { data = {}, strictRecovery = true,
            Read = function(self, key) return self.data[key] end,
            Write = function(self, key, value) self.data[key] = value; return true end }""")
        checkpoint = self.h.load("src/storage/Checkpoint.luau").new(store)
        self.session = self.h.load("src/engine/Session.luau").new(
            self.broker, checkpoint, lua_table(self.h.lua, self.h.session))

    def close(self):
        self.session.Close(self.session)

    def test_dispatch_uses_the_call_it_validated(self):
        plan = self.h.lua.execute("""return { count = 0,
            describe = function(proposal)
                planCount = (planCount or 0) + 1
                return { remote = planCount == 1 and 'DoJob' or 'Withdraw',
                    method = 'InvokeServer', arity = 0, args = {} }
            end }""")
        adapter = self.h.load("src/transport/NativeDispatchAdapter.luau")
        transport = adapter.new(plan, self.executor)
        transport.Send(transport, self.h.proposal(),
            self.h.lua.eval("function(_reply) end"),
            self.h.lua.eval("function() return true end"))
        self.executor.Drain(self.executor)
        self.assertEqual(self.h.lua.globals().planCount, 1)
        self.assertEqual(self.executor["calls"][1]["remote"], "DoJob")

    def test_durable_authorization_cannot_replace_the_validated_call(self):
        proposal = self.h.proposal()
        proposal.intent = lua_table(self.h.lua, {'kind': 'job','targetId': 'j_watch'})
        self.h.lua.globals().authorizationUnsent = 0
        self.transport.Send(self.transport, proposal, self.h.lua.eval('function() end'),
            self.h.lua.eval('function() return true end'), None,
            self.h.lua.eval('function() authorizationUnsent=authorizationUnsent+1 end'),
            self.h.lua.eval("function() return {remote='Withdraw',method='InvokeServer',arity=1,args={10}} end"))
        self.executor.Drain(self.executor)
        self.assertEqual(len(self.executor.calls), 0)
        self.assertEqual(self.h.lua.globals().authorizationUnsent, 1)

    def test_durable_authorization_must_recheck_the_guard_after_its_write(self):
        proposal = self.h.proposal()
        proposal.intent = lua_table(self.h.lua, {'kind': 'job','targetId': 'j_watch'})
        self.h.lua.globals().authorizationAllowed = True
        self.transport.Send(self.transport, proposal, self.h.lua.eval('function() end'),
            self.h.lua.eval('function() return authorizationAllowed end'), None, None,
            self.h.lua.eval("function() authorizationAllowed=false; return {remote='DoJob',method='InvokeServer',arity=1,args={'j_watch'}} end"))
        self.executor.Drain(self.executor)
        self.assertEqual(len(self.executor.calls), 0)

    def test_broker_dispatches_its_preflight_call_without_replanning(self):
        plan = self.h.lua.execute("""return {
            describe = function()
                planCount = (planCount or 0) + 1
                return { remote = planCount == 1 and 'DoJob' or 'Withdraw',
                    method = 'InvokeServer', arity = 0, args = {} }
            end }""")
        adapter = self.h.load("src/transport/NativeDispatchAdapter.luau")
        transport = adapter.new(plan, self.executor)
        broker = self.h.load("src/engine/Broker.luau").new(
            self.h.clock, transport, self.h.journal, self.h.policy)
        proposal, snapshot = self.h.proposal(), self.h.snapshot()
        self.assertEqual(broker.Offer(broker, proposal, snapshot)[0],
                         "admitted")
        self.assertEqual(broker.Tick(broker, snapshot), "sent")
        self.executor.Drain(self.executor)
        self.assertEqual(self.h.lua.globals().planCount, 1)
        self.assertEqual(self.executor["calls"][1]["remote"], "DoJob")

    def test_mismatched_preflight_refuses_unsent_call(self):
        proposal = self.h.proposal()
        proposal["intent"] = lua_table(self.h.lua, {
            "kind": "job", "targetId": "j_watch"})
        valid, _, token = self.transport.Validate(self.transport, proposal)
        self.assertTrue(valid)
        self.assertFalse(self.transport.Send(self.transport, proposal,
            self.h.lua.eval("function(_reply) end"),
            self.h.lua.eval("function() return true end"),
            self.h.lua.table()))
        self.assertEqual(len(self.executor["queued"]), 0)
        self.assertTrue(self.transport.Send(self.transport, proposal,
            self.h.lua.eval("function(_reply) end"),
            self.h.lua.eval("function() return true end"), token))

    def test_other_native_invocation_blocks_mutation_admission(self):
        self.executor["busy"] = True
        self.executor["InFlight"] = self.h.lua.eval(
            "function(self) return self.busy end")
        proposal = self.h.proposal()
        proposal["intent"] = lua_table(self.h.lua, {
            "kind": "job", "targetId": "j_watch"})
        snapshot = self.h.snapshot()
        self.assertEqual(self.session.Offer(self.session,
            proposal, snapshot)[0], "wait")
        self.assertEqual(len(self.executor["queued"]), 0)
        self.executor["busy"] = False
        self.assertEqual(self.session.Offer(self.session,
            proposal, snapshot)[0], "admitted")

    def test_unmapped_action_is_blocked_before_checkpoint_or_send(self):
        try:
            proposal = self.h.proposal(feature="operations", key="op:1")
            self.assertEqual(self.session.Offer(self.session,
                proposal, self.h.snapshot())[0], "admitted")
            self.assertEqual(self.session.Tick(self.session,
                self.h.snapshot()), "transport_blocked")
            self.assertEqual(self.session.Status(self.session)["uncertainCount"], 0)
            self.assertEqual(len(self.executor["queued"]), 0)
            self.assertIsNone(self.session.Status(self.session)["active"])
        finally:
            self.close()

    def test_job_dispatch_is_scheduled_and_reply_needs_state_proof(self):
        try:
            proposal = self.h.proposal()
            proposal["intent"] = lua_table(self.h.lua, {
                "kind": "job", "targetId": "j_watch"})
            self.assertEqual(self.session.Offer(self.session,
                proposal, self.h.snapshot())[0], "admitted")
            self.assertEqual(self.session.Tick(self.session,
                self.h.snapshot()), "sent")
            self.assertEqual(self.session.Status(self.session)["uncertainCount"], 1)
            self.assertEqual(len(self.executor["calls"]), 0)
            self.executor.Drain(self.executor)
            self.assertEqual(self.executor["calls"][1]["remote"], "DoJob")
            self.assertEqual(self.broker.Observe(self.broker,
                self.h.snapshot()), "pending")
            self.assertEqual(self.broker.Observe(self.broker,
                self.h.snapshot(revision=2,
                    proofKey="jobs:j_watch:1")), "confirmed")
            self.assertEqual(self.session.Status(self.session)["uncertainCount"], 0)
        finally:
            self.close()

    def test_interrupted_invocation_remains_uncertain_until_45_seconds(self):
        try:
            proposal = self.h.proposal()
            proposal["intent"] = lua_table(self.h.lua, {
                "kind": "job", "targetId": "j_watch"})
            self.executor["fail"] = True
            self.session.Offer(self.session, proposal, self.h.snapshot())
            self.assertEqual(self.session.Tick(self.session,
                self.h.snapshot()), "sent")
            self.executor.Drain(self.executor)
            self.assertEqual(self.session.Status(self.session)["uncertainCount"], 1)
            self.h.at(45)
            self.assertEqual(self.session.Tick(self.session,
                self.h.snapshot()), "skipped_unconfirmed")
            self.assertEqual(self.session.Status(self.session)["uncertainCount"], 1)
        finally:
            self.close()

    def test_explicit_schedule_refusal_does_not_leave_unsent_checkpoint(self):
        try:
            self.executor["Schedule"] = self.h.lua.eval("""function(self, fn)
                self.queued[#self.queued + 1] = fn
                return false
            end""")
            proposal = self.h.proposal()
            proposal["intent"] = lua_table(self.h.lua, {
                "kind": "job", "targetId": "j_watch"})
            snapshot = self.h.snapshot()
            self.assertEqual(self.session.Offer(self.session,
                proposal, snapshot)[0], "admitted")
            self.assertEqual(self.session.Tick(self.session, snapshot),
                             "schedule_failed")
            self.assertIsNone(self.session.Status(self.session)["active"])
            self.assertEqual(self.session.Status(self.session)["uncertainCount"], 0)
            self.executor.Drain(self.executor)
            self.assertEqual(len(self.executor["calls"]), 0)
            self.assertEqual(self.session.Offer(self.session,
                proposal, snapshot)[0], "admitted")
            self.executor["Schedule"] = self.h.lua.eval("""function(self, fn)
                self.queued[#self.queued + 1] = fn
                return true
            end""")
            self.assertEqual(self.session.Tick(self.session, snapshot), "sent")
            self.executor.Drain(self.executor)
            self.assertEqual(len(self.executor["calls"]), 1)
        finally:
            self.close()

    def test_no_argument_claim_passes_transport_validation(self):
        try:
            proposal = self.h.proposal(feature="groupBonus", key="group:1")
            proposal["intent"] = lua_table(self.h.lua, {
                "kind": "groupBonusClaim", "groupId": 674050067})
            self.assertEqual(self.session.Offer(self.session,
                proposal, self.h.snapshot())[0], "admitted")
            self.assertEqual(self.session.Tick(self.session,
                self.h.snapshot()), "sent")
            self.executor.Drain(self.executor)
            self.assertEqual(self.executor["calls"][1]["remote"],
                             "ClaimGroupBonus")
            self.assertEqual(self.executor["calls"][1]["arity"], 0)
        finally:
            self.close()

    def test_invoker_receives_trailing_nil_as_third_argument(self):
        proposal = self.h.proposal(feature="bossShop", key="shop:gear:1")
        proposal["intent"] = lua_table(self.h.lua, {
            "kind": "bossShopBuy", "item": "w_policebaton",
            "itemKind": "gear", "quantity": 1})
        self.transport.Send(self.transport, proposal,
            self.h.lua.eval("function(_reply) end"),
            self.h.lua.eval("function() return true end"))
        self.executor.Drain(self.executor)
        call = self.executor["calls"][1]
        self.assertEqual(call["remote"], "BossAction")
        self.assertEqual(call["arity"], 3)
        self.assertEqual(call["args"]["n"], 3)
        self.assertIsNone(call["args"][3])
        bonus = self.h.proposal(feature="bonuses", key="bonus:daily")
        bonus["intent"] = lua_table(self.h.lua, {
            "kind": "contractBonusClaim", "period": "daily",
            "command": "claimbonus"})
        self.transport.Send(self.transport, bonus,
            self.h.lua.eval("function(_reply) end"),
            self.h.lua.eval("function() return true end"))
        self.executor.Drain(self.executor)
        call = self.executor["calls"][2]
        self.assertEqual(call["remote"], "ContractAction")
        self.assertEqual(call["arity"], 3)
        self.assertEqual(call["args"][1], "claimbonus")
        self.assertIsNone(call["args"][2])
        self.assertIsNone(call["args"][3])

    def test_market_collect_keeps_all_three_trailing_nil_arguments(self):
        proposal = self.h.proposal(feature="marketManage", key="market:collect")
        proposal["intent"] = lua_table(self.h.lua, {
            "kind": "marketCollectEarnings", "earningsBefore": 50,
            "goldBefore": 10})
        self.transport.Send(self.transport, proposal,
            self.h.lua.eval("function(_reply) end"),
            self.h.lua.eval("function() return true end"))
        self.executor.Drain(self.executor)
        call = self.executor["calls"][1]
        self.assertEqual(call["remote"], "MarketAction")
        self.assertEqual(call["arity"], 4)
        self.assertEqual([call["args"][i] for i in range(1, 5)],
                         ["collect", None, None, None])

    def test_expired_queued_action_never_reaches_invoker(self):
        try:
            proposal = self.h.proposal()
            proposal["intent"] = lua_table(self.h.lua, {
                "kind": "job", "targetId": "j_watch"})
            self.session.Offer(self.session, proposal, self.h.snapshot())
            self.assertEqual(self.session.Tick(self.session,
                self.h.snapshot()), "sent")
            self.h.at(45)
            self.assertEqual(self.session.Tick(self.session,
                self.h.snapshot()), "skipped_unconfirmed")
            self.executor.Drain(self.executor)
            self.assertEqual(len(self.executor["calls"]), 0)
        finally:
            self.close()

    def test_stale_queued_preflight_never_reaches_invoker(self):
        try:
            proposal = self.h.proposal()
            proposal["intent"] = lua_table(self.h.lua, {
                "kind": "job", "targetId": "j_watch"})
            snapshot = self.h.snapshot()
            self.session.Offer(self.session, proposal, snapshot)
            self.assertEqual(self.session.Tick(self.session,
                snapshot), "sent")
            self.h.at(2.01)
            self.executor.Drain(self.executor)
            self.assertEqual(len(self.executor["calls"]), 0)
            self.assertEqual(self.session.Status(self.session)["uncertainCount"], 0)
            self.assertIsNone(self.session.Status(self.session)["active"])
            self.h.at(45)
            self.assertEqual(self.session.Tick(self.session,
                self.h.snapshot()), "idle")
        finally:
            self.close()

    def test_newer_observation_fences_queued_dispatch(self):
        try:
            proposal = self.h.proposal()
            proposal["intent"] = lua_table(self.h.lua, {
                "kind": "job", "targetId": "j_watch"})
            snapshot = self.h.snapshot()
            self.session.Offer(self.session, proposal, snapshot)
            self.assertEqual(self.session.Tick(self.session,
                snapshot), "sent")
            self.assertEqual(self.session.Observe(self.session,
                self.h.snapshot(revision=2)), "pending")
            self.executor.Drain(self.executor)
            self.assertEqual(len(self.executor["calls"]), 0)
        finally:
            self.close()

    def test_stopped_session_fences_queued_action(self):
        proposal = self.h.proposal()
        proposal["intent"] = lua_table(self.h.lua, {
            "kind": "job", "targetId": "j_watch"})
        self.session.Offer(self.session, proposal, self.h.snapshot())
        self.assertEqual(self.session.Tick(self.session,
            self.h.snapshot()), "sent")
        self.close()
        self.executor.Drain(self.executor)
        self.assertEqual(len(self.executor["calls"]), 0)

    def test_expired_invoke_releases_other_feature_while_return_is_late(self):
        try:
            proposal = self.h.proposal()
            proposal["intent"] = lua_table(self.h.lua, {
                "kind": "job", "targetId": "j_watch"})
            self.session.Offer(self.session, proposal, self.h.snapshot())
            self.h.lua.globals().advance_invoke_clock = lambda: self.h.at(45)
            self.h.lua.globals().test_session = self.session
            self.h.lua.globals().test_broker = self.broker
            second = self.h.proposal(feature="operations", key="op:2")
            second["resources"] = lua_table(self.h.lua, {})
            same_feature = self.h.proposal(key="jobs:retry")
            self.h.lua.globals().second_proposal = second
            self.h.lua.globals().same_feature_proposal = same_feature
            self.h.lua.globals().second_snapshot = self.h.snapshot(
                captured_at=45)
            self.executor["Invoke"] = self.h.lua.eval("""function(self, remote, method, ...)
                advance_invoke_clock()
                test_session:Tick(second_snapshot)
                self.same_feature = test_broker:Offer(
                    same_feature_proposal, second_snapshot)
                self.nested = test_broker:Offer(second_proposal, second_snapshot)
                return { ok = true }
            end""")
            self.assertEqual(self.session.Tick(self.session,
                self.h.snapshot()), "sent")
            self.executor.Drain(self.executor)
            self.assertEqual(self.executor["same_feature"], "blocked")
            self.assertEqual(self.executor["nested"], "admitted")
            self.assertFalse(self.transport.InFlight(self.transport))
        finally:
            self.close()

    def test_late_invoke_completion_preserves_newer_transport_owner(self):
        old = self.h.proposal()
        old["intent"] = lua_table(self.h.lua, {
            "kind": "job", "targetId": "j_watch"})
        newer = self.h.proposal(feature="bosses", key="bosses:next")
        self.h.lua.globals().old_dispatch = old
        self.h.lua.globals().new_dispatch = newer
        self.h.lua.globals().test_dispatch = self.transport
        self.executor["Invoke"] = self.h.lua.eval("""function()
            assert(test_dispatch:ReleaseExpired(old_dispatch))
            test_dispatch.invoking = { proposal = new_dispatch }
            return { ok = true }
        end""")
        self.transport.Send(self.transport, old,
            self.h.lua.eval("function() end"),
            self.h.lua.eval("function() return true end"))
        self.executor.Drain(self.executor)
        self.assertTrue(self.transport.InFlight(self.transport))
        self.assertTrue(self.transport.ReleaseExpired(self.transport, newer))
        self.assertFalse(self.transport.InFlight(self.transport))

    def test_yielding_preflight_rechecks_freshness_when_it_resumes(self):
        try:
            proposal = self.h.proposal()
            proposal.intent = lua_table(self.h.lua, {"kind": "job", "targetId": "j_watch"})
            self.h.policy.canDispatch = self.h.lua.eval("function() coroutine.yield('preflight_wait'); return true end")
            self.session.Offer(self.session, proposal, self.h.snapshot())
            self.session.Tick(self.session, self.h.snapshot())
            self.h.lua.globals().yieldingQueued = self.executor.queued[1]
            self.h.lua.execute("dispatchWait=coroutine.create(yieldingQueued); assert(select(2,coroutine.resume(dispatchWait))=='preflight_wait')")
            self.h.at(3)
            self.h.lua.execute("assert(coroutine.resume(dispatchWait))")
            self.assertEqual(len(self.executor.calls), 0)
            self.assertEqual(self.session.Status(self.session).uncertainCount, 0)
        finally:
            self.close()

    def test_unloaded_unsent_callback_cannot_erase_a_new_checkpoint_owner(self):
        try:
            proposal = self.h.proposal()
            proposal.intent = lua_table(self.h.lua, {"kind": "job", "targetId": "j_watch"})
            self.session.Offer(self.session, proposal, self.h.snapshot())
            self.session.Tick(self.session, self.h.snapshot())
            self.session.Close(self.session)
            module = self.h.load("src/storage/Checkpoint.luau")
            fresh = module.new(self.session.checkpoint.storage)
            fresh.Load(fresh, "user-a", self.h.session["place"], "release-a")
            other = self.h.proposal("operations", "new-owner")
            self.assertTrue(fresh.Save(fresh, other)[0])
            self.executor.Drain(self.executor)
            restored = module.new(self.session.checkpoint.storage)
            records, reason = restored.Load(restored, "user-a", self.h.session["place"], "release-a")
            self.assertIsNone(reason)
            self.assertEqual({row.actionKey for row in records.values()}, {proposal.actionKey, other.actionKey})
            self.assertEqual(len(self.executor.calls), 0)
        finally:
            self.close()

    def test_adapter_rechecks_lease_after_a_yielding_guard_without_releasing_new_owner(self):
        try:
            lane = self.h.load("src/engine/RequestLane.luau").new(self.h.clock)
            plan = self.h.load("src/transport/NativeCallPlan.luau")
            self.executor.InvokeOwned = self.h.lua.eval("function(self,lease,remote,method,...) return self:Invoke(remote,method,...) end")
            transport = self.h.load("src/transport/NativeDispatchAdapter.luau").new(plan, self.executor, lane, self.h.clock)
            proposal = self.h.proposal()
            proposal.intent = lua_table(self.h.lua, {"kind": "job", "targetId": "j_watch"})
            transport.Send(transport, proposal, self.h.lua.eval("function() end"),
                self.h.lua.eval("function() coroutine.yield('guard_wait');return true end"))
            self.h.lua.globals().yieldingQueued = self.executor.queued[1]
            self.h.lua.execute("dispatchWait=coroutine.create(yieldingQueued); assert(select(2,coroutine.resume(dispatchWait))=='guard_wait')")
            self.h.at(46)
            newer = lane.TryAcquire(lane, "mutation", "new-owner", 91)[0]
            self.assertIsNotNone(newer)
            self.h.lua.execute("assert(coroutine.resume(dispatchWait))")
            self.assertEqual(len(self.executor.calls), 0)
            self.assertTrue(lane.Owns(lane, newer))
        finally:
            self.close()


if __name__ == "__main__":
    unittest.main()
