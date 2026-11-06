"""Collection protection is produced from current pending equipment plans."""
import unittest

from engine_harness import Harness, lua_table


class CollectionProtectionTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.producer = self.h.load(
            "src/engine/CollectionProtection.luau")
        self.raw = self.h.snapshot(native={"fullSync": True})
        self.context = lua_table(self.h.lua, {**self.h.session,
            "revision": 1, "capturedAt": 0})
        self.spec = self.h.lua.execute("""return {
            reader = { read = function(raw) return raw.native end },
            planner = { propose = function(_, config)
                return { feature = config.feature,
                    intent = { itemId = config.itemId } }
            end },
        }""")

    def derive(self, settings, features=None):
        return self.producer.derive(self.raw, self.context,
            lua_table(self.h.lua, settings),
            lua_table(self.h.lua, features or {}))

    def test_disabled_plans_produce_empty_current_proof(self):
        proof, reason = self.derive({})
        self.assertIsNone(reason)
        self.assertTrue(proof["covers"]["gear"])
        self.assertTrue(proof["covers"]["cosmetics"])
        self.assertIsNone(proof["protected"]["w_a"])

    def test_enabled_plans_protect_selected_items(self):
        proof, reason = self.derive({
            "crewGear": {"enabled": True, "feature": "crewGear",
                         "itemId": "w_a"},
            "cosmetics": {"enabled": True, "feature": "cosmetics",
                          "itemId": "bg_a"},
        }, {"crewGear": self.spec, "cosmetics": self.spec})
        self.assertIsNone(reason)
        self.assertEqual(proof["protected"]["w_a"], 1)
        self.assertEqual(proof["protected"]["bg_a"], 1)

    def test_enabled_unknown_planner_or_changed_sync_has_no_proof(self):
        self.assertIsNone(self.derive({
            "crewGear": {"enabled": True}})[0])
        self.raw["revision"] = 2
        self.assertIsNone(self.derive({})[0])


if __name__ == "__main__":
    unittest.main()
