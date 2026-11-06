"""Owned Crew results settle independently of passive Cash; unknown replies never do."""
import unittest
from contextlib import contextmanager

import test_crew_hire_runtime as hire_fixture
import test_crew_train_runtime as train_fixture
from engine_harness import lua_table


class CrewOwnedSettlementTests(unittest.TestCase):
    @contextmanager
    def fixture(self, kind):
        f = (hire_fixture.CrewHireRuntimeTests() if kind == "crewHire"
             else train_fixture.CrewTrainRuntimeTests())
        f.setUp()
        try:
            yield f
        finally:
            f.tearDown()

    def after(self, f, kind, revision=2, cash=None, completed=False):
        if kind == "crewHire":
            return f.raw(revision, True, 20001.25 if cash is None else cash)
        raw = f.raw(revision, 401.25 if cash is None else cash, not completed)
        if completed:
            raw.native.crew[2].train = 1
            raw.native.serverNow = 1405
        return raw

    def observe(self, f, raw):
        f.h.at(raw.capturedAt)
        f.f.app.Step(f.f.app, raw)

    def held(self, f, action):
        records = f.f.runtime.checkpoint.Records(f.f.runtime.checkpoint)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[1].actionKey, action)
        cost = 10000 if records[1].feature == "crewHire" else 100
        self.assertEqual(records[1].resources.cash, cost)
        self.assertEqual(records[1].custody.funds.cash, cost)
        self.assertEqual(len(f.f.executor.calls), 1)

    def test_owned_success_settles_with_passive_cash_and_preserves_hire_allowance(self):
        for kind, completed in (("crewHire", False), ("crewTrain", False), ("crewTrain", True)):
            with self.subTest(kind=kind, completed=completed), self.fixture(kind) as f:
                f.begin()
                self.observe(f, self.after(f, kind, completed=completed))
                self.assertEqual(f.f.runtime.Status(f.f.runtime).outcomes[kind], "confirmed")
                self.assertEqual(len(f.f.runtime.checkpoint.Records(f.f.runtime.checkpoint)), 0)
                self.assertEqual(len(f.f.executor.calls), 1)
                if kind == "crewHire":
                    usage = f.f.runtime.checkpoint.Allowance(f.f.runtime.checkpoint, kind)[0]
                    self.assertEqual((usage.attempted, usage.spent), (1, 10000))

    def test_owned_effect_does_not_guess_income_or_require_a_net_wallet_debit(self):
        for kind, cash in (("crewHire", 30000), ("crewHire", 31000.5),
                           ("crewTrain", 500), ("crewTrain", 510.5)):
            with self.subTest(kind=kind, cash=cash), self.fixture(kind) as f:
                f.begin()
                self.observe(f, self.after(f, kind, cash=cash))
                self.assertEqual(f.f.runtime.Status(f.f.runtime).outcomes[kind], "confirmed")
                self.assertEqual(len(f.f.runtime.checkpoint.Records(f.f.runtime.checkpoint)), 0)
                self.assertEqual(len(f.f.executor.calls), 1)

    def test_normal_descriptor_recovers_owned_result_with_passive_cash_without_replay(self):
        for kind, completed in (("crewHire", False), ("crewTrain", False), ("crewTrain", True)):
            with self.subTest(kind=kind, completed=completed), self.fixture(kind) as f:
                f.begin()
                f.f.restart()
                raw = self.after(f, kind, revision=0, completed=completed)
                if not completed:
                    raw.native.serverNow = 1005
                self.observe(f, raw)
                self.assertEqual(f.f.runtime.Status(f.f.runtime).recoveries[kind], "confirmed")
                self.assertEqual(len(f.f.runtime.checkpoint.Records(f.f.runtime.checkpoint)), 0)
                self.assertEqual(len(f.f.executor.calls), 1)
                if kind == "crewHire":
                    usage = f.f.runtime.checkpoint.Allowance(f.f.runtime.checkpoint, kind)[0]
                    self.assertEqual((usage.attempted, usage.spent), (1, 10000))

    def test_transient_codes_hold_original_cash_custody_through_timeout_and_restart(self):
        for kind in ("crewHire", "crewTrain"):
            for code in ("pending", "busy"):
                for ok in (True, False):
                    with self.subTest(kind=kind, code=code, ok=ok), self.fixture(kind) as f:
                        reply = f.f.executor.reply
                        if reply is None:
                            reply = lua_table(f.h.lua, {"ok": ok})
                            f.f.executor.reply = reply
                        reply.ok, reply.code = ok, code
                        f.begin()
                        action = f.f.runtime.checkpoint.Records(f.f.runtime.checkpoint)[1].actionKey
                        cash = (20000 if kind == "crewHire" else 400) if ok else (30000 if kind == "crewHire" else 500)
                        raw = self.after(f, kind, cash=cash) if ok else f.raw(2)
                        self.observe(f, raw)
                        self.held(f, action)
                        raw = self.after(f, kind, revision=46, cash=cash) if ok else f.raw(46)
                        self.observe(f, raw)
                        f.f.drain()
                        self.held(f, action)
                        f.f.restart()
                        raw = self.after(f, kind, revision=0, cash=cash) if ok else f.raw(0)
                        raw.native.serverNow = 1005
                        self.observe(f, raw)
                        f.choose()
                        self.observe(f, raw)
                        f.f.drain()
                        self.held(f, action)

    def test_passive_cash_path_requires_strict_new_clock_and_exact_owned_effect(self):
        cases = ("equal_clock", "old_clock", "missing_clock", "wrong_scope", "partial_sync",
                 "nonfinite_cash", "negative_reply", "negative_unchanged_with_income", "missing_effect", "cash_only_debit")
        for kind in ("crewHire", "crewTrain"):
            for case in cases:
                with self.subTest(kind=kind, case=case), self.fixture(kind) as f:
                    if case in ("negative_reply", "negative_unchanged_with_income"):
                        f.f.executor.reply = lua_table(f.h.lua, {"ok": False})
                    f.begin()
                    action = f.f.runtime.checkpoint.Records(f.f.runtime.checkpoint)[1].actionKey
                    raw = self.after(f, kind)
                    if case == "equal_clock": raw.native.serverNow = 1001
                    elif case == "old_clock": raw.native.serverNow = 1000
                    elif case == "missing_clock": raw.native.serverNow = None
                    elif case == "wrong_scope": raw.account = "other-account"
                    elif case == "partial_sync": raw.native.fullSync = False
                    elif case == "nonfinite_cash": raw.native.cash = float("inf")
                    elif case in ("missing_effect", "cash_only_debit", "negative_unchanged_with_income"):
                        cash = (20000 if kind == "crewHire" else 400) if case == "cash_only_debit" else (30001 if kind == "crewHire" else 501)
                        raw = f.raw(2, False, cash) if kind == "crewHire" else f.raw(2, cash, False)
                    self.observe(f, raw)
                    self.held(f, action)

    def test_hire_passive_cash_requires_real_new_returned_identity_and_stable_other_roster(self):
        for case in ("missing_returned_id", "missing_replica_id", "replaced_member", "changed_other", "duplicate_new_id"):
            with self.subTest(case=case), self.fixture("crewHire") as f:
                if case == "missing_returned_id": f.f.executor.reply.member.healId = None
                f.begin()
                action = f.f.runtime.checkpoint.Records(f.f.runtime.checkpoint)[1].actionKey
                raw = self.after(f, "crewHire")
                if case == "missing_replica_id": raw.native.crew[2].healId = None
                elif case == "replaced_member": raw.native.crew[2].healId = "replacement"
                elif case == "changed_other": raw.native.crew[3].name = "Changed"
                elif case == "duplicate_new_id": raw.native.crew[3].healId = "new-member"
                self.observe(f, raw)
                self.held(f, action)

    def test_training_passive_cash_requires_original_member_and_exact_time_or_level(self):
        for case in ("replacement", "wrong_target", "early_timer", "late_timer", "expired_timer", "early_completion", "wrong_level"):
            with self.subTest(case=case), self.fixture("crewTrain") as f:
                f.begin()
                action = f.f.runtime.checkpoint.Records(f.f.runtime.checkpoint)[1].actionKey
                raw = self.after(f, "crewTrain", completed=case in ("early_completion", "wrong_level"))
                if case == "replacement": raw.native.crew[2].healId = "replacement"
                elif case == "wrong_target": raw.native.crew[2].training.to = 2
                elif case == "early_timer": raw.native.crew[2].training.endsAt = 1300
                elif case == "late_timer": raw.native.crew[2].training.endsAt = 1303
                elif case == "expired_timer": raw.native.serverNow = 1302
                elif case == "early_completion": raw.native.serverNow = 1300
                elif case == "wrong_level": raw.native.crew[2].train = 2
                self.observe(f, raw)
                self.held(f, action)
