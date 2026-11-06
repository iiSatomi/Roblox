"""Conditional native historical rows: no present or former Family identity is invented."""
import unittest

import test_family_boss_query as query_fixture
import test_family_claim_read_pipeline as pipeline_fixture
import test_family_takedown_claims as claim_fixture
from engine_harness import lua_table


class FamilylessQueryTests(unittest.TestCase):
    def setUp(self):
        self.fixture = query_fixture.FamilyBossQueryTests()
        self.fixture.setUp()
        self.h, self.query = self.fixture.h, self.fixture.query

    def raw(self):
        raw = self.fixture.raw()
        raw.native.family = None
        return raw

    def reply(self):
        return lua_table(self.h.lua, {"ok": True, "serverNow": 1050,
            "week": 100, "inFamily": False,
            "claims": [{"week": 99, "stage": 7, "expiresAt": 1300,
                "medal": "m_weekly"}]})

    def test_explicit_familyless_reply_keeps_unknown_combat_fields_absent(self):
        raw = self.raw()
        request, why = self.query.Prepare(self.query, raw)
        self.assertIsNotNone(request, why)
        staged, why = self.query.Accept(self.query, raw, request, self.reply())
        self.assertIsNotNone(staged, why)
        state = staged.familyTakedownProof.state
        self.assertIsNone(state.famId)
        self.assertIsNone(staged.familyTakedownProof.header.familyId)
        context = self.fixture.raw()
        context.serverNow = 1050
        view, why = self.fixture.fixture.reader.read(staged, context)
        self.assertIsNotNone(view, why)
        self.assertEqual((view.week, view.inFamily, view.claims[1].week, view.claims[1].stage),
            (100, False, 99, 7))
        for field in ("famId", "runKey", "stage", "resetAt", "free", "freeMax",
                "freeUsed", "freeRegen", "nextFreeAt", "tickets", "myDmg", "claimedStages"):
            self.assertIsNone(view[field], field)

    def test_familyless_reply_requires_explicit_false_and_no_old_family_id(self):
        for field, value in (("inFamily", True), ("inFamily", None),
                ("famId", 9), ("famId", "former-family"), ("famId", False), ("famId", "")):
            with self.subTest(field=field, value=value):
                raw = self.raw()
                request, why = self.query.Prepare(self.query, raw)
                self.assertIsNotNone(request, why)
                reply = self.reply()
                reply[field] = value
                self.assertIsNone(self.query.Accept(self.query, raw, request, reply)[0])

    def test_missing_claims_is_unknown_and_cannot_become_empty_claim_list(self):
        raw = self.raw()
        request, why = self.query.Prepare(self.query, raw)
        self.assertIsNotNone(request, why)
        reply = self.reply()
        reply.claims = None
        self.assertIsNone(self.query.Accept(self.query, raw, request, reply)[0])

    def test_sparse_duplicate_future_and_untrusted_familyless_rows(self):
        for change in ("sparse", "duplicate", "future-week", "clock"):
            with self.subTest(change=change):
                raw = self.raw()
                request, why = self.query.Prepare(self.query, raw)
                self.assertIsNotNone(request, why)
                reply = self.reply()
                if change == "sparse": reply.claims[3], reply.claims[1] = reply.claims[1], None
                elif change == "duplicate": reply.claims[2] = reply.claims[1]
                elif change == "future-week": reply.claims[1].week = 101
                else: reply.serverNow = 1060
                self.assertIsNone(self.query.Accept(self.query, raw, request, reply)[0])

    def test_membership_change_while_read_is_in_flight_rejects_old_reply(self):
        raw = self.raw()
        request, why = self.query.Prepare(self.query, raw)
        self.assertIsNotNone(request, why)
        raw.native.family = lua_table(self.h.lua, {"id": "new-family"})
        self.assertIsNone(self.query.Accept(self.query, raw, request, self.reply())[0])

    def test_malformed_present_family_cannot_be_treated_as_absent(self):
        for value in (False, {}, {"id": ""}, {"id": 0}):
            raw = self.raw()
            raw.native.family = lua_table(self.h.lua, value)
            self.assertIsNone(self.query.Prepare(self.query, raw)[0])


