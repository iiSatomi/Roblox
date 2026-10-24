"""Rewards facts come from a current source, not the incoming snapshot."""
from datetime import datetime, timezone
import unittest

from engine_harness import Harness, lua_table


NOW = int(datetime(2026, 10, 24, 12, tzinfo=timezone.utc).timestamp())


class RewardsProofProducerTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.producer = self.h.load(
            "src/engine/RewardsProofProducer.luau")
        self.raw = self.h.snapshot(captured_at=40,
            native={"fullSync": True, "serverNow": NOW},
            groupConfig={"id": 674050067})
        self.context = lua_table(self.h.lua, {**self.h.session,
            "revision": 1, "capturedAt": 40})
        self.source = self.h.lua.execute("""return {
            release = 'release-a',
            IsWeekend = function() return true end,
            Membership = function() return true, 35 end,
        }""")

    def derive(self):
        return self.producer.derive(self.raw, self.context,
                                    self.source)

    def test_same_day_weekend_and_recent_member(self):
        proofs, reason = self.derive()
        self.assertIsNone(reason)
        self.assertTrue(proofs["weekendBuff"]["active"])
        self.assertEqual(proofs["weekendBuff"]["day"], 2026297)
        self.assertTrue(proofs["groupMembership"]["isMember"])
        self.assertEqual(proofs["groupMembership"]["account"], "user-a")

    def test_stale_membership_and_changed_sync_fail_closed(self):
        self.source["Membership"] = self.h.lua.eval(
            "function() return true, 9 end")
        proofs, _ = self.derive()
        self.assertIsNone(proofs["groupMembership"])
        self.assertIsNotNone(proofs["weekendBuff"])
        self.raw["revision"] = 2
        self.assertIsNone(self.derive()[0])


if __name__ == "__main__":
    unittest.main()
