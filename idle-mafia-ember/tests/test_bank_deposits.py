"""Bank deposits preserve purchase savings and prove exact transfer."""
import unittest

from engine_harness import Harness, lua_table


class BankDepositTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.context = self.h.load("src/game/Context.luau").new(self.h.contracts)
        self.reader = self.h.load("src/game/BankState.luau")
        self.planner = self.h.load("src/features/BankDeposits.luau")
        self.evidence = self.h.load("src/features/BankDepositsEvidence.luau")

    def raw(self, revision=1, cash=50000, banked=1000, savings=15000,
            no_fee=False):
        return self.h.snapshot(revision=revision,
            native={"fullSync": True, "cash": cash, "banked": banked,
                    "derived": {"noBankFees": no_fee}},
            bankConfig={"depositFee": 0.1},
            purchaseSavings={**self.h.session,
                             "revision": revision, "capturedAt": 0,
                             "amount": savings})

    def view(self, raw):
        context, reason = self.context.Read(self.context, raw,
            lua_table(self.h.lua, self.h.session), 0, 2)
        self.assertIsNone(reason)
        return self.reader.read(raw, context)

    def proposal(self, raw=None, threshold=10000, keep=0,
                 uncertain=0, enabled=True):
        view, reason = self.view(raw or self.raw())
        self.assertIsNone(reason)
        return self.planner.propose(view,
            lua_table(self.h.lua, {"enabled": enabled,
                                   "depositThreshold": threshold,
                                   "cashToKeep": keep}),
            lua_table(self.h.lua, {"cash": 0, "uncertainCash": uncertain}))

    def test_exact_excess_with_purchase_savings_and_uncertain_cash(self):
        proposal, reason = self.proposal(uncertain=5000)
        self.assertIsNone(reason)
        self.assertEqual(proposal["resources"]["cash"], 30000)
        self.assertEqual(proposal["intent"]["amount"], 30000)
        self.assertEqual(proposal["intent"]["expectedFeeRate"], 0.1)
        no_fee, _ = self.proposal(self.raw(no_fee=True))
        self.assertEqual(no_fee["intent"]["expectedFeeRate"], 0)

    def test_reply_and_exact_replication_confirm(self):
        before = self.raw()
        proposal, _ = self.proposal(before)
        self.assertEqual(proposal["intent"]["amount"], 35000)
        baseline, reason = self.evidence.capture(proposal, before)
        self.assertIsNone(reason)
        header, _ = self.h.contracts.validateSnapshot(before,
            lua_table(self.h.lua, self.h.session))
        reply = lua_table(self.h.lua, {"ok": True, "fee": 3500,
                                        "kept": 31500})
        self.assertEqual(self.evidence.evaluate(proposal, header,
            self.raw(2), reply, baseline), "pending")
        self.assertEqual(self.evidence.evaluate(proposal, header,
            self.raw(2, cash=15000, banked=32500), reply, baseline),
            "confirmed")

    def test_missing_savings_bad_fee_and_below_threshold_block(self):
        self.assertIsNone(self.proposal(enabled=False)[0])
        self.assertIsNone(self.proposal(self.raw(cash=23000))[0])
        bad = self.raw()
        bad["purchaseSavings"] = None
        self.assertIsNone(self.view(bad)[0])
        bad = self.raw()
        bad["native"]["derived"]["noBankFees"] = None
        self.assertIsNone(self.view(bad)[0])
        bad = self.raw()
        bad["bankConfig"]["depositFee"] = 2
        self.assertIsNone(self.view(bad)[0])

    def test_bad_reply_or_cash_mismatch_stays_pending(self):
        before = self.raw()
        proposal, _ = self.proposal(before)
        baseline, _ = self.evidence.capture(proposal, before)
        header, _ = self.h.contracts.validateSnapshot(before,
            lua_table(self.h.lua, self.h.session))
        after = self.raw(2, cash=15000, banked=32500)
        self.assertEqual(self.evidence.evaluate(proposal, header, after,
            lua_table(self.h.lua, {"ok": True, "fee": 3500,
                                    "kept": 35000}), baseline), "pending")
        self.assertEqual(self.evidence.evaluate(proposal, header,
            self.raw(2, cash=15001, banked=32500),
            lua_table(self.h.lua, {"ok": True, "fee": 3500,
                                    "kept": 31500}), baseline), "pending")
        self.assertEqual(self.evidence.evaluate(proposal, header,
            self.raw(2), lua_table(self.h.lua, {"ok": False}), baseline),
            "rejected")

    def test_pending_or_negative_with_changed_balances_cannot_resolve_a_transfer(self):
        before=self.raw();proposal=self.proposal(before)[0]
        baseline=self.evidence.capture(proposal,before)[0]
        header=self.h.contracts.validateSnapshot(before,lua_table(self.h.lua,self.h.session))[0]
        for after,reply in ((self.raw(2,cash=40000),{"ok":False}),
                (self.raw(2,banked=2000),{"ok":False}),
                (self.raw(2,cash=15000,banked=32500),{"ok":True,"pending":True,"fee":3500,"kept":31500})):
            self.assertEqual(self.evidence.evaluate(proposal,header,after,lua_table(self.h.lua,reply),baseline),"pending")

    def test_fee_or_pass_change_blocks_send(self):
        before = self.raw()
        proposal, _ = self.proposal(before)
        before["bankConfig"]["depositFee"] = 0.2
        self.assertIsNone(self.evidence.capture(proposal, before)[0])
        before["bankConfig"]["depositFee"] = 0.1
        before["native"]["derived"]["noBankFees"] = True
        self.assertIsNone(self.evidence.capture(proposal, before)[0])

    def test_fractional_native_balances_use_integer_deposit(self):
        before = self.raw(cash=50000.25, banked=1000.75)
        proposal, reason = self.proposal(before)
        self.assertIsNone(reason)
        self.assertEqual(proposal["intent"]["amount"], 35000)
        baseline, reason = self.evidence.capture(proposal, before)
        self.assertIsNone(reason)
        header, _ = self.h.contracts.validateSnapshot(before,
            lua_table(self.h.lua, self.h.session))
        after = self.raw(2, cash=15000.25, banked=32500.75)
        reply = lua_table(self.h.lua, {"ok": True, "fee": 3500,
                                        "kept": 31500})
        self.assertEqual(self.evidence.evaluate(proposal, header,
            after, reply, baseline), "confirmed")


if __name__ == "__main__":
    unittest.main()
