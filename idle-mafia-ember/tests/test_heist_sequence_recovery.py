"""Restart recovery may poll a known sent action but never replay it."""
import unittest

from engine_harness import Harness, lua_table


class HeistSequenceRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.module = self.h.load("src/tabs/heists/SequenceRecovery.luau")
        self.identity = lua_table(self.h.lua, self.h.session)
        self.record = lua_table(self.h.lua, {
            "account": "user-a", "place": "73897506680154",
            "release": "release-a", "actionName": "start",
            "arg1": "h_a", "sequence": 7,
            "actionKey": "heists:abc", "sentAt": 10,
            "sent": True,
        })

    def test_known_sent_action_yields_status_only_call(self):
        call, reason = self.module.statusCall(self.record, self.identity)
        self.assertIsNone(reason)
        self.assertEqual(call["remote"], "HeistAction")
        self.assertEqual(call["arity"], 3)
        self.assertEqual([call["args"][i] for i in (1, 2, 3)],
                         ["status", "h_a", 7])
        self.assertEqual(call["kind"], "statusOnly")

    def test_collect_retains_nil_middle_argument(self):
        self.record["actionName"] = "collect"
        self.record["arg1"] = None
        call, reason = self.module.statusCall(self.record, self.identity)
        self.assertIsNone(reason)
        self.assertEqual(call["args"][1], "status")
        self.assertIsNone(call["args"][2])
        self.assertEqual(call["args"][3], 7)

    def test_unknown_ownership_or_unsent_record_is_blocked(self):
        self.record["sent"] = False
        self.assertIsNone(self.module.statusCall(
            self.record, self.identity)[0])
        self.record["sent"] = True
        self.record["release"] = "other"
        self.assertIsNone(self.module.statusCall(
            self.record, self.identity)[0])

    def test_no_pending_is_unresolved_not_permission_to_replay(self):
        self.assertEqual(self.module.classify(lua_table(self.h.lua,
            {"code": "no_pending"})), "unresolved")
        self.assertEqual(self.module.classify(lua_table(self.h.lua,
            {"pending": True})), "waiting")
        self.assertEqual(self.module.classify(lua_table(self.h.lua,
            {"ok": True})), "reported")
        self.assertEqual(self.module.classify(lua_table(self.h.lua,
            {"ok": False})), "reported")


if __name__ == "__main__":
    unittest.main()
