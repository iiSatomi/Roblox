"""All Heist lanes retain their actual capture contracts in bounded recovery data."""
import unittest

from engine_harness import lua_table
import test_heist_start
import test_heist_collection
import test_favor_help
import test_sabotage


class HeistRecoveryProjectionTests(unittest.TestCase):
    def test_real_lane_baselines_recapture_after_unrelated_catalogs_are_omitted(self):
        # Reuse the existing real planner/evidence fixtures rather than substituting
        # a test-only capture function for these security-sensitive contracts.
        cases = (("heists",test_heist_start.HeistStartTests),
            ("heistCollect",test_heist_collection.HeistCollectionTests),
            ("favors",test_favor_help.FavorHelpTests),
            ("sabotage",test_sabotage.SabotageTests))
        for feature,fixture in cases:
            with self.subTest(feature=feature):
                helper = fixture(methodName="runTest")
                helper.setUp()
                h = helper.h
                if feature=="heistCollect":
                    proposal,before = helper.plan()
                    evidence = helper.collection
                else:
                    before = helper.raw()
                    evidence = helper.evidence
                    if feature=="sabotage":
                        proposal,reason = helper.proposal(before)
                    else:
                        view,reason = helper.view(before)
                        self.assertIsNone(reason)
                        reservations = helper.reserves() if feature=="heists" else helper.reserve()
                        proposal,reason = helper.planner.propose(view,helper.settings(),reservations)
                    self.assertIsNone(reason)
                baseline,reason = evidence.capture(proposal,before)
                self.assertIsNone(reason)
                before.native.inventory = lua_table(h.lua,{f"item_{i}_"+"x"*24:i for i in range(1500)})
                before.data = before.native
                before.stationCatalog = lua_table(h.lua,[
                    {"id":f"district_{i}","holder":"x"*100,"capacity":5} for i in range(1500)])
                pending = h.load("src/storage/PendingAction.luau")
                encoded,reason = pending.Capture(proposal,before,baseline)
                self.assertIsNone(reason)
                decoded = pending.Decode(encoded)
                self.assertIsNone(decoded.before.stationCatalog)
                self.assertIsNone(decoded.before.data)
                self.assertEqual(decoded.before.native.inventory['item_1_'+"x"*24],1)
                for key in ("catalogKey","heistCatalog","heistBoardProof","favorUsageProof",
                        "sabotageUsageProof","localUserIdProof","heistControllerProof"):
                    if before[key] is not None:
                        self.assertIsNotNone(decoded.before[key],key)
                recaptured,reason = evidence.capture(decoded.proposal,decoded.before)
                self.assertIsNone(reason)
                recoded,reason = pending.Capture(decoded.proposal,decoded.before,recaptured)
                self.assertIsNone(reason)
                self.assertTrue(pending.Same(encoded,recoded))


if __name__ == "__main__":
    unittest.main()
