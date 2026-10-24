"""Collection deposits preserve worn/spare gear and prove exact custody."""
import unittest

from engine_harness import Harness, lua_table


class CollectionDonateTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        source = self.h.load("src/tabs/collection/NativeCollectionCatalog.luau")
        self.feature = self.h.load(
            "src/tabs/collection/CollectionDonate.luau")
        catalog = source.new(lua_table(self.h.lua,
            {"ITEMS_BY_ID": {"w_a": {"id": "w_a",
                "kind": "weapon", "rarity": 4,
                "atk": 2, "def": 1}}}), lua_table(self.h.lua,
            {"COLLECTION": {"bonusByRarity": [1, 2, 3, 5],
                "tiers": [{"count": 1, "mult": 1},
                          {"count": 10, "mult": 2}]}}),
            "2" * 64, "release-a")
        self.before = self.h.snapshot(native={"fullSync": True,
            "inventory": {"w_a": 4}, "inventoryBound": {},
            "collection": {"w_a": 9}, "collectionBound": {},
            "crew": [{"name": "Player", "weapon": "w_a"},
                     {"name": "Ally", "rarity": 4}],
            "equippedBorder": None, "equippedBackground": None})
        self.before, reason = catalog.Enrich(catalog, self.before)
        self.assertIsNone(reason)
        self.context = lua_table(self.h.lua, {**self.h.session,
            "revision": 1, "capturedAt": 0,
            "collectionCatalogKey": "2" * 64})
        producer = self.h.load("src/engine/CollectionProtection.luau")
        proof, reason = producer.derive(self.before, self.context,
            lua_table(self.h.lua, {}), lua_table(self.h.lua, {}))
        self.assertIsNone(reason)
        self.context["collectionProtection"] = proof
        self.before["collectionProtection"] = proof

    def plan(self):
        view, reason = self.feature.read(self.before, self.context)
        self.assertIsNone(reason)
        proposal, reason = self.feature.propose(view, lua_table(self.h.lua,
            {"enabled": True, "custom": {"maxBatch": 2,
                "sparesToKeep": 1}}))
        self.assertIsNone(reason)
        return proposal

    def test_preserves_worn_spare_and_confirms_exact_move(self):
        proposal = self.plan()
        self.assertEqual(proposal["intent"]["args"][1], "deposit")
        self.assertEqual(proposal["intent"]["args"][2], "w_a")
        self.assertEqual(proposal["intent"]["args"][3], 2)
        baseline, reason = self.feature.capture(proposal, self.before)
        self.assertIsNone(reason)
        after = self.h.snapshot(revision=2, native={"fullSync": True,
            "inventory": {"w_a": 2}, "inventoryBound": {},
            "collection": {"w_a": 11}, "collectionBound": {},
            "crew": [{"name": "Player", "weapon": "w_a"},
                     {"name": "Ally", "rarity": 4}]})
        self.assertEqual(self.feature.evaluate(proposal, self.before,
            after, lua_table(self.h.lua, {"ok": True, "moved": 2}),
            baseline), "confirmed")
        after["native"]["collection"]["w_a"] = 10
        self.assertEqual(self.feature.evaluate(proposal, self.before,
            after, lua_table(self.h.lua, {"ok": True, "moved": 2}),
            baseline), "pending")

    def test_worn_or_loose_change_blocks_capture(self):
        proposal = self.plan()
        self.before["native"]["crew"][2]["weapon"] = "w_a"
        self.assertIsNone(self.feature.capture(proposal, self.before)[0])
        self.before["native"]["crew"][2]["weapon"] = None
        self.before["native"]["inventory"]["w_a"] = 1
        self.assertIsNone(self.feature.capture(proposal, self.before)[0])


if __name__ == "__main__":
    unittest.main()
