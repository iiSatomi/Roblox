"""Favor modes and reward filters against the legacy mafia/Heists.lua planner."""
import math
import random
import unittest

from engine_harness import Harness, lua_table


MODES = ("Balanced", "Cash reward", "XP reward", "Ending soon", "Highest tier")
NOW = 2000000


def legacy_winner(rows, mode, *, cap=None, min_cash=0, min_xp=0,
                  relations="Friends or Family", player_level=20):
    """Independent oracle for favorPlan's eligible maxima, score and tie scan.

    Source: mafia/Heists.lua favorPlan, lines 39-73. Native caps apply before
    thresholds; only eligible rows contribute maxima. IDs keep their types.
    """
    candidates = []
    for row in rows:
        friend = row.get("friend", True) is True
        family = row.get("relation") == "family"
        related = (friend if relations == "Friends only" else family
                   if relations == "Family only" else friend or family)
        cash = min(row.get("cash", 0), cap) if cap is not None else row.get("cash", 0)
        xp = row.get("xp", 0)
        level = row.get("level", 1)
        if (row.get("ends", 30) > 0 and level <= player_level
                and row.get("sabos", 0) == 0 and row.get("helps", 0) < 5
                and related and cash >= min_cash and xp >= min_xp):
            candidates.append((row, cash, xp, level))
    if not candidates:
        return None
    maxima = tuple(max(candidate[index] for candidate in candidates)
                   for index in (1, 2, 3))
    best = None
    score = None
    for row, cash, xp, level in candidates:
        if mode == "Cash reward":
            rank = cash
        elif mode == "XP reward":
            rank = xp
        elif mode == "Ending soon":
            rank = -row.get("ends", 30)
        elif mode == "Highest tier":
            rank = level
        else:
            rank = sum(value / maximum if maximum > 0 else 0
                       for value, maximum in zip((cash, xp, level), maxima))
        tie = (row.get("ends", 30), str(row["id"]))
        if (best is None or rank > score
                or rank == score and tie < (best.get("ends", 30), str(best["id"]))):
            best, score = row, rank
    return best["id"]


class FavorRankingTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        board_reader = self.h.load("src/game/HeistBoardState.luau")
        self.context = self.h.load("src/game/Context.luau").new(
            self.h.contracts, None, None, board_reader)
        self.reader = self.h.load("src/game/FavorsState.luau")
        self.planner = self.h.load("src/features/FavorHelp.luau")
        self.evidence = self.h.load("src/features/FavorHelpEvidence.luau")

    def raw(self, rows, *, cap=None, favors=12, energy=20, attempts=0, level=20):
        catalog, native_rows = [], []
        for index, row in enumerate(rows):
            heist_id = "heist-" + str(index)
            catalog.append({"id": heist_id, "level": row.get("level", 1),
                            "stake": 100, "energy": 2,
                            "helpCash": row.get("cash", 0),
                            "helpXp": row.get("xp", 0)})
            native_rows.append({"id": row["id"], "ownerId": index + 42,
                                "heistId": heist_id,
                                "endsAt": NOW + row.get("ends", 30),
                                "friend": row.get("friend", True),
                                "famRel": row.get("relation"),
                                "helpsUsed": row.get("helps", 0),
                                "sabosUsed": row.get("sabos", 0)})
        board = {"ok": True, "serverNow": NOW, "rows": native_rows,
                 "startsLeft": 1, "bustWait": 0, "favorsLeft": favors,
                 "helpFavorCost": 1, "helpEnergyCost": 2,
                 "helpMaxPerHeist": 5, "helpCashCap": cap}
        return self.h.snapshot(native={"fullSync": True, "serverNow": NOW,
            "level": level, "pools": {"energy": energy}},
            heistCatalog=catalog,
            heistBoardProof={"account": "user-a", "capturedAt": 0, "board": board},
            favorUsageProof={"account": "user-a", "day": 23,
                             "attempts": attempts, "capturedAt": 0})

    def view(self, raw):
        context, reason = self.context.Read(self.context, raw,
            lua_table(self.h.lua, self.h.session), 0, 2)
        self.assertIsNotNone(context, reason)
        view, reason = self.reader.read(raw, context)
        self.assertIsNotNone(view, reason)
        return view

    def settings(self, mode="Balanced", **custom):
        return lua_table(self.h.lua, {"enabled": True, "policy": mode,
            "custom": {"maxDailyAttempts": 5, "minFavorReserve": 5,
                       "minEnergyReserve": 10, "relations": "Friends or Family",
                       **custom}})

    def plan(self, raw, mode="Balanced", *, reservations=None, **custom):
        return self.planner.propose(self.view(raw), self.settings(mode, **custom),
            lua_table(self.h.lua, reservations or {}))

    def selected(self, raw, mode="Balanced", **custom):
        proposal, reason = self.plan(raw, mode, **custom)
        self.assertIsNotNone(proposal, reason)
        self.assertIsNone(reason)
        return proposal["intent"]["rowId"]

    def test_each_legacy_mode_has_its_own_primary_score(self):
        rows = [
            {"id": "cash", "cash": 900, "xp": 10, "level": 1, "ends": 6},
            {"id": "xp", "cash": 10, "xp": 900, "level": 1, "ends": 7},
            {"id": "tier", "cash": 1, "xp": 1, "level": 20, "ends": 8},
            {"id": "balanced", "cash": 700, "xp": 700, "level": 17, "ends": 9},
            {"id": "soon", "cash": 100, "xp": 100, "level": 3, "ends": 1},
        ]
        raw = self.raw(rows)
        expected = {"Balanced": "balanced", "Cash reward": "cash", "XP reward": "xp",
                    "Highest tier": "tier", "Ending soon": "soon", "Best reward": "cash"}
        for mode, wanted in expected.items():
            with self.subTest(mode=mode):
                self.assertEqual(self.selected(raw, mode), wanted)

    def test_best_reward_preserves_cash_then_xp_and_typed_id_ties(self):
        raw = self.raw([{"id": "more-xp", "cash": 99, "xp": 999},
                        {"id": "cash-only", "cash": 100, "xp": 1},
                        {"id": "winner", "cash": 100, "xp": 2}])
        self.assertEqual(self.selected(raw, "Best reward"), "winner")
        tied = self.raw([{"id": "0"}, {"id": 9}])
        self.assertEqual(self.selected(tied, "Best reward"), 9)
        self.assertEqual(self.selected(tied, "Highest tier"), "0")

    def test_primary_ties_use_expiry_then_textual_native_id(self):
        for mode in MODES:
            with self.subTest(mode=mode):
                raw = self.raw([{"id": 1, "ends": 30}, {"id": 2, "ends": 20},
                                {"id": 10, "ends": 20}])
                self.assertEqual(self.selected(raw, mode), 10)

    def test_cash_and_xp_ties_ignore_other_reward_and_tier(self):
        cases = (("Cash reward", [{"id": "2", "cash": 50, "xp": 999, "level": 20},
                                  {"id": "10", "cash": 50, "xp": 1, "level": 1}]),
                 ("XP reward", [{"id": "2", "cash": 999, "xp": 50, "level": 20},
                                {"id": "10", "cash": 1, "xp": 50, "level": 1}]))
        for mode, rows in cases:
            with self.subTest(mode=mode):
                self.assertEqual(self.selected(self.raw(rows), mode), "10")

    def test_equal_text_mixed_type_ids_retain_first_row_and_exact_identity(self):
        for mode in MODES:
            for ids in ((731, "731"), ("731", 731)):
                with self.subTest(mode=mode, ids=ids):
                    raw = self.raw([{"id": value} for value in ids])
                    proposal, reason = self.plan(raw, mode)
                    self.assertIsNotNone(proposal, reason)
                    selected = proposal["intent"]["rowId"]
                    self.assertEqual(selected, ids[0])
                    self.assertIs(type(selected), type(ids[0]))
                    prefix = "number:" if isinstance(selected, int) else "string:"
                    self.assertIn(prefix + "731", proposal["actionKey"])
                    self.assertIsNotNone(self.evidence.capture(proposal, raw)[0])

    def test_cash_cap_precedes_ranking_and_reward_filter(self):
        raw = self.raw([{"id": "large", "cash": 10000, "level": 20, "ends": 30},
                        {"id": "capped", "cash": 600, "xp": 100, "level": 10,
                         "ends": 20}], cap=500)
        for mode in ("Cash reward", "Balanced"):
            with self.subTest(mode=mode):
                proposal, reason = self.plan(raw, mode, minRewardCash=500)
                self.assertIsNotNone(proposal, reason)
                self.assertEqual(proposal["intent"]["rowId"], "capped")
                self.assertEqual(proposal["intent"]["rewardCash"], 500)
                self.assertIsNone(self.plan(raw, mode, minRewardCash=500.01)[0])
                self.assertIsNotNone(self.evidence.capture(proposal, raw)[0])

    def test_reward_filters_precede_balanced_maxima(self):
        cases = (("minRewardXp", [{"id": "a", "cash": 100, "xp": 40, "level": 10, "ends": 20},
                                  {"id": "b", "cash": 40, "xp": 100, "level": 10, "ends": 30},
                                  {"id": "excluded", "cash": 10000, "xp": 0, "level": 20}], "a"),
                 ("minRewardCash", [{"id": "a", "cash": 100, "xp": 40, "level": 10, "ends": 30},
                                    {"id": "b", "cash": 40, "xp": 100, "level": 10, "ends": 20},
                                    {"id": "excluded", "cash": 0, "xp": 10000, "level": 20}], "b"))
        for field, rows, expected in cases:
            with self.subTest(field=field):
                self.assertEqual(self.selected(self.raw(rows), **{field: 0.5}), expected)

    def test_ineligible_high_rewards_do_not_distort_balanced_maxima(self):
        eligible = [{"id": "a", "cash": 100, "xp": 40, "level": 10, "ends": 20},
                    {"id": "b", "cash": 40, "xp": 100, "level": 10, "ends": 30}]
        exclusions = ({"ends": 0}, {"ends": -1}, {"friend": False},
                      {"level": 21}, {"sabos": 1}, {"helps": 5})
        for change in exclusions:
            with self.subTest(change=change):
                excluded = {"id": "excluded", "cash": 10000, "level": 20, **change}
                self.assertEqual(self.selected(self.raw(eligible + [excluded])), "a")

    def test_zero_reward_maxima_are_safe_and_ties_retain_first(self):
        for cap in (None, 0):
            for mode in MODES:
                with self.subTest(mode=mode, cap=cap):
                    raw = self.raw([{"id": "same", "level": 1},
                                    {"id": "earlier", "level": 1, "ends": 10}], cap=cap)
                    self.assertEqual(self.selected(raw, mode), "earlier")
        raw = self.raw([{"id": "low", "level": 1}, {"id": "tier", "level": 2}])
        self.assertEqual(self.selected(raw), "tier")

    def test_reward_filters_default_zero_and_allow_fractional_thresholds(self):
        for mode in MODES + ("Best reward",):
            with self.subTest(mode=mode):
                raw = self.raw([{"id": "zero"}])
                self.assertEqual(self.selected(raw, mode), "zero")
                self.assertIsNone(self.plan(raw, mode, minRewardCash=0.5)[0])
                self.assertIsNone(self.plan(raw, mode, minRewardXp=0.5)[0])
                raw = self.raw([{"id": "exact", "cash": 10, "xp": 20}])
                self.assertEqual(self.selected(raw, mode, minRewardCash=9.5,
                                               minRewardXp=20), "exact")
                self.assertIsNone(self.plan(raw, mode, minRewardCash=10.01)[0])
                self.assertIsNone(self.plan(raw, mode, minRewardXp=20.01)[0])
                huge = self.raw([{"id": "bound", "cash": 10**15, "xp": 10**15}])
                self.assertEqual(self.selected(huge, mode, minRewardCash=10**15,
                                               minRewardXp=10**15), "bound")

    def test_reward_filters_reject_unsafe_or_non_numeric_thresholds(self):
        raw = self.raw([{"id": "safe", "cash": 100, "xp": 100}])
        invalid = (-1, math.nan, math.inf, -math.inf, 10**15 + 1, True, False, "0", {})
        for field in ("minRewardCash", "minRewardXp"):
            for value in invalid:
                for mode in MODES + ("Best reward",):
                    with self.subTest(field=field, value=value, mode=mode):
                        proposal, reason = self.plan(raw, mode, **{field: value})
                        self.assertIsNone(proposal)
                        self.assertIsInstance(reason, str)

    def test_all_modes_keep_daily_relation_resource_and_opt_in_guards(self):
        for mode in MODES + ("Best reward",):
            for resource, boundary, blocked in (("favors", 6, 7), ("energy", 8, 9)):
                with self.subTest(mode=mode, resource=resource):
                    raw = self.raw([{"id": "safe"}])
                    self.assertIsNotNone(self.plan(raw, mode,
                        reservations={resource: 2, "uncertain" + resource.title(): boundary - 2})[0])
                    self.assertIsNone(self.plan(raw, mode,
                        reservations={resource: 2, "uncertain" + resource.title(): blocked - 2})[0])
            with self.subTest(mode=mode):
                self.assertIsNone(self.plan(self.raw([{"id": "cap"}], attempts=5), mode)[0])
                self.assertIsNone(self.plan(self.raw([{"id": "other", "friend": False}]), mode)[0])
                self.assertIsNone(self.plan(self.raw([{"id": "friend"}]), mode,
                                           relations="Family only")[0])
                self.assertIsNone(self.plan(self.raw([{"id": "family", "friend": False,
                                                       "relation": "family"}]), mode,
                                           relations="Friends only")[0])
                settings = self.settings(mode)
                settings["energyReserve"] = 19
                view = self.view(self.raw([{"id": "safe"}]))
                self.assertIsNone(self.planner.propose(view, settings, self.h.lua.table())[0])
                settings["enabled"] = False
                self.assertIsNone(self.planner.propose(view, settings, self.h.lua.table())[0])

    def test_malformed_rows_neither_rank_nor_change_balanced_maxima(self):
        rows = [{"id": "a", "cash": 100, "xp": 40, "level": 10, "ends": 20},
                {"id": "b", "cash": 40, "xp": 100, "level": 10, "ends": 30},
                {"id": "invalid", "cash": 10000, "level": 20}]
        invalid = (("id", ""), ("ownerId", 0), ("level", 0), ("endsAt", math.inf),
                   ("endsAt", NOW + 0.5), ("helpsUsed", -1), ("sabosUsed", 0.5),
                   ("rewardCash", math.nan), ("rewardCash", math.inf),
                   ("rewardCash", "10000"), ("rewardXp", -1))
        for field, value in invalid:
            with self.subTest(field=field, value=value):
                view = self.view(self.raw(rows))
                view["rows"][3][field] = value
                proposal, reason = self.planner.propose(view, self.settings(), self.h.lua.table())
                self.assertIsNotNone(proposal, reason)
                self.assertEqual(proposal["intent"]["rowId"], "a")

    def test_all_modes_match_deterministic_legacy_oracle(self):
        rng = random.Random(653)
        for sample in range(50):
            rows = [{"id": index + 1 if rng.random() < 0.5 else "run-" + str(index),
                     "cash": rng.choice((0, 1, 10, 40, 100, 500, 10000)),
                     "xp": rng.choice((0, 1, 10, 40, 100, 500)),
                     "level": rng.choice((1, 5, 10, 20, 21)),
                     "ends": rng.choice((-1, 0, 1, 10, 30)),
                     "friend": rng.random() < 0.5,
                     "relation": rng.choice((None, "family", "other", "war")),
                     "helps": rng.choice((0, 1, 4, 5)), "sabos": rng.choice((0, 0, 1))}
                    for index in range(12)]
            cap = rng.choice((None, 0, 50, 500))
            custom = {"minRewardCash": rng.choice((0, 0.5, 40, 100)),
                      "minRewardXp": rng.choice((0, 0.5, 40, 100)),
                      "relations": rng.choice(("Friends or Family", "Friends only", "Family only"))}
            raw = self.raw(rows, cap=cap)
            for mode in MODES:
                with self.subTest(sample=sample, mode=mode):
                    expected = legacy_winner(rows, mode, cap=cap,
                        min_cash=custom["minRewardCash"], min_xp=custom["minRewardXp"],
                        relations=custom["relations"])
                    proposal, reason = self.plan(raw, mode, **custom)
                    actual = proposal["intent"]["rowId"] if proposal is not None else None
                    self.assertEqual(actual, expected, reason)
                    if expected is not None:
                        self.assertIs(type(actual), type(expected))


if __name__ == "__main__":
    unittest.main()
