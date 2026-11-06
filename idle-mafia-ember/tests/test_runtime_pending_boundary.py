"""Explicit nonterminal callbacks cannot be settled by an ordinary adapter."""
import unittest

from engine_harness import lua_table
import test_automation_runtime as fixture


class RuntimePendingBoundaryTests(unittest.TestCase):
    def prepare(self, reply, verdict='confirmed'):
        self.f = fixture.AutomationRuntimeTests(); self.f.setUp()
        f = self.f
        self.spec = f.runtime.features.jobs
        self.spec.evidence.evaluate = f.h.lua.eval("function() return '" + verdict + "' end")
        self.spec.recoverSaved = f.h.lua.eval("function() return '" + verdict + "' end")
        f.runtime.Resume(f.runtime)
        self.settings = f.settings(True, False, False)
        f.step(settings=self.settings)
        self.assertEqual(len(f.h.transport.sent), 1)
        f.h.transport.callbacks[1](lua_table(f.h.lua, reply))

    def tearDown(self):
        if getattr(self, 'f', None): self.f.runtime.Close(self.f.runtime)

    def test_pending_callback_retains_record_live_after_timeout_and_during_recovery(self):
        for marker in ({'pending': True}, {'code': 'pending'}):
            for ok in (False, True):
                for verdict in ('rejected', 'confirmed'):
                    with self.subTest(marker=marker, ok=ok, verdict=verdict):
                        self.prepare(dict(marker, ok=ok), verdict)
                        f = self.f; f.h.at(1)
                        f.step(f.raw(2), f.settings(False, False, False))
                        self.assertEqual(len(f.runtime.checkpoint.Records(f.runtime.checkpoint)), 1)
                        self.assertIsNotNone(f.runtime.session.broker.active)
                        f.h.at(45); f.step(f.raw(3), f.settings(False, False, False))
                        f.h.at(46); f.step(f.raw(4), f.settings(False, False, False))
                        self.assertIsNone(f.runtime.session.broker.active)
                        self.assertEqual(len(f.runtime.checkpoint.Records(f.runtime.checkpoint)), 1)
                        self.assertEqual(len(f.h.transport.sent), 1)
                        self.assertIsNone(f.runtime.recoveries.jobs)
                        f.runtime.Close(f.runtime)

    def test_terminal_callback_still_reaches_feature_evaluator(self):
        self.prepare({'ok': True})
        f = self.f; f.h.at(1)
        f.step(f.raw(2), f.settings(False, False, False))
        self.assertEqual(len(f.runtime.checkpoint.Records(f.runtime.checkpoint)), 0)
        self.assertEqual(f.runtime.outcomes.jobs, 'confirmed')

    def test_lifecycle_owner_can_resolve_using_independent_terminal_status(self):
        self.prepare({'ok': True, 'code': 'pending'})
        f = self.f
        # Keep the sent action until the normal deadline; then an independent
        # lifecycle owner can recover it from its own terminal status evidence.
        self.spec.evidence.evaluate = f.h.lua.eval("function() return 'pending' end")
        f.h.at(45); f.step(f.raw(2), f.settings(False, False, False))
        self.spec.lifecycle = f.h.lua.eval("{recover=function() return 'confirmed' end}")
        f.h.at(46); f.step(f.raw(3), f.settings(False, False, False))
        self.assertEqual(len(f.runtime.checkpoint.Records(f.runtime.checkpoint)), 0)
        self.assertEqual(f.runtime.recoveries.jobs, 'confirmed')
        self.assertEqual(len(f.h.transport.sent), 1)
