"""Heist mutations describe native act inputs, without allocating server sequences."""
import unittest

from engine_harness import Harness, lua_table


class HeistCallPlanTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.module = self.h.load("src/tabs/heists/HeistCallPlan.luau")

    def test_four_native_action_descriptions_preserve_collect_nil_argument(self):
        for feature, kind, action, target in (
            ("heists", "heistStart", "start", "h_a"),
            ("heistCollect", "heistCollect", "collect", None),
            ("favors", "favorHelp", "help", "row-a"),
            ("sabotage", "heistSabotage", "sabotage", "row-b"),
        ):
            with self.subTest(feature=feature):
                intent = {"kind": kind, "needsSequence": True}
                if action == "start":
                    intent.update(heistId=target, expectedStake=10, expectedEnergy=2)
                    resources = {"cash": 10, "energy": 2}
                elif action == "collect":
                    intent.update(resultKey="a" * 64)
                    resources = {}
                else:
                    intent.update(rowId=target, expectedFavorCost=1, expectedEnergyCost=2)
                    resources = {"favors": 1, "energy": 2}
                proposal = lua_table(self.h.lua, {"feature": feature, "intent": intent,
                                                    "resources": resources})
                call, reason = self.module.describe(proposal)
                self.assertIsNone(reason)
                self.assertEqual((call.remote, call.method, call.arity),
                                 ("HeistAction", "InvokeServer", 2))
                self.assertTrue(call.nativeAct)
                self.assertEqual(call.args[1], action)
                self.assertEqual(call.args[2], target)
                self.assertIsNone(call.sequence)
                proposal.resources.gold = 1
                self.assertIsNone(self.module.describe(proposal)[0])

    def test_unknown_kind_or_missing_sequence_contract_is_blocked(self):
        proposal = lua_table(self.h.lua, {"feature": "heists", "resources": {},
            "intent": {"kind": "heistStart", "heistId": "h_a"}})
        self.assertIsNone(self.module.describe(proposal)[0])


if __name__ == "__main__":
    unittest.main()
