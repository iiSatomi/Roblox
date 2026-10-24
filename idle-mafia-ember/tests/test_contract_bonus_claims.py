"""Completion bonuses are separate from entry claims and purchases."""
from datetime import datetime, timezone
import unittest

from engine_harness import Harness, lua_table


NOW = int(datetime(2026, 10, 21, 12, tzinfo=timezone.utc).timestamp())


class ContractBonusClaimTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.context = self.h.load("src/game/Context.luau").new(self.h.contracts)
        self.reader = self.h.load("src/game/ContractBonusesState.luau")
        self.planner = self.h.load("src/features/ContractBonuses.luau")
        self.evidence = self.h.load("src/features/ContractBonusesEvidence.luau")

    def raw(self, revision=1, daily=None, weekly=None,
            daily_claimed=False, weekly_claimed=False,
            day_reset=NOW + 3600, week_reset=NOW + 86400):
        daily = daily if daily is not None else [
            {"id": "d" + str(i), "claimed": True} for i in range(1, 6)]
        weekly = weekly if weekly is not None else [
            {"id": "w" + str(i), "claimed": True} for i in range(1, 6)]
        return self.h.snapshot(revision=revision,
            native={"fullSync": True, "serverNow": NOW,
                    "contracts": {"daily": daily, "weekly": weekly,
                                  "bonusClaimed": daily_claimed,
                                  "weeklyBonusClaimed": weekly_claimed},
                    "derived": {"contractDayReset": day_reset,
                                "contractWeekReset": week_reset}},
            contractConfig={"dailyTiers": [1, 1, 2, 2, 3],
                            "weeklyTiers": [4, 4, 4, 4, 4]},
            contractBonusConfig={"daily": {"seals": 2,
                                            "energyRefill": True},
                                 "weekly": {"seals": 12,
                                            "crate": "crate_fixervault"}},
            catalogKey="contracts-build-1")

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

    def test_daily_bonus_claim_and_marker(self):
        before = self.raw()
        proposal, reason = self.proposal(before)
        self.assertIsNone(reason)
        self.assertEqual(proposal["feature"], "bonuses")
        self.assertEqual(proposal["intent"]["command"], "claimbonus")
        self.assertEqual(proposal["intent"]["rewardKind"], "energyRefill")
        baseline, reason = self.evidence.capture(proposal, before)
        self.assertIsNone(reason)
        header, _ = self.h.contracts.validateSnapshot(before,
            lua_table(self.h.lua, self.h.session))
        ok = lua_table(self.h.lua, {"ok": True})
        self.assertEqual(self.evidence.evaluate(proposal, header,
            self.raw(2), ok, baseline), "pending")
        self.assertEqual(self.evidence.evaluate(proposal, header,
            self.raw(2, daily_claimed=True), ok, baseline), "confirmed")

    def test_weekly_bonus_and_legacy_single_row(self):
        raw = self.raw(daily_claimed=True,
            weekly={"id": "w_legacy", "claimed": True})
        proposal, reason = self.proposal(raw)
        self.assertIsNone(reason)
        self.assertEqual(proposal["intent"]["command"], "claimweeklybonus")
        self.assertEqual(proposal["intent"]["rewardItem"],
                         "crate_fixervault")
        baseline, reason = self.evidence.capture(proposal, raw)
        self.assertIsNone(reason)
        header, _ = self.h.contracts.validateSnapshot(raw,
            lua_table(self.h.lua, self.h.session))
        after = self.raw(2, daily_claimed=True, weekly_claimed=True,
            weekly={"id": "w_legacy", "claimed": True})
        self.assertEqual(self.evidence.evaluate(proposal, header, after,
            lua_table(self.h.lua, {"ok": True}), baseline), "confirmed")

    def test_incomplete_rows_and_bad_reward_metadata_block(self):
        self.assertIsNone(self.proposal(enabled=False)[0])
        raw = self.raw()
        raw["native"]["contracts"]["daily"][1]["claimed"] = False
        view, reason = self.view(raw)
        self.assertIsNone(reason)
        self.assertEqual(view["ready"][1]["period"], "weekly")
        raw["native"]["contracts"]["weekly"][1]["claimed"] = False
        self.assertEqual(len(self.view(raw)[0]["ready"]), 0)
        bad = self.raw()
        bad["contractBonusConfig"]["weekly"]["crate"] = None
        self.assertIsNone(self.view(bad)[0])
        bad = self.raw(day_reset=NOW + 4)
        self.assertIsNone(self.view(bad)[0])

    def test_reset_change_or_rejected_reply_is_not_success(self):
        before = self.raw()
        proposal, _ = self.proposal(before)
        baseline, _ = self.evidence.capture(proposal, before)
        header, _ = self.h.contracts.validateSnapshot(before,
            lua_table(self.h.lua, self.h.session))
        after = self.raw(2, daily_claimed=True, day_reset=NOW + 86400)
        self.assertEqual(self.evidence.evaluate(proposal, header, after,
            lua_table(self.h.lua, {"ok": True}), baseline), "pending")
        self.assertEqual(self.evidence.evaluate(proposal, header,
            self.raw(2), lua_table(self.h.lua, {"ok": False}), baseline),
            "rejected")


if __name__ == "__main__":
    unittest.main()
