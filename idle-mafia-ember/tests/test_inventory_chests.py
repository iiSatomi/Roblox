"""Only owned unbound crates may be opened; replies need exact Sync deltas."""
import unittest

from engine_harness import Harness, lua_table


class InventoryChestTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        source = self.h.load("src/tabs/inventory/NativeCrateCatalog.luau")
        self.feature = self.h.load("src/tabs/inventory/Chests.luau")
        catalog = source.new(lua_table(self.h.lua,
            {"ITEMS_BY_ID": {"crate_a": {"id": "crate_a",
                "kind": "crate"}}}), lua_table(self.h.lua,
            {"CRATE_BATCH_MAX": 10}), "f" * 64, "release-a")
        self.before = self.h.snapshot(native={"fullSync": True,
            "inventory": {"crate_a": 3},
            "inventoryBound": {"crate_a": 2}})
        self.before, reason = catalog.Enrich(catalog, self.before)
        self.assertIsNone(reason)
        self.context = lua_table(self.h.lua, {**self.h.session,
            "revision": 1, "capturedAt": 0,
            "crateCatalogKey": "f" * 64,
            "crateLuckProof": {"account": "user-a", "capturedAt": 0,
                "revision": 1, "luck": 0.25}})
        self.before["crateLuckProof"] = lua_table(self.h.lua,
            {"account": "user-a", "capturedAt": 0,
             "revision": 1, "luck": 0.25})

    def plan(self):
        view, reason = self.feature.read(self.before, self.context)
        self.assertIsNone(reason)
        proposal, reason = self.feature.propose(view, lua_table(self.h.lua,
            {"enabled": True, "policy": "Largest stack",
             "custom": {"maxBatch": 2}}))
        self.assertIsNone(reason)
        return proposal

    def test_unbound_batch_and_reward_inventory_evidence(self):
        proposal = self.plan()
        args = proposal["intent"]["args"]
        self.assertEqual(args[1], "crate_a")
        self.assertFalse(args[2])
        self.assertEqual(args[3], 2)
        self.assertEqual(args[4], 0.25)
        baseline, reason = self.feature.capture(proposal, self.before)
        self.assertIsNone(reason)
        after = self.h.snapshot(revision=2, native={"fullSync": True,
            "inventory": {"crate_a": 1, "prize_a": 2},
            "inventoryBound": {"crate_a": 2}})
        reply = lua_table(self.h.lua, {"ok": True,
            "opened": 2, "itemIds": ["prize_a", "prize_a"]})
        self.assertEqual(self.feature.evaluate(proposal, self.before,
            after, reply, baseline), "confirmed")
        after["native"]["inventory"]["prize_a"] = 1
        self.assertEqual(self.feature.evaluate(proposal, self.before,
            after, reply, baseline), "pending")

    def test_luck_change_or_bound_only_blocks(self):
        proposal = self.plan()
        self.before["native"]["inventory"]["crate_a"] = 0
        self.assertIsNone(self.feature.capture(proposal, self.before)[0])
        self.before["native"]["inventory"]["crate_a"] = 3
        self.context["crateLuckProof"]["luck"] = 0.3
        self.assertIsNone(self.feature.read(self.before, self.context)[0])
        self.before["crateLuckProof"]["luck"] = 0.3
        self.assertIsNone(self.feature.capture(proposal, self.before)[0])


if __name__ == "__main__":
    unittest.main()
