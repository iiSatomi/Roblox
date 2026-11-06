"""Personal result-slot identity, native counter continuity and exact collection evidence."""
import hashlib
import unittest

from engine_harness import Harness, lua_table


class HeistCollectionTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.h.lua.globals().testHash = lambda value: hashlib.sha256(value.encode()).hexdigest()
        self.hash = self.h.lua.eval("function(value) return testHash(value) end")
        self.collection = self.h.load("src/tabs/heists/HeistCollection.luau").new(
            self.hash, "a" * 64, "release-a")

    def raw(self, revision=1, result=True, session="run-a"):
        raw = self.h.snapshot(revision=revision, session=session, native={"fullSync": True,
            "serverNow": 1987300, "cash": 1000, "xp": 10}, catalogKey="a" * 64,
            heistBoardProof={"account": "user-a", "capturedAt": 0, "sourceKey": "a" * 64,
                "board": {"ok": True, "rows": [], "serverNow": 1987300,
                    "result": {"heistId": "h_a", "ok": True, "cash": 100, "xp": 20,
                               "crates": 1, "crateId": "crate_loot"} if result else None}})
        proof = {field: raw[field] for field in (
            "session", "account", "place", "release", "revision", "capturedAt")}
        proof.update(sequence=7, controllersClear=True)
        raw.heistControllerProof = lua_table(self.h.lua, proof)
        raw.heistBoardProof.header = lua_table(self.h.lua, {field: raw[field] for field in (
            "session", "account", "place", "release", "revision", "capturedAt")})
        return raw

    def plan(self, raw=None):
        raw = self.raw() if raw is None else raw
        view, why = self.collection.read(raw, raw)
        self.assertIsNone(why)
        proposal, why = self.collection.propose(view, lua_table(self.h.lua, {"enabled": True}))
        self.assertIsNone(why)
        return proposal, raw

    def test_personal_slot_plan_names_full_result_signature_and_current_counter(self):
        proposal, before = self.plan()
        self.assertEqual(proposal.intent.kind, "heistCollect")
        self.assertEqual(proposal.intent.controllerSequenceBefore, 7)
        self.assertEqual(proposal.intent.serverDay, 23)
        self.assertEqual(len(proposal.intent.resultKey), 64)
        self.assertEqual(dict(proposal.resources.items()), {})
        before.heistBoardProof.board.result.extraLabel = "new identity detail"
        self.assertIsNone(self.collection.capture(proposal, before)[0])

    def test_counter_day_and_signature_are_rechecked_by_capture(self):
        for changed in ("counter", "day", "reward"):
            with self.subTest(changed=changed):
                proposal, before = self.plan()
                if changed == "counter":
                    before.heistControllerProof.sequence = 8
                elif changed == "day":
                    before.native.serverNow = 2073700
                    before.heistBoardProof.board.serverNow = 2073700
                else:
                    before.heistBoardProof.board.result.xp = 21
                self.assertIsNone(self.collection.capture(proposal, before)[0])

    def test_exact_collected_rewards_and_newer_empty_result_slot_confirm(self):
        proposal, before = self.plan()
        baseline = self.collection.capture(proposal, before)[0]
        reply = lua_table(self.h.lua, {"ok": True, "collected": True, "cash": 100,
                                     "xp": 20, "crates": 1, "crateId": "crate_loot"})
        after = self.raw(revision=2, result=False)
        self.assertEqual(self.collection.evaluate(proposal, before, after, reply, baseline), "confirmed")
        for changed in ("missing_rewards", "wrong_reward", "result_remains", "old_revision"):
            with self.subTest(changed=changed):
                altered_after = self.raw(revision=2, result=False)
                altered_reply = lua_table(self.h.lua, dict(reply.items()))
                if changed == "missing_rewards":
                    altered_reply.xp = None
                elif changed == "wrong_reward":
                    altered_reply.crates = 2
                elif changed == "result_remains":
                    altered_after = self.raw(revision=2)
                else:
                    altered_after.revision = 1
                self.assertEqual(self.collection.evaluate(
                    proposal, before, altered_after, altered_reply, baseline), "pending")

    def test_restart_evidence_requires_same_scope_and_saved_exact_reply(self):
        proposal, before = self.plan()
        saved = lua_table(self.h.lua, {"proposal": proposal, "before": before,
            "baseline": self.collection.capture(proposal, before)[0], "reply": {
                "ok": True, "collected": True, "cash": 100, "xp": 20,
                "crates": 1, "crateId": "crate_loot"}})
        after = self.raw(revision=0, result=False, session="run-b")
        self.assertEqual(self.collection.recoverSaved(saved, after), "confirmed")
        after.account = "another-account"
        self.assertIsNone(self.collection.recoverSaved(saved, after))


if __name__ == "__main__":
    unittest.main()