class FamilylessClaimPlanningTests(unittest.TestCase):
    def setUp(self):
        self.fixture = claim_fixture.FamilyTakedownClaimTests()
        self.fixture.setUp()
        self.h = self.fixture.h

    def raw(self):
        raw = self.fixture.raw(stages=[{"week": 99, "stage": 7,
            "expiresAt": 1300, "cash": 10}], week=99, state_week=100,
            fam_id=None, in_family=False)
        for field in ("stage", "resetAt", "freeMax", "freeUsed", "freeRegen", "tickets", "myDmg", "claimedStages"):
            raw.familyTakedownProof.state[field] = None
        return raw

    def test_exact_historical_claim_plans_and_captures_without_family_id(self):
        raw = self.raw()
        proposal, why = self.fixture.propose(raw)
        self.assertIsNotNone(proposal, why)
        self.assertEqual((proposal.intent.week, proposal.intent.stage), (99, 7))
        self.assertIsNone(proposal.intent.famId)
        baseline, why = self.fixture.evidence.capture(proposal, raw)
        self.assertIsNotNone(baseline, why)
        self.assertIsNone(baseline.famId)

    def test_current_week_claim_cannot_use_familyless_history_path(self):
        raw = self.raw()
        raw.familyTakedownProof.state.claims[1].week = 100
        self.assertIsNone(self.fixture.propose(raw)[0])

    def test_no_member_identity_is_a_claim_view_only(self):
        raw = self.raw()
        context, why = self.fixture.context.Read(self.fixture.context, raw,
            lua_table(self.h.lua, self.h.session), 0, 2)
        self.assertIsNone(why)
        attacks = self.h.load("src/features/FamilyBossAttacks.luau")
        self.assertIsNone(attacks.propose(context.takedown,
            lua_table(self.h.lua, {"enabled": True}), self.h.lua.table())[0])


