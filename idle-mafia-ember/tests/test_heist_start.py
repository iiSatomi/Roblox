"""Offline personal Heist selection and conservative run evidence."""
import unittest

from engine_harness import Harness, lua_table


class HeistStartTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.context = self.h.load("src/game/Context.luau").new(self.h.contracts)
        self.reader = self.h.load("src/game/HeistBoardState.luau")
        self.planner = self.h.load("src/features/HeistStart.luau")
        self.evidence = self.h.load("src/features/HeistStartEvidence.luau")

    def raw(self, revision=1, mine=None, cash=1000, energy=10,
            starts=2, bust=0, day=23):
        now = day * 86400 + 100
        return self.h.snapshot(revision=revision,
            native={"fullSync": True, "serverNow": now,
                "level": 20, "cash": cash,
                "pools": {"energy": energy}},
            catalogKey="heists-build-1",
            heistCatalog=[
                {"id": "h_low", "level": 10, "stake": 100,
                 "energy": 2, "crateCount": 1},
                {"id": "h_high", "level": 20, "stake": 400,
                 "energy": 5, "crateCount": 2}],
            heistBoardProof={"account": "user-a", "capturedAt": 0,
                "query": None, "board": {"ok": True,
                    "serverNow": now, "mine": mine,
                    "rows": [], "startsLeft": starts,
                    "bustWait": bust}})

    def view(self, raw):
        context = self.context.Read(self.context, raw,
            lua_table(self.h.lua, self.h.session), 0, 2)[0]
        return self.reader.read(raw, context)

    def settings(self, policy="Best chest"):
        return lua_table(self.h.lua, {"enabled": True,
            "policy": policy})

    def reserves(self, cash=0, energy=0):
        return lua_table(self.h.lua, {"cash": cash,
            "energy": energy, "uncertainCash": 0,
            "uncertainEnergy": 0})

    def test_selects_highest_affordable_chest_and_tier(self):
        view, reason = self.view(self.raw())
        self.assertIsNone(reason)
        proposal, reason = self.planner.propose(view, self.settings(),
            self.reserves())
        self.assertIsNone(reason)
        self.assertEqual(proposal["intent"]["heistId"], "h_high")
        self.assertEqual(proposal["resources"]["cash"], 400)
        self.assertTrue(proposal["intent"]["needsSequence"])
        self.assertEqual(self.planner.propose(view,
            self.settings("Highest tier"), self.reserves())[0]
            ["intent"]["heistId"], "h_high")

    def test_reservations_cap_and_busy_board_block(self):
        view, _ = self.view(self.raw())
        proposal, _ = self.planner.propose(view, self.settings(),
            self.reserves(cash=700, energy=6))
        self.assertEqual(proposal["intent"]["heistId"], "h_low")
        self.assertIsNone(self.planner.propose(view, self.settings(),
            self.reserves(cash=950))[0])
        full, _ = self.view(self.raw(starts=0))
        self.assertIsNone(self.planner.propose(full, self.settings(),
            self.reserves())[0])
        active, _ = self.view(self.raw(mine={"id": "run-1",
            "heistId": "h_low", "endsAt": 2000000}))
        self.assertIsNone(self.planner.propose(active, self.settings(),
            self.reserves())[0])

    def test_confirmation_requires_reply_run_id_and_new_board(self):
        before = self.raw()
        view, _ = self.view(before)
        proposal, _ = self.planner.propose(view, self.settings(),
            self.reserves())
        baseline, reason = self.evidence.capture(proposal, before)
        self.assertIsNone(reason)
        after = self.raw(revision=2, starts=1,
            mine={"id": "run-2", "heistId": "h_high",
                  "endsAt": 2000000})
        self.assertEqual(self.evidence.evaluate(proposal, before, after,
            lua_table(self.h.lua, {"ok": True}), baseline), "pending")
        self.assertEqual(self.evidence.evaluate(proposal, before, after,
            lua_table(self.h.lua, {"ok": True, "runId": "other"}),
            baseline), "pending")
        self.assertEqual(self.evidence.evaluate(proposal, before, after,
            lua_table(self.h.lua, {"ok": True, "runId": "run-2"}),
            baseline), "confirmed")

    def test_preflight_rejects_changed_board_or_price(self):
        before = self.raw()
        view, _ = self.view(before)
        proposal, _ = self.planner.propose(view, self.settings(),
            self.reserves())
        before["heistBoardProof"]["board"]["startsLeft"] = 1
        self.assertIsNone(self.evidence.capture(proposal, before)[0])
        before["heistBoardProof"]["board"]["startsLeft"] = 2
        before["heistCatalog"][2]["stake"] = 401
        self.assertIsNone(self.evidence.capture(proposal, before)[0])


if __name__ == "__main__":
    unittest.main()
