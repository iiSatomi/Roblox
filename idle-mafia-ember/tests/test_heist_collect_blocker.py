"""Visible personal Heist results cannot be sent without identity proof."""
import unittest

from engine_harness import Harness, lua_table


class HeistCollectBlockerTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.planner = self.h.load("src/features/HeistCollect.luau")
        self.evidence = self.h.load("src/features/HeistCollectEvidence.luau")

    def test_visible_result_reports_blocker_and_never_proposes(self):
        view = lua_table(self.h.lua, {"state": "result",
            "resultHeistId": "h_a", "resultAddressable": False,
            "resultSummary": {"ok": True, "cash": 1000}})
        proposal, reason = self.planner.propose(view,
            lua_table(self.h.lua, {"enabled": True}))
        self.assertIsNone(proposal)
        self.assertIn("identity", reason)
        view["resultAddressable"] = True
        proposal, reason = self.planner.propose(view,
            lua_table(self.h.lua, {"enabled": True}))
        self.assertIsNone(proposal)
        self.assertIn("sequence", reason)

    def test_evidence_boundary_cannot_admit_collect(self):
        baseline, reason = self.evidence.capture(lua_table(self.h.lua, {
            "feature": "heistCollect", "intent": {"kind": "heistCollect"}}),
            self.h.snapshot())
        self.assertIsNone(baseline)
        self.assertIn("unverified", reason)


if __name__ == "__main__":
    unittest.main()
