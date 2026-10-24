"""Withdrawal proposals require an enabled exact purchase shortfall."""
import unittest

from engine_harness import Harness, lua_table


class PurposeWithdrawTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.context = self.h.load("src/game/Context.luau").new(self.h.contracts)
        self.reader = self.h.load("src/game/WithdrawalState.luau")
        self.planner = self.h.load("src/features/PurposeWithdrawals.luau")
        self.evidence = self.h.load("src/features/PurposeWithdrawalsEvidence.luau")

    def raw(self, revision=1, cash=1000, banked=20000,
            purpose="safehouse", required=8000, request=True):
        data = self.h.snapshot(revision=revision,
            native={"fullSync": True, "cash": cash, "banked": banked})
        if request:
            data["fundingRequest"] = lua_table(self.h.lua, {
                "account": "user-a", "capturedAt": 0,
                "purpose": purpose, "purchaseKey": "safehouse:4",
                "requiredCash": required})
        return data

    def view(self, raw):
        context, reason = self.context.Read(self.context, raw,
            lua_table(self.h.lua, self.h.session), 0, 2)
        self.assertIsNone(reason)
        return self.reader.read(raw, context)

    def proposal(self, raw=None, enabled=True, purpose_on=True,
                 max_withdrawal=1000000):
        view, reason = self.view(raw or self.raw())
        self.assertIsNone(reason)
        return self.planner.propose(view, lua_table(self.h.lua, {
            "enabled": enabled, "maxWithdrawal": max_withdrawal,
            "allowOperations": purpose_on, "allowSafehouse": purpose_on}))

    def test_exact_shortfall_and_state_proof(self):
        before = self.raw()
        proposal, reason = self.proposal(before)
        self.assertIsNone(reason)
        self.assertEqual(proposal["feature"], "withdraw")
        self.assertEqual(proposal["intent"]["amount"], 7000)
        self.assertEqual(proposal["intent"]["purpose"], "safehouse")
        baseline, reason = self.evidence.capture(proposal, before)
        self.assertIsNone(reason)
        header, _ = self.h.contracts.validateSnapshot(before,
            lua_table(self.h.lua, self.h.session))
        ok = lua_table(self.h.lua, {"ok": True})
        self.assertEqual(self.evidence.evaluate(proposal, header,
            self.raw(2), ok, baseline), "pending")
        self.assertEqual(self.evidence.evaluate(proposal, header,
            self.raw(2, cash=8000, banked=13000), ok, baseline), "confirmed")

    def test_only_enabled_purpose_and_bounded_amount(self):
        self.assertIsNone(self.proposal(enabled=False)[0])
        self.assertIsNone(self.proposal(purpose_on=False)[0])
        self.assertIsNone(self.proposal(max_withdrawal=6999)[0])
        self.assertIsNone(self.proposal(self.raw(banked=6999))[0])
        self.assertIsNone(self.proposal(self.raw(cash=8000))[0])
        self.assertIsNone(self.view(self.raw(purpose="shop"))[0])
        self.assertIsNone(self.view(self.raw(request=False))[0])

    def test_request_identity_change_and_wrong_transfer_wait(self):
        before = self.raw()
        proposal, _ = self.proposal(before)
        baseline, _ = self.evidence.capture(proposal, before)
        header, _ = self.h.contracts.validateSnapshot(before,
            lua_table(self.h.lua, self.h.session))
        changed = self.raw(2, cash=8000, banked=13000)
        changed["fundingRequest"]["purchaseKey"] = "safehouse:5"
        self.assertEqual(self.evidence.evaluate(proposal, header, changed,
            lua_table(self.h.lua, {"ok": True}), baseline), "pending")
        self.assertEqual(self.evidence.evaluate(proposal, header,
            self.raw(2, cash=8001, banked=13000),
            lua_table(self.h.lua, {"ok": True}), baseline), "pending")
        self.assertEqual(self.evidence.evaluate(proposal, header,
            self.raw(2), lua_table(self.h.lua, {"ok": False}), baseline),
            "rejected")


if __name__ == "__main__":
    unittest.main()
