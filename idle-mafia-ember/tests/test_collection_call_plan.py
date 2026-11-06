"""Collection deposits have one reviewed native signature."""
import unittest

from engine_harness import Harness, lua_table


class CollectionCallPlanTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.plan = self.h.load(
            "src/tabs/collection/CollectionCallPlan.luau")

    def test_exact_deposit_call(self):
        proposal = lua_table(self.h.lua, {"feature": "collectionDonate",
            "intent": {"kind": "collectionDonate",
                       "itemId": "w_a", "amount": 2,
                       "catalogKey": "a" * 64}})
        call, reason = self.plan.describe(proposal)
        self.assertIsNone(reason)
        self.assertEqual(call.remote, "CollectionAction")
        self.assertEqual(call.method, "InvokeServer")
        self.assertEqual(call.arity, 3)
        self.assertEqual(call.args[1], "deposit")
        self.assertEqual(call.args[2], "w_a")
        self.assertEqual(call.args[3], 2)
        proposal["intent"]["amount"] = 0
        self.assertIsNone(self.plan.describe(proposal)[0])


if __name__ == "__main__":
    unittest.main()
