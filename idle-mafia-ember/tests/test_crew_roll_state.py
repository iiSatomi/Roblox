"""Native Crew Auto Roll status is readable while start stays blocked."""
import unittest

from engine_harness import Harness, lua_table


class CrewRollStateTests(unittest.TestCase):
    def test_reads_owned_state_but_never_sends(self):
        h = Harness()
        module = h.load("src/tabs/crew/CrewRollState.luau")
        raw = h.snapshot(native={"fullSync": True, "cash": 10000,
            "derived": {"autoRoll": False},
            "crew": [{"name": "Player"}, {},
                     {"name": "Ally", "rarity": 4, "rolling": True}]})
        context = lua_table(h.lua, {**h.session,
            "revision": 1, "capturedAt": 0})
        view, reason = module.read(raw, context)
        self.assertIsNone(reason)
        self.assertEqual(view["emptySlots"][1], 2)
        self.assertEqual(view["activeSlots"][1], 3)
        self.assertFalse(view["passDerived"])
        self.assertIsNone(module.propose(view, lua_table(h.lua,
            {"enabled": True}))[0])
        self.assertIsNone(module.capture()[0])
        self.assertEqual(module.evaluate(), "pending")


if __name__ == "__main__":
    unittest.main()
