"""Owned Crew healing items require sequence, cooldown and custody proof."""
import unittest

from engine_harness import Harness, lua_table


class CrewHealItemsTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.source = self.h.load(
            "src/tabs/crew/NativeHealItemCatalog.luau")
        self.feature = self.h.load("src/tabs/crew/CrewHealItems.luau")
        items = {item: {"id": item, "kind": "consumable",
            "restore": {"pool": "health", "percent": percent}}
            for item, percent in (("con_bandages", 25),
                ("con_medkit_small", 50), ("con_medkit_large", 100))}
        self.catalog = self.source.new(lua_table(self.h.lua,
            {"ITEMS_BY_ID": items}), lua_table(self.h.lua,
            {"TERRITORY": {"injurySeconds": 1200},
             "CONSUMABLES": {"henchmanCooldownSeconds": 3}}),
            "c" * 64, "release-a")
        self.now = 2000000
        self.before = self.h.snapshot(native={"fullSync": True,
            "serverNow": self.now, "henchmanConsumableUseSequence": 7,
            "henchmanConsumableReadyAt": self.now - 1,
            "inventoryBound": {"con_bandages": 2},
            "inventory": {"con_bandages": 1},
            "crew": [{"name": "Player"}, {"name": "Ally", "rarity": 4,
                "healId": "injury-a", "injuredUntil": self.now + 700}]})
        self.before, reason = self.catalog.Enrich(self.catalog, self.before)
        self.assertIsNone(reason)
        self.context = lua_table(self.h.lua, {**self.h.session,
            "revision": 1, "capturedAt": 0, "serverNow": self.now,
            "healItemCatalogKey": "c" * 64})

    def plan(self):
        view, reason = self.feature.read(self.before, self.context)
        self.assertIsNone(reason)
        proposal, reason = self.feature.propose(view, lua_table(self.h.lua,
            {"enabled": True, "policy": "con_bandages",
             "custom": {"minRemaining": 300}}))
        self.assertIsNone(reason)
        return proposal

    def test_bound_first_payload_and_exact_confirmation(self):
        proposal = self.plan()
        args = proposal["intent"]["args"]
        self.assertEqual(args[1], "healitem")
        self.assertEqual(args[2], 2)
        self.assertEqual(args[3]["itemId"], "con_bandages")
        self.assertTrue(args[3]["fromBound"])
        self.assertEqual(args[3]["sequence"], 7)
        baseline, reason = self.feature.capture(proposal, self.before)
        self.assertIsNone(reason)
        after = self.h.snapshot(revision=2, native={"fullSync": True,
            "serverNow": self.now + 2,
            "henchmanConsumableUseSequence": 8,
            "henchmanConsumableReadyAt": self.now + 3,
            "inventoryBound": {"con_bandages": 1},
            "inventory": {"con_bandages": 1},
            "crew": [{"name": "Player"}, {"name": "Ally", "rarity": 4,
                "healId": "injury-a", "injuredUntil": self.now + 400}]})
        reply = lua_table(self.h.lua, {"ok": True,
            "sequence": 8, "readyAt": self.now + 3})
        self.assertEqual(self.feature.evaluate(proposal, self.before,
            after, reply, baseline), "confirmed")
        after["native"]["inventoryBound"]["con_bandages"] = 2
        self.assertEqual(self.feature.evaluate(proposal, self.before,
            after, reply, baseline), "pending")

    def test_cooldown_or_sequence_change_blocks(self):
        proposal = self.plan()
        self.before["native"]["henchmanConsumableReadyAt"] = self.now + 2
        self.assertIsNone(self.feature.capture(proposal, self.before)[0])
        self.before["native"]["henchmanConsumableReadyAt"] = self.now - 1
        self.before["native"]["henchmanConsumableUseSequence"] = 8
        self.assertIsNone(self.feature.capture(proposal, self.before)[0])

    def test_missing_item_or_duplicate_identity_blocks(self):
        self.before["native"]["inventoryBound"]["con_bandages"] = 0
        self.before["native"]["inventory"]["con_bandages"] = 0
        view, reason = self.feature.read(self.before, self.context)
        self.assertIsNone(reason)
        self.assertIsNone(self.feature.propose(view, lua_table(self.h.lua,
            {"enabled": True, "policy": "con_bandages",
             "custom": {"minRemaining": 300}}))[0])
        self.before["native"]["crew"][3] = lua_table(self.h.lua,
            {"name": "Ally", "rarity": 4, "healId": "injury-b"})
        self.assertIsNone(self.feature.read(self.before, self.context)[0])


if __name__ == "__main__":
    unittest.main()
