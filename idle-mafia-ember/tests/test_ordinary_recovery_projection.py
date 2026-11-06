"""Ordinary capture contracts survive full-account snapshot projection."""
import unittest

from engine_harness import lua_table
from recovery_projection_harness import assert_projection
import test_contract_entry_claims
import test_contract_bonus_claims
import test_earned_trophies
import test_free_briefcase_picks
import test_skills
import test_purpose_withdrawals
import test_safehouse_upgrades
import test_properties
import test_shop_cash


class OrdinaryRecoveryProjectionTests(unittest.TestCase):
    def test_ordinary_planners_reproduce_capture_after_projection(self):
        cases = (("contracts",test_contract_entry_claims.ContractEntryClaimTests,"proposal"),
            ("bonuses",test_contract_bonus_claims.ContractBonusClaimTests,"proposal"),
            ("trophies",test_earned_trophies.EarnedTrophyTests,"propose"),
            ("briefcases",test_free_briefcase_picks.FreeBriefcasePickTests,"proposal"),
            ("skills",test_skills.SkillsTests,"propose"),
            ("withdraw",test_purpose_withdrawals.PurposeWithdrawTests,"proposal"),
            ("safehouse",test_safehouse_upgrades.SafehouseUpgradeTests,"proposal"),
            ("properties",test_properties.PropertiesTests,None),
            ("shop",test_shop_cash.ShopCashTests,None))
        for feature,fixture,method in cases:
            with self.subTest(feature=feature):
                helper = fixture(methodName="runTest")
                helper.setUp()
                before = helper.raw()
                if method:
                    proposal,reason = getattr(helper,method)(before)
                else:
                    view,reason = helper.view(before)
                    self.assertIsNone(reason)
                    proposal,reason = helper.planner.propose(view,helper.settings(),
                        lua_table(helper.h.lua,{"cash":0,"uncertainCash":0}))
                self.assertIsNone(reason)
                self.assertEqual(proposal.feature,feature)
                assert_projection(self,helper.h,helper.evidence,proposal,before)


if __name__ == "__main__":
    unittest.main()
