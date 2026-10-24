"""Current-week Family Takedown claims need a durable exact-stage proof."""
import unittest

from engine_harness import Harness, lua_table


class FamilyTakedownClaimTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.takedown = self.h.load("src/game/FamilyTakedownState.luau")
        self.context = self.h.load("src/game/Context.luau").new(
            self.h.contracts, None, None, None, None, None, None,
            self.takedown)
        self.reader = self.h.load("src/game/FamilyBossClaimState.luau")
        self.planner = self.h.load("src/features/FamilyBossClaims.luau")
        self.evidence = self.h.load(
            "src/features/FamilyBossClaimsEvidence.luau")

    def raw(self, revision=1, now=1050, stages=None,
            claimed=None, attempted=None, week=100, fam_id=9,
            state_week=None, in_family=True):
        state_week = state_week or week
        if stages is None:
            stages = [{"week": week, "stage": 2,
                       "expiresAt": 1300},
                      {"week": week, "stage": 1,
                       "expiresAt": 1300}]
        return self.h.snapshot(revision=revision,
            native={"fullSync": True, "serverNow": now},
            familyTakedownProof={"account": "user-a",
                "capturedAt": self.h.lua.globals().testNow,
                "state": {"week": state_week, "famId": fam_id,
                    "inFamily": in_family, "stage": 3,
                    "resetAt": 2000, "freeMax": 3,
                    "freeUsed": 1, "freeRegen": 60,
                    "tickets": 0, "myDmg": 100,
                    "claims": stages,
                    "claimedStages": claimed or []}},
            familyClaimUsageProof={"account": "user-a",
                "capturedAt": self.h.lua.globals().testNow,
                "week": week, "stages": attempted or []},
            familyClaimUsageProofs={str(week): {
                "account": "user-a",
                "capturedAt": self.h.lua.globals().testNow,
                "week": week, "stages": attempted or []}})

    def propose(self, raw):
        context = self.context.Read(self.context, raw,
            lua_table(self.h.lua, self.h.session),
            self.h.lua.globals().testNow, 2)[0]
        view, reason = self.reader.read(raw, context)
        self.assertIsNone(reason)
        return self.planner.propose(view,
            lua_table(self.h.lua, {"enabled": True}))

    def test_exact_newer_claim_confirms(self):
        before = self.raw()
        proposal, reason = self.propose(before)
        self.assertIsNone(reason)
        self.assertEqual(proposal["intent"]["stage"], 1)
        baseline, reason = self.evidence.capture(proposal, before)
        self.assertIsNone(reason)
        self.h.at(1)
        after = self.raw(revision=2, stages=[{"week": 100,
            "stage": 2, "expiresAt": 1300}],
            claimed=[1], attempted=[1])
        self.assertEqual(self.evidence.evaluate(proposal, before,
            after, lua_table(self.h.lua, {"ok": True}), baseline),
            "confirmed")
        after["familyTakedownProof"]["state"]["claimedStages"] = \
            lua_table(self.h.lua, [])
        self.assertEqual(self.evidence.evaluate(proposal, before,
            after, lua_table(self.h.lua, {"ok": True}), baseline),
            "pending")

    def test_attempted_expired_and_other_week_claims_wait(self):
        self.assertEqual(self.propose(self.raw(attempted=[1]))[0]
                         ["intent"]["stage"], 2)
        self.assertEqual(self.propose(self.raw(claimed=[1]))[0]
                         ["intent"]["stage"], 2)
        self.assertIsNone(self.propose(self.raw(
            attempted=[1, 2]))[0])
        self.assertIsNone(self.propose(self.raw(now=1300))[0])
        self.assertIsNone(self.propose(self.raw(in_family=False))[0])
        self.assertIsNone(self.propose(self.raw(stages=[{
            "week": 100, "stage": 7, "expiresAt": 1300}]))[0])
        historical = self.propose(self.raw(stages=[{
            "week": 99, "stage": 7, "expiresAt": 1300}]))[0]
        self.assertEqual(historical["intent"]["week"], 99)

    def test_no_reply_or_expired_replica_never_confirms(self):
        before = self.raw()
        proposal = self.propose(before)[0]
        baseline = self.evidence.capture(proposal, before)[0]
        self.h.at(1)
        after = self.raw(revision=2, stages=[{"week": 100,
            "stage": 2, "expiresAt": 1300}],
            claimed=[1], attempted=[1])
        self.assertEqual(self.evidence.evaluate(proposal, before,
            after, lua_table(self.h.lua, {}), baseline), "pending")
        self.assertEqual(self.evidence.evaluate(proposal, before,
            after, lua_table(self.h.lua, {"ok": False}), baseline),
            "pending")
        after["native"]["serverNow"] = 1300
        self.assertEqual(self.evidence.evaluate(proposal, before,
            after, lua_table(self.h.lua, {"ok": True}), baseline),
            "pending")

    def test_preflight_rejects_duplicate_exact_claim_rows(self):
        before = self.raw()
        proposal = self.propose(before)[0]
        before["familyTakedownProof"]["state"]["claims"][3] = \
            lua_table(self.h.lua, {"week": 100, "stage": 1,
                "expiresAt": 1300})
        self.assertIsNone(self.evidence.capture(proposal, before)[0])

    def test_historical_claim_remains_available_after_leaving_family(self):
        before = self.raw(stages=[{"week": 99, "stage": 7,
            "expiresAt": 1300, "label": "Weekly reward"}],
            week=99, state_week=100, in_family=False)
        proposal, reason = self.propose(before)
        self.assertIsNone(reason)
        self.assertEqual(proposal["intent"]["week"], 99)
        self.assertEqual(proposal["intent"]["stage"], 7)
        baseline, reason = self.evidence.capture(proposal, before)
        self.assertIsNone(reason)
        self.h.at(1)
        after = self.raw(revision=2, now=1051, stages=[],
            attempted=[7], week=99, state_week=100, in_family=False)
        reply = lua_table(self.h.lua, {"ok": True})
        self.assertEqual(self.evidence.evaluate(proposal, before,
            after, reply, baseline), "confirmed")


if __name__ == "__main__":
    unittest.main()
