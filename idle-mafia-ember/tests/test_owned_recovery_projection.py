"""Crew, owned inventory and Prestige retain their real capture contracts."""
import unittest

from recovery_projection_harness import assert_projection
import test_crew_auto_equip
import test_crew_gear
import test_crew_sort
import test_crew_heal
import test_crew_training
import test_crew_heal_items
import test_inventory_cosmetics
import test_inventory_chests
import test_inventory_restoratives
import test_collection_donate
import test_prestige_reset


class OwnedRecoveryProjectionTests(unittest.TestCase):
    def test_owned_action_planners_reproduce_capture_after_projection(self):
        cases = (("crew",test_crew_auto_equip.CrewAutoEquipTests),
            ("crewGear",test_crew_gear.CrewGearTests),
            ("crewSort",test_crew_sort.CrewSortTests),
            ("crewHeal",test_crew_heal.CrewHealTests),
            ("crewTrain",test_crew_training.CrewTrainingTests),
            ("crewHealItems",test_crew_heal_items.CrewHealItemsTests),
            ("cosmetics",test_inventory_cosmetics.InventoryCosmeticTests),
            ("chests",test_inventory_chests.InventoryChestTests),
            ("restoratives",test_inventory_restoratives.InventoryRestorativesTests),
            ("collectionDonate",test_collection_donate.CollectionDonateTests),
            ("prestige",test_prestige_reset.PrestigeResetTests))
        for feature,fixture in cases:
            with self.subTest(feature=feature):
                helper = fixture(methodName="runTest")
                helper.setUp()
                planned = helper.plan()
                if feature=="prestige":
                    proposal,before = planned
                    evidence = helper.reset
                else:
                    proposal = planned[0] if isinstance(planned,tuple) else planned
                    before = helper.raw if feature=="crewTrain" else helper.before
                    evidence = helper.feature
                self.assertEqual(proposal.feature,feature)
                assert_projection(self,helper.h,evidence,proposal,before)


if __name__ == "__main__":
    unittest.main()