class FamilylessClaimReadPipelineTests(unittest.TestCase):
    def setUp(self):
        self.p = pipeline_fixture.FamilyClaimReadPipelineTests()
        self.p.setUp()
        self.p.native.family = None
        state = self.p.h.lua.globals().familyState
        state.famId, state.inFamily = None, False
        for field in ("stage", "resetAt", "freeMax", "freeUsed", "freeRegen", "tickets", "myDmg", "claimedStages"):
            state[field] = None
        state.claims[1].week, state.claims[1].stage = 99, 7
        self.p.reader.ObserveSync(self.p.reader, self.p.native)

    def tearDown(self):
        self.p.tearDown()

    def join_other_family(self):
        p = self.p
        state = p.h.lua.globals().familyState
        p.native.family = lua_table(p.h.lua, {"id": "new-family"})
        state.famId, state.inFamily = "new-family", True
        for field, value in {"stage": 2, "resetAt": 2000, "freeMax": 10,
                "freeUsed": 0, "freeRegen": 3600, "tickets": 0, "myDmg": 120}.items():
            state[field] = value
        state.claimedStages = p.h.lua.table()
        p.reader.ObserveSync(p.reader, p.native)

    def test_app_claim_confirms_exact_awards_without_family_or_stamina_spend(self):
        p = self.p
        stamina = p.native.pools.stamina
        p.begin_claim()
        p.drain()
        p.followup()
        self.assertEqual(p.runtime.Status(p.runtime).outcomes.familyBossClaims, "confirmed")
        calls = p.executor.calls
        self.assertEqual([row.args[1] for row in calls.values()], ["state", "claim", "state"])
        self.assertEqual((calls[2].args.n, calls[2].args[2], calls[2].args[3]), (3, 99, 7))
        self.assertEqual(p.native.pools.stamina, stamina)
        self.assertIsNone(p.native.family)
        self.assertEqual(list(p.runtime.checkpoint.FamilyClaimUsage(p.runtime.checkpoint, 99, 3.25).stages.values()), [7])

    def test_saved_familyless_claim_recovers_exact_awards_without_replay(self):
        p = self.p
        p.begin_claim()
        p.drain()
        p.restart()
        p.attach_current_read()
        p.step()
        self.assertEqual(p.runtime.Status(p.runtime).recoveries.familyBossClaims, "confirmed")
        self.assertEqual(len(p.executor.calls), 0)
        self.assertEqual(list(p.runtime.checkpoint.FamilyClaimUsage(p.runtime.checkpoint, 99, 0).stages.values()), [7])

    def test_missing_awards_remain_pending_and_saved_after_row_removal(self):
        p = self.p
        p.executor.noAward = True
        p.begin_claim()
        p.drain()
        p.followup()
        self.assertIsNone(p.runtime.Status(p.runtime).outcomes.familyBossClaims)
        p.restart()
        p.attach_current_read()
        p.step()
        self.assertIsNone(p.runtime.Status(p.runtime).recoveries.familyBossClaims)
        self.assertEqual(len(p.runtime.checkpoint.Records(p.runtime.checkpoint)), 1)

    def test_saved_wrong_reward_origin_is_held(self):
        p = self.p
        p.begin_claim()
        p.drain()
        p.native.inventoryBound.gold_bar = 0
        p.native.inventory.gold_bar = 1
        p.restart()
        p.attach_current_read()
        p.step()
        self.assertIsNone(p.runtime.Status(p.runtime).recoveries.familyBossClaims)
        self.assertEqual(len(p.runtime.checkpoint.Records(p.runtime.checkpoint)), 1)

    def test_queued_claim_is_fenced_when_membership_changes(self):
        p = self.p
        p.begin_claim()
        self.join_other_family()
        p.attach_current_read()
        p.step()
        p.drain()
        self.assertEqual([row.args[1] for row in p.executor.calls.values()], ["state"])
        self.assertEqual(len(p.runtime.checkpoint.FamilyClaimUsage(p.runtime.checkpoint, 99, .25).stages), 0)

    def test_saved_claim_never_retargets_changed_membership(self):
        p = self.p
        p.begin_claim()
        p.drain()
        p.restart()
        self.join_other_family()
        p.attach_current_read()
        p.step()
        self.assertIsNone(p.runtime.Status(p.runtime).recoveries.familyBossClaims)
        self.assertEqual(len(p.runtime.checkpoint.Records(p.runtime.checkpoint)), 1)
        self.assertEqual(len(p.executor.calls), 0)

    def test_attachment_rejects_invented_old_family_identity_and_invalidates_on_sync(self):
        p = self.p
        raw = p.reader.Capture(p.reader)[0]
        request, why = p.tab.PrepareFamilyBossRead(p.tab, raw)
        self.assertIsNotNone(request, why)
        staged, why = p.tab.AcceptFamilyBossRead(p.tab, raw, request, p.h.lua.globals().familyState)
        self.assertIsNotNone(staged, why)
        self.assertTrue(p.reader.AttachFamilyBoss(p.reader, staged))
        staged.familyTakedownProof.state.famId = "former-family"
        self.assertFalse(p.reader.AttachFamilyBoss(p.reader, staged))
        staged.familyTakedownProof.state.famId = None
        p.reader.ObserveSync(p.reader, p.native)
        self.assertIsNone(p.reader.Capture(p.reader)[0].familyTakedownProof)
        self.assertFalse(p.reader.AttachFamilyBoss(p.reader, staged))

    def test_rejection_needs_unchanged_claim_and_unchanged_awards(self):
        p = self.p
        p.executor.noRemoval = p.executor.noAward = True
        p.executor.reply = lua_table(p.h.lua, {"ok": False})
        p.begin_claim()
        p.drain()
        p.followup()
        self.assertEqual(p.runtime.Status(p.runtime).outcomes.familyBossClaims, "rejected")

    def test_all_off_and_unload_do_not_send(self):
        p = self.p
        p.step()
        self.assertEqual(len(p.executor.queued), 0)
        p.app.Set(p.app, "familyBossClaims.enabled", True)
        p.app.Resume(p.app)
        p.step()
        p.app.Destroy(p.app)
        p.drain()
        self.assertEqual(len(p.executor.calls), 0)


if __name__ == "__main__":
    unittest.main()
