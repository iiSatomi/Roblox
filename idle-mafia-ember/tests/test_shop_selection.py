"""Source-ordered cash Shop rules preserve both legacy selection regimes."""
import unittest

from engine_harness import Harness, lua_table


class ShopSelectionTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.context = self.h.load("src/game/Context.luau").new(self.h.contracts)
        self.reader = self.h.load("src/game/ShopState.luau")
        self.planner = self.h.load("src/features/ShopBuy.luau")
        self.data = {"SHOP": [
            {"item": "w_z", "price": 150, "limit": 3},
            {"item": "bg_a", "price": 200},
            {"item": "crate_a", "price": 80},
            {"item": "w_a", "price": 50, "level": 20},
            {"item": "paid_weapon", "price": 1},
            {"item": "robux_weapon", "price": 1, "robuxPrice": 10},
            {"item": "gold_weapon", "goldPrice": 1},
            {"item": "unknown_item", "price": 1}],
            "ITEMS_BY_ID": {
                "w_z": {"kind": "weapon", "rarity": 1},
                "bg_a": {"kind": "background", "rarity": 7},
                "crate_a": {"kind": "crate", "rarity": 8},
                "w_a": {"kind": "weapon", "rarity": 4},
                "paid_weapon": {"kind": "weapon", "rarity": 9, "paid": True},
                "robux_weapon": {"kind": "weapon", "rarity": 9},
                "gold_weapon": {"kind": "weapon", "rarity": 9},
                "unknown_item": {"kind": "mystery", "rarity": 9}}}
        self.catalog = self.h.load("src/tabs/shop/NativeShopCatalog.luau").new(
            lua_table(self.h.lua, self.data), "a" * 64, "release-a")

    def raw(self):
        raw = self.h.snapshot(native={"fullSync": True, "level": 10, "cash": 1000,
            "serverNow": 1220, "inventory": {}, "inventoryBound": {},
            "collection": {}, "collectionBound": {}, "shopBought": {},
            "shopRotation": {"slot": 4, "bought": {}}, "autoBuyRules": {"on": False}},
            shopQuoteProof={**self.h.session, "revision": 1, "capturedAt": 0,
                "catalogKey": "a" * 64, "slot": 4,
                "stock": {row["item"]: True for row in self.data["SHOP"]},
                "quotes": {row["item"]: row.get("price", 1) for row in self.data["SHOP"]}})
        return self.catalog.Enrich(self.catalog, raw)[0]

    def propose(self, raw=None, **changes):
        raw = raw if raw is not None else self.raw()
        context = self.context.Read(self.context, raw, lua_table(self.h.lua, self.h.session), 0, 2)[0]
        view, why = self.reader.read(raw, context)
        self.assertIsNone(why)
        settings = {"enabled": True, "itemId": "w_z", "selection": "All cash items",
            "selectedIds": "", "kind": "All allowed", "minRarity": 1,
            "ownedCap": 0, "allowCosmetics": False, "allowCrates": False,
            "priceRule": "Buy all allowed", "cashMax": 100,
            "rarityOverride": False, "overrideRarities": "7,8",
            "cashReserve": 100, "purchaseCap": 1000, **changes}
        return self.planner.propose(view, lua_table(self.h.lua, settings), self.h.lua.table())

    def test_native_order_is_retained_and_paid_robux_gold_unsupported_kinds_excluded(self):
        raw = self.raw()
        self.assertEqual([raw.shopCatalog.order[i] for i in range(1, 5)],
                         ["w_z", "bg_a", "crate_a", "w_a"])
        for item in ("paid_weapon", "robux_weapon", "gold_weapon", "unknown_item"):
            self.assertIsNone(raw.shopCatalog.offers[item])
        self.assertEqual(self.propose()[0].intent.itemId, "w_z")

    def test_selected_ids_use_native_order_not_csv_order_and_gold_stays_unavailable(self):
        p, reason = self.propose(selection="Selected cash items", selectedIds="crate_a,w_z,gold_weapon")
        self.assertIsNone(reason)
        self.assertEqual(p.intent.itemId, "w_z")
        self.assertIsNone(self.propose(selection="Selected cash items", selectedIds="gold_weapon")[0])

    def test_empty_unknown_or_malformed_selections_refuse_without_default_item(self):
        for value in ("", "removed", "w_z,,crate_a", "w_z,w_z"):
            self.assertIsNone(self.propose(selection="Selected cash items", selectedIds=value)[0], value)

    def test_simple_modes_bypass_category_rarity_and_owned_filters_like_legacy(self):
        raw = self.raw()
        raw.native.inventory.w_z = 20
        p, reason = self.propose(raw, kind="Crates", minRarity=9, ownedCap=1)
        self.assertIsNone(reason)
        self.assertEqual(p.intent.itemId, "w_z")
        raw.native.shopRotation.bought.w_z = True
        self.assertEqual(self.propose(raw)[0].intent.itemId, "bg_a")

    def test_category_modes_require_cosmetic_and_crate_permissions(self):
        self.assertIsNone(self.propose(selection="Category rules", kind="Cosmetics")[0])
        self.assertEqual(self.propose(selection="Category rules", kind="Cosmetics", allowCosmetics=True)[0].intent.itemId, "bg_a")
        self.assertIsNone(self.propose(selection="Category rules", kind="Crates")[0])
        self.assertEqual(self.propose(selection="Category rules", kind="Crates", allowCrates=True)[0].intent.itemId, "crate_a")

    def test_category_owned_cap_counts_all_four_item_origins(self):
        for origin in ("inventory", "inventoryBound", "collection", "collectionBound"):
            raw = self.raw()
            raw.native[origin].w_z = 1
            self.assertIsNone(self.propose(raw, selection="Category rules", ownedCap=1)[0], origin)
        self.assertIsNone(self.propose(selection="Category rules", minRarity=2)[0])

    def test_override_prioritizes_native_order_ignores_selection_and_conditional_price(self):
        p, reason = self.propose(selection="Selected cash items", selectedIds="w_z",
            priceRule="Buy cash items under price", cashMax=1, rarityOverride=True)
        self.assertIsNone(reason)
        self.assertEqual(p.intent.itemId, "bg_a")
        self.assertTrue(p.intent.rarityOverride)
        self.assertEqual(self.propose(rarityOverride=True, purchaseCap=100)[0].intent.itemId, "crate_a")
        self.assertIsNone(self.propose(rarityOverride=True, purchaseCap=50)[0])

    def test_override_keeps_category_owned_cap_and_unconditional_cash_reserve(self):
        raw = self.raw()
        raw.native.collectionBound.bg_a = 1
        self.assertEqual(self.propose(raw, selection="Category rules", ownedCap=1,
            rarityOverride=True)[0].intent.itemId, "crate_a")
        self.assertIsNone(self.propose(rarityOverride=True, cashReserve=950)[0])

    def test_lifetime_bought_rotation_and_level_caps_precede_selection(self):
        raw = self.raw()
        raw.native.shopBought.w_z = 3
        raw.native.shopRotation.bought.bg_a = True
        self.assertEqual(self.propose(raw)[0].intent.itemId, "crate_a")
        raw.native.shopRotation.bought.crate_a = True
        self.assertIsNone(self.propose(raw)[0])

    def test_existing_single_item_mode_and_unconditional_cap_remain_supported(self):
        self.assertEqual(self.propose(selection="Single item", itemId="crate_a")[0].intent.itemId, "crate_a")
        self.assertIsNone(self.propose(selection="Single item", itemId="bg_a", purchaseCap=199)[0])

    def test_native_tab_unlock_is_independent_of_offer_level(self):
        raw = self.raw()
        raw.shopCatalog.unlockLevel = 11
        self.assertIsNone(self.propose(raw)[0])


if __name__ == "__main__":
    unittest.main()
