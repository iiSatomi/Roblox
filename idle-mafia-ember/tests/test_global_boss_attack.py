"""Guarded ordinary Global Boss hits with personal evidence."""
import unittest

from engine_harness import Harness, lua_table


class GlobalBossAttackTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.context = self.h.load("src/game/Context.luau").new(
            self.h.contracts, None, None, None, None,
            self.h.load("src/game/GlobalBossState.luau"))
        self.reader = self.h.load("src/game/GlobalBossAttackState.luau")
        self.planner = self.h.load("src/features/GlobalBossAttack.luau")
        self.evidence = self.h.load(
            "src/features/GlobalBossAttackEvidence.luau")

    def raw(self, revision=1, now=2000100, health=80,
            stamina=10, usage=0, last=0, mine_hits=2,
            mine_damage=50, test_user=None):
        event = {"id": "hellfire", "startAt": 2000000,
                 "endAt": 2001000, "status": "live",
                 "hp": 10000, "dmg": 100}
        if test_user is not None: event["testUserId"] = test_user
        return self.h.snapshot(revision=revision,
            native={"fullSync": True, "serverNow": now,
                    "stats": {"maxHealth": 100},
                    "pools": {"health": health,
                              "stamina": stamina},
                    "gb": {"run": "hellfire_2000000",
                           "hits": mine_hits, "dmg": mine_damage,
                           "claimed": False}},
            globalBossProof={"account": "user-a",
                "capturedAt": 0, "event": event},
            localUserIdProof={"account": "user-a",
                "capturedAt": 0, "userId": 42},
            globalAttackUsageProof={"account": "user-a",
                "capturedAt": 0, "runKey": "hellfire_2000000",
                "hits": usage, "lastServerNow": last})

    def propose(self, raw):
        context = self.context.Read(self.context, raw,
            lua_table(self.h.lua, self.h.session), 0, 2)[0]
        view, reason = self.reader.read(raw, context)
        self.assertIsNone(reason)
        return self.planner.propose(view,
            lua_table(self.h.lua, {"enabled": True}),
            lua_table(self.h.lua, {"stamina": 0,
                "uncertainStamina": 0}))

    def test_exact_personal_hit_confirms(self):
        before = self.raw()
        proposal, reason = self.propose(before)
        self.assertIsNone(reason)
        baseline, reason = self.evidence.capture(proposal, before)
        self.assertIsNone(reason)
        self.h.at(1)
        after = self.raw(revision=2, usage=1, last=2000100,
                         mine_hits=3, mine_damage=125)
        after["globalBossProof"]["capturedAt"] = 1
        after["localUserIdProof"]["capturedAt"] = 1
        after["globalAttackUsageProof"]["capturedAt"] = 1
        self.assertEqual(self.evidence.evaluate(proposal, before,
            after, lua_table(self.h.lua, {"ok": True, "dmg": 75}),
            baseline), "confirmed")
        after["native"]["gb"]["hits"] = 2
        self.assertEqual(self.evidence.evaluate(proposal, before,
            after, lua_table(self.h.lua, {"ok": True, "dmg": 75}),
            baseline), "pending")

    def test_health_stamina_cap_spacing_and_access_block(self):
        for changes in ({"health": 74}, {"stamina": 1},
                        {"usage": 25},
                        {"usage": 1, "last": 2000098},
                        {"test_user": 99},
                        {"now": 2001000}):
            with self.subTest(changes=changes):
                self.assertIsNone(self.propose(
                    self.raw(**changes))[0])


if __name__ == "__main__":
    unittest.main()
