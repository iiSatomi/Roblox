"""A reset rejection needs new observation while retaining the real busy lease."""
import unittest
import test_native_prestige_app as fixture
from engine_harness import lua_table


class PrestigeObservationCustodyTests(unittest.TestCase):
    def setUp(self):
        self.g = fixture.NativePrestigeAppTests(); self.g.setUp(); self.g.attach_real_owner()
        self.f, self.h = self.g.f, self.g.h

    def tearDown(self): self.g.tearDown()

    def test_negative_original_sync_keeps_native_busy_and_durable_attempt_until_new_sync(self):
        f = self.f; f.begin(); f.executor.apply = False
        f.executor.reply = lua_table(self.h.lua, {'ok': False, 'code': 'requirements'})
        f.send(); f.app.Step(f.app, f.raw())
        self.assertEqual(len(f.runtime.checkpoint.Records(f.runtime.checkpoint)), 1)
        self.assertEqual(self.h.lua.eval('type')(self.g.port.busy), 'table')
        self.h.at(.25); f.app.Step(f.app, f.raw(revision=2, at=.25))
        self.assertEqual(f.runtime.Status(f.runtime).outcomes.prestige, 'rejected')
        self.assertEqual(len(f.runtime.checkpoint.Records(f.runtime.checkpoint)), 0)
        self.assertFalse(self.g.port.busy)
        self.assertEqual(f.runtime.checkpoint.prestigeAttempts, 1)
        self.assertEqual(f.executor.calls, 1)

    def test_saved_negative_equal_clock_stays_held_until_a_strictly_later_native_sync(self):
        f = self.f; f.begin(); f.executor.apply = False
        f.executor.reply = lua_table(self.h.lua, {'ok': False})
        f.send(); f.restart_all_off(); f.app.Step(f.app, f.raw(revision=0))
        self.assertEqual(len(f.runtime.checkpoint.Records(f.runtime.checkpoint)), 1)
        self.h.at(.25); f.app.Step(f.app, f.raw(revision=1, at=.25))
        self.assertEqual(f.runtime.Status(f.runtime).recoveries.prestige, 'rejected')
        self.assertEqual(len(f.runtime.checkpoint.Records(f.runtime.checkpoint)), 0)
        self.assertEqual(f.executor.calls, 0)
        self.assertEqual(f.runtime.checkpoint.prestigeAttempts, 1)

    def test_pending_code_exact_reset_effect_cannot_confirm_or_recover_a_reset(self):
        f = self.f; f.begin()
        f.executor.reply = lua_table(self.h.lua, {'ok': True, 'rank': 1, 'code': 'pending'})
        f.send(); self.h.at(.25)
        f.app.Step(f.app, f.raw(rank=1, level=1, xp=0, revision=2, at=.25))
        self.assertEqual(len(f.runtime.checkpoint.Records(f.runtime.checkpoint)), 1)
        self.h.at(46); f.app.Step(f.app, f.raw(rank=1, level=1, xp=0, revision=3, at=46))
        f.restart_all_off(); self.h.at(47)
        f.app.Step(f.app, f.raw(rank=1, level=1, xp=0, revision=0, at=47))
        self.assertEqual(len(f.runtime.checkpoint.Records(f.runtime.checkpoint)), 1)
        self.assertEqual(f.executor.calls, 0)
        self.assertEqual(f.runtime.checkpoint.prestigeAttempts, 1)


if __name__ == '__main__': unittest.main()
