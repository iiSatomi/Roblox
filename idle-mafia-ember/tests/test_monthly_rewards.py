"""UTC monthly claim stays dormant when the saved native config is disabled."""
from datetime import datetime, timezone
import unittest

from engine_harness import Harness, lua_table


def utc(year, month, day, hour=12, minute=0):
    return int(datetime(year, month, day, hour, minute,
                        tzinfo=timezone.utc).timestamp())


class MonthlyRewardsTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.context = self.h.load("src/game/Context.luau").new(self.h.contracts)
        self.reader = self.h.load("src/game/MonthlyRewardsState.luau")
        self.planner = self.h.load("src/features/MonthlyRewards.luau")
        self.evidence = self.h.load("src/features/MonthlyRewardsEvidence.luau")

    def raw(self, revision=1, when=None, enabled=True, monthly=None, **extra):
        data = {"native": {"fullSync": True,
                           "serverNow": when if when is not None else utc(2026, 10, 20),
                           "monthly": monthly},
                "monthlyConfig": {"enabled": enabled}}
        data.update(extra)
        return self.h.snapshot(revision=revision, **data)

    def view(self, raw):
        context, reason = self.context.Read(
            self.context, raw, lua_table(self.h.lua, self.h.session), 0, 2)
        self.assertIsNone(reason)
        return self.reader.read(raw, context)

    def proposal(self, raw=None, enabled=True):
        view, reason = self.view(raw or self.raw())
        self.assertIsNone(reason)
        return self.planner.propose(
            view, lua_table(self.h.lua, {"enabled": enabled}))

    def test_saved_disabled_config_and_midnight_block(self):
        self.assertIsNone(self.view(self.raw(enabled=False))[0])
        self.assertIsNone(self.view(self.raw(when=utc(2026, 10, 20, 0)))[0])
        self.assertIsNone(self.view(self.raw(when=utc(2026, 11, 1, 0)))[0])
        self.assertIsNone(self.view(self.raw(native={"fullSync": False}))[0])
        self.assertIsNone(self.proposal(enabled=False)[0])

    def test_exact_utc_day_and_month_limit(self):
        proposal, reason = self.proposal()
        self.assertIsNone(reason)
        self.assertEqual(proposal["feature"], "monthlyRewards")
        self.assertEqual(proposal["intent"]["month"], "2026-10")
        self.assertEqual(proposal["intent"]["today"], 2026293)
        self.assertEqual(proposal["intent"]["nextDay"], 1)
        self.assertEqual(len(list(proposal["resources"].items())), 0)
        feb, reason = self.view(self.raw(when=utc(2028, 2, 29)))
        self.assertIsNone(reason)
        self.assertEqual(feb["total"], 29)
        self.assertIsNone(self.view(self.raw(
            when=utc(2026, 10, 20), monthly={"month": "2026-10",
                                               "claimed": 30, "lastDay": 2026292}))[0])

    def test_claimed_today_and_malformed_record_block(self):
        today = {"month": "2026-10", "claimed": 1, "lastDay": 2026293}
        self.assertIsNone(self.view(self.raw(monthly=today))[0])
        self.assertIsNone(self.view(self.raw(monthly={"month": "2026-10",
                                                       "claimed": -1}))[0])
        self.assertIsNone(self.view(self.raw(monthly="not a record"))[0])
        old = {"month": "2026-09", "claimed": 27, "lastDay": 2026273}
        view, reason = self.view(self.raw(monthly=old))
        self.assertIsNone(reason)
        self.assertEqual(view["claimed"], 0)

    def test_exact_newer_claim_marker_required(self):
        before = self.raw()
        proposal, _ = self.proposal(before)
        baseline, reason = self.evidence.capture(proposal, before)
        self.assertIsNone(reason)
        header, _ = self.h.contracts.validateSnapshot(
            before, lua_table(self.h.lua, self.h.session))
        ok = lua_table(self.h.lua, {"ok": True})
        self.assertEqual(self.evidence.evaluate(
            proposal, header, self.raw(2), ok, baseline), "pending")
        after = self.raw(2, monthly={"month": "2026-10",
                                      "claimed": 1, "lastDay": 2026293})
        self.assertEqual(self.evidence.evaluate(
            proposal, header, after, ok, baseline), "confirmed")
        wrong_day = self.raw(2, monthly={"month": "2026-10",
                                          "claimed": 1, "lastDay": 2026294})
        self.assertEqual(self.evidence.evaluate(
            proposal, header, wrong_day, ok, baseline), "pending")

    def test_rejection_and_month_rollover_ambiguity(self):
        before = self.raw()
        proposal, _ = self.proposal(before)
        baseline, _ = self.evidence.capture(proposal, before)
        header, _ = self.h.contracts.validateSnapshot(
            before, lua_table(self.h.lua, self.h.session))
        no = lua_table(self.h.lua, {"ok": False})
        self.assertEqual(self.evidence.evaluate(
            proposal, header, self.raw(2), no, baseline), "rejected")
        rolled = self.raw(2, when=utc(2026, 11, 1, 12),
                          monthly={"month": "2026-11", "claimed": 1,
                                   "lastDay": 2026305})
        self.assertEqual(self.evidence.evaluate(
            proposal, header, rolled,
            lua_table(self.h.lua, {"ok": True}), baseline), "pending")


if __name__ == "__main__":
    unittest.main()
