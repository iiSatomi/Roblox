"""Saved rank thresholds yield read-only readiness; reset stays blocked."""
import unittest

from engine_harness import Harness, lua_table


class PrestigeTabTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.module = self.h.load("src/game/PrestigeState.luau")
        self.blocked = self.h.load("src/features/PrestigeBlocked.luau")
        self.state = self.module.new(lua_table(self.h.lua, {"PRESTIGE": {
            "maxRank": 6, "levelByRank": [200, 200, 200, 210, 220, 230]}}),
            "a" * 64, "release-a")
        self.context = self.h.load("src/game/Context.luau").new(
            self.h.contracts)

    def view(self, rank, level):
        raw = self.h.snapshot(native={"fullSync": True,
            "prestige": rank, "level": level})
        enriched, reason = self.state.Enrich(self.state, raw)
        self.assertIsNone(reason)
        context, reason = self.context.Read(self.context, enriched,
            lua_table(self.h.lua, self.h.session), 0, 2)
        self.assertIsNone(reason)
        return self.state.read(enriched, context)

    def test_rank_specific_readiness_and_max_rank(self):
        for rank, required in enumerate((200, 200, 200, 210, 220, 230)):
            with self.subTest(rank=rank):
                view, reason = self.view(rank, required - 1)
                self.assertIsNone(reason)
                self.assertFalse(view["ready"])
                self.assertEqual(view["requiredLevel"], required)
                ready, reason = self.view(rank, required)
                self.assertIsNone(reason)
                self.assertTrue(ready["ready"])
                self.assertEqual(ready["resetLevel"], 1)
                self.assertEqual(ready["resetXp"], 0)
        maximum, reason = self.view(6, 230)
        self.assertIsNone(reason)
        self.assertFalse(maximum["ready"])
        self.assertIsNone(maximum["nextRank"])

    def test_no_reset_proposal_even_when_ready(self):
        ready, _ = self.view(0, 200)
        self.assertIsNone(self.blocked.propose(ready,
            lua_table(self.h.lua, {"enabled": True}))[0])
        self.assertIsNone(self.blocked.capture()[0])
        self.assertEqual(self.blocked.evaluate(), "pending")


if __name__ == "__main__":
    unittest.main()
