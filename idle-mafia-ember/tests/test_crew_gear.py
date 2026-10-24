"""Crew gear swaps spend only loose unbound copies with set-aware gains."""
import unittest

from engine_harness import Harness, lua_table


class CrewGearTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        module = self.h.load("src/tabs/crew/CrewGear.luau")
        self.items = {"old_w": {"id": "old_w", "kind": "weapon",
            "atk": 2, "def": 1}, "new_w": {"id": "new_w",
            "kind": "weapon", "atk": 8, "def": 3}}
        gear_sets = self.h.lua.execute("""return {slotBonus = function()
            return 0, 0 end}""")
        self.feature = module.new(lua_table(self.h.lua,
            {"ITEMS_BY_ID": self.items}), gear_sets,
            "d" * 64, "release-a")
        self.before = self.h.snapshot(native={"fullSync": True,
            "serverNow": 2000000, "inventory": {"new_w": 1},
            "inventoryBound": {}, "crew": [
                {"name": "Player", "weapon": "old_w"},
                {"name": "Ally", "rarity": 4, "duty": "district"}]})
        self.context = lua_table(self.h.lua, {**self.h.session,
            "revision": 1, "capturedAt": 0,
            "gearSourceKey": "d" * 64})

    def plan(self):
        view, reason = self.feature["read"](self.before, self.context)
        self.assertIsNone(reason)
        proposal, reason = self.feature["propose"](view,
            lua_table(self.h.lua, {"enabled": True,
                "policy": "Attack"}))
        self.assertIsNone(reason)
        return proposal

    def test_safe_swap_and_newer_equipment_proof(self):
        proposal = self.plan()
        self.assertEqual(proposal["intent"]["remote"], "CrewEquip")
        self.assertEqual(proposal["intent"]["args"][1], 1)
        self.assertEqual(proposal["intent"]["args"][2], "weapon")
        self.assertEqual(proposal["intent"]["args"][3], "new_w")
        baseline, reason = self.feature["capture"](proposal, self.before)
        self.assertIsNone(reason)
        after = self.h.snapshot(revision=2, native={"fullSync": True,
            "serverNow": 2000001, "inventory": {"new_w": 0,
                "old_w": 1}, "inventoryBound": {}, "crew": [
                {"name": "Player", "weapon": "new_w"},
                {"name": "Ally", "rarity": 4, "duty": "district"}]})
        self.assertEqual(self.feature["evaluate"](proposal, self.before,
            after, lua_table(self.h.lua, {"ok": True}), baseline),
            "confirmed")
        after["native"]["inventory"]["new_w"] = 1
        self.assertEqual(self.feature["evaluate"](proposal, self.before,
            after, lua_table(self.h.lua, {"ok": True}), baseline),
            "pending")

    def test_bound_slot_or_missing_copy_blocks(self):
        self.before["native"]["crew"][1]["weaponBound"] = True
        self.assertIsNone(self.feature["propose"](
            self.feature["read"](self.before, self.context)[0],
            lua_table(self.h.lua, {"enabled": True,
                "policy": "Attack"}))[0])
        self.before["native"]["crew"][1]["weaponBound"] = False
        proposal = self.plan()
        self.before["native"]["inventory"]["new_w"] = 0
        self.assertIsNone(self.feature["capture"](proposal, self.before)[0])


if __name__ == "__main__":
    unittest.main()
