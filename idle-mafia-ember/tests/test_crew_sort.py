"""Native Crew sort requires exact order change with pinned slots intact."""
import unittest

from engine_harness import Harness, lua_table


class CrewSortTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.feature = self.h.load("src/tabs/crew/CrewSort.luau")
        self.before = self.h.snapshot(native={"fullSync": True, "crew": [
            {"name": "Player"}, {"name": "Weak", "rarity": 1},
            {"name": "Pinned", "rarity": 3, "duty": {"city": "A"}},
            {"name": "Strong", "rarity": 5}]})
        self.context = lua_table(self.h.lua, {**self.h.session,
            "revision": 1, "capturedAt": 0})

    def plan(self):
        view, reason = self.feature.read(self.before, self.context)
        self.assertIsNone(reason)
        proposal, reason = self.feature.propose(view,
            lua_table(self.h.lua, {"enabled": True}))
        self.assertIsNone(reason)
        return proposal

    def test_exact_swap_confirms_with_newer_sync(self):
        proposal = self.plan()
        self.assertEqual(proposal["intent"]["remote"], "CrewAction")
        self.assertEqual(proposal["intent"]["args"][1], "sort")
        baseline, _ = self.feature.capture(proposal, self.before)
        after = self.h.snapshot(native={"fullSync": True, "crew": [
            {"name": "Player"}, {"name": "Strong", "rarity": 5},
            {"name": "Pinned", "rarity": 3, "duty": {"city": "A"}},
            {"name": "Weak", "rarity": 1}]})
        after["revision"] = 2
        self.assertEqual(self.feature.evaluate(proposal, self.before, after,
            lua_table(self.h.lua, {"ok": True, "changed": True}),
            baseline), "confirmed")
        after["native"]["crew"][3]["name"] = "Other"
        self.assertEqual(self.feature.evaluate(proposal, self.before, after,
            lua_table(self.h.lua, {"ok": True, "changed": True}),
            baseline), "pending")

    def test_noop_and_stale_reply(self):
        proposal = self.plan()
        baseline, _ = self.feature.capture(proposal, self.before)
        self.assertEqual(self.feature.evaluate(proposal, self.before,
            self.before, lua_table(self.h.lua, {"ok": True,
                "changed": False}), baseline), "pending")
        after = self.h.snapshot(native={"fullSync": True, "crew": [
            {"name": "Player"}, {"name": "Weak", "rarity": 1},
            {"name": "Pinned", "rarity": 3, "duty": {"city": "A"}},
            {"name": "Strong", "rarity": 5}]})
        after["revision"] = 2
        self.assertEqual(self.feature.evaluate(proposal, self.before, after,
            lua_table(self.h.lua, {"ok": True, "changed": False}),
            baseline), "confirmed")

    def test_duplicate_identity_blocks_sort(self):
        self.before["native"]["crew"][4]["name"] = "Weak"
        self.before["native"]["crew"][4]["rarity"] = 1
        self.assertIsNone(self.feature.read(self.before, self.context)[0])


if __name__ == "__main__":
    unittest.main()
