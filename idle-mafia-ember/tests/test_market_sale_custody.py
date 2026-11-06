"""Owned-item sale custody only proposes safe unbound quantities."""
import unittest

from engine_harness import Harness, lua_table


class MarketSaleCustodyTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.module = self.h.load(
            "src/tabs/blackMarket/MarketSaleCustody.luau")
        self.header = {"session": "s", "account": "a", "place": "p",
                       "release": "r", "revision": 4, "capturedAt": 10}

    def inputs(self, loose=5, bound=1, collected=0, collected_bound=0,
               crew=None, equipped_border=None, protected=0):
        raw = dict(self.header)
        raw["native"] = {"fullSync": True,
            "inventory": {"w_baton": loose},
            "inventoryBound": {"w_baton": bound},
            "collection": {"w_baton": collected},
            "collectionBound": {"w_baton": collected_bound},
            "crew": crew if crew is not None else [{}],
            "equippedBorder": equipped_border}
        context = dict(self.header)
        context["collectionProtection"] = dict(self.header,
            covers={"gear": True, "cosmetics": True},
            protected={"w_baton": protected})
        item = {"id": "w_baton", "tradable": True,
                "kind": "weapon", "rarity": 2}
        settings = {"keepLoose": 1, "maxQuantity": 10,
                    "fromCollection": False,
                    "blockedItems": {}, "blockedKinds": {},
                    "blockedRarities": {}}
        tiers = [{"count": n} for n in (1, 10, 100, 1000, 5000)]
        return [lua_table(self.h.lua, value) for value in
                (raw, context, "w_baton", item, settings, tiers)]

    def assess(self, values):
        return self.module.assess(*values)

    def test_loose_quantity_keeps_configured_and_worn_copies(self):
        values = self.inputs(loose=5,
            crew=[{"weapon": "w_baton"}, {"weapon": "w_baton"}])
        candidate, reason = self.assess(values)
        self.assertIsNone(reason)
        self.assertEqual(candidate["loose"], 5)
        self.assertEqual(candidate["reservedLoose"], 2)
        self.assertEqual(candidate["quantity"], 3)
        self.assertEqual(candidate["withdraw"], 0)

    def test_held_transaction_copies_are_additional_to_spares_and_equipment(self):
        values = self.inputs(loose=5, protected=2)
        values[1].collectionProtection.reserved = lua_table(self.h.lua, {"w_baton": 2})
        candidate, reason = self.assess(values)
        self.assertIsNone(reason)
        self.assertEqual(candidate.quantity, 1)
        self.assertEqual(candidate.reservedLoose, 4)
        values[1].collectionProtection.reserved.w_baton = 4
        self.assertIsNone(self.assess(values)[0])
        for malformed in (-1, False, "2", float("nan")):
            values[1].collectionProtection.reserved.w_baton = malformed
            self.assertIsNone(self.assess(values)[0])

    def test_bound_inventory_never_increases_sale_quantity(self):
        values = self.inputs(loose=1, bound=100)
        self.assertIsNone(self.assess(values)[0])

    def test_only_collection_surplus_above_highest_checkpoint_is_eligible(self):
        values = self.inputs(loose=2, collected=5, collected_bound=7)
        values[4]["fromCollection"] = True
        candidate, reason = self.assess(values)
        self.assertIsNone(reason)
        self.assertEqual(candidate["checkpointFloor"], 10)
        self.assertEqual(candidate["collectionSurplus"], 2)
        self.assertEqual(candidate["quantity"], 3)
        self.assertEqual(candidate["withdraw"], 2)

    def test_upgraded_collection_variant_counts_toward_checkpoint_floor(self):
        values = self.inputs(loose=1, collected=5, collected_bound=4)
        values[0]["native"]["collectionBound"]["w_baton@1"] = 1
        values[4]["fromCollection"] = True
        self.assertIsNone(self.assess(values)[0])

    def test_configured_protection_and_quantity_cap_hold(self):
        values = self.inputs(loose=20, protected=4)
        values[4]["maxQuantity"] = 5
        candidate, reason = self.assess(values)
        self.assertIsNone(reason)
        self.assertEqual(candidate["reservedLoose"], 4)
        self.assertEqual(candidate["quantity"], 5)

    def test_blacklists_and_nontradable_items_are_rejected(self):
        for field, key in (("blockedItems", "w_baton"),
                           ("blockedKinds", "weapon"),
                           ("blockedRarities", 2)):
            with self.subTest(field=field):
                values = self.inputs()
                values[4][field][key] = True
                self.assertIsNone(self.assess(values)[0])
        values = self.inputs()
        values[3]["tradable"] = False
        self.assertIsNone(self.assess(values)[0])

    def test_missing_or_stale_custody_proof_fails_closed(self):
        values = self.inputs()
        values[1]["collectionProtection"]["revision"] = 3
        self.assertIsNone(self.assess(values)[0])
        values = self.inputs()
        values[0]["native"]["crew"] = None
        self.assertIsNone(self.assess(values)[0])
        values = self.inputs()
        values[0]["native"]["fullSync"] = False
        self.assertIsNone(self.assess(values)[0])


if __name__ == "__main__":
    unittest.main()
