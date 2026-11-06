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
                      "injuredUntil": self.now + 600}]},
            healRules={"release": self.h.session["release"],
                       "healStaminaCost": 5, "healSeconds": 300})
        self.context = lua_table(self.h.lua, {**self.h.session,
            "revision": 1, "capturedAt": 0, "serverNow": self.now})

    def plan(self, reserve=10):
        view, reason = self.feature.read(self.before, self.context)
        self.assertIsNone(reason)
        return self.feature.propose(view, lua_table(self.h.lua,
            {"enabled": True, "custom": {"staminaReserve": reserve}}))

    def test_cost_reserve_and_exact_injury_evidence(self):
        proposal, reason = self.plan()
        self.assertIsNone(reason)
        self.assertEqual(proposal["resources"]["stamina"], 5)
        self.assertEqual(proposal["intent"]["kind"], "crewHeal")
        self.assertEqual(proposal["intent"]["slot"], 2)
        self.assertEqual(proposal["intent"]["memberId"], "injury-a")
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
        self.before["healRules"]["release"] = "stale"
        self.assertIsNone(self.feature.read(self.before, self.context)[0])

    def test_reply_alone_or_stale_sync_cannot_confirm(self):
        proposal, _ = self.plan()
        baseline, _ = self.feature.capture(proposal, self.before)
        self.assertEqual(self.feature.evaluate(proposal, self.before,
            self.before, lua_table(self.h.lua, {"ok": True}),
            baseline), "pending")

    def test_duplicate_member_identity_blocks_slot_heal(self):
        self.before["native"]["crew"][3] = lua_table(self.h.lua,
            {"name": "Ally", "rarity": 4, "healId": "injury-a"})
        self.assertIsNone(self.feature.read(self.before, self.context)[0])

    def test_identical_names_with_distinct_heal_ids_do_not_block_healing(self):
        self.before.native.crew[3] = lua_table(self.h.lua,
            {"name": "Ally", "rarity": 4, "healId": "injury-b"})
        self.assertIsNotNone(self.plan()[0])

    def test_short_injury_uses_scaled_cost_and_can_finish(self):
        self.before.native.crew[2].injuredUntil = self.now + 200
        proposal, _ = self.plan()
        self.assertEqual(proposal.resources.stamina, 4)
        baseline = self.feature.capture(proposal, self.before)[0]
        after = self.h.snapshot(revision=2, native={"fullSync": True,
            "serverNow": self.now + 1, "pools": {"stamina": 11},
            "crew": [{}, {"name": "Ally", "rarity": 4,
                "healId": "injury-a", "injuredUntil": 0}]})
        self.assertEqual(self.feature.evaluate(proposal, self.before, after,
            lua_table(self.h.lua, {"ok": True}), baseline), "confirmed")

    def test_fractional_server_and_injury_times_remain_readable(self):
        self.before["native"]["serverNow"] = self.now + 0.25
        self.context["serverNow"] = self.now + 0.25
        self.before["native"]["crew"][2]["injuredUntil"] = self.now + 600.5
        view, reason = self.feature.read(self.before, self.context)
        self.assertIsNone(reason)
        self.assertEqual(view["injured"][1]["slot"], 2)

    def test_send_time_rechecks_quote_duty_and_declared_stamina(self):
        for drift in ("cost", "duty", "resources"):
            proposal, _ = self.plan()
            if drift == "cost": proposal.intent.expectedCost = 1
            elif drift == "duty": self.before.native.crew[2].duty = self.h.lua.table()
            else: proposal.resources.stamina = 0
            self.assertIsNone(self.feature.capture(proposal, self.before)[0], drift)
            self.before.native.crew[2].duty = None

    def test_wrong_timer_reduction_or_transient_reply_cannot_confirm(self):
        proposal, _ = self.plan()
        baseline, _ = self.feature.capture(proposal, self.before)
        after = self.h.snapshot(revision=2, native={"fullSync": True,
            "serverNow": self.now + 1, "pools": {"stamina": 15},
            "crew": [{}, {"name": "Ally", "rarity": 4, "healId": "injury-a",
                "injuredUntil": self.now + 301}]})
        reply = lua_table(self.h.lua, {"ok": True})
        self.assertEqual(self.feature.evaluate(proposal, self.before, after, reply, baseline), "pending")
        after.native.pools.stamina = 10
        after.native.crew[2].injuredUntil = self.now + 200
        self.assertEqual(self.feature.evaluate(proposal, self.before, after, reply, baseline), "pending")
        after.native.crew[2].injuredUntil = self.now + 300
        reply.pending = True
        self.assertEqual(self.feature.evaluate(proposal, self.before, after, reply, baseline), "pending")


if __name__ == "__main__":
    unittest.main()
