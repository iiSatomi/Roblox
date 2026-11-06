"""One bounded logical owner is reserved before any deferred work runs."""
import unittest

from engine_harness import Harness


class RequestLaneTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.lane = self.h.load("src/engine/RequestLane.luau").new(self.h.clock)

    def acquire(self, kind="mutation", key="jobs:one", deadline=45):
        return self.lane.TryAcquire(self.lane, kind, key, deadline)

    def test_queued_work_has_exclusive_opaque_owner(self):
        token, reason = self.acquire("read", "family:state", 5)
        self.assertIsNone(reason)
        self.assertTrue(self.lane.Owns(self.lane, token))
        self.assertIsNone(self.acquire()[0])
        self.assertIsNone(self.acquire("membership", "group:one", 5)[0])
        self.assertTrue(self.lane.Release(self.lane, token, "returned"))
        self.assertIsNotNone(self.acquire()[0])

    def test_exact_deadline_releases_only_scheduling_ownership(self):
        token, _ = self.acquire()
        self.h.at(44.999)
        self.assertTrue(self.lane.Owns(self.lane, token))
        self.h.at(45)
        self.assertFalse(self.lane.Owns(self.lane, token))
        next_token, reason = self.acquire("read", "territory:map", 50)
        self.assertIsNone(reason)
        self.assertFalse(self.lane.Release(self.lane, token, "late_return"))
        self.assertTrue(self.lane.Owns(self.lane, next_token))

    def test_forged_token_and_status_mutation_cannot_change_owner(self):
        token, _ = self.acquire()
        self.assertFalse(self.lane.Release(self.lane, self.h.lua.table(), "returned"))
        status = self.lane.Status(self.lane)
        status.active.deadline = 0
        self.assertTrue(self.lane.Owns(self.lane, token))

    def test_bad_kind_key_deadline_and_close_fail_closed(self):
        for args in (("unknown", "a", 5), ("read", "", 5), ("read", "a", 0),
                ("read", "a", 46), ("read", "a", float('nan'))):
            self.assertIsNone(self.acquire(*args)[0])
        token, _ = self.acquire()
        self.lane.Close(self.lane)
        self.assertFalse(self.lane.Owns(self.lane, token))
        self.assertIsNone(self.acquire()[0])

    def test_read_expiry_allows_another_source_and_stale_release_is_ignored(self):
        token, _ = self.acquire("read", "heists:board", 5)
        self.h.at(5)
        replacement, _ = self.acquire("read", "market:browse", 10)
        self.assertFalse(self.lane.Owns(self.lane, token))
        self.assertTrue(self.lane.Owns(self.lane, replacement))
        self.assertFalse(self.lane.Release(self.lane, token, "returned"))


if __name__ == "__main__":
    unittest.main()
