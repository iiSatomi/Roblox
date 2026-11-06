"""Claims preserve a fractional wallet baseline through real App custody/recovery."""
import unittest

import test_family_claim_read_pipeline as pipeline_fixture
import test_family_takedown_claims as claim_fixture
from engine_harness import lua_table


class FamilyClaimFractionalCashTests(unittest.TestCase):
    def setUp(self):
        self.p = pipeline_fixture.FamilyClaimReadPipelineTests()
        self.p.setUp()
        self.p.native.cash = 1000.25
        self.p.reader.ObserveSync(self.p.reader, self.p.native)

    def tearDown(self):
        self.p.tearDown()

    def test_exact_reward_confirms_with_fractional_cash_baseline(self):
        p = self.p
        p.begin_claim(); p.drain(); p.followup()
        self.assertEqual(p.runtime.Status(p.runtime).outcomes.familyBossClaims, "confirmed")
        self.assertEqual(p.native.cash, 1010.25)
        self.assertEqual([row.args[1] for row in p.executor.calls.values()], ["state", "claim", "state"])
        self.assertEqual(list(p.runtime.checkpoint.FamilyClaimUsage(p.runtime.checkpoint, 100, 3.25).stages.values()), [1])
        p.h.at(10); p.step(); p.drain()
        self.assertEqual(len(p.executor.calls), 3)

    def test_item_only_reward_preserves_fractional_cash(self):
        p = self.p
        p.h.lua.globals().familyState.claims[1].cash = 0
        p.begin_claim(); p.drain(); p.followup()
        self.assertEqual(p.runtime.Status(p.runtime).outcomes.familyBossClaims, "confirmed")
        self.assertEqual(p.native.cash, 1000.25)
        self.assertEqual(p.native.inventoryBound.gold_bar, 1)

    def test_rejection_preserves_fractional_cash_and_used_attempt(self):
        p = self.p
        p.executor.noRemoval = p.executor.noAward = True
        p.executor.reply = lua_table(p.h.lua, {"ok": False})
        p.begin_claim(); p.drain(); p.followup()
        self.assertEqual(p.runtime.Status(p.runtime).outcomes.familyBossClaims, "rejected")
        self.assertEqual(p.native.cash, 1000.25)
        self.assertEqual(list(p.runtime.checkpoint.FamilyClaimUsage(p.runtime.checkpoint, 100, 3.25).stages.values()), [1])

    def test_short_fraction_does_not_confirm_or_recover(self):
        p = self.p
        p.begin_claim(); p.drain()
        p.native.cash = 1010
        p.followup()
        self.assertIsNone(p.runtime.Status(p.runtime).outcomes.familyBossClaims)
        p.restart(); p.attach_current_read(); p.step()
        self.assertIsNone(p.runtime.Status(p.runtime).recoveries.familyBossClaims)
        self.assertEqual(len(p.runtime.checkpoint.Records(p.runtime.checkpoint)), 1)
        self.assertEqual(len(p.executor.calls), 0)

    def test_exact_saved_fractional_cash_award_recovers_without_replay(self):
        p = self.p
        p.begin_claim(); p.drain(); p.restart(); p.attach_current_read(); p.step()
        self.assertEqual(p.runtime.Status(p.runtime).recoveries.familyBossClaims, "confirmed")
        self.assertEqual(len(p.runtime.checkpoint.Records(p.runtime.checkpoint)), 0)
        self.assertEqual(len(p.executor.calls), 0)
        self.assertEqual(p.native.cash, 1010.25)

    def test_unload_after_dispatch_retains_exact_receipt_for_fresh_owner(self):
        p = self.p
        p.begin_claim(); p.drain(); p.app.Destroy(p.app)
        p.restart(); p.attach_current_read(); p.step()
        self.assertEqual(p.runtime.Status(p.runtime).recoveries.familyBossClaims, "confirmed")
        self.assertEqual(len(p.executor.calls), 0)
        self.assertEqual(list(p.runtime.checkpoint.FamilyClaimUsage(p.runtime.checkpoint, 100, 0).stages.values()), [1])

    def test_disable_before_dispatch_refunds_stage_attempt(self):
        p = self.p
        p.begin_claim(); p.app.Set(p.app, "familyBossClaims.enabled", False); p.drain()
        self.assertEqual([row.args[1] for row in p.executor.calls.values()], ["state"])
        self.assertEqual(len(p.runtime.checkpoint.FamilyClaimUsage(p.runtime.checkpoint, 100, .25).stages), 0)
        self.assertEqual(p.native.cash, 1000.25)

    def test_unload_before_dispatch_does_not_invoke_claim(self):
        p = self.p
        p.begin_claim(); p.app.Destroy(p.app); p.drain()
        self.assertEqual([row.args[1] for row in p.executor.calls.values()], ["state"])
        self.assertEqual(p.native.cash, 1000.25)

    def test_disable_after_dispatch_still_settles_exact_award(self):
        p = self.p
        p.begin_claim(); p.drain(); p.app.Set(p.app, "familyBossClaims.enabled", False)
        p.followup()
        self.assertEqual(p.runtime.Status(p.runtime).outcomes.familyBossClaims, "confirmed")
        self.assertEqual(p.native.cash, 1010.25)


class FamilyClaimCashGuardTests(unittest.TestCase):
    def setUp(self):
        self.f = claim_fixture.FamilyTakedownClaimTests()
        self.f.setUp()

    def test_negative_and_nonfinite_cash_refuse_capture(self):
        f = self.f
        for value in (-.25, float("nan"), float("inf"), -float("inf")):
            with self.subTest(value=value):
                before = f.raw()
                proposal = f.propose(before)[0]
                before.native.cash = value
                self.assertIsNone(f.evidence.capture(proposal, before)[0])
                self.assertFalse(f.evidence.canDispatch(proposal, before))

    def test_negative_and_nonfinite_cash_never_settle(self):
        f = self.f
        before = f.raw()
        proposal = f.propose(before)[0]
        baseline = f.evidence.capture(proposal, before)[0]
        f.h.at(1)
        for value in (-.25, float("nan"), float("inf"), -float("inf")):
            for ok in (True, False):
                with self.subTest(value=value, ok=ok):
                    after = f.raw(revision=2, stages=[] if ok else None,
                        claimed=[1] if ok else None, attempted=[1])
                    after.native.cash = value
                    reply = lua_table(f.h.lua, {"ok": ok})
                    self.assertEqual(f.evidence.evaluate(proposal, before, after, reply, baseline), "pending")
                    data = lua_table(f.h.lua, {"proposal": proposal, "before": before,
                        "baseline": baseline, "reply": reply})
                    self.assertIsNone(f.evidence.recoverSaved(data, after))

    def test_previously_accepted_large_finite_integer_cash_remains_accepted(self):
        f = self.f
        before = f.raw()
        proposal = f.propose(before)[0]
        before.native.cash = 9007199254740992
        self.assertIsNotNone(f.evidence.capture(proposal, before)[0])
        self.assertTrue(f.evidence.canDispatch(proposal, before))

    def test_fractional_reward_amount_remains_unplannable(self):
        f = self.f
        before = f.raw(stages=[{"week": 100, "stage": 1, "expiresAt": 1300, "cash": .25}])
        self.assertIsNone(f.propose(before)[0])


if __name__ == "__main__":
    unittest.main()
