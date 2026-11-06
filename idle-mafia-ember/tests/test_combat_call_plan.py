"""Combat signatures stay within the tab-owned native call boundary."""
import unittest

from engine_harness import Harness, lua_table


class CombatCallPlanTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        base = self.h.load("src/transport/NativeCallPlan.luau")
        combat = self.h.load("src/tabs/combat/CombatCallPlan.luau")
        self.plan = base.withCombat(base, combat)

    def describe(self, feature, intent):
        return self.plan.describe(lua_table(self.h.lua,
            {"feature": feature, "intent": intent}))

    def test_six_boss_signatures(self):
        rows = [
            ("bosses", {"kind": "bossStageAttack", "stage": 2},
             "BossAction", 2, "stageAttack"),
            ("globalBossAttack", {"kind": "globalBossAttack",
                "runKey": "dragon_1"}, "GlobalBossAction", 1, "attack"),
            ("globalBossClaim", {"kind": "globalBossClaim",
                "runKey": "dragon_1"}, "GlobalBossAction", 1, "claim"),
            ("familyBossAttacks", {"kind": "familyBossAttack",
                "week": 12, "famId": 77, "stage": 1},
             "FamilyBossAction", 1, "attack"),
            ("familyBossClaims", {"kind": "familyBossClaim",
                "week": 12, "stage": 1},
             "FamilyBossAction", 3, "claim"),
            ("bossShop", {"kind": "bossShopBuy",
                "item": "crate_loot", "itemKind": "crate",
                "quantity": 10}, "BossAction", 3, "shopBuy"),
        ]
        for feature, intent, remote, arity, action in rows:
            with self.subTest(feature=feature):
                call, reason = self.describe(feature, intent)
                self.assertIsNone(reason)
                self.assertEqual(call.remote, remote)
                self.assertEqual(call.arity, arity)
                self.assertEqual(call.args[1], action)

    def test_bad_boss_item_and_player_attack_have_no_call(self):
        self.assertIsNone(self.describe("bossShop",
            {"kind": "bossShopBuy", "item": "mystery",
             "itemKind": "gear", "quantity": 1})[0])
        self.assertIsNone(self.describe("combat",
            {"kind": "playerAttack", "target": 42})[0])


if __name__ == "__main__":
    unittest.main()
