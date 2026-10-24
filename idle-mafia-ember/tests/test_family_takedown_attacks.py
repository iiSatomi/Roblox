"""Free-charge Family Takedown attacks require personal native proof."""
import unittest

from engine_harness import Harness, lua_table


class FamilyTakedownAttackTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.takedown = self.h.load("src/game/FamilyTakedownState.luau")
        self.context = self.h.load("src/game/Context.luau").new(
            self.h.contracts, None, None, None, None, None, None,
            self.takedown)
        self.reader = self.h.load("src/game/FamilyBossAttackState.luau")
        self.planner = self.h.load("src/features/FamilyBossAttacks.luau")
        self.evidence = self.h.load(
            "src/features/FamilyBossAttacksEvidence.luau")

    def raw(self, revision=1, now=1050, tickets=0, free_used=1,
            damage=100, health=80, stamina=5, hit_back=20,
            hits=0, last=0, week=100, fam_id=9):
        captured = self.h.lua.globals().testNow
        return self.h.snapshot(revision=revision,
            native={"fullSync": True, "serverNow": now,
                "stats": {"maxHealth": 100},
                "pools": {"health": health, "stamina": stamina}},
            familyTakedownProof={"account": "user-a",
                "capturedAt": captured,
                "state": {"week": week, "famId": fam_id,
                    "inFamily": True, "stage": 2,
                    "resetAt": 2000, "freeMax": 3,
                    "freeUsed": free_used, "freeRegen": 60,
                    "tickets": tickets, "myDmg": damage,
                    "claims": [], "claimedStages": []}},
            familyAttackProof={"account": "user-a",
                "capturedAt": captured, "week": week,
                "famId": fam_id, "stage": 2,
                "staminaCost": 1,
                "hitBackMax": hit_back},
            familyAttackUsageProof={"account": "user-a",
                "capturedAt": captured, "week": week,
                "famId": fam_id, "hits": hits,
                "lastServerNow": last})

    def propose(self, raw):
        context = self.context.Read(self.context, raw,
            lua_table(self.h.lua, self.h.session),
            self.h.lua.globals().testNow, 2)[0]
        view, reason = self.reader.read(raw, context)
        self.assertIsNone(reason)
        return self.planner.propose(view,
            lua_table(self.h.lua, {"enabled": True}),
            lua_table(self.h.lua, {"stamina": 0,
                "uncertainStamina": 0}))

    def test_newer_personal_damage_and_free_use_confirm(self):
        before = self.raw()
        proposal, reason = self.propose(before)
        self.assertIsNone(reason)
        baseline, reason = self.evidence.capture(proposal, before)
        self.assertIsNone(reason)
        self.h.at(1)
        after = self.raw(revision=2, damage=150,
            free_used=2, hits=1, last=1050)
        reply = lua_table(self.h.lua, {"ok": True, "dmg": 50,
            "tickets": 0, "freeLeft": 1})
        self.assertEqual(self.evidence.evaluate(proposal, before,
            after, reply, baseline), "confirmed")
        after["familyTakedownProof"]["state"]["myDmg"] = 100
        self.assertEqual(self.evidence.evaluate(proposal, before,
            after, reply, baseline), "pending")
        after["familyTakedownProof"]["state"]["myDmg"] = 150
        after["familyTakedownProof"]["state"]["tickets"] = 1
        self.assertEqual(self.evidence.evaluate(proposal, before,
            after, reply, baseline), "pending")

    def test_ticket_health_stamina_cap_and_spacing_block(self):
        for changes in ({"tickets": 1}, {"free_used": 3},
                        {"hit_back": 0},
                        {"health": 60, "hit_back": 20},
                        {"stamina": 1}, {"hits": 25},
                        {"hits": 1, "last": 1048}):
            with self.subTest(changes=changes):
                self.assertIsNone(self.propose(
                    self.raw(**changes))[0])
        context = self.context.Read(self.context,
            self.raw(now=2000), lua_table(self.h.lua,
                self.h.session), 0, 2)[0]
        self.assertEqual(context["takedown"]["status"],
                         "unknown")

    def test_stage_clear_can_confirm_without_new_attack_quote(self):
        before = self.raw()
        proposal = self.propose(before)[0]
        baseline = self.evidence.capture(proposal, before)[0]
        self.h.at(1)
        after = self.raw(revision=2, damage=150,
            free_used=2, hits=1, last=1050)
        after["familyTakedownProof"]["state"]["stage"] = 3
        after["familyAttackProof"] = None
        reply = lua_table(self.h.lua, {"ok": True, "dmg": 50,
            "tickets": 0, "freeLeft": 1})
        self.assertEqual(self.evidence.evaluate(proposal, before,
            after, reply, baseline), "confirmed")


if __name__ == "__main__":
    unittest.main()
