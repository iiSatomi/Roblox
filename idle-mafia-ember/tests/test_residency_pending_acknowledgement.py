"""Owner-approval acknowledgements permit observation, never manufacture a lease."""
import json
import unittest
from contextlib import contextmanager

import test_residency_runtime as fixture
import test_runtime_pending_boundary as boundary_fixture
from engine_harness import lua_table


class ResidencyPendingAcknowledgementTests(unittest.TestCase):
    @contextmanager
    def fixture(self, reply=None, admission="request"):
        f = fixture.ResidencyRuntimeTests(); f.setUp()
        try:
            f.select(**{"residency.custom.allowRequests": True, "residency.custom.allowReplace": True})
            before = f.raw(lease={"d": "old", "rent": 1, "active": True}, admission=admission, elsewhere="Old district")
            f.app.Step(f.app, before)
            f.executor.reply = lua_table(f.h.lua, reply or {"ok": True, "pending": True})
            f.executor.callback()
            yield f, before
        finally:
            f.tearDown()

    def approved(self, f, revision=2):
        return f.raw(revision, {"d": "d1", "rent": 1, "active": True}, status="resident", myRent=1)

    def restart(self, f):
        f.app.Destroy(f.app)
        def wire(v):
            if not hasattr(v, "items"): return v
            entries = dict(v.items())
            if entries and set(entries) == set(range(1, len(entries) + 1)):
                return [wire(entries[i]) for i in range(1, len(entries) + 1)]
            return {k: wire(value) for k, value in entries.items()}
        for key, value in list(f.f.storage.data.items()):
            f.f.storage.data[key] = lua_table(f.h.lua, json.loads(json.dumps(wire(value), allow_nan=False)))
        f.h.session["session"] = "residency-approval-restart"
        f.h.at(0)
        f.h.clock = f.h.load("src/engine/Clock.luau").new(f.h.lua.eval("function() return testNow end"))
        f.app, f.runtime, f.executor = f.f.start_app(with_residency=True)

    def test_json_restart_accepts_later_exact_approved_lease_after_request_acknowledgement(self):
        with self.fixture() as (f, before):
            record = f.runtime.checkpoint.Records(f.runtime.checkpoint)[1]
            action, request = record.actionKey, record.requestId
            f.h.at(46)
            pending = f.raw(3, {"d": "old", "rent": 1, "active": True}, status="pending", myRent=1, admission="request")
            pending.native.serverNow = 1046
            f.app.Step(f.app, pending)
            self.assertEqual(len(f.runtime.checkpoint.Records(f.runtime.checkpoint)), 1)
            self.restart(f)
            after = self.approved(f, 0); after.native.serverNow = 1050
            self.assertIsNotNone(f.runtime.session.broker.Fresh(f.runtime.session.broker, after, 0)[0])
            f.app.Step(f.app, after)
            self.assertEqual(f.runtime.Status(f.runtime).recoveries.residency, "confirmed")
            self.assertEqual(len(f.runtime.checkpoint.Records(f.runtime.checkpoint)), 0)
            self.assertEqual(f.runtime.checkpoint.residencyAttempts, 1)
            self.assertEqual(len(f.executor.calls), 0)
            self.assertIsInstance(action, str)
            self.assertGreater(request, 0)

    def test_unrelated_or_explicit_pending_and_busy_callbacks_hold_even_with_selected_lease(self):
        cases = [({"ok": False, "pending": True}, "request"),
                 ({"ok": True, "pending": True, "code": "pending"}, "request"),
                 ({"ok": True, "pending": True, "code": "busy"}, "request"),
                 ({"ok": True, "code": "pending"}, "request"),
                 ({"ok": True, "code": "busy"}, "request"),
                 ({"ok": True, "pending": True}, "open")]
        for reply, admission in cases:
            with self.subTest(reply=reply, admission=admission), self.fixture(reply, admission) as (f, _):
                action = f.runtime.checkpoint.Records(f.runtime.checkpoint)[1].actionKey
                f.h.at(1); f.app.Step(f.app, self.approved(f))
                self.assertEqual(len(f.runtime.checkpoint.Records(f.runtime.checkpoint)), 1)
                self.assertEqual(f.runtime.checkpoint.Records(f.runtime.checkpoint)[1].actionKey, action)
                self.restart(f)
                after = self.approved(f, 0); after.native.serverNow = 1050
                f.app.Step(f.app, after)
                self.assertEqual(f.runtime.checkpoint.Records(f.runtime.checkpoint)[1].actionKey, action)
                self.assertIsNone(f.runtime.Status(f.runtime).recoveries.residency)
                self.assertEqual(len(f.executor.calls), 0)

    def test_acknowledgement_never_replaces_exact_lease_rent_kind_and_scope_proof(self):
        with self.fixture() as (f, before):
            record = f.runtime.checkpoint.Records(f.runtime.checkpoint)[1]
            data = f.runtime.checkpoint.Recovery(f.runtime.checkpoint, record.actionKey)[0]
            module = f.runtime.features.residency.evidence
            for case in ("unchanged", "rent", "kind", "district", "inactive", "scope", "clock"):
                with self.subTest(case=case):
                    after = self.approved(f)
                    if case == "unchanged": after = f.raw(2, {"d": "old", "rent": 1, "active": True}, status="pending")
                    elif case == "rent": after.native.derived.residency.rent = 2
                    elif case == "kind": after.native.derived.residency.kind = "jobCut"
                    elif case == "district": after.native.derived.residency.d = "other"
                    elif case == "inactive": after.native.derived.residency.active = False
                    elif case == "scope": after.account = "other"
                    else: after.native.serverNow = 1000
                    self.assertEqual(module.evaluate(data.proposal, before, after, data.reply, data.baseline), "pending")

    def test_acknowledgement_requires_original_explicit_request_permission(self):
        with self.fixture() as (f, _):
            row = f.runtime.checkpoint.Records(f.runtime.checkpoint)[1]
            data = f.runtime.checkpoint.Recovery(f.runtime.checkpoint, row.actionKey)[0]
            evidence = f.runtime.features.residency.evidence
            self.assertTrue(evidence.allowsPendingAcknowledgement(data.proposal, data.before, data.reply))
            data.proposal.intent.allowRequests = False
            self.assertFalse(evidence.allowsPendingAcknowledgement(data.proposal, data.before, data.reply))


