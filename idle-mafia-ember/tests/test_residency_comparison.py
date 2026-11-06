"""Replacement decisions compare current native resident contribution and rent."""
import unittest

import test_conditional_feature_contracts as conditional


class ResidencyComparisonTests(unittest.TestCase):
    def setUp(self):
        self.fixture = conditional.ConditionalContracts()
        self.fixture.setUp()
        self.h = self.fixture.h
        self.raw = self.fixture.residency_raw()
        self.module = self.h.load("src/tabs/territory/Residency.luau")
        self.raw.native.derived.territoryBonuses = self.fixture.table({"landlord": 0.385})
        self.raw.native.derived.residency = self.fixture.table({"d": "previous", "kind": "landlord",
            "share": 0.065, "rent": 0, "active": True})
        self.raw.residencyView.elsewhere = "Previous district"
        self.raw.residencyView.share, self.raw.residencyView.rent = 0.075, 0
        self.settings = self.fixture.table({"enabled": True, "districtId": "d1", "selectedKind": "landlord",
            "maxRentPct": 10, "minSharePct": 0, "allowReplace": True, "allowRequests": False, "maxAttempts": 1})

    def preview(self):
        preview, reason = self.module.preview(self.raw, self.raw, self.settings)
        self.assertIsNone(reason)
        return preview

    def test_current_free_six_point_five_percent_dominates_four_percent_with_rent(self):
        self.raw.residencyView.share, self.raw.residencyView.rent = 0.04, 1
        preview = self.preview()
        self.assertFalse(preview.eligible)
        self.assertTrue(preview.comparisonVerified)
        self.assertEqual((preview.previousSharePct, preview.previousRentPct), (6.5, 0))
        self.assertFalse(preview.effectiveGainVerified)

    def test_same_kind_higher_share_without_more_rent_is_verified_below_cap(self):
        preview = self.preview()
        self.assertTrue(preview.eligible)
        self.assertTrue(preview.effectiveGainVerified)
        self.assertEqual(preview.currentEffectivePct, 38.5)

    def test_cross_kind_and_unknown_current_share_or_total_are_unverified(self):
        for change in ("kind", "share", "total"):
            with self.subTest(change=change):
                self.setUp()
                if change == "kind":
                    self.raw.native.derived.residency.kind = "enforcers"
                elif change == "share":
                    self.raw.native.derived.residency.share = None
                else:
                    self.raw.native.derived.territoryBonuses = None
                preview = self.preview()
                self.assertFalse(preview.eligible)
                self.assertFalse(preview.comparisonVerified)

    def test_capped_bonus_cannot_justify_another_move_but_lower_rent_can(self):
        self.settings.selectedKind = "shopDiscount"
        self.raw.residencyView.kind = "shopDiscount"
        self.raw.native.derived.territoryBonuses = self.fixture.table({"shopDiscount": 0.25})
        self.raw.native.derived.residency.kind = "shopDiscount"
        self.raw.native.derived.residency.share = 0.025
        self.raw.residencyView.share = 0.05
        self.assertFalse(self.preview().eligible)
        self.raw.native.derived.residency.rent = 2
        self.raw.residencyView.rent = 1
        preview = self.preview()
        self.assertTrue(preview.eligible)
        self.assertTrue(preview.rentImprovementVerified)
        self.assertFalse(preview.effectiveGainVerified)

    def test_higher_share_with_higher_rent_requires_unavailable_tradeoff_valuation(self):
        self.raw.residencyView.rent = 1
        preview = self.preview()
        self.assertFalse(preview.eligible)
        self.assertFalse(preview.comparisonVerified)

    def test_prepared_move_cannot_use_a_changed_effective_comparison(self):
        view, _ = self.module.read(self.raw, self.raw)
        proposal, reason = self.module.propose(view, self.settings)
        self.assertIsNone(reason)
        self.assertIsNotNone(self.module.capture(proposal, self.raw)[0])
        self.raw.native.derived.territoryBonuses.landlord = 0.38
        self.assertIsNone(self.module.capture(proposal, self.raw)[0])

    def test_lease_confirmation_requires_selected_native_bonus_and_quoted_share(self):
        module, before, proposal, baseline, after = self.fixture.residency_attempt()
        after.native.derived.residency.kind = "enforcers"
        self.assertEqual(module.evaluate(proposal, before, after, self.fixture.table({"ok": True}), baseline), "pending")
        after.native.derived.residency.kind = "landlord"
        after.native.derived.residency.share = 0.001
        self.assertEqual(module.evaluate(proposal, before, after, self.fixture.table({"ok": True}), baseline), "pending")


if __name__ == "__main__":
    unittest.main()
