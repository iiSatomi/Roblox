"""Player restoratives require owned custody, cooldown and sequence evidence."""
import unittest

from engine_harness import Harness, lua_table


ITEMS = (("con_bandages", "health", 25),
         ("con_medkit_small", "health", 50),
         ("con_medkit_large", "health", 100),
         ("con_energy_small", "energy", 25),
         ("con_energy", "energy", 50),
         ("con_energy_pack", "energy", 100),
         ("con_peanuts", "stamina", 25),
         ("con_sandwich", "stamina", 50),
         ("con_lunchbox", "stamina", 100))


class InventoryRestorativesTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        source = self.h.load(
            "src/tabs/inventory/NativeRestorativeCatalog.luau")
        self.feature = self.h.load(
            "src/tabs/inventory/Restoratives.luau")
        data = lua_table(self.h.lua, {"ITEMS_BY_ID": {
            item: {"id": item, "kind": "consumable",
                   "restore": {"pool": pool, "percent": percent}}
            for item, pool, percent in ITEMS}})
        catalog = source.new(data, lua_table(self.h.lua,
            {"CONSUMABLES": {"cooldownSeconds": 3}}),
            "e" * 64, "release-a")
        self.before = self.h.snapshot(native={"fullSync": True,
            "serverNow": 2000000, "consumableUseSequence": 4,
            "consumableReadyAt": 1999999,
            "pools": {"health": 30, "energy": 100, "stamina": 50},
            "stats": {"maxHealth": 100, "maxStamina": 100},
            "derived": {"effMaxEnergy": 100},
            "inventoryBound": {"con_medkit_small": 1},
            "inventory": {"con_medkit_small": 1}})
        self.before, reason = catalog.Enrich(catalog, self.before)
        self.assertIsNone(reason)
        self.context = lua_table(self.h.lua, {**self.h.session,
            "revision": 1, "capturedAt": 0, "serverNow": 2000000,
            "restorativeCatalogKey": "e" * 64})

    def settings(self):
        return lua_table(self.h.lua, {"enabled": True,
            "policy": "Balanced recovery", "custom": {
                "healthBelow": 50, "energyBelow": 25,
                "staminaBelow": 25, "custody": "Bound only"}})

    def plan(self):
        view, reason = self.feature.read(self.before, self.context)
        self.assertIsNone(reason)
        proposal, reason = self.feature.propose(view, self.settings())
        self.assertIsNone(reason)
        return proposal

    def test_bound_first_and_exact_newer_sequence(self):
        proposal = self.plan()
        args = proposal["intent"]["args"]
        self.assertEqual(args[1], "con_medkit_small")
        self.assertTrue(args[2])
        self.assertEqual(args[3], 4)
        baseline, reason = self.feature.capture(proposal, self.before)
        self.assertIsNone(reason)
        after = self.h.snapshot(revision=2, native={"fullSync": True,
            "serverNow": 2000001, "consumableUseSequence": 5,
            "consumableReadyAt": 2000003,
            "pools": {"health": 80},
            "inventoryBound": {"con_medkit_small": 0},
            "inventory": {"con_medkit_small": 1}})
        reply = lua_table(self.h.lua, {"ok": True,
            "sequence": 5, "readyAt": 2000003,
            "resource": "health", "gain": 50})
        self.assertEqual(self.feature.evaluate(proposal, self.before,
            after, reply, baseline), "confirmed")
        after["native"]["inventoryBound"]["con_medkit_small"] = 1
        self.assertEqual(self.feature.evaluate(proposal, self.before,
            after, reply, baseline), "pending")

    def test_cooldown_and_sequence_fence(self):
        proposal = self.plan()
        self.before["native"]["consumableReadyAt"] = 2000002
        self.assertIsNone(self.feature.capture(proposal, self.before)[0])
        self.before["native"]["consumableReadyAt"] = 1999999
        self.before["native"]["consumableUseSequence"] = 5
        self.assertIsNone(self.feature.capture(proposal, self.before)[0])


if __name__ == "__main__":
    unittest.main()
