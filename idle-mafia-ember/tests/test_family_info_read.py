"""Family contribution info joins the shared reader without authorizing spending."""
import unittest

import test_family_contribution_pipeline as fixture
from engine_harness import lua_table


class FamilyInfoReadTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture.FamilyContributionPipelineTests()
        self.fixture.setUp()
        self.h = self.fixture.h
        self.tab = self.fixture.tab()
        self.reader = self.h.load("src/transport/NativeSnapshotReader.luau").new(
            lua_table(self.h.lua, self.h.session), self.h.clock, "a" * 64)
        self.reader.ObserveSync(self.reader, self.fixture.raw().native)

    def test_shared_source_uses_exact_info_read_and_actor_only_proof(self):
        sources = self.tab.ReadSources(self.tab, self.reader)
        self.assertEqual(len(sources), 1)
        source = sources[1]
        self.assertFalse(source.enabled(lua_table(self.h.lua, {}), None))
        self.assertTrue(source.enabled(lua_table(self.h.lua, {"familyCash": {"enabled": True}}), None))
        raw = self.reader.Capture(self.reader)[0]
        request, reason = source.prepare(raw)
        self.assertIsNone(reason)
        self.assertEqual((request.remote, request.arity, request.args[1]), ("FamilyAction", 1, "info"))
        reply = lua_table(self.h.lua, {"ok": True, "family": self.fixture.family()})
        staged, reason = source.accept(raw, request, reply)
        self.assertIsNone(reason)
        self.assertTrue(source.commit(staged))
        proof = self.reader.Capture(self.reader)[0].familyContributionProof
        self.assertEqual((proof.family.actorId, proof.family.ledger.cash), (42, 500))
        self.assertIsNone(proof.family.members)
        reply.family.members[1].donated = 1
        self.assertEqual(self.reader.Capture(self.reader)[0].familyContributionProof.family.ledger.cash, 500)

    def test_wrong_source_changed_membership_and_new_sync_cannot_attach_old_info(self):
        raw = self.reader.Capture(self.reader)[0]
        query = self.tab.NewInfoQuery(self.tab)
        request, _ = query.Prepare(query, raw)
        staged, _ = query.Stage(query, raw, request,
            lua_table(self.h.lua, {"ok": True, "family": self.fixture.family()}))
        staged.familyContributionProof.sourceKey = "b" * 64
        self.assertFalse(self.reader.AttachFamilyContribution(self.reader, staged))
        staged.familyContributionProof.sourceKey = "a" * 64
        self.assertTrue(self.reader.AttachFamilyContribution(self.reader, staged))
        changed = self.fixture.raw().native
        changed.family.id = "other"
        self.reader.ObserveSync(self.reader, changed)
        self.assertIsNone(self.reader.Capture(self.reader)[0].familyContributionProof)
        self.assertFalse(self.reader.AttachFamilyContribution(self.reader, staged))

    def test_close_fences_source_and_query_cannot_stage_pending_or_rate_limit(self):
        source = self.tab.ReadSources(self.tab, self.reader)[1]
        raw = self.reader.Capture(self.reader)[0]
        for change in ({"pending": True}, {"code": "rate_limited"}):
            request, _ = source.prepare(raw)
            reply = {"ok": True, "family": self.fixture.family(), **change}
            self.assertIsNone(source.accept(raw, request, lua_table(self.h.lua, reply))[0])
        self.tab.Close(self.tab)
        self.assertIsNone(source.prepare(raw)[0])

    def tearDown(self):
        self.tab.Close(self.tab)
        self.reader.Close(self.reader)


if __name__ == "__main__":
    unittest.main()
