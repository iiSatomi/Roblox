"""Effective buff aggregation from saved native rules; no game client."""
import unittest

from engine_harness import Harness, lua_table


class BuffContextTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.reader = self.h.load("src/game/BuffContext.luau")
        self.context = self.h.load("src/game/Context.luau").new(
            self.h.contracts, None, self.reader)

    def raw(self, daily="rush_hour", global_ends=None, decree_ends=None,
            daily_end=2000100, personal_xp_end=0):
        return self.h.snapshot(native={"fullSync": True, "serverNow": 2000000},
            buffProof={"account": "user-a", "capturedAt": 0,
                "serverNow": 2000000, "daily": {"id": daily,
                    "startsAt": 1999900, "endsAt": daily_end},
                "globalEnds": global_ends or {},
                "decreeEnds": decree_ends or {},
                "globalAmounts": {}, "personalXpEnd": personal_xp_end})

    def view(self, raw):
        return self.context.Read(self.context, raw,
            lua_table(self.h.lua, self.h.session), 0, 2)[0]["buffs"]

    def test_daily_and_global_use_maximum(self):
        view = self.view(self.raw(global_ends={"ops": 2000050}))
        self.assertEqual(view["ops"]["value"], 2)
        self.assertEqual(view["ops"]["source"], "global")
        self.assertEqual(view["ops"]["endsAt"], 2000050)
        self.assertEqual(view["mastery"]["value"], 1)

    def test_daily_only_and_weekend(self):
        daily = self.view(self.raw())
        self.assertEqual(daily["ops"]["value"], 1.25)
        self.assertEqual(daily["ops"]["source"], "daily")
        weekend = self.view(self.raw(daily="weekend"))
        self.assertEqual(weekend["xp"]["value"], 2)
        self.assertEqual(weekend["luck"]["value"], 0.1)
        self.assertEqual(weekend["boss"]["value"], 1)

    def test_decree_and_daily_overlap(self):
        view = self.view(self.raw(daily="old_habits",
            decree_ends={"mastery": 2000080, "xp": 2000080}))
        self.assertEqual(view["mastery"]["value"], 2)
        self.assertEqual(view["mastery"]["source"], "decree")
        self.assertEqual(view["xp"]["value"], 1.25)

    def test_expired_global_and_invalid_proof_fail_closed(self):
        expired = self.view(self.raw(global_ends={"ops": 2000000}))
        self.assertEqual(expired["ops"]["value"], 1.25)
        bad = self.raw(daily="unknown")
        self.assertEqual(self.view(bad)["status"], "unknown")
        bad = self.raw(daily_end=2000000)
        self.assertEqual(self.view(bad)["status"], "unknown")
        bad = self.raw()
        bad["buffProof"]["account"] = "someone-else"
        self.assertEqual(self.view(bad)["status"], "unknown")

    def test_shared_context_without_reader_stays_unknown(self):
        context = self.h.load("src/game/Context.luau").new(self.h.contracts)
        raw = self.raw()
        view = context.Read(context, raw,
            lua_table(self.h.lua, self.h.session), 0, 2)[0]
        self.assertEqual(view["buffs"]["status"], "unknown")

    def test_personal_xp_and_equal_strength_keep_later_expiry(self):
        personal = self.view(self.raw(personal_xp_end=2000200))
        self.assertEqual(personal["xp"]["value"], 2)
        self.assertEqual(personal["xp"]["source"], "personal")
        weekend = self.view(self.raw(daily="weekend",
            daily_end=2000100, personal_xp_end=2000200))
        self.assertEqual(weekend["xp"]["source"], "personal")
        self.assertEqual(weekend["xp"]["endsAt"], 2000200)
        expired = self.view(self.raw(personal_xp_end=2000000))
        self.assertEqual(expired["xp"]["value"], 1)


if __name__ == "__main__":
    unittest.main()
