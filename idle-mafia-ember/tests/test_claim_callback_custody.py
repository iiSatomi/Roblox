"""Claim callbacks cannot settle pending/transient work or stale Sync evidence."""
import unittest
import test_group_bonus as group_fixture
import test_earned_trophies as trophy_fixture
import test_contract_entry_claims as entry_fixture
import test_contract_bonus_claims as bonus_fixture
import test_global_boss_claim as global_fixture
import test_automation_runtime as runtime_fixture
from engine_harness import lua_table


KINDS = ('groupBonus', 'trophies', 'contracts', 'bonuses', 'globalBossClaim')
CASES = {'groupBonus': group_fixture.GroupBonusTests,
         'trophies': trophy_fixture.EarnedTrophyTests,
         'contracts': entry_fixture.ContractEntryClaimTests,
         'bonuses': bonus_fixture.ContractBonusClaimTests,
         'globalBossClaim': global_fixture.GlobalBossClaimTests}


def frame(f, kind, revision=1, awarded=False):
    if kind == 'groupBonus': raw = f.raw(revision, claimed=awarded)
    elif kind == 'trophies':
        raw = f.raw(revision, ready=['t_grudgeledger'] if awarded else None,
                    bound={'t_eldersignet': 1} if awarded else None)
    elif kind == 'contracts':
        raw = f.raw(revision)
        raw.native.contracts.daily[1].claimed = awarded
    elif kind == 'bonuses': raw = f.raw(revision, daily_claimed=awarded)
    else: raw = f.raw(revision, claimed=awarded, attempts=1 if awarded else 0)
    if raw.native.serverNow is None: raw.native.serverNow = 2000100
    for key in ('globalBossProof', 'localUserIdProof', 'globalClaimUsageProof'):
        if raw[key] is not None: raw[key].capturedAt = raw.capturedAt
    return raw


def proposal(f, kind, before):
    if kind == 'groupBonus':
        view, why = f.view(before); assert why is None, why
        return f.planner.propose(view, lua_table(f.h.lua, {'enabled': True}))
    if kind == 'trophies': return f.propose(before)
    return f.proposal(before)


def reply(f, **extra):
    return lua_table(f.h.lua, {'ok': True, 'medals': 2,
        'won': [{'i': 'crate_loot', 'n': 2}], **extra})


class ClaimCallbackCustodyTests(unittest.TestCase):
    def case(self, kind):
        f = CASES[kind](); f.setUp()
        before = frame(f, kind)
        p, why = proposal(f, kind, before); self.assertIsNone(why)
        baseline, why = f.evidence.capture(p, before); self.assertIsNone(why)
        return f, before, p, baseline

    def test_transient_callbacks_hold_even_with_new_exact_award_or_unchanged_sync(self):
        for kind in KINDS:
            for transient in ({'pending': True}, {'code': 'pending'}, {'code': 'no_pending'},
                              {'code': 'rate_limited'}, {'code': 'busy'}, {'code': 'presence'}):
                for ok in (False, True):
                    for awarded in (False, True):
                        with self.subTest(kind=kind, transient=transient, ok=ok, awarded=awarded):
                            f, before, p, baseline = self.case(kind)
                            f.h.at(1)
                            self.assertEqual(f.evidence.evaluate(p, before, frame(f, kind, 2, awarded),
                                reply(f, ok=ok, **transient), baseline), 'pending')

    def test_terminal_negative_needs_newer_unchanged_sync(self):
        for kind in KINDS:
            with self.subTest(kind=kind):
                f, before, p, baseline = self.case(kind)
                self.assertEqual(f.evidence.evaluate(p, before, frame(f, kind),
                    reply(f, ok=False), baseline), 'pending')
                f.h.at(1)
                self.assertEqual(f.evidence.evaluate(p, before, frame(f, kind, 2),
                    reply(f, ok=False), baseline), 'rejected')
                self.assertEqual(f.evidence.evaluate(p, before, frame(f, kind, 2, True),
                    reply(f, ok=False), baseline), 'pending')

    def test_trophy_negative_cannot_release_changed_selected_copy_custody(self):
        f, before, p, baseline = self.case('trophies')
        for ready, count in ((True, 1), (False, 0), (False, 2)):
            with self.subTest(ready=ready, count=count):
                after = frame(f, 'trophies', 2)
                after.native.derived.trophyReady = lua_table(f.h.lua, ['t_eldersignet'] if ready else [])
                after.native.inventoryBound.t_eldersignet = count
                self.assertEqual(f.evidence.evaluate(p, before, after, reply(f, ok=False), baseline), 'pending')

    def test_ordinary_terminal_positive_remains_compatible(self):
        for kind in KINDS:
            with self.subTest(kind=kind):
                f, before, p, baseline = self.case(kind); f.h.at(1)
                self.assertEqual(f.evidence.evaluate(p, before, frame(f, kind, 2, True),
                    reply(f), baseline), 'confirmed')


