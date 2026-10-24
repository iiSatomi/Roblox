"""Guarded ordinary staged Boss attacks; no Roblox transport."""
from datetime import datetime, timezone
import unittest

from engine_harness import Harness, lua_table


class BossesTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.stage_reader = self.h.load("src/game/BossStageState.luau")
        self.context = self.h.load("src/game/Context.luau").new(
            self.h.contracts, None, None, None, self.stage_reader)
        self.reader = self.h.load("src/game/BossesState.luau")
        self.planner = self.h.load("src/features/Bosses.luau")
        self.evidence = self.h.load("src/features/BossesEvidence.luau")
        self.now = 2000000
        self.day = int(datetime.fromtimestamp(self.now,
            tz=timezone.utc).strftime("%Y%j"))

    def raw(self, revision=1, best=1, hp=200, done=None,
            hits=0, spent=0, last=0, health=80, stamina=12,
            auto=None):
        return self.h.snapshot(revision=revision,
            native={"fullSync": True, "serverNow": self.now,
                    "level": 20,
                    "stats": {"maxHealth": 100},
                    "pools": {"health": health,
                              "stamina": stamina},
                    "bossStage": {"best": best, "day": self.day,
                        "done": {} if done is None else done,
                        "hp": {"2": hp}, "auto": auto}},
            bossStageProof={"account": "user-a", "capturedAt": 0,
                "staminaCost": 1,
                "stages": [{"stage": 1, "level": 5, "hp": 100,
                            "hitBackMax": 10},
                           {"stage": 2, "level": 10, "hp": 200,
                            "hitBackMax": 20}]},
            bossUsageProof={"account": "user-a", "capturedAt": 0,
                "day": self.day, "hits": hits, "stamina": spent,
                "lastServerNow": last})

    def view(self, raw):
        context = self.context.Read(self.context, raw,
            lua_table(self.h.lua, self.h.session), 0, 2)[0]
        return self.reader.read(raw, context)

    def propose(self, raw):
        view, reason = self.view(raw)
        self.assertIsNone(reason)
        return self.planner.propose(view,
            lua_table(self.h.lua, {"enabled": True}),
            lua_table(self.h.lua, {"stamina": 0,
                "uncertainStamina": 0}))

    def test_prefers_next_stage_and_exact_hit_confirmation(self):
        before = self.raw()
        proposal, reason = self.propose(before)
        self.assertIsNone(reason)
        self.assertEqual(proposal["intent"]["stage"], 2)
        self.assertEqual(proposal["resources"]["stamina"], 1)
        baseline, reason = self.evidence.capture(proposal, before)
        self.assertIsNone(reason)
        after = self.raw(revision=2, hp=150, hits=1, spent=1,
                         last=self.now, stamina=11)
        self.assertEqual(self.evidence.evaluate(proposal, before,
            after, lua_table(self.h.lua, {"ok": True}), baseline),
            "confirmed")
        after["native"]["bossStage"]["hp"]["2"] = 200
        self.assertEqual(self.evidence.evaluate(proposal, before,
            after, lua_table(self.h.lua, {"ok": True}), baseline),
            "pending")

    def test_daily_clear_falls_back_to_repeat(self):
        proposal, reason = self.propose(self.raw(done={"2": True}))
        self.assertIsNone(reason)
        self.assertEqual(proposal["intent"]["stage"], 1)

    def test_health_stamina_spacing_and_caps_block(self):
        self.assertIsNone(self.propose(self.raw(health=59))[0])
        self.assertIsNone(self.propose(self.raw(stamina=1))[0])
        self.assertIsNone(self.propose(self.raw(hits=100,
            spent=100))[0])
        self.assertIsNone(self.propose(self.raw(hits=1, spent=1,
            last=self.now - 2))[0])

    def test_fractional_regen_pools_use_whole_available_units(self):
        proposal, reason = self.propose(self.raw(
            health=80.8, stamina=2.9))
        self.assertIsNone(reason)
        self.assertEqual(proposal["intent"]["stage"], 2)
        self.assertIsNone(self.propose(self.raw(stamina=1.9))[0])

    def test_preflight_rechecks_health_and_auto_owner(self):
        before = self.raw()
        proposal, _ = self.propose(before)
        before["native"]["pools"]["health"] = 60
        self.assertIsNone(self.evidence.capture(proposal, before)[0])
        before["native"]["pools"]["health"] = 80
        before["native"]["bossStage"]["auto"] = 2
        self.assertIsNone(self.evidence.capture(proposal, before)[0])

    def test_different_stage_change_does_not_confirm(self):
        before = self.raw()
        proposal, _ = self.propose(before)
        baseline, _ = self.evidence.capture(proposal, before)
        after = self.raw(revision=2, hits=1, spent=1,
                         last=self.now)
        after["native"]["bossStage"]["hp"]["1"] = 40
        self.assertEqual(self.evidence.evaluate(proposal, before,
            after, lua_table(self.h.lua, {"ok": True}), baseline),
            "pending")


if __name__ == "__main__":
    unittest.main()
