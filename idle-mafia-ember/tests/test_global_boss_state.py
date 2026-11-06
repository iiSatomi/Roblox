"""Read-only Global Boss run, access and claimability facts."""
import unittest

from engine_harness import Harness, lua_table


class GlobalBossStateTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.reader = self.h.load("src/game/GlobalBossState.luau")
        self.context = self.h.load("src/game/Context.luau").new(
            self.h.contracts, None, None, None, None, self.reader)

    def raw(self, now=2000100, status="live", damage=100,
            test_user=None, mine_run="hellfire_2000000",
            mine_damage=50, claimed=False, result_at=2000050):
        event = {"id": "hellfire", "startAt": 2000000,
                 "endAt": 2001000, "status": status,
                 "hp": 10000, "dmg": damage}
        if test_user is not None:
            event["testUserId"] = test_user
        if status == "done":
            event["resultAt"] = result_at
        return self.h.snapshot(native={"fullSync": True,
            "serverNow": now,
            "gb": {"run": mine_run, "dmg": mine_damage,
                   "hits": 2, "claimed": claimed}},
            localUserIdProof={"account": "user-a",
                "capturedAt": 0, "userId": 42},
            globalBossProof={"account": "user-a",
                "capturedAt": 0, "event": event})

    def read(self, raw):
        base = self.h.load("src/game/Context.luau").new(self.h.contracts)
        context = base.Read(base, raw,
            lua_table(self.h.lua, self.h.session), 0, 2)[0]
        return self.reader.read(raw, context)

    def test_live_time_decay_and_exact_personal_run(self):
        view, reason = self.read(self.raw())
        self.assertIsNone(reason)
        self.assertEqual(view["runKey"], "hellfire_2000000")
        self.assertTrue(view["canAttack"])
        self.assertEqual(view["remainingHp"], 8900)
        self.assertEqual(view["mineDamage"], 50)
        view, reason = self.read(self.raw(mine_run="old_1"))
        self.assertIsNone(reason)
        self.assertEqual(view["mineDamage"], 0)

    def test_private_access_and_pending_time(self):
        view, _ = self.read(self.raw(test_user=99))
        self.assertFalse(view["accessible"])
        self.assertFalse(view["canAttack"])
        view, _ = self.read(self.raw(now=1999900))
        self.assertEqual(view["phase"], "pending")
        self.assertFalse(view["canAttack"])

    def test_done_claim_needs_participation_and_grace(self):
        view, _ = self.read(self.raw(status="done"))
        self.assertTrue(view["claimable"])
        view, _ = self.read(self.raw(status="done", claimed=True))
        self.assertFalse(view["claimable"])
        view, _ = self.read(self.raw(status="done",
            mine_run="old_1"))
        self.assertFalse(view["claimable"])
        view, _ = self.read(self.raw(now=2000050 + 604800,
            status="done"))
        self.assertFalse(view["claimable"])

    def test_bad_proof_and_optional_context_do_not_send(self):
        raw = self.raw()
        raw["globalBossProof"]["account"] = "other"
        self.assertIsNone(self.read(raw)[0])
        raw = self.raw()
        context, reason = self.context.Read(self.context, raw,
            lua_table(self.h.lua, self.h.session), 0, 2)
        self.assertIsNone(reason)
        self.assertTrue(context["globalBoss"]["canAttack"])
        self.assertEqual(len(self.h.transport["sent"]), 0)
        raw["globalBossProof"] = None
        context, _ = self.context.Read(self.context, raw,
            lua_table(self.h.lua, self.h.session), 0, 2)
        self.assertEqual(context["globalBoss"]["status"], "unknown")


if __name__ == "__main__":
    unittest.main()
