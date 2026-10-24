"""Saved weekend rule and cached Group membership stay read-only."""
import unittest

from engine_harness import Harness, lua_table


class NativeRewardsSourceTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.module = self.h.load(
            "src/tabs/rewards/NativeRewardsSource.luau")
        self.rule = self.h.lua.execute("""return {
            isWeekend = function(now) return now >= 172800 end,
        }""")
        self.h.at(100.5)
        self.lookup = self.h.lua.eval("""function(groupId)
            return groupId == 674050067
        end""")
        self.source, self.reason = self.module.new(
            self.rule, self.lookup, self.h.clock,
            "release-a", "user-a", 674050067)

    def test_weekend_and_cached_membership_feed_producer(self):
        self.assertIsNone(self.reason)
        self.assertIs(self.source.IsWeekend(self.source, 100), False)
        self.assertTrue(self.source.IsWeekend(self.source, 172800))
        self.assertIsNone(self.source.Membership(self.source,
            "user-a", 674050067))
        self.assertTrue(self.source.Refresh(self.source,
            "user-a", 674050067))
        member, checked = self.source.Membership(self.source,
            "user-a", 674050067)
        self.assertTrue(member)
        self.assertEqual(checked, 100.5)
        raw = self.h.snapshot(captured_at=100.5,
            native={"fullSync": True, "serverNow": 172800},
            groupConfig={"id": 674050067})
        context = lua_table(self.h.lua, {**self.h.session,
            "revision": 1, "capturedAt": 100.5})
        producer = self.h.load(
            "src/engine/RewardsProofProducer.luau")
        proof, reason = producer.derive(raw, context, self.source)
        self.assertIsNone(reason)
        self.assertTrue(proof["weekendBuff"]["active"])
        self.assertTrue(proof["groupMembership"]["isMember"])
        self.source.Close(self.source)
        self.assertIsNone(self.source.Membership(self.source,
            "user-a", 674050067))

    def test_wrong_identity_and_failed_lookup_do_not_cache(self):
        self.assertFalse(self.source.Refresh(self.source,
            "other", 674050067))
        self.assertIsNone(self.source.Membership(self.source,
            "other", 674050067))
        self.source["lookup"] = self.h.lua.eval(
            "function() error('unavailable') end")
        self.assertFalse(self.source.Refresh(self.source,
            "user-a", 674050067))
        self.assertIsNone(self.source.Membership(self.source,
            "user-a", 674050067))


if __name__ == "__main__":
    unittest.main()
