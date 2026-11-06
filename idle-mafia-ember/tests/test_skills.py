"""Saved-client skill rules through one offline broker-compatible proposal."""
import unittest

from engine_harness import Harness, lua_table


RULES = {
    "energy": {"baseCost": 1, "costEvery": 5},
    "stamina": {"baseCost": 1, "costEvery": 5},
    "health": {"baseCost": 1, "costEvery": 5},
    "attack": {"baseCost": 1, "costEvery": 3},
    "defense": {"baseCost": 1, "costEvery": 3},
    "property": {"baseCost": 1, "costMultiplier": 2},
}


class SkillsTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.context = self.h.load("src/game/Context.luau").new(self.h.contracts)
        self.reader = self.h.load("src/game/SkillsState.luau")
        self.planner = self.h.load("src/features/Skills.luau")
        self.evidence = self.h.load("src/features/SkillsEvidence.luau")

    def raw(self, revision=1, points=12, allocs=None, rules=None, **changes):
        data = {"native": {"fullSync": True, "skillPoints": points,
                           "allocs": allocs if allocs is not None else
                           {"energy": 4}, "pools": {"energy": 10}},
                "skillRules": rules if rules is not None else RULES,
                "catalogKey": "skill-build-1"}
        data.update(changes)
        return self.h.snapshot(revision=revision, **data)

    def view(self, raw):
        context, reason = self.context.Read(
            self.context, raw, lua_table(self.h.lua, self.h.session), 0, 2)
        self.assertIsNone(reason)
        return self.reader.read(raw, context)

    def propose(self, raw=None, **settings):
        view, reason = self.view(raw or self.raw())
        self.assertIsNone(reason)
        values = {"enabled": True, "stat": "energy",
                  "maxAllocations": 8, "batchSize": 100}
        values.update(settings)
        return self.planner.propose(view, lua_table(self.h.lua, values))

    def test_current_cost_steps_and_bounded_native_batch(self):
        proposal, reason = self.propose()
        self.assertIsNone(reason)
        self.assertEqual(proposal["feature"], "skills")
        self.assertEqual(proposal["intent"]["stat"], "energy")
        self.assertEqual(proposal["intent"]["count"], 4)
        self.assertEqual(proposal["resources"]["skillPoints"], 7)
        self.assertIn("skill-build-1", proposal["actionKey"])
        one, reason = self.propose(batchSize=1)
        self.assertIsNone(reason)
        self.assertEqual(one["intent"]["count"], 1)
        self.assertEqual(one["resources"]["skillPoints"], 1)

    def test_expensive_property_limited_by_points_and_target(self):
        proposal, reason = self.propose(
            self.raw(points=15, allocs={"property": 2}),
            stat="property", maxAllocations=10)
        self.assertIsNone(reason)
        self.assertEqual(proposal["intent"]["count"], 2)
        self.assertEqual(proposal["resources"]["skillPoints"], 12)
        self.assertIsNone(self.propose(stat="property", maxAllocations=0)[0])

    def test_reader_and_planner_fail_closed(self):
        self.assertIsNone(self.view(self.raw(rules={"energy": RULES["energy"]}))[0])
        self.assertIsNone(self.view(self.raw(points=-1))[0])
        self.assertIsNone(self.view(self.raw(allocs={"energy": 1.5}))[0])
        self.assertIsNone(self.view(self.raw(native={"fullSync": False}))[0])
        self.assertIsNone(self.propose(enabled=False)[0])
        self.assertIsNone(self.propose(stat="luck")[0])
        self.assertIsNone(self.propose(batchSize=101)[0])
        self.assertIsNone(self.propose(maxAllocations=4)[0])

    def test_exact_replication_confirms_not_reply_alone(self):
        before = self.raw()
        proposal, _ = self.propose(before)
        baseline, reason = self.evidence.capture(proposal, before)
        self.assertIsNone(reason)
        header, _ = self.h.contracts.validateSnapshot(
            before, lua_table(self.h.lua, self.h.session))
        reply = lua_table(self.h.lua, {"ok": True})
        self.assertEqual(self.evidence.evaluate(
            proposal, header, self.raw(2), reply, baseline), "pending")
        after = self.raw(2, points=5, allocs={"energy": 8})
        self.assertEqual(self.evidence.evaluate(
            proposal, header, after, reply, baseline), "confirmed")
        self.assertEqual(self.evidence.evaluate(
            proposal, header, self.raw(2, points=5, allocs={"energy": 7}),
            reply, baseline), "pending")

    def test_rejection_and_session_mismatch(self):
        before = self.raw()
        proposal, _ = self.propose(before)
        baseline, _ = self.evidence.capture(proposal, before)
        header, _ = self.h.contracts.validateSnapshot(
            before, lua_table(self.h.lua, self.h.session))
        rejected = lua_table(self.h.lua, {"ok": False})
        self.assertEqual(self.evidence.evaluate(
            proposal, header, self.raw(2), rejected, baseline), "rejected")
        self.assertEqual(self.evidence.evaluate(
            proposal, header, self.raw(2, account="other"),
            rejected, baseline), "pending")


if __name__ == "__main__":
    unittest.main()
