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
            Write = function(self, key, value) self.data[key] = value end }""")
        checkpoint = self.h.load("src/storage/Checkpoint.luau").new(store)
        self.session = self.h.load("src/engine/Session.luau").new(
            self.broker, checkpoint, lua_table(self.h.lua, self.h.session))

    def close(self):
        self.session.Close(self.session)

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
            self.h.at(45)
            self.assertEqual(self.session.Tick(self.session,
                self.h.snapshot()), "skipped_unconfirmed")
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

    def test_invoke_still_running_blocks_next_broker_owner(self):
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
            self.h.lua.globals().second_proposal = second
            self.h.lua.globals().second_snapshot = self.h.snapshot()
            self.executor["Invoke"] = self.h.lua.eval("""function(self, remote, method, ...)
                advance_invoke_clock()
                test_session:Tick(second_snapshot)
                self.nested = test_broker:Offer(second_proposal, second_snapshot)
                return { ok = true }
            end""")
            self.assertEqual(self.session.Tick(self.session,
                self.h.snapshot()), "sent")
            self.executor.Drain(self.executor)
            self.assertEqual(self.executor["nested"], "wait")
            self.assertFalse(self.transport.InFlight(self.transport))
        finally:
            self.close()


if __name__ == "__main__":
    unittest.main()