class PendingHookBoundaryTests(unittest.TestCase):
    def test_hook_throw_or_truthy_nonboolean_cannot_release_ordinary_custody(self):
        for hook in ("function() error('unavailable') end", "function() return 1 end"):
            with self.subTest(hook=hook):
                f = boundary_fixture.RuntimePendingBoundaryTests()
                try:
                    f.prepare({"ok": True, "pending": True})
                    f.spec.evidence.allowsPendingAcknowledgement = f.f.h.lua.eval(hook)
                    f.f.h.at(1); f.f.step(f.f.raw(2), f.f.settings(False, False, False))
                    self.assertEqual(len(f.f.runtime.checkpoint.Records(f.f.runtime.checkpoint)), 1)
                finally:
                    f.tearDown()

    def test_even_a_true_hook_cannot_exempt_negative_or_coded_pending_callbacks(self):
        for reply in ({"ok": False, "pending": True},
                      {"ok": True, "pending": True, "code": "busy"},
                      {"ok": True, "pending": True, "code": "pending"}):
            with self.subTest(reply=reply):
                f = boundary_fixture.RuntimePendingBoundaryTests()
                try:
                    f.prepare(reply)
                    f.spec.evidence.allowsPendingAcknowledgement = f.f.h.lua.eval("function() return true end")
                    f.f.h.at(1); f.f.step(f.f.raw(2), f.f.settings(False, False, False))
                    self.assertEqual(len(f.f.runtime.checkpoint.Records(f.f.runtime.checkpoint)), 1)
                finally:
                    f.tearDown()
