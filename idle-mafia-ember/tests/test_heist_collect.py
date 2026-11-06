"""Native result fingerprints, controller sequences, and exact collection effects."""
import hashlib
import json
import unittest

import test_heist_board_state as fixture
from engine_harness import lua_table


class HeistCollectTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture.HeistBoardStateTests()
        self.fixture.setUp()
        self.h = self.fixture.h
        self.planner = self.h.load("src/features/HeistCollect.luau")
        self.evidence = self.h.load("src/features/HeistCollectEvidence.luau")
        self.outcome = {"heistId": "h_a", "heistName": "Native result", "ok": True,
            "cash": 100, "xp": 20, "gold": 1, "crates": 2,
            "crateId": "crate_heist", "bonusCrates": 1, "bonusCrateId": "crate_bonus",
            "progress": 3, "goal": 3, "nativeExtra": {"retained": False}}
        self.result_key = hashlib.sha256(json.dumps(self.outcome, sort_keys=True).encode()).hexdigest()
        self.before = self.raw()

    def raw(self, revision=1, counter=4, result=True, now=2000000):
        raw = self.fixture.raw(result=self.outcome if result else None)
        raw.revision = revision
        raw.capturedAt = self.h.lua.globals().testNow
        raw.native.serverNow = now
        raw.native.cash, raw.native.level, raw.native.xp = 1000, 2, 5
        raw.native.maxLevel, raw.native.prestige = 2, 0
        raw.native.inventory = lua_table(self.h.lua, {"owned": 2, "crate_heist": 3})
        raw.native.inventoryBound = lua_table(self.h.lua, {"owned": 1, "gold_bar": 4})
        proof = raw.heistBoardProof
        proof.capturedAt, proof.sourceKey = raw.capturedAt, "b" * 64
        proof.board.serverNow = now
        proof.header = lua_table(self.h.lua, {key: raw[key] for key in
            ("session", "account", "place", "release", "revision", "capturedAt")})
        protocol = {key: raw[key] for key in
            ("session", "account", "place", "release", "revision", "capturedAt")}
        protocol.update({"nativeJob": "job-a", "nativeEpoch": "epoch-a",
            "nativeSourceKey": "a" * 64, "controllerCounter": counter,
            "resultKey": self.result_key if result else None,
            "xpThresholds": {1: 10, 2: 18, 3: 30, 4: 45, 5: 50, 6: 70, 7: 120, 8: 155},
            "quote": {"sequence": counter + 1, "nativeJob": "job-a",
                "nativeEpoch": "epoch-a", "nativeSourceKey": "a" * 64}})
        raw.heistProtocolProof = lua_table(self.h.lua, protocol)
        return raw

    def view(self, raw):
        view, why = self.fixture.view(raw)
        self.assertIsNotNone(view, why)
        # Source-bound inputs consumed by the planner; production Enrich owns them.
        view.protocol = raw.heistProtocolProof
        view.result = raw.heistBoardProof.board.result
        view.resultKey = raw.heistProtocolProof.resultKey
        view.resultAddressable = view.resultKey is not None
        return view

    def propose(self, raw=None):
        return self.planner.propose(self.view(raw or self.before),
            lua_table(self.h.lua, {"enabled": True}))

    def capture(self):
        proposal, why = self.propose()
        self.assertIsNotNone(proposal, why)
        baseline, why = self.evidence.capture(proposal, self.before)
        self.assertIsNotNone(baseline, why)
        return proposal, baseline

    def after(self, awarded=True, removed=True):
        self.h.at(1)
        after = self.raw(revision=2, counter=5, result=not removed, now=2000001)
        if awarded:
            after.native.cash = 1100
            after.native.level, after.native.xp, after.native.maxLevel = 3, 7, 3
            after.native.inventory.crate_heist = 5
            after.native.inventoryBound.crate_bonus = 1
            after.native.inventoryBound.gold_bar = 5
        return after

    def reply(self, **changes):
        reply = {"ok": True, "collected": True, "cash": 100, "xp": 20}
        reply.update(changes)
        return lua_table(self.h.lua, reply)

    def test_owned_awarded_xp_can_differ_from_board_base_quote(self):
        proposal,baseline=self.capture();after=self.after();after.native.xp=26
        reply=self.reply(xp=39,xpEventMultiplier=1)
        self.assertEqual(self.evidence.evaluate(proposal,self.before,after,reply,baseline),'confirmed')
        data=lua_table(self.h.lua,{'proposal':proposal,'before':self.before,'baseline':baseline,'reply':reply})
        self.assertEqual(self.evidence.recoverSaved(data,after),'confirmed')
        self.assertEqual(baseline.rewards.xp,20)
        self.assertEqual(baseline.projection.xp,7)
    def test_legacy_saved_base_projection_recovers_bonus_from_original_full_protocol(self):
        proposal,baseline=self.capture();baseline.xpThresholds=None
        after=self.after();after.native.xp=26
        data=lua_table(self.h.lua,{'proposal':proposal,'before':self.before,'baseline':baseline,'reply':self.reply(xp=39)})
        self.assertEqual(self.evidence.recoverSaved(data,after),'confirmed')
        self.assertIsNone(baseline.xpThresholds)
        data.before.heistProtocolProof.xpThresholds[3]=None
        self.assertIsNone(self.evidence.recoverSaved(data,after))
    def test_bonus_reply_alone_or_changed_source_does_not_confirm(self):
        proposal,baseline=self.capture();after=self.after();reply=self.reply(xp=39,xpEventMultiplier=1)
        self.assertEqual(self.evidence.evaluate(proposal,self.before,after,reply,baseline),'pending')
        after.native.xp=26;after.heistProtocolProof.nativeEpoch='other'
        self.assertEqual(self.evidence.evaluate(proposal,self.before,after,reply,baseline),'pending')
    def test_awarded_xp_requires_saved_thresholds_and_valid_exact_number(self):
        for award in (-1,1.5,float('inf'),float('nan'),'39'):
            proposal,baseline=self.capture();after=self.after();after.native.xp=26
            self.assertEqual(self.evidence.evaluate(proposal,self.before,after,self.reply(xp=award),baseline),'pending')
        proposal,baseline=self.capture();after=self.after();after.native.xp=26
        baseline.xpThresholds[3]=None
        self.assertEqual(self.evidence.evaluate(proposal,self.before,after,self.reply(xp=39),baseline),'pending')
    def test_source_owned_quote_proposes_exact_collect_without_fake_run_id(self):
        proposal, why = self.propose()
        self.assertIsNotNone(proposal, why)
        intent = proposal.intent
        self.assertEqual((proposal.feature, intent.kind, intent.sequence), ("heistCollect", "heistCollect", 5))
        self.assertEqual((intent.nativeJob, intent.nativeEpoch, intent.nativeSourceKey, intent.resultKey),
            ("job-a", "epoch-a", "a" * 64, self.result_key))
        self.assertIsNone(intent.runId)
        self.assertIsNone(intent.heistId)  # Native collect arg1 is nil.
        self.assertEqual(len(proposal.resources), 0)

    def test_unknown_success_reward_is_not_defaulted_to_zero(self):
        for field in ("cash", "xp", "gold", "crates", "bonusCrates"):
            with self.subTest(field=field):
                raw = self.raw()
                raw.heistBoardProof.board.result[field] = None
                self.assertIsNone(self.propose(raw)[0])

    def test_no_sequence_or_source_scope_never_proposes(self):
        for field in ("quote", "nativeJob", "nativeEpoch", "nativeSourceKey", "controllerCounter", "resultKey"):
            with self.subTest(field=field):
                raw = self.raw()
                raw.heistProtocolProof[field] = None
                self.assertIsNone(self.propose(raw)[0])

    def test_changed_quote_scope_or_counter_never_proposes(self):
        for field, value in (("sequence", 7), ("nativeJob", "other"),
                ("nativeEpoch", "other"), ("nativeSourceKey", "c" * 64)):
            raw = self.raw()
            raw.heistProtocolProof.quote[field] = value
            self.assertIsNone(self.propose(raw)[0], field)

    def test_capture_retains_complete_result_and_reward_origin_baseline(self):
        _, baseline = self.capture()
        self.before.heistBoardProof.board.result.nativeExtra.retained = True
        self.assertFalse(baseline.result.nativeExtra.retained)
        self.assertEqual(baseline.resultKey, self.result_key)
        self.assertEqual((baseline.inventory.crate_heist, baseline.inventoryBound.gold_bar), (3, 4))

    def test_capture_rejects_stale_protocol_header_and_missing_reward_custody(self):
        proposal = self.propose()[0]
        for field in ("revision", "account", "capturedAt"):
            raw = self.raw()
            raw.heistProtocolProof[field] = "changed"
            self.assertIsNone(self.evidence.capture(proposal, raw)[0], field)
        raw = self.raw()
        raw.native.inventoryBound = None
        self.assertIsNone(self.evidence.capture(proposal, raw)[0])

    def test_missing_or_insufficient_xp_thresholds_block_capture(self):
        proposal = self.propose()[0]
        for field in (2, 3):
            raw = self.raw()
            raw.heistProtocolProof.xpThresholds[field] = None
            self.assertIsNone(self.evidence.capture(proposal, raw)[0])
        raw = self.raw()
        raw.native.xp = None
        self.assertIsNone(self.evidence.capture(proposal, raw)[0])

    def test_collect_requires_removed_result_and_exact_complete_rewards(self):
        proposal, baseline = self.capture()
        self.assertEqual(self.evidence.evaluate(proposal, self.before, self.after(), self.reply(), baseline), "confirmed")
        self.assertEqual(self.evidence.evaluate(proposal, self.before, self.after(awarded=False), self.reply(), baseline), "pending")
        self.assertEqual(self.evidence.evaluate(proposal, self.before, self.after(removed=False), self.reply(), baseline), "pending")

    def test_passive_cash_growth_preserves_exact_collection_and_saved_recovery(self):
        proposal, baseline = self.capture()
        after = self.after()
        after.native.cash = 1100 + 30000000000
        self.assertEqual(self.evidence.evaluate(proposal, self.before, after, self.reply(), baseline), "confirmed")
        after.session = after.heistBoardProof.header.session = after.heistProtocolProof.session = "reloaded"
        data = lua_table(self.h.lua, {"proposal": proposal, "before": self.before,
            "baseline": baseline, "reply": self.reply()})
        self.assertEqual(self.evidence.recoverSaved(data, after), "confirmed")

    def test_passive_cash_can_coexist_with_failed_result_dismissal_without_other_changes(self):
        result = self.before.heistBoardProof.board.result
        result.ok, result.busted = False, True
        for field in ("cash", "xp", "gold", "crates", "bonusCrates", "crateId", "bonusCrateId"):
            result[field] = None
        proposal, baseline = self.capture()
        after = self.after(awarded=False)
        after.native.cash = 1000 + 30000000000
        reply = lua_table(self.h.lua, {"ok": True, "collected": False})
        self.assertEqual(self.evidence.evaluate(proposal, self.before, after, reply, baseline), "confirmed")
        after.native.cash = 999
        self.assertEqual(self.evidence.evaluate(proposal, self.before, after, reply, baseline), "pending")

    def test_passive_cash_still_prevents_exact_rejection_from_claiming_unchanged_custody(self):
        proposal, baseline = self.capture()
        after = self.after(awarded=False, removed=False)
        reply = lua_table(self.h.lua, {"ok": False, "collected": False})
        after.native.cash = 1001
        self.assertEqual(self.evidence.evaluate(proposal, self.before, after, reply, baseline), "pending")
        after.native.cash = 1000
        self.assertEqual(self.evidence.evaluate(proposal, self.before, after, reply, baseline), "rejected")

    def test_passive_cash_never_substitutes_for_item_xp_sequence_or_result_proof(self):
        proposal, baseline = self.capture()
        for mode in ("partial-item", "origin-transfer", "partial-xp", "new-counter", "old-counter", "result-retained"):
            after = self.after(removed=mode != "result-retained")
            after.native.cash = 1100 + 30000000000
            if mode == "partial-item": after.native.inventoryBound.crate_bonus = None
            elif mode == "origin-transfer":
                after.native.inventory.crate_heist = 2
                after.native.inventoryBound.crate_heist = 3
            elif mode == "partial-xp": after.native.xp = 6
            elif mode == "new-counter": after.heistProtocolProof.controllerCounter = 6
            elif mode == "old-counter": after.heistProtocolProof.controllerCounter = 4
            self.assertEqual(self.evidence.evaluate(proposal, self.before, after, self.reply(), baseline), "pending", mode)

    def test_partial_cash_xp_or_item_award_remains_pending(self):
        proposal, baseline = self.capture()
        for field, value in (("cash", 1099), ("xp", 6), ("level", 2), ("maxLevel", 2)):
            after = self.after()
            after.native[field] = value
            self.assertEqual(self.evidence.evaluate(proposal, self.before, after, self.reply(), baseline), "pending", field)
        after = self.after()
        after.native.inventoryBound.crate_bonus = None
        self.assertEqual(self.evidence.evaluate(proposal, self.before, after, self.reply(), baseline), "pending")

    def test_origin_transfer_and_unrelated_inventory_changes_do_not_count_as_reward(self):
        proposal, baseline = self.capture()
        after = self.after()
        after.native.inventory.crate_heist = 2
        after.native.inventoryBound.crate_heist = 3
        self.assertEqual(self.evidence.evaluate(proposal, self.before, after, self.reply(), baseline), "pending")
        after = self.after()
        after.native.inventory.owned = 3
        self.assertEqual(self.evidence.evaluate(proposal, self.before, after, self.reply(), baseline), "pending")

    def test_quote_allows_unknown_award_origin_but_preserves_both_prior_origins(self):
        proposal, baseline = self.capture()
        after = self.after()
        after.native.inventory.crate_heist = 4
        after.native.inventoryBound.crate_heist = 1
        self.assertEqual(self.evidence.evaluate(proposal, self.before, after, self.reply(), baseline), "confirmed")

    def test_multiple_level_crossings_do_not_treat_max_level_highwater_as_cap(self):
        self.before.heistBoardProof.board.result.xp = 250
        proposal, baseline = self.capture()
        after = self.after()
        after.native.level, after.native.xp, after.native.maxLevel = 7, 42, 7
        self.assertEqual(self.evidence.evaluate(proposal, self.before, after, self.reply(xp=250), baseline), "confirmed")

    def test_changed_xp_helper_quote_stays_pending(self):
        proposal, baseline = self.capture()
        after = self.after()
        after.heistProtocolProof.xpThresholds[3] = 31
        self.assertEqual(self.evidence.evaluate(proposal, self.before, after, self.reply(), baseline), "pending")

    def test_counter_epoch_job_source_or_board_source_change_stays_pending(self):
        proposal, baseline = self.capture()
        for field, value in (("controllerCounter", 6), ("controllerCounter", 4),
                ("nativeJob", "other"), ("nativeEpoch", "other"), ("nativeSourceKey", "c" * 64)):
            after = self.after()
            after.heistProtocolProof[field] = value
            self.assertEqual(self.evidence.evaluate(proposal, self.before, after, self.reply(), baseline), "pending", field)
        after = self.after()
        after.heistBoardProof.sourceKey = "c" * 64
        self.assertEqual(self.evidence.evaluate(proposal, self.before, after, self.reply(), baseline), "pending")

    def test_transient_uncollected_and_changed_terminal_quotes_stay_pending(self):
        proposal, baseline = self.capture()
        for changes in ({"pending": True}, {"code": "no_pending"}, {"code": "rate_limited"},
                {"code": "presence"}, {"code": "busy"}, {"collected": False}, {"cash": 101}, {"xp": 21}):
            self.assertEqual(self.evidence.evaluate(proposal, self.before, self.after(), self.reply(**changes), baseline), "pending", changes)

    def test_exact_rejection_requires_result_and_every_balance_unchanged(self):
        proposal, baseline = self.capture()
        reply = self.reply(ok=False, collected=False)
        self.assertEqual(self.evidence.evaluate(proposal, self.before,
            self.after(awarded=False, removed=False), reply, baseline), "rejected")
        self.assertEqual(self.evidence.evaluate(proposal, self.before,
            self.after(awarded=False, removed=True), reply, baseline), "pending")
        self.assertEqual(self.evidence.evaluate(proposal, self.before,
            self.after(awarded=True, removed=False), reply, baseline), "pending")

    def test_failed_result_dismissal_requires_explicit_no_payout_and_exact_non_cash_custody(self):
        result = self.before.heistBoardProof.board.result
        result.ok, result.busted = False, True
        for field in ("cash", "xp", "gold", "crates", "bonusCrates", "crateId", "bonusCrateId"):
            result[field] = None
        proposal, baseline = self.capture()
        after = self.after(awarded=False)
        self.assertEqual(self.evidence.evaluate(proposal, self.before, after,
            lua_table(self.h.lua, {"ok": True, "collected": False}), baseline), "confirmed")
        self.assertEqual(self.evidence.evaluate(proposal, self.before, after,
            lua_table(self.h.lua, {"ok": True}), baseline), "pending")

    def test_exact_saved_result_recovers_without_replay_only_in_same_controller_scope(self):
        proposal, baseline = self.capture()
        after = self.after()
        after.session = after.heistBoardProof.header.session = after.heistProtocolProof.session = "reloaded"
        data = lua_table(self.h.lua, {"proposal": proposal, "before": self.before,
            "baseline": baseline, "reply": self.reply()})
        self.assertEqual(self.evidence.recoverSaved(data, after), "confirmed")
        after.heistProtocolProof.nativeEpoch = "new-native-controller"
        self.assertIsNone(self.evidence.recoverSaved(data, after))

    def completed_receipt_case(self):
        proposal, baseline = self.capture()
        after = self.after()
        after.session = after.heistBoardProof.header.session = after.heistProtocolProof.session = "new-session"
        after.heistProtocolProof.nativeJob = "new-job"
        after.heistProtocolProof.nativeEpoch = "new-epoch"
        after.heistProtocolProof.controllerCounter = 0
        after.heistProtocolProof.quote = None
        data = lua_table(self.h.lua, {"proposal": proposal, "before": self.before,
            "baseline": baseline, "reply": self.reply()})
        return data, after

    def test_completed_positive_receipt_recovers_on_new_controller_without_counter_adoption(self):
        data, after = self.completed_receipt_case()
        self.assertEqual(self.evidence.recoverCompleted(data, after), "confirmed")
        self.assertEqual(after.heistProtocolProof.controllerCounter, 0)
        self.assertEqual(data.proposal.intent.nativeJob, "job-a")
        self.assertEqual(data.proposal.intent.nativeEpoch, "epoch-a")
        self.assertEqual(data.proposal.intent.sequence, 5)
        self.assertIsNone(self.evidence.recoverSaved(data, after))

    def test_completed_cross_controller_receipt_uses_exact_awarded_xp_and_saved_legacy_thresholds(self):
        data, after = self.completed_receipt_case()
        data.reply.xp, after.native.xp = 39, 26
        data.baseline.xpThresholds = None
        self.assertEqual(self.evidence.recoverCompleted(data, after), "confirmed")
        self.assertIsNone(data.baseline.xpThresholds)
        after.native.xp = 27
        self.assertIsNone(self.evidence.recoverCompleted(data, after))

    def test_cross_controller_requires_successful_completed_receipt_not_pending_rejection_or_dismissal(self):
        for mode in ("missing", "pending", "rejected", "not-collected", "presence", "no_pending", "rate_limited", "busy", "wrong-cash", "wrong-xp", "failed-result"):
            with self.subTest(mode=mode):
                data, after = self.completed_receipt_case()
                if mode == "missing": data.reply = None
                elif mode == "pending": data.reply.pending = True
                elif mode == "rejected": data.reply.ok = False
                elif mode == "not-collected": data.reply.collected = False
                elif mode in ("presence", "no_pending", "rate_limited", "busy"): data.reply.code = mode
                elif mode == "wrong-cash": data.reply.cash += 1
                elif mode == "wrong-xp": data.reply.xp += 1
                else: data.baseline.result.ok = False
                self.assertIsNone(self.evidence.recoverCompleted(data, after))

    def test_cross_controller_keeps_all_exact_custody_source_clock_and_result_guards(self):
        for mode in ("cash", "partial-xp", "extra-xp", "level", "maxLevel", "prestige", "partial-item",
                     "missing-inventory", "origin-transfer", "unrelated-item", "threshold", "board-source",
                     "native-source", "clock", "result-retained", "new-mine", "same-controller"):
            with self.subTest(mode=mode):
                data, after = self.completed_receipt_case()
                if mode == "cash": after.native.cash = 1099
                elif mode == "partial-xp": after.native.xp = 6
                elif mode == "extra-xp": after.native.xp = 8
                elif mode == "level": after.native.level = 2
                elif mode == "maxLevel": after.native.maxLevel = 4
                elif mode == "prestige": after.native.prestige = 1
                elif mode == "partial-item": after.native.inventoryBound.crate_bonus = None
                elif mode == "missing-inventory": after.native.inventoryBound = None
                elif mode == "origin-transfer":
                    after.native.inventory.owned -= 1
                    after.native.inventoryBound.owned += 1
                elif mode == "unrelated-item": after.native.inventory.unrelated = 1
                elif mode == "threshold": after.heistProtocolProof.xpThresholds[3] = 31
                elif mode == "board-source": after.heistBoardProof.sourceKey = "c" * 64
                elif mode == "native-source": after.heistProtocolProof.nativeSourceKey = "c" * 64
                elif mode == "clock": after.native.serverNow = 1999999
                elif mode == "result-retained":
                    after.heistBoardProof.board.result = self.before.heistBoardProof.board.result
                    after.heistProtocolProof.resultKey = self.result_key
                elif mode == "new-mine": after.heistBoardProof.board.mine = lua_table(self.h.lua, {"id": "different-run"})
                else:
                    after.heistProtocolProof.nativeJob = "job-a"
                    after.heistProtocolProof.nativeEpoch = "epoch-a"
                self.assertIsNone(self.evidence.recoverCompleted(data, after))

    def test_cross_controller_changed_account_place_release_or_forged_baseline_remains_held(self):
        for mode in ("account", "place", "release", "baseline", "before", "other-feature"):
            with self.subTest(mode=mode):
                data, after = self.completed_receipt_case()
                if mode in ("account", "place", "release"):
                    after[mode] = after.heistProtocolProof[mode] = after.heistBoardProof.header[mode] = "changed"
                    if mode == "account": after.heistBoardProof.account = "changed"
                elif mode == "baseline": data.baseline.cash += 1
                elif mode == "before": data.before.heistBoardProof.board.result.heistId = "different-run"
                else: data.proposal.feature = "heists"
                self.assertIsNone(self.evidence.recoverCompleted(data, after))

    def test_missing_or_tampered_saved_baseline_never_recovers(self):
        proposal, baseline = self.capture()
        data = lua_table(self.h.lua, {"proposal": proposal, "before": self.before,
            "baseline": baseline, "reply": self.reply()})
        baseline.result.nativeExtra.retained = True
        self.assertIsNone(self.evidence.recoverSaved(data, self.after()))
        data.reply = None
        self.assertIsNone(self.evidence.recoverSaved(data, self.after()))

    def test_queued_result_fingerprint_change_fences_dispatch(self):
        proposal, _ = self.capture()
        self.assertTrue(self.evidence.canDispatch(proposal, self.before))
        raw = self.raw()
        raw.heistProtocolProof.resultKey = "c" * 64
        self.assertFalse(self.evidence.canDispatch(proposal, raw))


if __name__ == "__main__":
    unittest.main()
