"""Bounded future native reads under a fake monotonic clock."""
import unittest

from engine_harness import Harness, lua_table


class ReadBudgetTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.module = self.h.load("src/engine/ReadBudget.luau")
        self.budget = self.module.new(self.h.clock,
            lua_table(self.h.lua, [
                {"id": "sync", "interval": 1},
                {"id": "catalog", "interval": 10},
                {"id": "membership", "interval": 30}]), 3, 60)

    def test_one_in_flight_and_fair_initial_order(self):
        first, token = self.budget.Due(self.budget)
        self.assertEqual(first, "sync")
        self.assertIsNone(self.budget.Due(self.budget)[0])
        self.assertTrue(self.budget.Finish(self.budget, token, True))
        self.assertEqual(self.budget.Due(self.budget)[0], "catalog")

    def test_success_obeys_each_interval(self):
        for expected in ("sync", "catalog", "membership"):
            name, token = self.budget.Due(self.budget)
            self.assertEqual(name, expected)
            self.assertTrue(self.budget.Finish(self.budget, token, True))
        self.assertIsNone(self.budget.Due(self.budget)[0])
        self.h.at(1)
        self.assertEqual(self.budget.Due(self.budget)[0], "sync")

    def test_optional_source_filter_skips_unrequested_reads(self):
        allowed = lua_table(self.h.lua, {"membership": True})
        name, token = self.budget.Due(self.budget, allowed)
        self.assertEqual(name, "membership")
        self.assertTrue(self.budget.Finish(self.budget, token, True))
        self.assertIsNone(self.budget.Due(self.budget, allowed)[0])
        self.assertEqual(self.budget.Due(self.budget)[0], "sync")

    def test_timeout_fences_late_completion_and_backs_off(self):
        _, old = self.budget.Due(self.budget)
        self.h.at(3)
        name, fresh = self.budget.Due(self.budget)
        self.assertEqual(name, "catalog")
        self.assertFalse(self.budget.Finish(self.budget, old, True))
        self.assertTrue(self.budget.Finish(self.budget, fresh, True))
        self.h.at(4)
        self.assertEqual(self.budget.Due(self.budget)[0], "membership")
        self.h.at(6)
        self.assertFalse(self.budget.Finish(self.budget, fresh, True))

    def test_ownership_expires_before_delayed_read_starts(self):
        _, token = self.budget.Due(self.budget)
        self.assertTrue(self.budget.Owns(self.budget, token))
        self.h.at(3)
        self.assertFalse(self.budget.Owns(self.budget, token))

    def test_failure_backoff_is_per_source_and_recovers(self):
        name, token = self.budget.Due(self.budget)
        self.assertEqual(name, "sync")
        self.assertTrue(self.budget.Finish(self.budget, token, False))
        name, token = self.budget.Due(self.budget)
        self.assertEqual(name, "catalog")
        self.assertTrue(self.budget.Finish(self.budget, token, True))
        name, token = self.budget.Due(self.budget)
        self.assertEqual(name, "membership")
        self.assertTrue(self.budget.Finish(self.budget, token, True))
        self.h.at(2)
        state = self.budget.Status(self.budget)
        self.assertEqual(state["sync"]["failures"], 1)
        self.assertEqual(state["sync"]["nextAt"], 2)
        name, token = self.budget.Due(self.budget)
        self.assertEqual(name, "sync")
        self.assertTrue(self.budget.Finish(self.budget, token, True))
        state = self.budget.Status(self.budget)
        self.assertEqual(state["sync"]["failures"], 0)
        self.assertEqual(state["sync"]["nextAt"], 3)

    def test_rejects_bad_source_config(self):
        with self.assertRaises(Exception):
            self.module.new(self.h.clock,
                lua_table(self.h.lua, [{"id": "sync", "interval": 0}]),
                3, 60)

    def test_close_fences_active_token_and_future_reads(self):
        name, token = self.budget.Due(self.budget)
        self.assertEqual(name, "sync")
        self.budget.Close(self.budget)
        self.assertFalse(self.budget.Finish(self.budget, token, True))
        self.h.at(100)
        self.assertIsNone(self.budget.Due(self.budget)[0])


if __name__ == "__main__":
    unittest.main()
