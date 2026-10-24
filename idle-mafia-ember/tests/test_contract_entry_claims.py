"""Contract entry claims require stable row identity and reset window."""
from datetime import datetime, timezone
import unittest

from engine_harness import Harness, lua_table


NOW = int(datetime(2026, 10, 21, 12, tzinfo=timezone.utc).timestamp())


class ContractEntryClaimTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.context = self.h.load("src/game/Context.luau").new(self.h.contracts)
        self.reader = self.h.load("src/game/ContractEntriesState.luau")
        self.planner = self.h.load("src/features/ContractEntries.luau")
        self.evidence = self.h.load("src/features/ContractEntriesEvidence.luau")

    def raw(self, revision=1, daily=None, weekly=None, now=NOW,
            day_reset=NOW + 3600, week_reset=NOW + 86400):
        daily = daily if daily is not None else [
            {"id": "c_rounds", "done": True, "claimed": False},
            {"id": "c_cash", "done": False, "claimed": False},
            {"id": "c_hire", "done": False, "claimed": False},
            {"id": "c_jobs", "done": False, "claimed": False},
            {"id": "c_boss", "done": False, "claimed": False},
        ]
        weekly = weekly if weekly is not None else [
            {"id": "w_rounds", "done": False, "claimed": False},
            {"id": "w_cash", "done": False, "claimed": False},
            {"id": "w_hire", "done": False, "claimed": False},
            {"id": "w_jobs", "done": False, "claimed": False},
            {"id": "w_boss", "done": False, "claimed": False},
        ]
        return self.h.snapshot(revision=revision,
            native={"fullSync": True, "serverNow": now,
                    "contracts": {"daily": daily, "weekly": weekly},
                    "derived": {"contractDayReset": day_reset,
                                "contractWeekReset": week_reset}},
            contractConfig={"dailyTiers": [1, 1, 2, 2, 3],
                            "weeklyTiers": [4, 4, 4, 4, 4]},
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

    def test_daily_entry_exact_index_and_reply_plus_marker(self):
        before = self.raw()
        proposal, reason = self.proposal(before)
        self.assertIsNone(reason)
        intent = proposal["intent"]
        self.assertEqual((intent["period"], intent["index"], intent["rowId"]),
                         ("daily", 1, "c_rounds"))
        self.assertEqual(intent["command"], "claim")
        baseline, reason = self.evidence.capture(proposal, before)
        self.assertIsNone(reason)
        header, _ = self.h.contracts.validateSnapshot(before,
            lua_table(self.h.lua, self.h.session))
        ok = lua_table(self.h.lua, {"ok": True})
        self.assertEqual(self.evidence.evaluate(proposal, header,
            self.raw(2), ok, baseline), "pending")
        after = self.raw(2)
        after["native"]["contracts"]["daily"][1]["claimed"] = True
        self.assertEqual(self.evidence.evaluate(proposal, header,
            after, ok, baseline), "confirmed")

    def test_weekly_and_old_single_weekly_entry(self):
        daily = [{"id": "d" + str(i), "done": True, "claimed": True}
                 for i in range(1, 6)]
        weekly = {"id": "w_legacy", "done": True, "claimed": False}
        raw = self.raw(daily=daily, weekly=weekly)
        view, reason = self.view(raw)
        self.assertIsNone(reason)
        self.assertEqual(view["ready"][1]["period"], "weekly")
        self.assertEqual(view["ready"][1]["index"], 1)
        proposal, reason = self.planner.propose(view,
            lua_table(self.h.lua, {"enabled": True}))
        self.assertIsNone(reason)
        self.assertEqual(proposal["intent"]["command"], "claimweekly")
        baseline, reason = self.evidence.capture(proposal, raw)
        self.assertIsNone(reason)
        after = self.raw(2, daily=daily, weekly={"id": "w_legacy",
                                             "done": True, "claimed": True})
        header, _ = self.h.contracts.validateSnapshot(raw,
            lua_table(self.h.lua, self.h.session))
        self.assertEqual(self.evidence.evaluate(proposal, header, after,
            lua_table(self.h.lua, {"ok": True}), baseline), "confirmed")

    def test_changed_row_or_reset_never_confirms(self):
        before = self.raw()
        proposal, _ = self.proposal(before)
        baseline, _ = self.evidence.capture(proposal, before)
        header, _ = self.h.contracts.validateSnapshot(before,
            lua_table(self.h.lua, self.h.session))
        changed = self.raw(2)
        changed["native"]["contracts"]["daily"][1]["id"] = "c_other"
        changed["native"]["contracts"]["daily"][1]["claimed"] = True
        ok = lua_table(self.h.lua, {"ok": True})
        self.assertEqual(self.evidence.evaluate(proposal, header, changed,
            ok, baseline), "pending")
        reset = self.raw(2, day_reset=NOW + 86400)
        reset["native"]["contracts"]["daily"][1]["claimed"] = True
        self.assertEqual(self.evidence.evaluate(proposal, header, reset,
            ok, baseline), "pending")

    def test_unready_disabled_stale_and_bad_config_block(self):
        self.assertIsNone(self.proposal(enabled=False)[0])
        self.assertIsNone(self.view(self.raw(day_reset=NOW + 4))[0])
        bad = self.raw()
        bad["native"]["fullSync"] = False
        self.assertIsNone(self.view(bad)[0])
        bad = self.raw()
        bad["contractConfig"]["dailyTiers"][1] = 9
        self.assertIsNone(self.view(bad)[0])
        bad = self.raw()
        bad["native"]["contracts"]["daily"][1]["done"] = None
        self.assertIsNone(self.view(bad)[0])

    def test_failed_reply_rejects_without_progress(self):
        before = self.raw()
        proposal, _ = self.proposal(before)
        baseline, _ = self.evidence.capture(proposal, before)
        header, _ = self.h.contracts.validateSnapshot(before,
            lua_table(self.h.lua, self.h.session))
        self.assertEqual(self.evidence.evaluate(proposal, header,
            self.raw(2), lua_table(self.h.lua, {"ok": False}), baseline),
            "rejected")


if __name__ == "__main__":
    unittest.main()
