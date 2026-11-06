"""Transient replies preserve both stores of one owned replacement cycle."""
import json
import unittest
from contextlib import contextmanager

import test_crew_runtime as fixture
from engine_harness import lua_table
from test_redundant_store import plain


class CrewReplacementTransientTests(unittest.TestCase):
    @contextmanager
    def sent(self, phase, code, ok):
        f = fixture.CrewRuntimeTests(); f.setUp()
        try:
            f.choose(); f.step()
            if phase == 'hire':
                f.drain(); f.step(revision=2, stage='empty')
            reply = {'ok': ok, 'code': code}
            if phase == 'hire' and ok:
                reply.update(index=2, member={'name': 'New', 'rarity': 2, 'atk': 5, 'def': 6})
            f.executor.reply = lua_table(f.h.lua, reply)
            f.drain()
            self.phase = phase
            self.action = f.owner.Active(f.owner).proposal.actionKey
            self.calls = len(f.executor.calls)
            self.prior_outcome = f.runtime.Status(f.runtime).outcomes.crewRoll
            yield f
        finally:
            f.tearDown()

    def state(self, ok):
        if self.phase == 'dismiss': return ('empty' if ok else 'member'), 50000
        return ('hired' if ok else 'empty'), (40000 if ok else 50000)

    def held(self, f):
        record = f.owner.Active(f.owner)
        self.assertIsNotNone(record)
        self.assertEqual(record.stage, 'sentDismiss' if self.phase == 'dismiss' else 'sentHire')
        self.assertEqual(record.proposal.actionKey, self.action)
        self.assertEqual((f.owner.Usage(f.owner).attempted, f.owner.Usage(f.owner).spent),
                         (1, 0 if self.phase == 'dismiss' else 10000))
        pending = f.runtime.checkpoint.Records(f.runtime.checkpoint)
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[1].actionKey, self.action)
        self.assertEqual(len(f.executor.calls), self.calls)

    def test_pending_busy_presence_preserve_positive_and_negative_lifecycle_custody(self):
        for phase in ('dismiss', 'hire'):
            for code in ('pending', 'busy', 'presence'):
                for ok in (False, True):
                    with self.subTest(phase=phase, code=code, ok=ok), self.sent(phase, code, ok) as f:
                        stage, cash = self.state(ok)
                        f.step(revision=3, stage=stage, cash=cash); self.held(f)
                        self.assertEqual(f.runtime.Status(f.runtime).outcomes.crewRoll, self.prior_outcome)
                        f.step(revision=48, stage=stage, cash=cash); f.drain(); self.held(f)
                        self.assertEqual(f.runtime.Status(f.runtime).outcomes.crewRoll, 'skipped_unconfirmed')
                        raw = f.f.raw(revision=48, stage=stage, cash=cash)
                        funds = f.runtime.reservationOwner.Held(f.runtime.reservationOwner, raw)[0].funds
                        self.assertGreaterEqual(funds.cash, 10000)
                        for key, saved in list(f.storage.data.items()):
                            f.storage.data[key] = lua_table(f.h.lua, json.loads(json.dumps(plain(saved))))
                        f.restart(); f.step(revision=49, stage=stage, cash=cash)
                        f.choose(); f.step(revision=50, stage=stage, cash=cash); f.drain(); self.held(f)
                        self.assertIsNone(f.runtime.Status(f.runtime).recoveries.crewRoll)
                        self.assertFalse(f.owner.KnownUnsent(f.owner))
                        self.assertFalse(f.owner.CancelUnsent(f.owner, self.action)[0])
                        f.app.Pause(f.app)
                        if phase == 'hire':
                            current = f.f.raw(revision=50, stage=stage, cash=cash)
                            self.assertFalse(f.owner.ReleaseRejectedHire(f.owner, current, 50)[0])
                        preview = f.app.PreviewFeatureRecovery(f.app, 'crewRoll')[0]
                        self.assertIsNone(preview, 'A transient returned action cannot be reviewed as unsent/rejected')


if __name__ == '__main__': unittest.main()
