"""Exact deadline, cooldown and late result fencing."""
import unittest

from engine_harness import Harness, ROOT, lua_table


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        for name in ("Broker.luau", "Journal.luau"):
            self.assertTrue((ROOT / "src/engine" / name).is_file(), f"{name} missing")
        self.h = Harness()

    def send_first(self):
        h = self.h
        h.broker.Offer(h.broker, h.proposal(), h.snapshot())
        h.broker.Tick(h.broker, h.snapshot())
        self.assertEqual(len(h.transport["sent"]), 1)

    def test_skip_only_at_exact_deadline_then_cool_down_feature(self):
        h = self.h
        self.send_first()
        h.at(44.999)
        h.broker.Tick(h.broker, h.snapshot())
        self.assertEqual(h.broker.Status(h.broker)["active"]["phase"], "sent")
        h.at(45.0)
        h.broker.Tick(h.broker, h.snapshot())
        self.assertIsNone(h.broker.Status(h.broker)["active"])
        events = [e["kind"] for e in h.events().values()]
        self.assertEqual(events.count("skipped_unconfirmed"), 1)
        h.broker.Tick(h.broker, h.snapshot())
        self.assertEqual([e["kind"] for e in h.events().values()].count("skipped_unconfirmed"), 1)
        self.assertEqual(h.broker.Offer(h.broker, h.proposal(key="jobs:next"), h.snapshot())[0], "blocked")
        self.assertEqual(h.broker.Offer(h.broker, h.proposal(feature="operations", key="ops:ready"), h.snapshot())[0], "admitted")
        h.broker.Tick(h.broker, h.snapshot())
        self.assertEqual(len(h.transport["sent"]), 2)

    def test_late_callback_cannot_release_new_owner_or_count_success(self):
        h = self.h
        self.send_first()
        first_callback = h.transport["callbacks"][1]
        h.at(45)
        h.broker.Tick(h.broker, h.snapshot())
        h.broker.Offer(h.broker, h.proposal(feature="operations", key="ops:ready"), h.snapshot())
        h.broker.Tick(h.broker, h.snapshot())
        first_callback(lua_table(h.lua, {"ok": True}))
        self.assertEqual(h.broker.Status(h.broker)["active"]["actionKey"], "ops:ready")
        kinds = [e["kind"] for e in h.events().values()]
        self.assertIn("late_return", kinds)
        self.assertNotIn("confirmed", kinds)

    def test_callback_after_deadline_skips_even_before_next_planner_tick(self):
        h = self.h
        self.send_first()
        callback = h.transport["callbacks"][1]
        h.at(46)
        callback(lua_table(h.lua, {"ok": True}))
        self.assertIsNone(h.broker.Status(h.broker)["active"])
        kinds = [e["kind"] for e in h.events().values()]
        self.assertIn("skipped_unconfirmed", kinds)
        self.assertIn("late_return", kinds)
        self.assertNotIn("confirmed", kinds)

    def test_duplicate_action_key_is_not_replayed_after_skip(self):
        h = self.h
        self.send_first()
        h.at(91)
        h.broker.Tick(h.broker, h.snapshot())
        self.assertEqual(h.broker.Offer(h.broker, h.proposal(), h.snapshot())[0], "blocked")


if __name__ == "__main__":
    unittest.main()
