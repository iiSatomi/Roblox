"""Owned Family claims retain custody while callbacks are transient or contradictory."""
import json
import unittest
from contextlib import contextmanager

import test_family_claim_read_pipeline as fixture
from engine_harness import lua_table


class FamilyClaimOwnedSettlementTests(unittest.TestCase):
    @contextmanager
    def fixture(self):
        f = fixture.FamilyClaimReadPipelineTests(); f.setUp()
        try:
            yield f
        finally:
            f.tearDown()

    def held(self, f, action):
        records = f.runtime.checkpoint.Records(f.runtime.checkpoint)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[1].actionKey, action)
        self.assertEqual(list(f.runtime.checkpoint.FamilyClaimUsage(f.runtime.checkpoint, 100, 0).stages.values()), [1])

    def data(self, f):
        row = f.runtime.checkpoint.Records(f.runtime.checkpoint)[1]
        return f.runtime.checkpoint.Recovery(f.runtime.checkpoint, row.actionKey)[0]

    def json_roundtrip(self, f):
        def wire(value):
            if not hasattr(value, "items"): return value
            rows = dict(value.items())
            if rows and set(rows) == set(range(1, len(rows) + 1)):
                return [wire(rows[i]) for i in range(1, len(rows) + 1)]
            return {k: wire(v) for k, v in rows.items()}
        for key, value in list(f.base.storage.data.items()):
            f.base.storage.data[key] = lua_table(f.h.lua, json.loads(json.dumps(wire(value))))

    def test_pending_and_busy_hold_same_claim_through_timeout_and_normal_restart(self):
        for code in ("pending", "busy"):
            for ok in (True, False):
                with self.subTest(code=code, ok=ok), self.fixture() as f:
                    f.executor.reply = lua_table(f.h.lua, {"ok": ok, "code": code})
                    if not ok: f.executor.noAward = f.executor.noRemoval = True
                    f.begin_claim(); f.drain()
                    action = f.runtime.checkpoint.Records(f.runtime.checkpoint)[1].actionKey
                    f.followup(); self.held(f, action)
                    f.h.at(46); f.native.serverNow = f.h.lua.globals().familyState.serverNow = 1096
                    f.reader.ObserveSync(f.reader, f.native); f.step(); f.drain()
                    self.held(f, action)
                    self.assertEqual([call.args[1] for call in f.executor.calls.values()].count("claim"), 1)
                    f.restart()
                    f.native.serverNow = f.h.lua.globals().familyState.serverNow = 1097
                    f.reader.ObserveSync(f.reader, f.native); f.attach_current_read(); f.step()
                    f.app.Set(f.app, "familyBossClaims.enabled", True); f.app.Resume(f.app)
                    f.step(); f.drain(); self.held(f, action)
                    self.assertFalse(any(call.args[1] == "claim" for call in f.executor.calls.values()))

    def test_consumed_claim_and_exact_items_confirm_despite_passive_cash_without_proving_cash_award(self):
        for item_only in (False, True):
            with self.subTest(item_only=item_only), self.fixture() as f:
                if item_only: f.h.lua.globals().familyState.claims[1].cash = 0
                f.begin_claim(); f.drain(); data = self.data(f)
                expected_quote = 0 if item_only else 10
                self.assertEqual(data.baseline.awards.cash, expected_quote)
                original_keys = set(data.baseline.awards.keys())
                f.native.cash += .25
                f.followup()
                self.assertEqual(f.runtime.Status(f.runtime).outcomes.familyBossClaims, "confirmed")
                self.assertEqual(len(f.runtime.checkpoint.Records(f.runtime.checkpoint)), 0)
                self.assertEqual(f.native.inventoryBound.gold_bar, 1)
                self.assertEqual(f.native.inventory.crate_loot, 1)
                self.assertEqual(data.baseline.awards.cash, expected_quote)
                self.assertEqual(set(data.baseline.awards.keys()), original_keys)
                self.assertEqual(list(f.runtime.checkpoint.FamilyClaimUsage(f.runtime.checkpoint, 100, 0).stages.values()), [1])

    def test_normal_json_restart_recovers_same_quoted_claim_with_surplus_cash_without_replay(self):
        with self.fixture() as f:
            f.begin_claim(); f.drain(); data = self.data(f)
            f.native.cash += .25
            self.json_roundtrip(f); f.restart(); f.attach_current_read(); f.step()
            self.assertEqual(f.runtime.Status(f.runtime).recoveries.familyBossClaims, "confirmed")
            self.assertEqual(len(f.runtime.checkpoint.Records(f.runtime.checkpoint)), 0)
            self.assertEqual(len(f.executor.calls), 0)
            self.assertEqual(data.baseline.awards.cash, 10)
            self.assertEqual(list(f.runtime.checkpoint.FamilyClaimUsage(f.runtime.checkpoint, 100, 0).stages.values()), [1])

    def test_original_historical_stage_receipt_recovers_without_a_current_stage_marker(self):
        with self.fixture() as f:
            f.h.lua.globals().familyState.claims[1].week = 99
            f.begin_claim(); f.drain(); data = self.data(f)
            self.assertEqual(data.baseline.week, 99)
            original_fields = set(data.baseline.keys())
            f.native.cash += .25
            self.json_roundtrip(f); f.restart(); f.attach_current_read(); f.step()
            self.assertEqual(f.runtime.Status(f.runtime).recoveries.familyBossClaims, "confirmed")
            self.assertEqual(set(data.baseline.keys()), original_fields)
            self.assertEqual(len(f.h.lua.globals().familyState.claimedStages), 0)
            self.assertEqual(len(f.executor.calls), 0)
            self.assertEqual(list(f.runtime.checkpoint.FamilyClaimUsage(f.runtime.checkpoint, 99, 0).stages.values()), [1])

    def test_surplus_cash_requires_exact_stage_item_origins_source_and_new_observation(self):
        cases = ("same_clock", "old_clock", "missing_clock", "same_revision", "source", "scope", "expiry", "week", "family",
                 "missing_stage_marker", "claim_not_consumed", "partial_item", "wrong_origin", "cash_short", "cash_nan", "cash_inf")
        with self.fixture() as f:
            f.begin_claim(); f.drain(); data = self.data(f); f.native.cash += .25; f.followup()
            evidence = f.h.load("src/features/FamilyBossClaimsEvidence.luau")
            # Decode an independent exact receipt for each observation; no saved
            # original baseline or server reward quote is rewritten by the test.
            settled = f.reader.Capture(f.reader)[0]
            clone = f.h.lua.eval("function(v) local function c(x) if type(x)~='table' then return x end local r={} for k,a in pairs(x) do r[k]=c(a) end return r end return c(v) end")
            for case in cases:
                with self.subTest(case=case):
                    after = clone(settled)
                    state = after.familyTakedownProof.state
                    if case == "same_clock": after.native.serverNow = data.baseline.awards.serverNow
                    elif case == "old_clock": after.native.serverNow = data.baseline.awards.serverNow - 1
                    elif case == "missing_clock": after.native.serverNow = None
                    elif case == "same_revision": after.revision = data.baseline.revision
                    elif case == "source": after.familyTakedownProof.sourceKey = "b" * 64
                    elif case == "scope": after.account = "other"
                    elif case == "expiry": after.native.serverNow = data.baseline.expiresAt
                    elif case == "week": state.week += 1
                    elif case == "family": state.famId = "other"
                    elif case == "missing_stage_marker": state.claimedStages = f.h.lua.table()
                    elif case == "claim_not_consumed": state.claims = clone(data.before.familyTakedownProof.state.claims)
                    elif case == "partial_item": after.native.inventory.crate_loot = 0
                    elif case == "wrong_origin": after.native.inventoryBound.gold_bar = 0; after.native.inventory.gold_bar = 1
                    elif case == "cash_short": after.native.cash = data.baseline.awards.cashBefore + 9
                    elif case == "cash_nan": after.native.cash = float("nan")
                    else: after.native.cash = float("inf")
                    self.assertIsNone(evidence.recoverSaved(data, after))
