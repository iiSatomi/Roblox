"""Read-only staged city Boss state from account-labelled native evidence."""
from datetime import datetime, timezone
import unittest

from engine_harness import Harness, lua_table


class BossStageStateTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.reader = self.h.load("src/game/BossStageState.luau")
        self.context = self.h.load("src/game/Context.luau").new(
            self.h.contracts, None, None, None, self.reader)
        self.server_now = 2000000
        self.day = int(datetime.fromtimestamp(self.server_now,
            tz=timezone.utc).strftime("%Y%j"))

    def raw(self, revision=1, best=1, state_day=None,
            done=None, hp=None, proof_account="user-a"):
        return self.h.snapshot(revision=revision, native={
            "fullSync": True, "serverNow": self.server_now,
            "level": 20, "stats": {"maxHealth": 100},
            "pools": {"health": 80, "stamina": 12},
            "bossStage": {"best": best,
                          "day": self.day if state_day is None else state_day,
                          "done": {} if done is None else done,
                          "hp": {} if hp is None else hp}},
            bossStageProof={"account": proof_account, "capturedAt": 0,
                "staminaCost": 1,
                "stages": [{"stage": 1, "level": 5, "hp": 100,
                            "hitBackMax": 10},
                           {"stage": 2, "level": 10, "hp": 200,
                            "hitBackMax": 20},
                           {"stage": 3, "level": 25, "hp": 300,
                            "hitBackMax": 30}]})

    def read(self, raw):
        base = self.h.load("src/game/Context.luau").new(self.h.contracts)
        context = base.Read(base, raw,
            lua_table(self.h.lua, self.h.session), 0, 2)[0]
        return self.reader.read(raw, context)

    def test_daily_done_unlock_and_hp(self):
        raw = self.raw(done={"1": True}, hp={"2": 75})
        view, reason = self.read(raw)
        self.assertIsNone(reason)
        self.assertEqual(view["dayStamp"], self.day)
        self.assertEqual(view["best"], 1)
        self.assertTrue(view["stages"][1]["doneToday"])
        self.assertTrue(view["stages"][2]["unlocked"])
        self.assertEqual(view["stages"][2]["remainingHp"], 75)
        self.assertFalse(view["stages"][3]["unlocked"])

    def test_old_day_done_resets_and_invalid_hp_uses_max(self):
        raw = self.raw(state_day=self.day - 1,
                       done={"1": True}, hp={"2": 0})
        view, reason = self.read(raw)
        self.assertIsNone(reason)
        self.assertFalse(view["stages"][1]["doneToday"])
        self.assertEqual(view["stages"][2]["remainingHp"], 200)

    def test_proof_and_native_unknown_block(self):
        self.assertIsNone(self.read(self.raw(proof_account="other"))[0])
        raw = self.raw()
        raw["bossStageProof"]["stages"][1]["hp"] = -1
        self.assertIsNone(self.read(raw)[0])
        raw = self.raw()
        raw["native"]["bossStage"] = None
        self.assertIsNone(self.read(raw)[0])

    def test_context_injection_is_optional_and_read_only(self):
        raw = self.raw()
        context, reason = self.context.Read(self.context, raw,
            lua_table(self.h.lua, self.h.session), 0, 2)
        self.assertIsNone(reason)
        self.assertEqual(context["bossStages"]["best"], 1)
        self.assertEqual(len(self.h.transport["sent"]), 0)
        raw["bossStageProof"] = None
        context, reason = self.context.Read(self.context, raw,
            lua_table(self.h.lua, self.h.session), 0, 2)
        self.assertIsNone(reason)
        self.assertEqual(context["bossStages"]["status"], "unknown")


if __name__ == "__main__":
    unittest.main()
