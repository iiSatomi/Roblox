"""Explicit ordinary Heist sabotage with exact row and daily guards."""
import unittest

from engine_harness import Harness, lua_table


class SabotageTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.context = self.h.load("src/game/Context.luau").new(
            self.h.contracts, None, None,
            self.h.load("src/game/HeistBoardState.luau"))
        self.reader = self.h.load("src/game/SabotageState.luau")
        self.planner = self.h.load("src/features/Sabotage.luau")
        self.evidence = self.h.load("src/features/SabotageEvidence.luau")

    def raw(self, revision=1, owner=99, friend=False, relation=None,
            helps=0, sabos=0, favors=12, attempts=0, energy=20,
            row_id="run-1"):
        now = 2000000
        return self.h.snapshot(revision=revision,
            native={"fullSync": True, "serverNow": now,
                    "level": 20, "pools": {"energy": energy}},
            heistCatalog=[{"id": "h_a", "level": 10,
                           "stake": 100, "energy": 2}],
            heistBoardProof={"account": "user-a", "capturedAt": 0,
                "board": {"ok": True, "serverNow": now,
                    "rows": [{"id": row_id, "heistId": "h_a",
                        "ownerId": owner, "friend": friend,
                        "famRel": relation, "helpsUsed": helps,
                        "sabosUsed": sabos, "endsAt": now + 300}],
                    "favorsLeft": favors, "saboFavorCost": 2,
                    "saboEnergyCost": 3, "saboMaxPerHeist": 5}},
            localUserIdProof={"account": "user-a", "capturedAt": 0,
                              "userId": 42},
            sabotageUsageProof={"account": "user-a",
                "capturedAt": 0, "day": now // 86400,
                "attempts": attempts})

    def proposal(self, raw):
        context = self.context.Read(self.context, raw,
            lua_table(self.h.lua, self.h.session), 0, 2)[0]
        view, reason = self.reader.read(raw, context)
        self.assertIsNone(reason)
        return self.planner.propose(view,
            lua_table(self.h.lua, {"enabled": True}),
            lua_table(self.h.lua, {"energy": 0,
                "uncertainEnergy": 0, "favors": 0,
                "uncertainFavors": 0}))

    def test_selects_nonfriend_and_confirms_exact_row(self):
        before = self.raw()
        proposal, reason = self.proposal(before)
        self.assertIsNone(reason)
        self.assertEqual(proposal["intent"]["rowId"], "run-1")
        self.assertTrue(proposal["intent"]["needsSequence"])
        baseline, reason = self.evidence.capture(proposal, before)
        self.assertIsNone(reason)
        self.h.at(1)
        after = self.raw(revision=2, sabos=1, favors=10,
                         attempts=1)
        after["heistBoardProof"]["capturedAt"] = 1
        after["localUserIdProof"]["capturedAt"] = 1
        after["sabotageUsageProof"]["capturedAt"] = 1
        self.assertEqual(self.evidence.evaluate(proposal, before,
            after, lua_table(self.h.lua, {"ok": True}), baseline),
            "confirmed")
        after["heistBoardProof"]["board"]["rows"][1]["ownerId"] = 100
        self.assertEqual(self.evidence.evaluate(proposal, before,
            after, lua_table(self.h.lua, {"ok": True}), baseline),
            "pending")

    def test_self_friend_family_help_and_cap_block(self):
        for changes in ({"owner": 42}, {"friend": True},
                        {"relation": "family"}, {"helps": 1},
                        {"attempts": 5}, {"favors": 6},
                        {"energy": 12}):
            with self.subTest(changes=changes):
                self.assertIsNone(self.proposal(
                    self.raw(**changes))[0])

    def test_numeric_row_id_is_preserved(self):
        raw = self.raw(row_id=731)
        proposal, reason = self.proposal(raw)
        self.assertIsNone(reason)
        self.assertEqual(proposal["intent"]["rowId"], 731)
        self.assertIn("number:731", proposal["actionKey"])
        self.assertIsNotNone(self.evidence.capture(proposal, raw)[0])

    def test_missing_identity_or_usage_blocks(self):
        raw = self.raw()
        raw["localUserIdProof"] = None
        context = self.context.Read(self.context, raw,
            lua_table(self.h.lua, self.h.session), 0, 2)[0]
        self.assertIsNone(self.reader.read(raw, context)[0])
        raw = self.raw()
        raw["sabotageUsageProof"]["day"] -= 1
        context = self.context.Read(self.context, raw,
            lua_table(self.h.lua, self.h.session), 0, 2)[0]
        self.assertIsNone(self.reader.read(raw, context)[0])


if __name__ == "__main__":
    unittest.main()
