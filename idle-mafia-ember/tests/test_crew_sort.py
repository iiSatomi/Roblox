"""Native Crew sort requires exact order change with pinned slots intact."""
import hashlib
import json
import unittest
from lupa import lua_type

from engine_harness import Harness, lua_table


class CrewSortTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.h.lua.globals().crewSortHash = lambda value: hashlib.sha256(value.encode()).hexdigest()
        self.hash = self.h.lua.eval("function(value) return crewSortHash(value) end")
        self.feature = self.h.load("src/tabs/crew/CrewSort.luau")
        self.before = self.h.snapshot(native={"fullSync": True, "crew": [
            {"name": "Player"}, {"name": "Weak", "rarity": 1},
            {"name": "Pinned", "rarity": 3, "duty": {"city": "A"}},
            {"name": "Strong", "rarity": 5}]})
        self.context = lua_table(self.h.lua, {**self.h.session,
            "revision": 1, "capturedAt": 0})

    def plan(self):
        view, reason = self.feature.read(self.before, self.context)
        self.assertIsNone(reason)
        proposal, reason = self.feature.propose(view,
            lua_table(self.h.lua, {"enabled": True}), self.hash)
        self.assertIsNone(reason)
        return proposal

    def test_exact_swap_confirms_with_newer_sync(self):
        proposal = self.plan()
        self.assertEqual(proposal["intent"]["kind"], "crewSort")
        baseline, _ = self.feature.capture(proposal, self.before)
        after = self.h.snapshot(native={"fullSync": True, "crew": [
            {"name": "Player"}, {"name": "Strong", "rarity": 5},
            {"name": "Pinned", "rarity": 3, "duty": {"city": "A"}},
            {"name": "Weak", "rarity": 1}]})
        after["revision"] = 2
        self.assertEqual(self.feature.evaluate(proposal, self.before, after,
            lua_table(self.h.lua, {"ok": True, "changed": True}),
            baseline), "confirmed")
        after["native"]["crew"][3]["name"] = "Other"
        self.assertEqual(self.feature.evaluate(proposal, self.before, after,
            lua_table(self.h.lua, {"ok": True, "changed": True}),
            baseline), "pending")

    def test_noop_and_stale_reply(self):
        proposal = self.plan()
        baseline, _ = self.feature.capture(proposal, self.before)
        self.assertEqual(self.feature.evaluate(proposal, self.before,
            self.before, lua_table(self.h.lua, {"ok": True,
                "changed": False}), baseline), "pending")
        after = self.h.snapshot(native={"fullSync": True, "crew": [
            {"name": "Player"}, {"name": "Weak", "rarity": 1},
            {"name": "Pinned", "rarity": 3, "duty": {"city": "A"}},
            {"name": "Strong", "rarity": 5}]})
        after["revision"] = 2
        self.assertEqual(self.feature.evaluate(proposal, self.before, after,
            lua_table(self.h.lua, {"ok": True, "changed": False}),
            baseline), "confirmed")

    def test_duplicate_identity_blocks_sort(self):
        self.before["native"]["crew"][4]["name"] = "Weak"
        self.before["native"]["crew"][4]["rarity"] = 1
        self.assertIsNone(self.feature.read(self.before, self.context)[0])


    def large_roster(self, count=33):
        members = [{"name": "Player"}] + [
            {"name": f"Member {i:02d} with a long reviewed roster name", "rarity": 4,
             "healId": f"stable-member-{i:02d}-abcdefghijklmnopqrstuv", "weapon": f"weapon_{i}"}
            for i in range(2, count + 1)]
        self.before = self.h.snapshot(native={"fullSync": True, "serverNow": 1000, "crew": members})

    def test_large_roster_durably_saves_full_baseline_and_recovers_after_json_reload(self):
        for count in (33, 46):
            with self.subTest(count=count):
                self.large_roster(count)
                proposal = self.plan()
                baseline, reason = self.feature.capture(proposal, self.before)
                self.assertIsNone(reason)
                pending = self.h.load("src/storage/PendingAction.luau")
                checkpoints = self.h.load("src/storage/Checkpoint.luau")
                storage = self.h.lua.eval("{strictRecovery=true,data={},Read=function(self,key) return self.data[key] end,Write=function(self,key,value) self.data[key]=value return true end}")
                cp = checkpoints.new(storage, None, None, pending)
                cp.Load(cp, self.h.session['account'], self.h.session['place'], self.h.session['release'])
                ok, reason = cp.Save(cp, proposal, self.before, baseline)
                self.assertTrue(ok, reason)
                self.assertLessEqual(len(proposal.actionKey), 1000)
                self.assertTrue(cp.RecordReply(cp, proposal.actionKey, lua_table(self.h.lua, {"ok": True, "changed": True}))[0])
                def plain(value):
                    if lua_type(value) == 'table':
                        keys = list(value.keys())
                        if keys and set(keys) == set(range(1, len(keys) + 1)):
                            return [plain(value[index]) for index in range(1, len(keys) + 1)]
                        return {key: plain(child) for key, child in value.items()}
                    return value
                storage.data[cp.ScopeKey(cp)] = lua_table(self.h.lua, json.loads(json.dumps(plain(storage.data[cp.ScopeKey(cp)]))))
                restored = checkpoints.new(storage, None, None, pending)
                self.assertIsNone(restored.Load(restored, self.h.session['account'], self.h.session['place'], self.h.session['release'])[1])
                saved, reason = restored.Recovery(restored, proposal.actionKey)
                self.assertIsNone(reason)
                self.assertEqual(saved.baseline.count, count)
                self.assertEqual(saved.baseline.rows[count].payload.healId, f"stable-member-{count:02d}-abcdefghijklmnopqrstuv")
                after = self.h.snapshot(revision=0, native={"fullSync": True, "serverNow": 1001})
                after.session = 'restarted'
                after.native.crew = self.before.native.crew
                after.native.crew[2], after.native.crew[count] = after.native.crew[count], after.native.crew[2]
                self.assertEqual(self.feature.recoverSaved(saved, after), 'confirmed')
                after.native.crew[2].weapon = 'unrelated-gear-change'
                self.assertIsNone(self.feature.recoverSaved(saved, after))

    def test_bounded_identity_is_stable_across_sync_and_changes_with_last_member(self):
        self.large_roster(46)
        first = self.plan().actionKey
        self.assertLessEqual(len(first), 1000)
        self.before.revision = 2
        self.context.revision = 2
        self.assertEqual(self.plan().actionKey, first)
        self.before.native.crew[46].healId = 'different-stable-member'
        self.assertNotEqual(self.plan().actionKey, first)

    def test_missing_throwing_or_malformed_hash_refuses_new_proposal(self):
        view, _ = self.feature.read(self.before, self.context)
        for hash_fn in (None, self.h.lua.eval('function() error("unavailable") end'),
                        self.h.lua.eval('function() return "not-a-digest" end'),
                        self.h.lua.eval('function() return string.rep("0", 65) end')):
            with self.subTest(hash_fn=str(hash_fn)):
                proposal, reason = self.feature.propose(view, lua_table(self.h.lua, {'enabled': True}), hash_fn)
                self.assertIsNone(proposal)
                self.assertIsNotNone(reason)

    def test_legacy_receipt_key_recovers_without_retagging(self):
        proposal = self.plan()
        view, _ = self.feature.read(self.before, self.context)
        proposal.actionKey = 'crewSort:' + view.orderKey
        baseline, _ = self.feature.capture(proposal, self.before)
        self.before.native.serverNow = 1000
        baseline.serverNow = 1000
        after = self.h.snapshot(revision=0, native={"fullSync": True, "serverNow": 1001,
            "crew": [{"name": "Player"}, {"name": "Strong", "rarity": 5},
            {"name": "Pinned", "rarity": 3, "duty": {"city": "A"}}, {"name": "Weak", "rarity": 1}]})
        after.session = 'restarted'
        self.assertEqual(self.feature.recoverSaved(lua_table(self.h.lua, {
            'proposal': proposal, 'before': self.before, 'baseline': baseline,
            'reply': {'ok': True, 'changed': True}}), after), 'confirmed')

if __name__ == "__main__":
    unittest.main()
