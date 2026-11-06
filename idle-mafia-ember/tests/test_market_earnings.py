"""Sold-listing earnings collection requires exact newer Gold transfer."""
import unittest

from engine_harness import Harness, lua_table


class MarketEarningsTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.state = self.h.load("src/game/MarketEarningsState.luau")
        self.feature = self.h.load("src/features/MarketEarnings.luau")
        self.evidence = self.h.load("src/features/MarketEarningsEvidence.luau")
        self.call_plan = self.h.load("src/transport/NativeCallPlan.luau")

    def raw(self, revision=1, earnings=50, gold=10, full=True):
        return self.h.snapshot(revision=revision, native={
            "fullSync": full, "market": {"earnings": earnings},
            "inventory": {"gold_bar": gold}})

    def proposal(self):
        raw = self.raw()
        view, reason = self.state.read(raw, self.h.snapshot())
        self.assertIsNone(reason)
        proposal, reason = self.feature.propose(view,
            lua_table(self.h.lua, {"enabled": True, "minEarnings": 20}))
        self.assertIsNone(reason)
        return raw, proposal

    def test_eligibility_and_opt_in(self):
        self.assertIsNone(self.state.read(self.raw(full=False),
            self.h.snapshot())[0])
        self.assertIsNone(self.state.read(self.raw(earnings=0),
            self.h.snapshot())[0])
        view = self.state.read(self.raw(), self.h.snapshot())[0]
        self.assertIsNotNone(self.feature.propose(view,
            lua_table(self.h.lua, {"enabled": True}))[0])
        self.assertIsNone(self.feature.propose(view,
            lua_table(self.h.lua, {"enabled": False, "minEarnings": 1}))[0])
        self.assertIsNone(self.feature.propose(view,
            lua_table(self.h.lua, {"enabled": True, "minEarnings": 51}))[0])

    def test_saved_four_argument_collect_call(self):
        _, proposal = self.proposal()
        call, reason = self.call_plan.describe(proposal)
        self.assertIsNone(reason)
        self.assertEqual(call["remote"], "MarketAction")
        self.assertEqual(call["arity"], 4)
        self.assertEqual([call["args"][i] for i in range(1, 5)],
                         ["collect", None, None, None])

    def test_reply_needs_exact_newer_state(self):
        before, proposal = self.proposal()
        baseline, reason = self.evidence.capture(proposal, before)
        self.assertIsNone(reason)
        good = self.raw(revision=2, earnings=0, gold=60)
        pending = self.raw(revision=2, earnings=50, gold=10)
        reply = lua_table(self.h.lua, {"ok": True})
        self.assertEqual(self.evidence.evaluate(proposal, before, pending,
            reply, baseline), "pending")
        self.assertEqual(self.evidence.evaluate(proposal, before,
            self.raw(revision=2, earnings=0, gold=61), reply, baseline), "pending")
        self.assertEqual(self.evidence.evaluate(proposal, before,
            self.raw(revision=2, earnings=0, gold=60, full=False),
            reply, baseline), "pending")
        self.assertEqual(self.evidence.evaluate(proposal, before, good,
            reply, baseline), "confirmed")

    def test_preflight_and_rejection_fail_closed(self):
        before, proposal = self.proposal()
        self.assertIsNone(self.evidence.capture(proposal,
            self.raw(earnings=49))[0])
        baseline = self.evidence.capture(proposal, before)[0]
        self.assertEqual(self.evidence.evaluate(proposal, before,
            self.raw(revision=2, earnings=50, gold=10),
            lua_table(self.h.lua, {"ok": False}), baseline), "rejected")

    def test_broker_requires_newer_transfer_after_injected_dispatch(self):
        before, proposal = self.proposal()
        executor = self.h.lua.execute("""return {
            queued = {}, calls = {},
            Schedule = function(self, fn) self.queued[#self.queued + 1] = fn end,
            Invoke = function(self, remote, method, ...)
                self.calls[#self.calls + 1] = { remote = remote,
                    arity = select('#', ...), args = table.pack(...) }
                return { ok = true }
            end,
            Drain = function(self)
                local queued = self.queued
                self.queued = {}
                for _, fn in ipairs(queued) do fn() end
            end,
        }""")
        adapter = self.h.load("src/transport/NativeDispatchAdapter.luau").new(
            self.call_plan, executor)
        policy = self.h.policy
        policy["captureBefore"] = self.evidence.capture
        policy["confirm"] = self.evidence.evaluate
        broker = self.h.load("src/engine/Broker.luau").new(
            self.h.clock, adapter, self.h.journal, policy)
        store = self.h.lua.execute("""return { data = {}, strictRecovery = true,
            Read = function(self, key) return self.data[key] end,
            Write = function(self, key, value) self.data[key] = value end,
        }""")
        checkpoint = self.h.load("src/storage/Checkpoint.luau").new(store)
        session = self.h.load("src/engine/Session.luau").new(
            broker, checkpoint, lua_table(self.h.lua, self.h.session))
        try:
            self.assertEqual(session.Offer(session, proposal, before)[0], "admitted")
            self.assertEqual(session.Tick(session, before), "sent")
            self.assertEqual(session.Status(session)["uncertainCount"], 1)
            executor.Drain(executor)
            self.assertEqual(executor["calls"][1]["arity"], 4)
            self.assertEqual(session.Observe(session,
                self.raw(revision=2, earnings=50, gold=10)), "pending")
            self.assertEqual(session.Observe(session,
                self.raw(revision=2, earnings=0, gold=60)), "confirmed")
            self.assertEqual(session.Status(session)["uncertainCount"], 0)
        finally:
            session.Close(session)


if __name__ == "__main__":
    unittest.main()
