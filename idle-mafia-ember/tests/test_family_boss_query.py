"""A fresh owned Family Takedown state reply is distinct from an attack result."""
import unittest

import test_family_takedown_state as fixture
from engine_harness import lua_table


class FamilyBossQueryTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture.FamilyTakedownStateTests()
        self.fixture.setUp()
        self.h = self.fixture.h
        self.module = self.h.load("src/tabs/combat/FamilyBossQuery.luau")
        self.query = self.module.new(self.fixture.reader, "a" * 64, "release-a")

    def raw(self, revision=1):
        raw = self.fixture.snapshot()
        raw.revision = revision
        raw.native.family = lua_table(self.h.lua, {"id": 9})
        raw.familyTakedownProof = None
        return raw

    def reply(self):
        state = self.fixture.snapshot().familyTakedownProof.state
        state.ok, state.serverNow = True, 1050
        state.claimedStages = lua_table(self.h.lua, [1])
        return state

    def test_exact_read_only_call_and_bounded_claim_state(self):
        raw = self.raw()
        request, reason = self.query.Prepare(self.query, raw)
        self.assertIsNone(reason)
        self.assertEqual((request.remote, request.arity, request.args[1], request.args[2]),
            ("FamilyBossAction", 2, "state", None))
        reply = self.reply()
        staged, reason = self.query.Accept(self.query, raw, request, reply)
        self.assertIsNone(reason)
        self.assertEqual(staged.familyTakedownProof.state.week, 100)
        self.assertEqual(staged.familyTakedownProof.state.claimedStages[1], 1)
        reply.claims[1].week = 77
        self.assertEqual(staged.familyTakedownProof.state.claims[1].week, 99)
        raw.serverNow = raw.native.serverNow
        view, reason = self.fixture.reader.read(staged, raw)
        self.assertIsNone(reason)
        self.assertEqual(view.free, 1)
        self.assertEqual(len(self.h.transport.sent), 0)

    def test_reply_needs_same_full_sync_and_family(self):
        for field, value in (("revision", 2), ("account", "other")):
            raw = self.raw()
            request, _ = self.query.Prepare(self.query, raw)
            raw[field] = value
            self.assertIsNone(self.query.Accept(self.query, raw, request, self.reply())[0])
        raw = self.raw()
        request, _ = self.query.Prepare(self.query, raw)
        raw.native.family.id = 10
        self.assertIsNone(self.query.Accept(self.query, raw, request, self.reply())[0])
        raw = self.raw()
        request, _ = self.query.Prepare(self.query, raw)
        reply = self.reply()
        reply.famId = 10
        self.assertIsNone(self.query.Accept(self.query, raw, request, reply)[0])

    def test_old_request_pending_rate_limited_and_repeat_accept_cannot_stage(self):
        raw = self.raw()
        old, _ = self.query.Prepare(self.query, raw)
        current, _ = self.query.Prepare(self.query, raw)
        self.assertIsNone(self.query.Accept(self.query, raw, old, self.reply())[0])
        for key, value in (("pending", True), ("code", "rate_limited")):
            reply = self.reply()
            reply[key] = value
            self.assertIsNone(self.query.Accept(self.query, raw, current, reply)[0])
        self.assertIsNotNone(self.query.Accept(self.query, raw, current, self.reply())[0])
        self.assertIsNone(self.query.Accept(self.query, raw, current, self.reply())[0])

    def test_sparse_duplicate_oversized_claims_and_untrusted_clock_are_refused(self):
        for change in ("sparse", "duplicate", "oversized", "clock"):
            raw = self.raw()
            request, _ = self.query.Prepare(self.query, raw)
            reply = self.reply()
            if change == "sparse": reply.claims[3], reply.claims[1] = reply.claims[1], None
            elif change == "duplicate": reply.claims[2] = reply.claims[1]
            elif change == "oversized": reply.claims = lua_table(self.h.lua, [{}] * 33)
            else: reply.serverNow = 1060
            self.assertIsNone(self.query.Accept(self.query, raw, request, reply)[0])

    def test_string_identity_is_copied_without_coercion(self):
        raw = self.raw()
        raw.native.family.id = "family-native-abc"
        request, reason = self.query.Prepare(self.query, raw)
        self.assertIsNone(reason)
        reply = self.reply()
        reply.famId = "family-native-abc"
        staged, reason = self.query.Accept(self.query, raw, request, reply)
        self.assertIsNone(reason)
        self.assertEqual(staged.familyTakedownProof.state.famId, "family-native-abc")
        raw = self.raw()
        raw.native.family.id = "9"
        request, reason = self.query.Prepare(self.query, raw)
        self.assertIsNone(reason)
        self.assertIsNone(self.query.Accept(self.query, raw, request, self.reply())[0])

    def test_invalid_family_ids_never_prepare_a_read(self):
        for value in ("", "x" * 121, "family\nother", "family\x00other", 0, -1, 1.5, True, float("inf")):
            with self.subTest(value=repr(value)):
                raw = self.raw()
                raw.native.family.id = value
                self.assertIsNone(self.query.Prepare(self.query, raw)[0])

    def test_close_and_invalid_baseline_cannot_create_requests(self):
        raw = self.raw()
        raw.native.fullSync = False
        self.assertIsNone(self.query.Prepare(self.query, raw)[0])
        self.query.Close(self.query)
        self.assertIsNone(self.query.Prepare(self.query, self.raw())[0])


if __name__ == "__main__":
    unittest.main()
