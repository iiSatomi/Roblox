"""Read-only player target facts from a bounded hit list and full Sync."""
import unittest

from engine_harness import Harness, lua_table


class PlayerTargetStateTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.reader = self.h.load("src/tabs/combat/PlayerTargetState.luau")
        self.rules = lua_table(self.h.lua, {"hospitalHealth": 20,
            "staminaCost": 1, "dailyTargetCap": 5})

    def raw(self, counts=None, shield=0, health=80, stamina=4):
        now = 2000000
        return self.h.snapshot(native={"fullSync": True, "serverNow": now,
            "pools": {"health": health, "stamina": stamina},
            "attackDaily": {"day": now // 86400,
                            "counts": {"42": 2} if counts is None else counts}},
            hitListProof={"account": "user-a", "capturedAt": 0,
                "rows": [{"userId": 42, "name": "Target", "level": 10,
                          "shielded": shield}]})

    def context(self):
        return lua_table(self.h.lua, {**self.h.session,
            "revision": 1, "capturedAt": 0, "serverNow": 2000000})

    def test_reads_current_daily_target_capacity_without_proposing_attack(self):
        view, reason = self.reader.read(self.raw(), self.context(), self.rules)
        self.assertIsNone(reason)
        self.assertEqual(view["rows"][1]["userId"], 42)
        self.assertEqual(view["rows"][1]["remainingDaily"], 3)
        self.assertEqual(view["health"], 80)
        self.assertEqual(view["stamina"], 4)
        self.assertIsNone(view["intent"])

    def test_previous_native_day_does_not_spend_todays_target_allowance(self):
        raw=self.raw(counts={'42':5});raw.native.attackDaily.day-=1
        view,why=self.reader.read(raw,self.context(),self.rules)
        self.assertIsNotNone(view,why);self.assertEqual(view.rows[1].remainingDaily,5)
        self.assertEqual(view.rows[1].attacksToday,0)
        self.assertEqual(raw.native.attackDaily.counts['42'],5)
        self.assertEqual(raw.native.attackDaily.day,2000000//86400-1)

    def test_future_or_malformed_native_day_never_means_unused_allowance(self):
        for day in (2000000//86400+1,-1,2.5,'23',float('nan')):
            with self.subTest(day=day):
                raw=self.raw();raw.native.attackDaily.day=day
                self.assertIsNone(self.reader.read(raw,self.context(),self.rules)[0])

    def test_unknown_or_stale_daily_counts_fail_closed(self):
        raw = self.raw()
        raw["native"]["attackDaily"] = None
        self.assertIsNone(self.reader.read(raw, self.context(), self.rules)[0])
        raw = self.raw()
        raw["hitListProof"]["capturedAt"] = 1
        self.assertIsNone(self.reader.read(raw, self.context(), self.rules)[0])

    def test_shield_and_cap_are_reported_as_blockers(self):
        view, _ = self.reader.read(self.raw(counts={"42": 5}, shield=12),
                                   self.context(), self.rules)
        self.assertEqual(view["rows"][1]["remainingDaily"], 0)
        self.assertTrue(view["rows"][1]["shielded"])
        low, _ = self.reader.read(self.raw(health=10, stamina=0),
                                  self.context(), self.rules)
        self.assertFalse(low["resourceReady"])

    def test_fractional_regenerating_pools_are_readable(self):
        view, reason = self.reader.read(self.raw(health=80.5, stamina=3.25),
                                        self.context(), self.rules)
        self.assertIsNone(reason)
        self.assertEqual(view["stamina"], 3.25)

    def test_current_boolean_shields_preserve_the_actual_blocked_state(self):
        for shield in (False, True):
            with self.subTest(shield=shield):
                view, reason = self.reader.read(self.raw(shield=shield), self.context(), self.rules)
                self.assertIsNotNone(view, reason)
                self.assertIs(view.rows[1].shielded, shield)

    def test_bad_shield_types_and_nonfinite_values_are_not_unshielded(self):
        for shield in ("false", "0", float("nan"), float("inf"), float("-inf"), {}):
            with self.subTest(shield=repr(shield)):
                self.assertIsNone(self.reader.read(self.raw(shield=shield), self.context(), self.rules)[0])
