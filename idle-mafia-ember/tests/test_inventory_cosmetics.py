"""Safe cosmetic changes use owned unbound copies and newer worn state."""
import unittest

from engine_harness import Harness, lua_table


class InventoryCosmeticTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        module = self.h.load("src/tabs/inventory/Cosmetics.luau")
        self.feature = module.new(lua_table(self.h.lua,
            {"ITEMS_BY_ID": {
                "bg_old": {"id": "bg_old", "kind": "background",
                           "atk": 1, "def": 1},
                "bg_new": {"id": "bg_new", "kind": "background",
                           "atk": 5, "def": 3}}}),
            "1" * 64, "release-a")
        self.before = self.h.snapshot(native={"fullSync": True,
            "equippedBackground": "bg_old", "inventory": {
                "bg_old": 1, "bg_new": 1}, "inventoryBound": {},
            "collectionBound": {}})
        self.context = lua_table(self.h.lua, {**self.h.session,
            "revision": 1, "capturedAt": 0,
            "cosmeticSourceKey": "1" * 64})

    def plan(self):
        view, reason = self.feature["read"](self.before, self.context)
        self.assertIsNone(reason)
        proposal, reason = self.feature["propose"](view,
            lua_table(self.h.lua, {"enabled": True,
                "policy": "Balanced"}))
        self.assertIsNone(reason)
        return proposal

    def test_unbound_display_upgrade(self):
        proposal = self.plan()
        self.assertEqual(proposal["intent"]["remote"], "EquipBackground")
        self.assertEqual(proposal["intent"]["args"][1], "bg_new")
        baseline, reason = self.feature["capture"](proposal, self.before)
        self.assertIsNone(reason)
        after = self.h.snapshot(revision=2, native={"fullSync": True,
            "equippedBackground": "bg_new", "inventory": {
                "bg_old": 1, "bg_new": 1}, "inventoryBound": {},
            "collectionBound": {}})
        self.assertEqual(self.feature["evaluate"](proposal, self.before,
            after, lua_table(self.h.lua, {"ok": True}), baseline),
            "confirmed")

    def test_bound_custody_or_changed_worn_blocks(self):
        proposal = self.plan()
        self.before["native"]["equippedBackground"] = None
        self.assertIsNone(self.feature["capture"](proposal, self.before)[0])
        self.before["native"]["equippedBackground"] = "bg_old"
        self.before["native"]["inventoryBound"]["bg_new"] = 1
        self.assertIsNone(self.feature["read"](self.before,
            self.context)[0])


if __name__ == "__main__":
    unittest.main()
