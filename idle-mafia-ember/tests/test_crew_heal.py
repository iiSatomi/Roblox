"""Native Crew healing uses saved cost rules and exact injury reduction."""
import unittest

from engine_harness import Harness, lua_table


class CrewHealTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.feature = self.h.load("src/tabs/crew/CrewHeal.luau")
        self.now = 2000000
        self.before = self.h.snapshot(native={"fullSync": True,
            "serverNow": self.now, "pools": {"stamina": 15},
            "crew": [{"name": "Player"},
                     {"name": "Ally", "rarity": 4,
                      "healId": "injury-a",
                      "injuredUntil": self.now + 600}]})
        self.context = lua_table(self.h.lua, {**self.h.session,
            "revision": 1, "capturedAt": 0, "serverNow": self.now,
            "healRules": {"release": self.h.session["release"],
                          "healStaminaCost": 5, "healSeconds": 300}})

    def plan(self, reserve=10):
        view, reason = self.feature.read(self.before, self.context)
        self.assertIsNone(reason)
        return self.feature.propose(view, lua_table(self.h.lua,
            {"enabled": True, "custom": {"staminaReserve": reserve}}))

    def test_cost_reserve_and_exact_injury_evidence(self):
        proposal, reason = self.plan()
        self.assertIsNone(reason)
        self.assertEqual(proposal["resources"]["stamina"], 5)
        self.assertEqual(proposal["intent"]["args"][1], "heal")
        self.assertEqual(proposal["intent"]["args"][2], 2)
        self.assertEqual(proposal["intent"]["args"][3]["memberId"],
                         "injury-a")
        baseline, reason = self.feature.capture(proposal, self.before)
        self.assertIsNone(reason)
        after = self.h.snapshot(native={"fullSync": True,
            "serverNow": self.now + 5, "pools": {"stamina": 10},
            "crew": [{"name": "Player"}, {"name": "Ally", "rarity": 4,
                "healId": "injury-a",
                "injuredUntil": self.now + 300}]})
        after["revision"] = 2
        self.assertEqual(self.feature.evaluate(proposal, self.before,
            after, lua_table(self.h.lua, {"ok": True}),
            baseline), "confirmed")
        after["native"]["crew"][2]["name"] = "Other"
        self.assertEqual(self.feature.evaluate(proposal, self.before,
            after, lua_table(self.h.lua, {"ok": True}),
            baseline), "pending")

    def test_stamina_reserve_and_unknown_rules_block(self):
        self.assertIsNone(self.plan(reserve=11)[0])
        self.context["healRules"]["release"] = "stale"
        self.assertIsNone(self.feature.read(self.before, self.context)[0])

    def test_reply_alone_or_stale_sync_cannot_confirm(self):
        proposal, _ = self.plan()
        baseline, _ = self.feature.capture(proposal, self.before)
        self.assertEqual(self.feature.evaluate(proposal, self.before,
            self.before, lua_table(self.h.lua, {"ok": True}),
            baseline), "pending")

    def test_duplicate_member_identity_blocks_slot_heal(self):
        self.before["native"]["crew"][3] = lua_table(self.h.lua,
            {"name": "Ally", "rarity": 4})
        self.assertIsNone(self.feature.read(self.before, self.context)[0])


if __name__ == "__main__":
    unittest.main()
