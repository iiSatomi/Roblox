"""Earned ladder claims use replicated readiness and same-day markers."""
from datetime import datetime, timezone
import unittest

from engine_harness import Harness, lua_table


NOW = int(datetime(2026, 10, 21, 12, tzinfo=timezone.utc).timestamp())
DAY = 2026294
RUNGS = [
    {"seconds": 300, "kind": "cash", "flat": 10000,
     "tiers": {2: {"kind": "cash", "minutes": 15},
               3: {"kind": "cash", "minutes": 30},
               4: {"kind": "cash", "minutes": 60}}},
    {"seconds": 900, "kind": "energy"},
    {"seconds": 1800, "kind": "crate", "crate": "crate_loot",
     "tiers": {2: {"kind": "stamina"}}},
    {"seconds": 3600, "kind": "crate", "crate": "crate_rare",
     "tiers": {2: {"kind": "seals", "amount": 2},
               3: {"kind": "seals", "amount": 3},
               4: {"kind": "seals", "amount": 4}}},
    {"seconds": 5400, "kind": "xpboost", "minutes": 30,
     "weekend": {"kind": "gold", "amount": 3}},
    {"seconds": 7200, "kind": "mystery"},
    {"seconds": 10800, "kind": "crate", "crate": "crate_consumables_bound",
     "bound": True},
]


class PlaytimeClaimTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.context = self.h.load("src/game/Context.luau").new(self.h.contracts)
        self.reader = self.h.load("src/game/PlaytimeState.luau")
        self.planner = self.h.load("src/features/Playtime.luau")
        self.evidence = self.h.load("src/features/PlaytimeEvidence.luau")

    def raw(self, revision=1, seconds=5400, claimed=None, weekend=False,
            server_now=NOW, catalog=None, **changes):
        data = {"native": {"fullSync": True, "serverNow": server_now,
                           "level": 102, "maxLevel": 102,
                           "playtime": {"todaySeconds": seconds,
                                        "laddersClaimed": claimed if claimed is not None
                                        else {"1": 4, "2": 4, "3": 4, "4": 4}}},
                "catalogKey": "ladder-build-1",
                "ladderCatalog": catalog if catalog is not None else RUNGS,
                "ladderTiers": [1, 10, 30, 102],
                "weekendBuff": {"active": weekend, "day": int(datetime.fromtimestamp(
                    server_now, timezone.utc).strftime("%Y%j"))}}
        data.update(changes)
        return self.h.snapshot(revision=revision, **data)

    def view(self, raw):
        context, reason = self.context.Read(
            self.context, raw, lua_table(self.h.lua, self.h.session), 0, 2)
        self.assertIsNone(reason)
        return self.reader.read(raw, context)

    def propose(self, raw=None, enabled=True):
        view, reason = self.view(raw or self.raw())
        self.assertIsNone(reason)
        return self.planner.propose(
            view, lua_table(self.h.lua, {"enabled": enabled}))

    def test_weekday_and_weekend_90_minute_reward(self):
        view, reason = self.view(self.raw())
        self.assertIsNone(reason)
        self.assertEqual(view["ready"][1]["index"], 5)
        self.assertEqual(view["ready"][1]["rewardKind"], "xpboost")
        weekend, reason = self.view(self.raw(weekend=True))
        self.assertIsNone(reason)
        self.assertEqual(weekend["ready"][1]["rewardKind"], "gold")
        self.assertEqual(weekend["ready"][1]["rewardAmount"], 3)

    def test_mystery_and_bound_crate_resolve_without_opening(self):
        claim5 = {str(i): 4 for i in range(1, 6)}
        mystery, reason = self.view(self.raw(seconds=7200, claimed=claim5))
        self.assertIsNone(reason)
        self.assertEqual(mystery["ready"][1]["index"], 6)
        self.assertEqual(mystery["ready"][1]["rewardKind"], "mystery")
        claim6 = {str(i): 4 for i in range(1, 7)}
        crate, reason = self.view(self.raw(seconds=10800, claimed=claim6))
        self.assertIsNone(reason)
        self.assertEqual(crate["ready"][1]["rewardKind"], "crate")
        self.assertEqual(crate["ready"][1]["rewardItem"],
                         "crate_consumables_bound")
        self.assertTrue(crate["ready"][1]["rewardBound"])

    def test_disabled_unreplicated_or_malformed_blocks(self):
        self.assertIsNone(self.propose(enabled=False)[0])
        self.assertIsNone(self.propose(self.raw(seconds=5399))[0])
        self.assertIsNone(self.view(self.raw(native={"fullSync": False}))[0])
        self.assertIsNone(self.view(self.raw(weekendBuff=None))[0])
        self.assertIsNone(self.view(self.raw(catalog=RUNGS[:6]))[0])
        broken = [dict(row) for row in RUNGS]
        broken[5]["seconds"] = 5400
        self.assertIsNone(self.view(self.raw(catalog=broken))[0])

    def test_one_exact_index_and_claimed_marker_proves_it(self):
        before = self.raw()
        proposal, reason = self.propose(before)
        self.assertIsNone(reason)
        self.assertEqual(proposal["feature"], "playtime")
        self.assertEqual(proposal["intent"]["index"], 5)
        self.assertEqual(proposal["intent"]["rewardKind"], "xpboost")
        baseline, reason = self.evidence.capture(proposal, before)
        self.assertIsNone(reason)
        header, _ = self.h.contracts.validateSnapshot(
            before, lua_table(self.h.lua, self.h.session))
        ok = lua_table(self.h.lua, {"ok": True})
        self.assertEqual(self.evidence.evaluate(
            proposal, header, self.raw(2), ok, baseline), "pending")
        after = self.raw(2, claimed={str(i): 4 for i in range(1, 6)})
        self.assertEqual(self.evidence.evaluate(
            proposal, header, after, ok, baseline), "confirmed")
        other = self.raw(2, claimed={"1": 4, "2": 4, "3": 4,
                                     "4": 4, "6": 4})
        self.assertEqual(self.evidence.evaluate(
            proposal, header, other, ok, baseline), "pending")

    def test_rejection_and_next_day_are_not_success(self):
        before = self.raw()
        proposal, _ = self.propose(before)
        baseline, _ = self.evidence.capture(proposal, before)
        header, _ = self.h.contracts.validateSnapshot(
            before, lua_table(self.h.lua, self.h.session))
        self.assertEqual(self.evidence.evaluate(
            proposal, header, self.raw(2),
            lua_table(self.h.lua, {"ok": False}), baseline), "rejected")
        after = self.raw(2, server_now=NOW + 86400,
                         claimed={str(i): 4 for i in range(1, 6)})
        self.assertEqual(self.evidence.evaluate(
            proposal, header, after,
            lua_table(self.h.lua, {"ok": True}), baseline), "pending")

    def test_missing_claim_map_is_treated_as_unclaimed(self):
        before = self.raw(seconds=300, claimed={})
        before["native"]["playtime"]["laddersClaimed"] = None
        proposal, reason = self.propose(before)
        self.assertIsNone(reason)
        self.assertEqual(proposal["intent"]["index"], 1)
        baseline, reason = self.evidence.capture(proposal, before)
        self.assertIsNone(reason)
        header, _ = self.h.contracts.validateSnapshot(
            before, lua_table(self.h.lua, self.h.session))
        after = self.raw(2, seconds=300, claimed={"1": 1})
        self.assertEqual(self.evidence.evaluate(
            proposal, header, after,
            lua_table(self.h.lua, {"ok": True}), baseline), "confirmed")


if __name__ == "__main__":
    unittest.main()
