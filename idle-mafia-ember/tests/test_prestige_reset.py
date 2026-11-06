"""Explicit Prestige reset permission, exact outcomes and restart evidence."""
import unittest

from engine_harness import Harness, lua_table


class PrestigeResetTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.reader = self.h.load("src/game/PrestigeState.luau").new(
            lua_table(self.h.lua, {"PRESTIGE": {"maxRank": 6,
                "levelByRank": [200, 200, 200, 210, 220, 230]}}),
            "a" * 64, "release-a")
        self.module = self.h.load("src/tabs/prestige/PrestigeReset.luau")
        self.reset = self.module.new(self.reader)
        self.settings = lua_table(self.h.lua, {"enabled": True,
            "allowReset": True, "targetRank": 1, "maxResets": 1})

    def snapshot(self, rank=0, level=200, xp=25, revision=1, **changes):
        raw = self.h.snapshot(revision=revision, native={"fullSync": True,
            "prestige": rank, "level": level, "xp": xp, "serverNow": revision},
            **changes)
        proof = {key: raw[key] for key in (
            "session", "account", "place", "release", "revision", "capturedAt")}
        proof.update(attempted=0, controllersClear=True)
        raw.prestigeUsageProof = lua_table(self.h.lua, proof)
        return self.reader.Enrich(self.reader, raw)[0]

    def plan(self, before=None):
        before = self.snapshot() if before is None else before
        view, why = self.reader.read(before, before)
        self.assertIsNone(why)
        proposal, why = self.reset.propose(view, self.settings)
        self.assertIsNone(why)
        return proposal, before

    def test_explicit_reset_describes_one_native_prestige_call(self):
        proposal, _ = self.plan()
        call, reason = self.module.describe(proposal)
        self.assertIsNone(reason)
        self.assertEqual((call.remote, call.method, call.arity),
                         ("PrestigeAction", "InvokeServer", 1))
        self.assertEqual(list(call.args.values()), ["prestige"])
        self.assertEqual(proposal.actionKey, "prestige:0:1")
        self.assertEqual(dict(proposal.resources.items()), {})

    def test_permission_budget_and_native_clear_proof_are_required(self):
        for setting, value in (("enabled", False), ("allowReset", False),
                               ("maxResets", 0)):
            with self.subTest(setting=setting):
                self.setUp()
                self.settings[setting] = value
                before = self.snapshot()
                view = self.reader.read(before, before)[0]
                self.assertIsNone(self.reset.propose(view, self.settings)[0])
        for clear, attempted in ((False, 0), (True, 1)):
            with self.subTest(clear=clear, attempted=attempted):
                self.setUp()
                before = self.snapshot()
                before.prestigeUsageProof.controllersClear = clear
                before.prestigeUsageProof.attempted = attempted
                view = self.reader.read(before, before)[0]
                self.assertIsNone(self.reset.propose(view, self.settings)[0])

    def test_dispatch_capture_rechecks_current_level_and_attempt_usage(self):
        proposal, before = self.plan()
        self.assertIsNotNone(self.reset.capture(proposal, before)[0])
        before.native.xp = 26
        self.assertIsNone(self.reset.capture(proposal, before)[0])
        before.native.xp = 25
        before.prestigeUsageProof.attempted = 1
        self.assertIsNone(self.reset.capture(proposal, before)[0])

    def test_only_matching_reply_and_exact_rank_level_xp_transition_confirms(self):
        proposal, before = self.plan()
        baseline = self.reset.capture(proposal, before)[0]
        reply = lua_table(self.h.lua, {"ok": True, "rank": 1})
        after = self.snapshot(rank=1, level=1, xp=0, revision=2)
        self.assertEqual(self.reset.evaluate(proposal, before, after, reply, baseline),
                         "confirmed")
        for rank, level, xp in ((0, 1, 0), (1, 2, 0), (1, 1, 1), (2, 1, 0)):
            with self.subTest(rank=rank, level=level, xp=xp):
                changed = self.snapshot(rank=rank, level=level, xp=xp, revision=2)
                self.assertEqual(self.reset.evaluate(
                    proposal, before, changed, reply, baseline), "pending")
        reply.rank = 2
        self.assertEqual(self.reset.evaluate(proposal, before, after, reply, baseline),
                         "pending")

    def test_rejection_requires_unchanged_state_and_pending_codes_stay_pending(self):
        proposal, before = self.plan()
        baseline = self.reset.capture(proposal, before)[0]
        reply = lua_table(self.h.lua, {"ok": False})
        unchanged = self.snapshot(revision=2)
        self.assertEqual(self.reset.evaluate(proposal, before, unchanged, reply, baseline),
                         "rejected")
        changed = self.snapshot(rank=1, level=1, xp=0, revision=2)
        self.assertEqual(self.reset.evaluate(proposal, before, changed, reply, baseline),
                         "pending")
        for code in ("rate_limited", "busy", "presence"):
            with self.subTest(code=code):
                reply.code = code
                self.assertEqual(self.reset.evaluate(
                    proposal, before, unchanged, reply, baseline), "pending")

    def test_restart_recovery_needs_persisted_reply_and_exact_reset_state(self):
        proposal, before = self.plan()
        saved = lua_table(self.h.lua, {"proposal": proposal, "before": before,
            "baseline": self.reset.capture(proposal, before)[0],
            "reply": {"ok": True, "rank": 1}})
        after = self.snapshot(rank=1, level=1, xp=0, revision=2, session="run-b")
        self.assertEqual(self.reset.recoverSaved(saved, after), "confirmed")
        after.native.xp = 1
        self.assertIsNone(self.reset.recoverSaved(saved, after))
        after.native.xp = 0
        saved.reply = None
        self.assertIsNone(self.reset.recoverSaved(saved, after))


if __name__ == "__main__":
    unittest.main()
