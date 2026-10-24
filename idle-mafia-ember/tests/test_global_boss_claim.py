"""One offline settled Global Boss claim per exact run."""
import unittest

from engine_harness import Harness, lua_table


class GlobalBossClaimTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.context = self.h.load("src/game/Context.luau").new(
            self.h.contracts, None, None, None, None,
            self.h.load("src/game/GlobalBossState.luau"))
        self.reader = self.h.load("src/game/GlobalBossClaimState.luau")
        self.planner = self.h.load("src/features/GlobalBossClaim.luau")
        self.evidence = self.h.load(
            "src/features/GlobalBossClaimEvidence.luau")

    def raw(self, revision=1, claimed=False, run="hellfire_2000000",
            attempts=0, dmg=50, now=2000100):
        return self.h.snapshot(revision=revision,
            native={"fullSync": True, "serverNow": now,
                    "gb": {"run": run, "dmg": dmg,
                           "hits": 2, "claimed": claimed}},
            globalBossProof={"account": "user-a", "capturedAt": 0,
                "event": {"id": "hellfire", "startAt": 2000000,
                    "endAt": 2001000, "status": "done",
                    "hp": 10000, "dmg": 100,
                    "resultAt": 2000050}},
            localUserIdProof={"account": "user-a",
                "capturedAt": 0, "userId": 42},
            globalClaimUsageProof={"account": "user-a",
                "capturedAt": 0, "runKey": "hellfire_2000000",
                "attempts": attempts})

    def proposal(self, raw):
        context = self.context.Read(self.context, raw,
            lua_table(self.h.lua, self.h.session), 0, 2)[0]
        view, reason = self.reader.read(raw, context)
        self.assertIsNone(reason)
        return self.planner.propose(view,
            lua_table(self.h.lua, {"enabled": True}),
            lua_table(self.h.lua, {}))

    def test_exact_personal_claim_confirmation(self):
        before = self.raw()
        proposal, reason = self.proposal(before)
        self.assertIsNone(reason)
        self.assertEqual(proposal["intent"]["runKey"],
                         "hellfire_2000000")
        baseline, reason = self.evidence.capture(proposal, before)
        self.assertIsNone(reason)
        self.h.at(1)
        after = self.raw(revision=2, claimed=True, attempts=1)
        after["globalBossProof"]["capturedAt"] = 1
        after["localUserIdProof"]["capturedAt"] = 1
        after["globalClaimUsageProof"]["capturedAt"] = 1
        self.assertEqual(self.evidence.evaluate(proposal, before,
            after, lua_table(self.h.lua, {"ok": True}), baseline),
            "confirmed")
        after["native"]["gb"]["run"] = "other_1"
        self.assertEqual(self.evidence.evaluate(proposal, before,
            after, lua_table(self.h.lua, {"ok": True}), baseline),
            "pending")

    def test_wrong_run_claimed_or_attempted_blocks(self):
        for changes in ({"claimed": True}, {"run": "other_1"},
                        {"attempts": 1}, {"dmg": 0},
                        {"now": 2000050 + 604800}):
            with self.subTest(changes=changes):
                self.assertIsNone(self.proposal(self.raw(
                    **changes))[0])


if __name__ == "__main__":
    unittest.main()
