"""Shop preferences import atomically, without activity or spending authority."""
import json
import unittest

import test_profile_management as fixture
from test_redundant_store import plain


class ShopLegacyTests(unittest.TestCase):
    def setUp(self):
        self.f = fixture.ProfileManagementTests()
        self.f.setUp()
        self.app = self.f.app

    def tearDown(self):
        self.f.tearDown()

    def preview(self, **choices):
        return self.app.PreviewImport(self.app, json.dumps({"version": 17, **choices}))

    def test_saved_simple_modes_preserve_selection_and_cash_scopes_without_enabling(self):
        for all_items in (False, True):
            accepted, reason = self.preview(shopBuyAll=all_items,
                shopSelected={"w_z": True, "crate_a": True, "w_unused": False}, shopUseBank=True)
            self.assertTrue(accepted, reason)
            values = plain(self.app.staged["values"])
            self.assertEqual(values["shop.custom.selection"], "All cash items" if all_items else "Selected cash items")
            self.assertEqual(values["shop.custom.selectedIds"], "crate_a,w_z")
            self.assertTrue(values["withdraw.custom.allowShop"])
            self.assertFalse(values["withdraw.enabled"])
            self.assertFalse(values["shop.enabled"])
            self.assertEqual(len(self.f.base.storage.data), 0)

    def test_old_category_group_keeps_limits_and_override_rarity_names_exact(self):
        accepted, reason = self.preview(shopKind="Cosmetics", shopRule="Buy cash items under price",
            shopCashMax=123.5, shopOwnedCap=2, shopMinRarity=4.5, shopCosmetics=True,
            shopCrates=False, shopRarityOverride=True, shopOverrideRarities={"Secret": True, "Mythic": True, "Rare": False})
        self.assertTrue(accepted, reason)
        values = plain(self.app.staged["values"])
        for field, expected in {"selection": "Category rules", "kind": "Cosmetics",
            "priceRule": "Buy cash items under price", "cashMax": 123.5, "ownedCap": 2,
            "minRarity": 4.5, "allowCosmetics": True, "allowCrates": False,
            "rarityOverride": True, "overrideRarities": "6,7"}.items():
            self.assertEqual(values["shop.custom." + field], expected)
        self.assertFalse(values["withdraw.custom.allowShop"])

    def test_invalid_shop_group_never_partially_maps_or_applies(self):
        for change in ({"shopBuyAll": "true"}, {"shopSelected": {"w_z": "true"}},
                {"shopOverrideRarities": {"Imaginary": True}}, {"shopKind": "unknown"},
                {"shopUseBank": 1}, {"shopCashMax": -1}):
            before = plain(self.app.model.Snapshot(self.app.model))
            accepted, reason = self.preview(shopBuyAll=False, **({"shopSelected": {"w_z": True}} | change)) if "shopBuyAll" not in change else self.preview(**change)
            self.assertFalse(accepted, reason)
            self.assertIsNone(self.app.staged)
            mapped = plain(self.app.importReview.mapped)
            self.assertFalse(any(key.startswith("shop.custom.") or key == "withdraw.custom.allowShop" for key in mapped))
            self.assertEqual(plain(self.app.model.Snapshot(self.app.model)), before)

    def test_empty_selected_mode_stays_empty_and_nonempty_selection_needs_explicit_mode(self):
        accepted, reason = self.preview(shopBuyAll=False, shopSelected={})
        self.assertTrue(accepted, reason)
        self.assertEqual(self.app.staged["values"]["shop.custom.selection"], "Selected cash items")
        self.assertEqual(self.app.staged["values"]["shop.custom.selectedIds"], "")
        self.assertFalse(self.preview(shopSelected={"w_z": True})[0])

    def test_gold_and_shared_budget_history_are_still_unresolved(self):
        for field, value in (("shopGold", True), ("shopGoldMax", 2),
                             ("sessionBudget", 9999), ("perAction", 9999)):
            accepted, reason = self.preview(shopBuyAll=True, **{field: value})
            self.assertFalse(accepted)
            self.assertIn(field, reason)
            self.assertIsNone(self.app.staged)


if __name__ == "__main__":
    unittest.main()
