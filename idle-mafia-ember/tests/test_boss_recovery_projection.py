"""Every Boss lane keeps its source, usage and capture dependencies."""
import unittest

from recovery_projection_harness import assert_projection
import test_bosses
import test_boss_shop_buy
import test_global_boss_attack
import test_global_boss_claim
import test_family_takedown_attacks
import test_family_takedown_claims


class BossRecoveryProjectionTests(unittest.TestCase):
    def test_all_boss_lanes_reproduce_capture_after_projection(self):
        cases = (("bosses",test_bosses.BossesTests,"propose"),
            ("bossShop",test_boss_shop_buy.BossShopBuyTests,"propose"),
            ("globalBossAttack",test_global_boss_attack.GlobalBossAttackTests,"propose"),
            ("globalBossClaim",test_global_boss_claim.GlobalBossClaimTests,"proposal"),
            ("familyBossAttacks",test_family_takedown_attacks.FamilyTakedownAttackTests,"propose"),
            ("familyBossClaims",test_family_takedown_claims.FamilyTakedownClaimTests,"propose"))
        for feature,fixture,method in cases:
            with self.subTest(feature=feature):
                helper = fixture(methodName="runTest")
                helper.setUp()
                before = helper.raw()
                proposal,reason = getattr(helper,method)(before)
                self.assertIsNone(reason)
                self.assertEqual(proposal.feature,feature)
                assert_projection(self,helper.h,helper.evidence,proposal,before)


if __name__ == "__main__":
    unittest.main()
