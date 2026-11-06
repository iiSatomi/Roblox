"""The saved read-only board reply is staged with observed identity."""
import unittest

from engine_harness import Harness, lua_table


class HeistBoardQueryTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.module = self.h.load("src/tabs/heists/BoardQuery.luau")
        self.query = self.module.new(lua_table(self.h.lua, self.h.session))
        self.snapshot = self.h.snapshot(native={"fullSync": True,
            "serverNow": 2000000})
        self.reply = lua_table(self.h.lua, {"ok": True,
            "serverNow": 2000000, "rows": [{"id": "run-2",
                "heistId": "h_a", "ownerId": 123}],
            "startsLeft": 1, "bustWait": 0})

    def test_describes_exact_board_call_and_stages_copied_reply(self):
        call = self.query.Describe(self.query)
        self.assertEqual(call["remote"], "HeistAction")
        self.assertEqual(call["arity"], 1)
        self.assertEqual(call["args"][1], "board")
        staged, reason = self.query.Stage(self.query,
            self.snapshot, self.reply)
        self.assertIsNone(reason)
        proof = staged["heistBoardProof"]
        self.assertEqual(proof["account"], "user-a")
        self.assertEqual(proof["capturedAt"], 0)
        self.assertEqual(proof["board"]["rows"][1]["id"], "run-2")
        self.reply["rows"][1]["id"] = "changed"
        self.assertEqual(proof["board"]["rows"][1]["id"], "run-2")
        self.assertIsNone(self.snapshot["heistBoardProof"])

    def test_stale_identity_or_invalid_reply_fails_closed(self):
        self.snapshot["account"] = "other"
        self.assertIsNone(self.query.Stage(self.query,
            self.snapshot, self.reply)[0])
        self.snapshot["account"] = "user-a"
        self.reply["ok"] = False
        self.assertIsNone(self.query.Stage(self.query,
            self.snapshot, self.reply)[0])
        self.reply["ok"] = True
        self.reply["rows"][1]["id"] = self.h.lua.eval(
            "function() end")
        self.assertIsNone(self.query.Stage(self.query,
            self.snapshot, self.reply)[0])


if __name__ == "__main__":
    unittest.main()
