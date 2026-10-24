"""Saved client call shapes are staged without invoking a Roblox remote."""
import unittest

from engine_harness import Harness, lua_table


class NativeCallPlanTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.calls = self.h.load("src/transport/NativeCallPlan.luau")

    def plan(self, feature, intent):
        return self.calls.describe(lua_table(self.h.lua, {
            "feature": feature, "intent": intent}))

    def test_jobs_maps_only_a_valid_target_id(self):
        call, reason = self.plan("jobs", {"kind": "job",
            "targetId": "j_watch"})
        self.assertIsNone(reason)
        self.assertEqual(call["remote"], "DoJob")
        self.assertEqual(call["method"], "InvokeServer")
        self.assertEqual(call["arity"], 1)
        self.assertEqual(call["args"][1], "j_watch")
        self.assertIsNone(self.plan("jobs", {"kind": "job",
            "targetId": ""})[0])

    def test_cash_shop_preserves_nil_gold_argument_and_quote(self):
        call, reason = self.plan("shop", {"kind": "shopCashBuy",
            "itemId": "w_pipe", "slot": 4, "expectedCost": 120})
        self.assertIsNone(reason)
        self.assertEqual(call["remote"], "BuyShopItem")
        self.assertEqual(call["arity"], 3)
        self.assertEqual(call["args"][1], "w_pipe")
        self.assertIsNone(call["args"][2])
        self.assertEqual(call["args"][3], 120)

    def test_boss_shop_preserves_native_gear_and_crate_arity(self):
        gear, reason = self.plan("bossShop", {"kind": "bossShopBuy",
            "item": "w_policebaton", "itemKind": "gear", "quantity": 1})
        self.assertIsNone(reason)
        self.assertEqual(gear["remote"], "BossAction")
        self.assertEqual(gear["arity"], 3)
        self.assertEqual(gear["args"][1], "shopBuy")
        self.assertEqual(gear["args"][2], "w_policebaton")
        self.assertIsNone(gear["args"][3])
        crate, reason = self.plan("bossShop", {"kind": "bossShopBuy",
            "item": "crate_loot", "itemKind": "crate", "quantity": 10})
        self.assertIsNone(reason)
        self.assertEqual(crate["arity"], 3)
        self.assertEqual(crate["args"][3], 10)

    def test_operations_and_earned_claims_match_saved_calls(self):
        cases = [
            ("operations", {"kind": "operationStart", "targetId": "op_fence"},
             "StartOperation", 1, ["op_fence"]),
            ("collect", {"kind": "operationCollect", "index": 2},
             "CollectOperation", 1, [2]),
            ("contracts", {"kind": "contractEntryClaim", "period": "daily",
                           "command": "claim", "index": 3},
             "ContractAction", 3, ["claim", 3, None]),
            ("contracts", {"kind": "contractEntryClaim", "period": "weekly",
                           "command": "claimweekly", "index": 5},
             "ContractAction", 3, ["claimweekly", 5, None]),
            ("bonuses", {"kind": "contractBonusClaim", "period": "daily",
                         "command": "claimbonus"},
             "ContractAction", 3, ["claimbonus", None, None]),
            ("bonuses", {"kind": "contractBonusClaim", "period": "weekly",
                         "command": "claimweeklybonus"},
             "ContractAction", 3, ["claimweeklybonus", None, None]),
            ("briefcases", {"kind": "freeBriefcasePick", "command": "open",
                            "index": 7},
             "BriefcaseAction", 2, ["open", 7]),
        ]
        for feature, intent, remote, arity, args in cases:
            with self.subTest(feature=feature, intent=intent):
                call, reason = self.plan(feature, intent)
                self.assertIsNone(reason)
                self.assertEqual(call["remote"], remote)
                self.assertEqual(call["arity"], arity)
                self.assertEqual([call["args"][i] for i in range(1, arity + 1)],
                                 args)

    def test_claim_commands_and_indices_fail_closed(self):
        cases = [
            ("collect", {"kind": "operationCollect", "index": 0}),
            ("contracts", {"kind": "contractEntryClaim", "period": "daily",
                           "command": "claimweekly", "index": 1}),
            ("contracts", {"kind": "contractEntryClaim", "period": "weekly",
                           "command": "claimweekly", "index": 6}),
            ("bonuses", {"kind": "contractBonusClaim", "period": "daily",
                         "command": "claimweeklybonus"}),
            ("briefcases", {"kind": "freeBriefcasePick", "command": "buy",
                            "index": 1}),
            ("briefcases", {"kind": "freeBriefcasePick", "command": "open",
                            "index": 13}),
        ]
        for feature, intent in cases:
            with self.subTest(feature=feature, intent=intent):
                self.assertIsNone(self.plan(feature, intent)[0])

    def test_skill_money_safehouse_and_group_calls(self):
        cases = [
            ("skills", {"kind": "skillAllocation", "stat": "energy", "count": 4},
             "AllocateSkillPoint", ["energy", 4]),
            ("bank", {"kind": "bankDeposit", "amount": 35000},
             "BankDeposit", [35000]),
            ("withdraw", {"kind": "purposeWithdrawal", "amount": 500},
             "Withdraw", [500]),
            ("safehouse", {"kind": "safehouseUpgrade", "nextTier": 4},
             "UpgradeSafehouse", []),
            ("groupBonus", {"kind": "groupBonusClaim", "groupId": 674050067},
             "ClaimGroupBonus", []),
        ]
        for feature, intent, remote, args in cases:
            with self.subTest(feature=feature):
                call, reason = self.plan(feature, intent)
                self.assertIsNone(reason)
                self.assertEqual(call["remote"], remote)
                self.assertEqual(call["arity"], len(args))
                self.assertEqual([call["args"][i] for i in range(1, len(args) + 1)],
                                 args)

    def test_group_call_uses_current_membership_identity(self):
        call, reason = self.plan("groupBonus", {
            "kind": "groupBonusClaim", "groupId": 123456789})
        self.assertIsNone(reason)
        self.assertEqual(call["remote"], "ClaimGroupBonus")
        self.assertEqual(call["arity"], 0)

    def test_money_skill_and_no_arg_guards(self):
        cases = [
            ("skills", {"kind": "skillAllocation", "stat": "unknown", "count": 1}),
            ("skills", {"kind": "skillAllocation", "stat": "energy", "count": 0}),
            ("bank", {"kind": "bankDeposit", "amount": 1.5}),
            ("withdraw", {"kind": "purposeWithdrawal", "amount": 0}),
            ("safehouse", {"kind": "safehouseUpgrade", "nextTier": 19}),
            ("groupBonus", {"kind": "groupBonusClaim", "groupId": -1}),
        ]
        for feature, intent in cases:
            with self.subTest(feature=feature):
                self.assertIsNone(self.plan(feature, intent)[0])

    def test_source_backed_boss_attacks_and_claims(self):
        cases = [
            ("bosses", {"kind": "bossStageAttack", "stage": 8},
             "BossAction", ["stageAttack", 8]),
            ("globalBossAttack", {"kind": "globalBossAttack", "runKey": "event-1"},
             "GlobalBossAction", ["attack"]),
            ("globalBossClaim", {"kind": "globalBossClaim", "runKey": "event-1"},
             "GlobalBossAction", ["claim"]),
            ("familyBossAttacks", {"kind": "familyBossAttack", "week": 100,
                                   "famId": 9, "stage": 3},
             "FamilyBossAction", ["attack"]),
            ("familyBossClaims", {"kind": "familyBossClaim", "week": 100,
                                  "stage": 3},
             "FamilyBossAction", ["claim", 100, 3]),
        ]
        for feature, intent, remote, args in cases:
            with self.subTest(feature=feature):
                call, reason = self.plan(feature, intent)
                self.assertIsNone(reason)
                self.assertEqual(call["remote"], remote)
                self.assertEqual(call["arity"], len(args))
                self.assertEqual([call["args"][i] for i in range(1, len(args) + 1)],
                                 args)

    def test_boss_call_plan_never_selects_native_auto_or_bad_claim(self):
        self.assertIsNone(self.plan("bosses", {"kind": "stageAuto",
            "stage": 3})[0])
        self.assertIsNone(self.plan("familyBossClaims", {
            "kind": "familyBossClaim", "week": 0, "stage": 3})[0])
        self.assertIsNone(self.plan("globalBossClaim", {
            "kind": "globalBossClaim", "runKey": ""})[0])

    def test_property_build_keeps_native_nil_slot(self):
        call, reason = self.plan("properties", {"kind": "propertyBuild",
            "propId": "prop_corner", "optionalSlot": None})
        self.assertIsNone(reason)
        self.assertEqual(call["remote"], "BuyProperty")
        self.assertEqual(call["arity"], 2)
        self.assertEqual(call["args"][1], "prop_corner")
        self.assertIsNone(call["args"][2])
        self.assertIsNone(self.plan("properties", {"kind": "propertyBuild",
            "propId": "prop_corner", "optionalSlot": 2})[0])

    def test_playtime_ladder_claim_uses_saved_index(self):
        call, reason = self.plan("playtime", {"kind": "playtimeClaim",
            "index": 4, "day": 2026295, "rewardKind": "cash"})
        self.assertIsNone(reason)
        self.assertEqual(call["remote"], "ClaimLadder")
        self.assertEqual(call["arity"], 1)
        self.assertEqual(call["args"][1], 4)
        self.assertIsNone(self.plan("playtime", {"kind": "playtimeClaim",
            "index": 8})[0])

    def test_earned_trophy_and_monthly_calls_are_bounded(self):
        trophy, reason = self.plan("trophies", {"kind": "earnedTrophyClaim",
            "targetId": "t_eldersignet"})
        self.assertIsNone(reason)
        self.assertEqual(trophy["remote"], "ClaimTrophy")
        self.assertEqual(trophy["args"][1], "t_eldersignet")
        monthly, reason = self.plan("monthlyRewards", {"kind": "monthlyClaim",
            "month": 10, "nextDay": 2})
        self.assertIsNone(reason)
        self.assertEqual(monthly["remote"], "ClaimMonthly")
        self.assertEqual(monthly["arity"], 0)
        self.assertIsNone(self.plan("trophies", {"kind": "earnedTrophyClaim",
            "targetId": "t_other"})[0])
        self.assertIsNone(self.plan("monthlyRewards", {"kind": "monthlyClaim",
            "month": 0, "nextDay": 2})[0])

    def test_rejects_unverified_or_inconsistent_calls(self):
        for feature, intent in [
            ("heists", {"kind": "heistStart", "targetId": "h_1"}),
            ("bossShop", {"kind": "bossShopBuy", "item": "crate_loot",
                          "itemKind": "crate", "quantity": 2}),
            ("bossShop", {"kind": "bossShopBuy", "item": "crate_loot",
                          "itemKind": "gear", "quantity": 1}),
            ("bossShop", {"kind": "bossShopBuy", "item": "unknown",
                          "itemKind": "crate", "quantity": 1}),
            ("bossShop", {"kind": "bossShopBuy", "item": "w_policebaton",
                          "itemKind": "gear", "quantity": 10}),
        ]:
            self.assertIsNone(self.plan(feature, intent)[0])


if __name__ == "__main__":
    unittest.main()
