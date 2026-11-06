"""Missing Event Shop source must never become a speculative send."""
import unittest

from engine_harness import Harness, lua_table


class EventsTabTests(unittest.TestCase):
    def test_shop_descriptor_is_explicitly_blocked(self):
        h = Harness()
        blocked = h.load("src/tabs/events/EventShopBlocked.luau")
        tab = h.load("src/tabs/events/Module.luau").new(
            lua_table(h.lua, {
                "FreeBriefcasesState": h.load(
                    "src/game/FreeBriefcasesState.luau"),
                "FreeBriefcases": h.load(
                    "src/features/FreeBriefcases.luau"),
                "FreeBriefcasesEvidence": h.load(
                    "src/features/FreeBriefcasesEvidence.luau"),
                "EventShopBlocked": blocked,
            }))
        self.assertEqual([row["id"] for row in
                          tab.Descriptors(tab).values()],
                         ["briefcases", "eventShop"])
        self.assertIsNone(blocked.read()[0])
        self.assertIsNone(blocked.propose()[0])
        self.assertIsNone(blocked.capture()[0])


if __name__ == "__main__":
    unittest.main()
