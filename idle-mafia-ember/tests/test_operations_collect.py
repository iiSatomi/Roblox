"""Ready Operation collection stays separate from starting or paid finishing."""
import unittest

from engine_harness import Harness, lua_table


class OperationsCollectTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.context = self.h.load("src/game/Context.luau").new(self.h.contracts)
        self.reader = self.h.load("src/game/OperationsState.luau")
        self.planner = self.h.load("src/features/OperationsCollect.luau")
        self.evidence = self.h.load("src/features/OperationsCollectEvidence.luau")

    def raw(self, revision=1, active=None, **changes):
        data = {"native": {
            "fullSync": True, "level": 30, "maxLevel": 30,
            "respect": 100, "cash": 5000,
            "operations": {"active": active if active is not None else [
                {"opId": "op_fence", "remaining": 10, "slot": 1},
                {"opId": "op_truck", "remaining": 0, "slot": 2},
            ]}},
            "catalogKey": "ops-build-1",
            "operationCatalog": [
                {"id": "op_fence", "duration": 600, "cost": 200,
                 "cash": 1500, "xp": 20},
                {"id": "op_truck", "duration": 3600, "cost": 4000,
                 "cash": 18000, "xp": 180},
            ]}
        data.update(changes)
        return self.h.snapshot(revision=revision, **data)

    def propose(self, raw=None, enabled=True):
        raw = raw or self.raw()
        context, reason = self.context.Read(
            self.context, raw, lua_table(self.h.lua, self.h.session), 0, 2)
        self.assertIsNone(reason)
        view, reason = self.reader.read(raw, context)
        self.assertIsNone(reason)
        return self.planner.propose(view, lua_table(self.h.lua, {"enabled": enabled}))

    def test_only_ready_native_entry_produces_current_index(self):
        proposal, reason = self.propose()
        self.assertIsNone(reason)
        self.assertEqual(proposal["feature"], "collect")
        self.assertEqual(proposal["intent"]["index"], 2)
        self.assertEqual(proposal["intent"]["targetId"], "op_truck")
        self.assertEqual(len(list(proposal["resources"].items())), 0)

    def test_running_disabled_and_wrong_index_block(self):
        self.assertIsNone(self.propose(enabled=False)[0])
        raw = self.raw(active=[{"opId": "op_fence", "remaining": 1}])
        self.assertIsNone(self.propose(raw)[0])
        raw = self.raw(active=[{"opId": "op_truck", "remaining": -1}])
        self.assertEqual(self.propose(raw)[0]["intent"]["index"], 1)

    def test_reply_and_selected_run_disappearance_confirm(self):
        before = self.raw()
        proposal, _ = self.propose(before)
        baseline, reason = self.evidence.capture(proposal, before)
        self.assertIsNone(reason)
        header, _ = self.h.contracts.validateSnapshot(
            before, lua_table(self.h.lua, self.h.session))
        after = self.raw(2, [{"opId": "op_fence", "remaining": 9, "slot": 1}])
        result = self.evidence.evaluate(proposal, header, after,
                                        lua_table(self.h.lua, {"ok": True}), baseline)
        self.assertEqual(result, "confirmed")

    def test_reply_only_other_disappearance_and_rejection(self):
        before = self.raw()
        proposal, _ = self.propose(before)
        baseline, _ = self.evidence.capture(proposal, before)
        header, _ = self.h.contracts.validateSnapshot(
            before, lua_table(self.h.lua, self.h.session))
        unchanged = self.raw(2)
        other_removed = self.raw(2, [{"opId": "op_truck", "remaining": 0}])
        success = lua_table(self.h.lua, {"ok": True})
        self.assertEqual(self.evidence.evaluate(proposal, header, unchanged,
                                                success, baseline), "pending")
        self.assertEqual(self.evidence.evaluate(proposal, header, other_removed,
                                                success, baseline), "pending")
        self.assertEqual(self.evidence.evaluate(proposal, header, unchanged,
                         lua_table(self.h.lua, {"ok": False}), baseline), "rejected")
        self.assertEqual(self.evidence.evaluate(proposal, header, unchanged,
                         None, baseline), "pending")


if __name__ == "__main__":
    unittest.main()
