"""Inventory calls use reviewed native signatures with primitive intents."""
import unittest

from engine_harness import Harness, lua_table


class InventoryCallPlanTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        base = self.h.load("src/transport/NativeCallPlan.luau")
        self.plan = base.withInventory(
            base.withCrew(self.h.load("src/tabs/crew/CrewCallPlan.luau")),
            self.h.load("src/tabs/inventory/InventoryCallPlan.luau"))

    def describe(self, feature, intent):
        return self.plan.describe(lua_table(self.h.lua, {
            "feature": feature, "intent": intent}))

    def test_cosmetic_crate_and_player_consumable_arity(self):
        cases = [
            ("cosmetics", {"kind": "cosmetics", "cosmeticKind": "background",
                           "itemId": "bg_new", "sourceKey": "reviewed"},
             "EquipBackground", 1, ["bg_new"]),
            ("chests", {"kind": "chests", "itemId": "crate_a",
                        "amount": 2, "luck": 0.5, "catalogKey": "reviewed"},
             "OpenCrate", 4, ["crate_a", False, 2, 0.5]),
            ("restoratives", {"kind": "restoratives", "itemId": "con_a",
                             "fromBound": True, "sequence": 4,
                             "catalogKey": "reviewed"},
             "UseConsumable", 3, ["con_a", True, 4]),
        ]
        for feature, intent, remote, arity, args in cases:
            with self.subTest(feature=feature):
                call, reason = self.describe(feature, intent)
                self.assertIsNone(reason)
                self.assertEqual((call["remote"], call["arity"]),
                                 (remote, arity))
                self.assertEqual([call["args"][i] for i in range(1, arity + 1)],
                                 args)

    def test_invalid_item_or_sequence_cannot_be_dispatched(self):
        self.assertIsNone(self.describe("chests", {"kind": "chests",
            "itemId": "crate_a", "amount": 0, "luck": 0.5,
            "catalogKey": "reviewed"})[0])
        self.assertIsNone(self.describe("restoratives", {
            "kind": "restoratives", "itemId": "con_a",
            "fromBound": True, "sequence": -1,
            "catalogKey": "reviewed"})[0])


if __name__ == "__main__":
    unittest.main()
