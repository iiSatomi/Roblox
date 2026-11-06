"""Exact saved earned-Trophy receipts through real App/tab composition."""
import unittest

import test_borrowed_heist_goal_app as fixture
from engine_harness import lua_table


class TrophySavedOutcomeAppTests(unittest.TestCase):
    def setUp(self):
        self.f = fixture.BorrowedHeistGoalAppTests()
        self.f.setUp()

    def tearDown(self):
        self.f.tearDown()

    def claim(self, reply=None):
        f = self.f
        f.raw.native.derived.trophyReady = lua_table(f.h.lua, ["t_firstscore"])
        f.select(contract=False, starts=False, collect=False)
        f.app.Set(f.app, "trophies.enabled", True)
        f.executor.reply = lua_table(f.h.lua, reply if reply is not None else {"ok": True})
        f.step()
        f.drain()
        self.assertEqual(len(f.executor.calls), 1)
        self.assertEqual(f.executor.calls[1].remote, "ClaimTrophy")
        self.assertEqual(len(f.records()), 1)

    def reload(self, awarded=True, t=1):
        f = self.f
        f.app.Destroy(f.app)
        f.start_app()
        f.later(t, False)
        if awarded:
            f.raw.native.derived.trophyReady = f.h.lua.table()
            f.raw.native.inventoryBound.t_firstscore = 1
        self.assertFalse(f.app.model["values"]["trophies.enabled"])
        self.assertFalse(f.app.model["values"]["trophyFocus.enabled"])

    def test_exact_saved_positive_receipt_reconciles_all_off_without_replay(self):
        self.claim()
        self.reload()
        self.f.step()
        self.assertEqual(len(self.f.records()), 0)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).recoveries.trophies, "confirmed")
        self.assertEqual(len(self.f.executor.calls), 0)


    def assert_held(self):
        self.f.step()
        self.assertEqual(len(self.f.records()), 1)
        self.assertEqual(len(self.f.executor.calls), 0)
        self.assertIsNone(self.f.runtime.Status(self.f.runtime).recoveries.trophies)

    def observation(self):
        f = self.f
        raw, reason = f.trophies.Enrich(f.trophies, f.raw)
        self.assertIsNone(reason)
        return raw

    def saved(self):
        f = self.f
        return f.runtime.checkpoint.Recovery(f.runtime.checkpoint, f.records()[1].actionKey)[0]

    def test_new_session_uses_later_native_clock_without_adopting_revision(self):
        self.claim()
        f = self.f
        f.app.Destroy(f.app)
        f.h.session["session"] = "new-session"
        f.start_app()
        f.later(1, False)
        f.raw.session = "new-session"
        f.raw.revision = 1
        f.raw.native.derived.trophyReady = f.h.lua.table()
        f.raw.native.inventoryBound.t_firstscore = 1
        f.step()
        self.assertEqual(len(f.records()), 0)
        self.assertEqual(len(f.executor.calls), 0)
        self.assertEqual(f.runtime.Status(f.runtime).recoveries.trophies, "confirmed")

    def test_missing_positive_receipt_holds_even_when_selected_award_appears(self):
        self.claim({"pending": True})
        self.reload()
        self.assert_held()

    def test_negative_reply_cannot_reconcile_a_later_award(self):
        self.claim({"ok": False})
        self.reload()
        self.assert_held()

    def test_pending_positive_receipt_is_not_terminal(self):
        self.claim({"ok": True, "pending": True})
        self.reload()
        self.assert_held()

    def test_ready_marker_must_disappear(self):
        self.claim()
        self.reload()
        self.f.raw.native.derived.trophyReady = lua_table(self.f.h.lua, ["t_firstscore"])
        self.assert_held()

    def test_wrong_award_holds_original_checkpoint(self):
        self.claim()
        self.reload()
        self.f.raw.native.inventoryBound.t_firstscore = None
        self.f.raw.native.inventoryBound.t_streetname = 1
        self.assert_held()

    def test_doubled_selected_award_holds_original_checkpoint(self):
        self.claim()
        self.reload()
        self.f.raw.native.inventoryBound.t_firstscore = 2
        self.assert_held()

    def test_unrelated_item_award_prevents_attribution_after_reload(self):
        self.claim()
        self.reload()
        self.f.raw.native.inventory.gold_bar = 1
        self.assert_held()

    def test_existing_item_origin_change_is_not_exact_custody(self):
        f = self.f
        f.raw.native.inventory.bandage = 2
        self.claim()
        self.reload()
        f.raw.native.inventory.bandage = 1
        f.raw.native.inventoryBound.bandage = 1
        self.assert_held()

    def test_all_four_origins_are_required(self):
        self.claim()
        self.reload()
        self.f.raw.native.collectionBound = None
        self.assert_held()

    def test_wrong_source_and_nonconsuming_reclassification_remain_held(self):
        self.claim()
        self.reload()
        f = self.f
        data = self.saved()
        e = f.h.load("src/features/EarnedTrophiesEvidence.luau")
        self.assertEqual(e.recoverSaved(self.saved(), self.observation()), "confirmed")
        observed = self.observation()
        observed.catalogKey = "b" * 64
        self.assertIsNone(e.recoverSaved(data, observed))
        observed = self.observation()
        observed.trophyCatalog = lua_table(f.h.lua, [{"id": "t_firstscore", "kind": "trophy", "requiresItems": True}])
        self.assertIsNone(e.recoverSaved(data, observed))

    def test_changed_account_place_or_release_cannot_reconcile(self):
        self.claim()
        self.reload()
        f = self.f
        data = self.saved()
        e = f.h.load("src/features/EarnedTrophiesEvidence.luau")
        self.assertEqual(e.recoverSaved(self.saved(), self.observation()), "confirmed")
        for field in ("account", "place", "release"):
            observed = self.observation()
            observed[field] = "other"
            self.assertIsNone(e.recoverSaved(data, observed), field)

    def test_changed_saved_baseline_or_proposal_cannot_reconcile(self):
        self.claim()
        self.reload()
        f = self.f
        e = f.h.load("src/features/EarnedTrophiesEvidence.luau")
        self.assertEqual(e.recoverSaved(self.saved(), self.observation()), "confirmed")
        data = self.saved()
        data.baseline.targetId = "t_streetname"
        self.assertIsNone(e.recoverSaved(data, self.observation()))
        data = self.saved()
        data.proposal.actionKey = "unrelated-action"
        self.assertIsNone(e.recoverSaved(data, self.observation()))
        data = self.saved()
        data.proposal.resources.cash = 1
        self.assertIsNone(e.recoverSaved(data, self.observation()))

    def test_backward_clock_or_unchanged_revision_cannot_reconcile(self):
        self.claim()
        self.reload()
        f = self.f
        data = self.saved()
        e = f.h.load("src/features/EarnedTrophiesEvidence.luau")
        self.assertEqual(e.recoverSaved(self.saved(), self.observation()), "confirmed")
        f.raw.native.serverNow = data.before.native.serverNow - 1
        self.assertIsNone(e.recoverSaved(data, self.observation()))
        f.raw.native.serverNow = data.before.native.serverNow + 1
        f.raw.revision = data.before.revision
        self.assertIsNone(e.recoverSaved(data, self.observation()))
        f.raw.session = "new-session"
        f.raw.native.serverNow = data.before.native.serverNow
        self.assertIsNone(e.recoverSaved(data, self.observation()))

    def test_late_exact_receipt_keeps_45_second_skip_history_and_cooldown(self):
        self.claim()
        f = self.f
        f.later(45, False)
        f.step()
        self.assertEqual(f.runtime.Status(f.runtime).outcomes.trophies, "skipped_unconfirmed")
        cooldown = f.runtime.Status(f.runtime).cooldownUntil.trophies
        f.later(46, False)
        f.raw.native.derived.trophyReady = f.h.lua.table()
        f.raw.native.inventoryBound.t_firstscore = 1
        f.app.Pause(f.app)
        f.step()
        status = f.runtime.Status(f.runtime)
        self.assertEqual(status.cooldownUntil.trophies, cooldown)
        self.assertEqual(len(f.records()), 0)
        self.assertEqual(status.recoveries.trophies, "confirmed")
        self.assertEqual(status.outcomes.trophies, "skipped_unconfirmed")
        self.assertEqual(len(f.executor.calls), 1)
        kinds = [event.kind for event in status.recentActions.values()]
        self.assertIn("skipped_unconfirmed", kinds)
        self.assertIn("reconciled_saved", kinds)

    def test_partial_award_can_later_reconcile_without_another_claim(self):
        self.claim()
        self.reload(awarded=False)
        self.assert_held()
        f = self.f
        f.later(2, False)
        f.raw.native.derived.trophyReady = f.h.lua.table()
        f.raw.native.collectionBound.t_firstscore = 1
        f.step()
        self.assertEqual(len(f.records()), 0)
        self.assertEqual(len(f.executor.calls), 0)

    def test_queued_claim_disable_is_known_unsent_without_award_or_replay(self):
        f = self.f
        f.raw.native.derived.trophyReady = lua_table(f.h.lua, ["t_firstscore"])
        f.select(contract=False, starts=False, collect=False)
        f.app.Set(f.app, "trophies.enabled", True)
        f.step()
        f.app.Set(f.app, "trophies.enabled", False)
        f.drain()
        self.assertEqual(len(f.executor.calls), 0)
        self.assertEqual(len(f.records()), 0)

    def test_unload_during_invocation_cannot_mint_a_positive_saved_receipt(self):
        f = self.f
        f.raw.native.derived.trophyReady = lua_table(f.h.lua, ["t_firstscore"])
        f.executor.InvokeOwned = f.h.lua.eval("""function(s,token,remote,method,...)
            s.calls[#s.calls+1]={remote=remote,args=table.pack(...),owned=true}
            coroutine.yield('waiting');return {ok=true} end""")
        f.select(contract=False, starts=False, collect=False)
        f.app.Set(f.app, "trophies.enabled", True)
        f.step()
        f.h.lua.globals().trophyInvocation = f.executor.queued[1]
        f.h.lua.execute("trophyThread=coroutine.create(trophyInvocation);assert(coroutine.resume(trophyThread))")
        self.assertEqual(len(f.executor.calls), 1)
        f.app.Destroy(f.app)
        writes = len(f.base.storage.writes)
        f.h.lua.execute("assert(coroutine.resume(trophyThread))")
        self.assertEqual(len(f.base.storage.writes), writes)
        self.reload()
        self.assert_held()

    def test_fractional_wallet_cash_is_not_an_earned_item_claim_gate(self):
        self.f.raw.native.cash = 1000.25
        self.claim()
        self.reload()
        self.f.raw.native.cash = 1001.75
        self.f.step()
        self.assertEqual(len(self.f.records()), 0)
        self.assertEqual(len(self.f.executor.calls), 0)

    def test_sparse_or_duplicate_ready_list_is_not_complete_reward_evidence(self):
        self.claim()
        self.reload()
        f = self.f
        e = f.h.load("src/features/EarnedTrophiesEvidence.luau")
        data = self.saved()
        self.assertEqual(e.recoverSaved(data, self.observation()), "confirmed")
        for malformed in ({2: "t_firstscore"}, {1: "t_streetname", 2: "t_streetname"}):
            observed = self.observation()
            observed.native.derived.trophyReady = lua_table(f.h.lua, malformed)
            self.assertIsNone(e.recoverSaved(data, observed))

if __name__ == "__main__":
    unittest.main()
