"""Saved Family Takedown state and native free-charge regeneration."""
import unittest

from engine_harness import Harness, lua_table


class FamilyTakedownStateTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.reader = self.h.load("src/game/FamilyTakedownState.luau")
        self.context = self.h.load("src/game/Context.luau").new(
            self.h.contracts, None, None, None, None, None, None,
            self.reader)

    def snapshot(self, now=1050):
        return self.h.snapshot(native={"fullSync": True,
            "serverNow": now}, familyTakedownProof={
            "account": "user-a", "capturedAt": 0,
            "state": {"week": 100, "famId": 9, "inFamily": True,
                "stage": 2, "resetAt": 2000, "freeMax": 3,
                "freeUsed": 3, "freeRegen": 60,
                "nextFreeAt": 1000, "tickets": 4,
                "myDmg": 120,
                "claims": [{"week": 99, "stage": 3,
                            "expiresAt": 1200},
                           {"week": 98, "stage": 2,
                            "expiresAt": 1000}]}})

    def test_native_regeneration_and_identity(self):
        raw = self.snapshot()
        view, reason = self.context.Read(self.context, raw,
            lua_table(self.h.lua, self.h.session), 0, 2)
        self.assertIsNone(reason)
        state = view["takedown"]
        self.assertEqual(state["free"], 1)
        self.assertEqual(state["nextFreeAt"], 1060)
        self.assertEqual(state["runKey"], "100:9")
        self.assertEqual(state["tickets"], 4)
        self.assertEqual(len(state["claims"]), 1)
        self.assertEqual(state["claims"][1]["week"], 99)

    def test_stale_and_corrupt_week_fail_closed(self):
        raw = self.snapshot()
        raw["familyTakedownProof"]["capturedAt"] = -1
        self.assertIsNone(self.reader.read(raw, raw)[0])
        raw = self.snapshot(now=2000)
        self.assertIsNone(self.reader.read(raw, raw)[0])
        raw = self.snapshot()
        raw["familyTakedownProof"]["state"]["freeUsed"] = 4
        self.assertIsNone(self.reader.read(raw, raw)[0])
        raw = self.snapshot()
        raw["familyTakedownProof"]["state"]["claims"][2]["week"] = 99
        raw["familyTakedownProof"]["state"]["claims"][2]["stage"] = 3
        self.assertIsNone(self.reader.read(raw, raw)[0])

    def test_missing_expiry_does_not_invent_claimability(self):
        raw = self.snapshot()
        raw["familyTakedownProof"]["state"]["claims"][1]["expiresAt"] = None
        context, reason = self.context.Read(self.context, raw,
            lua_table(self.h.lua, self.h.session), 0, 2)
        self.assertIsNone(reason)
        self.assertEqual(len(context["takedown"]["claims"]), 0)

    def test_claimed_stage_list_is_bounded_and_exact(self):
        raw = self.snapshot()
        raw["familyTakedownProof"]["state"]["claimedStages"] = \
            lua_table(self.h.lua, [1, 1])
        context = self.context.Read(self.context, raw,
            lua_table(self.h.lua, self.h.session), 0, 2)[0]
        self.assertEqual(context["takedown"]["status"], "unknown")


if __name__ == "__main__":
    unittest.main()
