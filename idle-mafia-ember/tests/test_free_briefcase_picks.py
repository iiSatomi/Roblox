"""Free-only Briefcase selection, with source and board proof."""
from datetime import datetime, timezone
import unittest

from engine_harness import Harness, lua_table


NOW = int(datetime(2026, 10, 21, 12, tzinfo=timezone.utc).timestamp())


class FreeBriefcasePickTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.context = self.h.load("src/game/Context.luau").new(self.h.contracts)
        self.reader = self.h.load("src/game/FreeBriefcasesState.luau")
        self.planner = self.h.load("src/features/FreeBriefcases.luau")
        self.evidence = self.h.load("src/features/FreeBriefcasesEvidence.luau")

    def raw(self, revision=1, free=2, opened=None, season=7,
            board=3, now=NOW, end_at=NOW + 3600):
        return self.h.snapshot(revision=revision,
            native={"fullSync": True, "serverNow": now,
                    "briefcase": {"season": season, "free": free,
                                  "board": {"n": board, "cfg": 0,
                                            "opened": opened if opened is not None
                                            else {"c1": {"p": "cash2"}}}}},
            caseEvent={"season": season, "endAt": end_at},
            briefcaseRules={"cases": 12, "version": 0},
            catalogKey="cases-build-1")

    def view(self, raw):
        context, reason = self.context.Read(self.context, raw,
            lua_table(self.h.lua, self.h.session), 0, 2)
        self.assertIsNone(reason)
        return self.reader.read(raw, context)

    def proposal(self, raw=None, enabled=True):
        view, reason = self.view(raw or self.raw())
        self.assertIsNone(reason)
        return self.planner.propose(view,
            lua_table(self.h.lua, {"enabled": enabled}))

    def test_first_unopened_free_pick_and_exact_proof(self):
        before = self.raw()
        proposal, reason = self.proposal(before)
        self.assertIsNone(reason)
        self.assertEqual(proposal["intent"]["index"], 2)
        baseline, reason = self.evidence.capture(proposal, before)
        self.assertIsNone(reason)
        header, _ = self.h.contracts.validateSnapshot(before,
            lua_table(self.h.lua, self.h.session))
        ok = lua_table(self.h.lua, {"ok": True, "source": "free"})
        self.assertEqual(self.evidence.evaluate(proposal, header,
            self.raw(2), ok, baseline), "pending")
        after = self.raw(2, free=1,
            opened={"c1": {"p": "cash2"}, "c2": {"p": "gold3"}})
        self.assertEqual(self.evidence.evaluate(proposal, header,
            after, ok, baseline), "confirmed")

    def test_updated_twelve_free_picks_are_not_clamped_to_old_limit(self):
        proposal, reason = self.proposal(self.raw(free=12, opened={}))
        self.assertIsNone(reason)
        self.assertEqual(proposal["intent"]["free"], 12)
        self.assertEqual(proposal["intent"]["index"], 1)

    def test_key_source_and_unreplicated_reply_do_not_confirm(self):
        before = self.raw()
        proposal, _ = self.proposal(before)
        baseline, _ = self.evidence.capture(proposal, before)
        header, _ = self.h.contracts.validateSnapshot(before,
            lua_table(self.h.lua, self.h.session))
        after = self.raw(2, free=1,
            opened={"c1": {"p": "cash2"}, "c2": {"p": "gold3"}})
        self.assertEqual(self.evidence.evaluate(proposal, header, after,
            lua_table(self.h.lua, {"ok": True, "source": "key"}), baseline),
            "pending")
        self.assertEqual(self.evidence.evaluate(proposal, header, before,
            lua_table(self.h.lua, {"ok": True, "source": "free"}), baseline),
            "pending")

    def test_closed_event_zero_free_bad_board_and_disable_block(self):
        self.assertIsNone(self.proposal(enabled=False)[0])
        self.assertIsNone(self.view(self.raw(free=0))[0])
        self.assertIsNone(self.view(self.raw(end_at=NOW))[0])
        bad = self.raw()
        bad["native"]["briefcase"]["board"]["cfg"] = 2
        self.assertIsNone(self.view(bad)[0])
        bad = self.raw()
        bad["native"]["briefcase"]["board"]["opened"]["c13"] = {"p": "cash2"}
        self.assertIsNone(self.view(bad)[0])

    def test_season_or_board_change_and_failure_wait(self):
        before = self.raw()
        proposal, _ = self.proposal(before)
        baseline, _ = self.evidence.capture(proposal, before)
        header, _ = self.h.contracts.validateSnapshot(before,
            lua_table(self.h.lua, self.h.session))
        changed = self.raw(2, free=1, board=4,
            opened={"c2": {"p": "gold3"}})
        self.assertEqual(self.evidence.evaluate(proposal, header, changed,
            lua_table(self.h.lua, {"ok": True, "source": "free"}), baseline),
            "pending")
        changed = self.raw(2, free=1, season=8,
            opened={"c2": {"p": "gold3"}})
        self.assertEqual(self.evidence.evaluate(proposal, header, changed,
            lua_table(self.h.lua, {"ok": True, "source": "free"}), baseline),
            "pending")
        self.assertEqual(self.evidence.evaluate(proposal, header,
            self.raw(2), lua_table(self.h.lua, {"ok": False}), baseline),
            "rejected")

    def test_native_cleared_reply_and_exact_next_empty_board_confirm_a_free_pick(self):
        before = self.raw()
        proposal, _ = self.proposal(before)
        baseline, _ = self.evidence.capture(proposal, before)
        header, _ = self.h.contracts.validateSnapshot(before, lua_table(self.h.lua, self.h.session))
        after = self.raw(2, free=1, board=4, opened={})
        reply = lua_table(self.h.lua, {"ok": True, "source": "free", "cleared": True,
                                     "board": 3, "prize": "golden"})
        self.assertEqual(self.evidence.evaluate(proposal, header, after, reply, baseline), "confirmed")
        for change in ({"board": 2}, {"cleared": False}, {"source": "key"}, {"prize": ""}):
            with self.subTest(change=change):
                bad = lua_table(self.h.lua, {"ok": True, "source": "free", "cleared": True,
                    "board": 3, "prize": "golden", **change})
                self.assertEqual(self.evidence.evaluate(proposal, header, after, bad, baseline), "pending")
        self.assertEqual(self.evidence.evaluate(proposal, header,
            self.raw(2, free=1, board=5, opened={}), reply, baseline), "pending")

    def test_pending_and_transient_callbacks_cannot_confirm_or_terminally_reject(self):
        before = self.raw()
        proposal, _ = self.proposal(before)
        baseline, _ = self.evidence.capture(proposal, before)
        header, _ = self.h.contracts.validateSnapshot(before, lua_table(self.h.lua, self.h.session))
        reveal = self.raw(2, free=1, opened={"c1": {"p": "cash2"}, "c2": {"p": "gold3"}})
        cleared = self.raw(2, free=1, board=4, opened={})
        for signal in ({"pending": True}, {"code": "rate_limited"}, {"code": "busy"}, {"code": "presence"}):
            for ok in (True, False):
                for observed, state in ((reveal, "revealed"), (cleared, "cleared"), (self.raw(2), "unchanged")):
                    with self.subTest(signal=signal, ok=ok, state=state):
                        reply = lua_table(self.h.lua, {"ok": ok, "source": "free", "cleared": True,
                            "board": 3, "prize": "golden", **signal})
                        self.assertEqual(self.evidence.evaluate(proposal, header, observed, reply, baseline), "pending")


if __name__ == "__main__":
    unittest.main()
