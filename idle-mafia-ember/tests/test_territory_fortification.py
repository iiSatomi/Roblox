"""Only the saved two-argument fortview call and bounded display facts."""
import unittest

from engine_harness import Harness, ROOT, lua_table


class FortificationQueryTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        path = ROOT / "src/tabs/territory/FortificationQuery.luau"
        self.assertTrue(path.is_file(), "Missing read-only FortificationQuery")
        self.module = self.h.load(path.relative_to(ROOT).as_posix())
        self.query = self.module.new()

    def raw(self, revision=1, family="f1"):
        return self.h.snapshot(revision=revision, captured_at=10, native={
            "fullSync": True, "serverNow": 1700000000, "family": {"id": family}})

    def reply(self):
        return lua_table(self.h.lua, {"ok": True, "fort": {"structures": [
            {"key": "barricade", "lv": 2, "hp": 500, "hpMax": 1000, "rebuilding": True},
            {"key": "guardposts", "lv": 1}, {"key": "clinic", "lv": 0},
            {"key": "apartment", "lv": 5}], "donors": [{"name": "ignored"}],
            "gold": 999, "energy": 999}})

    def test_describes_exact_read_and_returns_only_copied_display_facts(self):
        raw = self.raw()
        request, reason = self.query.Prepare(self.query, "d1", raw)
        self.assertIsNone(reason)
        self.assertEqual((request.remote, request.method, request.arity,
            request.args[1], request.args[2]), ("TerritoryAction", "InvokeServer", 2, "fortview", "d1"))
        reply = self.reply()
        result, reason = self.query.Accept(self.query, request, reply)
        self.assertIsNone(reason)
        self.assertTrue(result.readOnly)
        self.assertEqual((result.districtId, result.familyId, result.count), ("d1", "f1", 4))
        reply.fort.structures[1].lv = 5
        request.header.revision = 99
        self.assertEqual(result.fort.structures[1].lv, 2)
        self.assertEqual(result.header.revision, 1)
        self.assertIsNone(result.fort.gold)
        self.assertIsNone(result.fort.energy)
        self.assertIsNone(result.fort.donors)
        raw.fortificationView = result
        view, reason = self.module.read(raw, raw)
        self.assertIsNone(reason)
        view.fort.structures[1].hp = 0
        self.assertEqual(result.fort.structures[1].hp, 500)
        self.assertEqual(len(self.h.transport.sent), 0)

    def test_stale_generation_close_and_mutated_request_are_refused(self):
        first = self.query.Prepare(self.query, "d1", self.raw())[0]
        second = self.query.Prepare(self.query, "d2", self.raw())[0]
        self.assertIsNone(self.query.Accept(self.query, first, self.reply())[0])
        second.header.revision = 100
        self.assertIsNone(self.query.Accept(self.query, second, self.reply())[0])
        third = self.query.Prepare(self.query, "d1", self.raw())[0]
        self.query.Close(self.query)
        self.assertIsNone(self.query.Accept(self.query, third, self.reply())[0])
        self.assertIsNone(self.query.Prepare(self.query, "d1", self.raw())[0])

    def test_wrong_family_revision_session_and_echoed_district_cannot_attach(self):
        raw = self.raw()
        request = self.query.Prepare(self.query, "d1", raw)[0]
        reply = self.reply()
        reply.fort.districtId = "d2"
        self.assertIsNone(self.query.Accept(self.query, request, reply)[0])
        reply = self.reply()
        reply.familyId = "other"
        self.assertIsNone(self.query.Accept(self.query, request, reply)[0])
        result = self.query.Accept(self.query, request, self.reply())[0]
        for field, value in (("revision", 2), ("session", "restart"), ("release", "new")):
            after = self.raw()
            after[field] = value
            after.fortificationView = result
            self.assertIsNone(self.module.read(after, after)[0])
        after = self.raw(family="other")
        after.fortificationView = result
        self.assertIsNone(self.module.read(after, after)[0])

    def test_malformed_oversized_sparse_duplicate_and_unknown_structures_are_unavailable(self):
        for problem in ("missing", "large", "sparse", "duplicate", "unknown", "level", "hp",
                        "max", "rebuilding", "partial"):
            request = self.query.Prepare(self.query, "d1", self.raw())[0]
            reply = self.reply()
            rows = reply.fort.structures
            if problem == "missing": reply.fort.structures = None
            elif problem == "large": rows[5] = rows[1]
            elif problem == "sparse": rows.extra = rows[1]
            elif problem == "duplicate": rows[2].key = "barricade"
            elif problem == "unknown": rows[2].key = "gold_purchase"
            elif problem == "level": rows[1].lv = 6
            elif problem == "hp": rows[1].hp = float("nan")
            elif problem == "max": rows[1].hp = 1001
            elif problem == "rebuilding": rows[1].rebuilding = "true"
            else: rows[4] = None
            self.assertIsNone(self.query.Accept(self.query, request, reply)[0], problem)

    def test_missing_or_malformed_snapshot_and_rejected_reply_do_not_succeed(self):
        for change in ("nil", "partial", "family", "clock", "revision"):
            raw = self.raw()
            if change == "nil": raw = None
            elif change == "partial": raw.native.fullSync = False
            elif change == "family": raw.native.family.id = None
            elif change == "clock": raw.native.serverNow = float("inf")
            else: raw.revision = 0.5
            self.assertIsNone(self.query.Prepare(self.query, "d1", raw)[0])
        for reply in (None, {"ok": False}, {"ok": True, "pending": True},
                      {"ok": True, "code": "rate_limited"}):
            request = self.query.Prepare(self.query, "d1", self.raw())[0]
            self.assertIsNone(self.query.Accept(self.query, request, lua_table(self.h.lua, reply))[0])


if __name__ == "__main__":
    unittest.main()