class ClaimCallbackAppTests(unittest.TestCase):
    def prepare(self, kind, returned):
        f = runtime_fixture.AutomationRuntimeTests(); f.setUp()
        source = CASES[kind](); source.setUp(); source.h = f.h
        executor = f.install_native_adapter(); executor.reply = reply(source, **returned)
        app = f.start_test_app(); self.addCleanup(lambda: app.Destroy(app))
        app.Set(app, kind + '.enabled', True); app.Resume(app)
        before = frame(source, kind)
        app.Step(app, before); executor.Drain(executor)
        self.assertEqual(len(executor.calls), 1, dict(f.runtime.Status(f.runtime).reasons.items()))
        f.original_key = f.runtime.checkpoint.Records(f.runtime.checkpoint)[1].actionKey
        return f, source, app, executor

    def test_actual_app_transient_reply_preserves_checkpoint_across_timeout_and_restart(self):
        for kind in KINDS:
            for returned, awarded in (({'ok': True, 'pending': True}, True),
                                      ({'ok': False, 'code': 'busy'}, False)):
                with self.subTest(kind=kind, reply=returned):
                    f, source, app, executor = self.prepare(kind, returned)
                    f.h.at(1); app.Step(app, frame(source, kind, 2, awarded))
                    records = f.runtime.checkpoint.Records(f.runtime.checkpoint)
                    self.assertEqual(len(records), 1)
                    action_key = records[1].actionKey
                    self.assertEqual(action_key, f.original_key)
                    f.h.at(46); after = frame(source, kind, 3, awarded)
                    app.Step(app, after)
                    self.assertEqual(len(f.runtime.checkpoint.Records(f.runtime.checkpoint)), 1)
                    self.assertEqual(len(executor.calls), 1)
                    if kind == 'globalBossClaim':
                        self.assertTrue(f.runtime.reservationOwner.Held(f.runtime.reservationOwner, after)[0].allItems)
                    prior = f.runtime
                    app.Destroy(app)
                    f.h.session['session'] = 'after-restart'
                    f.runtime = f.h.load('src/engine/AutomationRuntime.luau').new(lua_table(f.h.lua, {
                        'clock': f.h.clock, 'transport': prior.session.broker.transport,
                        'storage': f.storage, 'identity': f.h.session, 'modules': prior.modules,
                        'features': [prior.features[kind]], 'featurePages': {kind: 'rewards'}}))
                    restarted = f.start_test_app(); self.addCleanup(lambda a=restarted: a.Destroy(a))
                    restarted.Set(restarted, kind + '.enabled', True); restarted.Resume(restarted)
                    f.h.at(47); observed = frame(source, kind, 1, awarded)
                    observed.native.serverNow += 47
                    restarted.Step(restarted, observed); executor.Drain(executor)
                    self.assertEqual(len(executor.calls), 1)
                    records = f.runtime.checkpoint.Records(f.runtime.checkpoint)
                    self.assertEqual(len(records), 1)
                    self.assertEqual(records[1].actionKey, action_key)
                    saved, why = f.runtime.checkpoint.Recovery(f.runtime.checkpoint, action_key)
                    self.assertIsNone(why)
                    self.assertEqual(saved.reply.ok, returned['ok'])
                    self.assertEqual(saved.reply.pending, returned.get('pending'))
                    self.assertEqual(saved.reply.code, returned.get('code'))

    def test_actual_app_terminal_unchanged_rejection_resolves_only_after_new_sync(self):
        for kind in KINDS:
            with self.subTest(kind=kind):
                f, source, app, executor = self.prepare(kind, {'ok': False})
                app.Step(app, frame(source, kind))
                self.assertEqual(len(f.runtime.checkpoint.Records(f.runtime.checkpoint)), 1)
                f.h.at(1); app.Step(app, frame(source, kind, 2))
                self.assertEqual(f.runtime.Status(f.runtime).outcomes[kind], 'rejected')
                self.assertEqual(len(f.runtime.checkpoint.Records(f.runtime.checkpoint)), 0)
                self.assertEqual(len(executor.calls), 1)


if __name__ == '__main__': unittest.main()
