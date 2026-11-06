"""UI journal summaries must omit action identifiers, tokens and raw reasons."""
import unittest

from engine_harness import Harness, lua_table


class PublicJournalTests(unittest.TestCase):
    def test_bounded_public_view_excludes_sensitive_metadata(self):
        h = Harness()
        journal = h.load("src/engine/Journal.luau").new(100)
        for index in range(25):
            journal.Record(journal, lua_table(h.lua, {
                "kind": "sent", "feature": "jobs", "at": index,
                "actionKey": "account-private-" + str(index),
                "token": "secret-token", "reason": "private response",
                "duplicateRisk": index == 24,
            }))
        public = journal.PublicEvents(journal, 10)
        self.assertEqual(len(public), 10)
        self.assertEqual(public[1]["at"], 15)
        self.assertTrue(public[10]["duplicateRisk"])
        for row in public.values():
            self.assertEqual(set(row.keys()),
                             {"kind", "feature", "at", "duplicateRisk"})
        journal.Record(journal, lua_table(h.lua, {
            "kind": "sent", "feature": "private/account-id", "at": 25}))
        self.assertEqual(journal.PublicEvents(journal, 1)[1]["feature"],
                         "unknown")


if __name__ == "__main__":
    unittest.main()
