"""Crew reader only stages source-backed, identity-bound custody facts."""
import unittest

from engine_harness import Harness, lua_table


class CrewRosterStateTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.reader = self.h.load("src/tabs/crew/RosterState.luau")
        self.raw = self.h.snapshot(native={"fullSync": True,
            "crew": [{"name": "Player"}, {"name": "Ally", "rarity": 4,
                "border": "border_a"}],
            "inventory": {"border_a": 1},
            "inventoryBound": {"border_a": 2},
            "equippedBorder": "border_a"})
        self.context = {**self.h.session, "revision": 1,
            "capturedAt": 0, "itemsById": {
                "border_a": {"kind": "border", "name": "A"}}}

    def read(self):
        return self.reader.read(self.raw, lua_table(self.h.lua, self.context))

    def test_copies_members_and_keeps_worn_separate_from_loose(self):
        view, reason = self.read()
        self.assertIsNone(reason)
        self.assertEqual(view["members"][2]["border"], "border_a")
        self.assertEqual(view["borders"]["border_a"]["totalLoose"], 3)
        self.assertEqual(view["borders"]["border_a"]["worn"], 2)
        self.raw["native"]["crew"][2]["border"] = None
        self.assertEqual(view["members"][2]["border"], "border_a")

    def test_rejects_identity_and_partial_sync(self):
        self.raw["account"] = "other"
        self.assertIsNone(self.read()[0])
        self.raw["account"] = self.h.session["account"]
        self.raw["native"]["fullSync"] = False
        self.assertIsNone(self.read()[0])

    def test_rejects_unknown_border_and_invalid_counts(self):
        self.raw["native"]["crew"][2]["border"] = "unknown"
        self.assertIsNone(self.read()[0])
        self.raw["native"]["crew"][2]["border"] = "border_a"
        self.raw["native"]["inventoryBound"]["border_a"] = -1
        self.assertIsNone(self.read()[0])

    def test_rolling_member_can_have_no_name_yet(self):
        self.raw["native"]["crew"][2]["name"] = None
        self.raw["native"]["crew"][2]["rarity"] = None
        self.raw["native"]["crew"][2]["rolling"] = True
        view, reason = self.read()
        self.assertIsNone(reason)
        self.assertEqual(view["members"][2]["name"], "ROLLING")


if __name__ == "__main__":
    unittest.main()
