"""Saved native AutoEquipCrew call requires newer exact equipment evidence."""
import unittest

from engine_harness import Harness, lua_table


class CrewAutoEquipTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.feature = self.h.load("src/tabs/crew/AutoEquipCrew.luau")
        self.before = self.h.snapshot(native={"fullSync": True,
            "inventory": {"weapon_b": 1}, "inventoryBound": {},
            "crew": [{"name": "Player", "weapon": "old"},
                     {"name": "Ally", "rarity": 4, "armor": "armor_a"}]})
        self.context = lua_table(self.h.lua, {**self.h.session,
            "revision": 1, "capturedAt": 0})

    def plan(self):
        view, reason = self.feature.read(self.before, self.context)
        self.assertIsNone(reason)
        proposal, reason = self.feature.propose(view,
            lua_table(self.h.lua, {"enabled": True}))
        self.assertIsNone(reason)
        return proposal

    def test_no_argument_call_and_changed_gear_proof(self):
        proposal = self.plan()
        self.assertEqual(proposal["intent"]["remote"], "AutoEquipCrew")
        self.assertEqual(len(proposal["intent"]["args"]), 0)
        self.assertTrue(proposal["actionKey"].startswith("crewAutoEquip:"))
        baseline, reason = self.feature.capture(proposal, self.before)
        self.assertIsNone(reason)
        after = self.h.snapshot(native={"fullSync": True,
            "inventory": {}, "inventoryBound": {},
            "crew": [{"name": "Player", "weapon": "better"},
                     {"name": "Ally", "rarity": 4, "armor": "armor_a"}]})
        after["revision"] = 2
        ok = lua_table(self.h.lua, {"ok": True, "changed": True})
        self.assertEqual(self.feature.evaluate(proposal, self.before,
            after, ok, baseline), "confirmed")
        self.assertEqual(self.feature.evaluate(proposal, self.before,
            after, lua_table(self.h.lua, {"ok": False}), baseline), "rejected")

    def test_reply_only_cannot_confirm_and_noop_requires_fresh_sync(self):
        proposal = self.plan()
        baseline, _ = self.feature.capture(proposal, self.before)
        self.assertEqual(self.feature.evaluate(proposal, self.before,
            self.before, lua_table(self.h.lua, {"ok": True,
                "changed": True}), baseline), "pending")
        after = self.h.snapshot(native={"fullSync": True,
            "inventory": {"weapon_b": 1}, "inventoryBound": {},
            "crew": [{"name": "Player", "weapon": "old"},
                     {"name": "Ally", "rarity": 4, "armor": "armor_a"}]})
        after["revision"] = 2
        self.assertEqual(self.feature.evaluate(proposal, self.before,
            after, lua_table(self.h.lua, {"ok": True,
                "changed": False}), baseline), "confirmed")
        self.assertEqual(self.feature.evaluate(proposal, self.before,
            after, lua_table(self.h.lua, {"ok": True,
                "changed": True}), baseline), "pending")

    def test_other_member_or_partial_sync_does_not_confirm(self):
        proposal = self.plan()
        baseline, _ = self.feature.capture(proposal, self.before)
        after = self.h.snapshot(native={"fullSync": True,
            "inventory": {}, "inventoryBound": {},
            "crew": [{"name": "Player", "weapon": "better"},
                     {"name": "Other", "rarity": 4, "armor": "armor_a"}]})
        after["revision"] = 2
        reply = lua_table(self.h.lua, {"ok": True, "changed": True})
        self.assertEqual(self.feature.evaluate(proposal, self.before,
            after, reply, baseline), "pending")
        after["native"]["crew"][2]["name"] = "Ally"
        after["native"]["fullSync"] = False
        self.assertEqual(self.feature.evaluate(proposal, self.before,
            after, reply, baseline), "pending")

    def test_action_key_stable_across_revisions_until_inventory_changes(self):
        first = self.plan()["actionKey"]
        self.before["revision"] = 2
        self.context["revision"] = 2
        self.assertEqual(self.plan()["actionKey"], first)
        self.before["native"]["inventory"]["weapon_b"] = 2
        self.assertNotEqual(self.plan()["actionKey"], first)

    def test_tab_exposes_native_descriptor_and_roster_reader(self):
        tab = self.h.load("src/tabs/crew/Module.luau").new(
            lua_table(self.h.lua, {"RosterState":
                self.h.load("src/tabs/crew/RosterState.luau"),
                "AutoEquipCrew": self.feature,
                "CrewSort": self.h.load("src/tabs/crew/CrewSort.luau"),
                "CrewHeal": self.h.load("src/tabs/crew/CrewHeal.luau"),
                "CrewTrain": self.h.load("src/tabs/crew/CrewTrain.luau"),
                "CrewHire": self.h.load("src/tabs/crew/CrewHire.luau"),
                "CrewHealItems": self.h.load(
                    "src/tabs/crew/CrewHealItems.luau"),
                "NativeHireCatalog": self.h.load(
                    "src/tabs/crew/NativeHireCatalog.luau"),
                "NativeHealItemCatalog": self.h.load(
                    "src/tabs/crew/NativeHealItemCatalog.luau"),
                "CrewGear": self.h.load("src/tabs/crew/CrewGear.luau"),
                "CrewRollState": self.h.load(
                    "src/tabs/crew/CrewRollState.luau"),
                "gearSets": self.h.lua.execute("""return {slotBonus =
                    function() return 0, 0 end}"""),
                "NativeTrainingCatalog": self.h.load(
                    "src/tabs/crew/NativeTrainingCatalog.luau"),
                "gameData": {"ITEMS_BY_ID": {item: {
                    "id": item, "kind": "consumable",
                    "restore": {"pool": "health", "percent": percent}}
                    for item, percent in (("con_bandages", 25),
                        ("con_medkit_small", 50),
                        ("con_medkit_large", 100))}},
                "config": {"TERRITORY": {"injurySeconds": 1200},
                    "CONSUMABLES": {"henchmanCooldownSeconds": 3},
                    "CREW": {"hireTiers": [
                    {"id": "street", "cost": 10000}], "training": {
                    "minRarity": 4, "maxLevel": 1,
                    "maxConcurrent": 1,
                    "cost": {i: [100] for i in range(4, 9)},
                    "minutes": {i: [5] for i in range(4, 9)}}}},
                "fingerprint": "a" * 64, "release": "release-a"}))
        self.assertEqual(tab["Descriptors"](tab)[1]["id"], "crew")


if __name__ == "__main__":
    unittest.main()
