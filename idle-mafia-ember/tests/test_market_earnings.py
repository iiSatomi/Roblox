"""Sold-listing earnings collection requires exact newer Gold transfer."""
import unittest

from engine_harness import Harness, lua_table


class MarketEarningsTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.state = self.h.load("src/game/MarketEarningsState.luau")
        self.feature = self.h.load("src/features/MarketEarnings.luau")
        self.evidence = self.h.load("src/features/MarketEarningsEvidence.luau")
        base = self.h.load("src/transport/NativeCallPlan.luau")
        market = self.h.load(
            "src/tabs/blackMarket/MarketCallPlan.luau")
        self.call_plan = base.withMarket(base, market)

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

    def test_absent_gold_inventory_key_means_zero_balance(self):
        before = self.raw(gold=0)
        before["native"]["inventory"]["gold_bar"] = None
        view, reason = self.state.read(before, self.h.snapshot())
        self.assertIsNone(reason)
        self.assertEqual(view.gold, 0)
        proposal = self.feature.propose(view,
            lua_table(self.h.lua, {"enabled": True, "minEarnings": 1}))[0]
        baseline, reason = self.evidence.capture(proposal, before)
        self.assertIsNone(reason)
        self.assertEqual(baseline.gold, 0)

    def test_saved_four_argument_collect_call(self):
        _, proposal = self.proposal()
        call, reason = self.call_plan.describe(proposal)
        self.assertIsNone(reason)
        self.assertEqual(call["remote"], "MarketAction")
        self.assertEqual(call["arity"], 4)
        self.assertEqual([call["args"][i] for i in range(1, 5)],
                         ["collect", None, None, None])

    def test_market_trade_has_no_call_until_transaction_is_owned(self):
        for feature, intent in (
            ("marketFlip", {"kind": "marketBuy", "listingId": 42}),
            ("marketRent", {"kind": "marketRent", "periods": 1,
                "cost": 1, "durationSeconds": 43200}),
            ("marketSell", {"kind": "marketList", "item": "w_baton"}),
        ):
            with self.subTest(feature=feature):
                call, reason = self.call_plan.describe(lua_table(self.h.lua, {
                    "feature": feature, "intent": intent}))
                self.assertIsNone(call)
                self.assertIn("Unverified", reason)

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

    def test_transient_codes_cannot_prove_a_terminal_result_live_or_after_reload(self):
        before, proposal = self.proposal()
        before.native.serverNow = 1000
        baseline = self.evidence.capture(proposal, before)[0]
        for code in ("rate_limited", "busy", "presence"):
            for ok in (False, True):
                with self.subTest(code=code, ok=ok):
                    reply = lua_table(self.h.lua, {"ok": ok, "code": code})
                    after = self.raw(revision=2, earnings=0 if ok else 50, gold=60 if ok else 10)
                    after.native.serverNow = 1001
                    self.assertEqual(self.evidence.evaluate(proposal, before, after, reply, baseline), "pending")
                    after.session = "reloaded"
                    after.revision = 0
                    data = lua_table(self.h.lua, {"proposal": proposal, "before": before,
                        "baseline": baseline, "reply": reply})
                    self.assertIsNone(self.evidence.recoverSaved(data, after))

    def test_pending_or_unrelated_negative_result_cannot_release_claim(self):
        before, proposal = self.proposal()
        baseline = self.evidence.capture(proposal,before)[0]
        self.assertEqual(self.evidence.evaluate(proposal,before,self.raw(revision=2),
            lua_table(self.h.lua,{'ok':False,'pending':True}),baseline),'pending')
        self.assertEqual(self.evidence.evaluate(proposal,before,self.raw(revision=2,gold=9),
            lua_table(self.h.lua,{'ok':False}),baseline),'pending')
        self.assertEqual(self.evidence.evaluate(proposal,before,self.raw(),
            lua_table(self.h.lua,{'ok':False}),baseline),'pending')

    def test_saved_earned_payout_requires_original_terms_and_advancing_native_clock(self):
        before, proposal = self.proposal()
        before.native.serverNow = 1000
        baseline = self.evidence.capture(proposal,before)[0]
        data = lua_table(self.h.lua,{'proposal':proposal,'before':before,'baseline':baseline,'reply':{'ok':True}})
        after = self.raw(revision=0,earnings=0,gold=60)
        after.session = 'reloaded'
        after.native.serverNow = 1001
        self.assertEqual(self.evidence.recoverSaved(data,after),'confirmed')
        for value in (None,999,1000):
            after.native.serverNow = value
            self.assertIsNone(self.evidence.recoverSaved(data,after))
        after.native.serverNow = 1001
        data.baseline.gold = 9
        self.assertIsNone(self.evidence.recoverSaved(data,after))

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
            Write = function(self, key, value) self.data[key] = value; return true end,
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
