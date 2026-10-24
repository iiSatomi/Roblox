"""Ordinary Operation start proposals use current unlocks and cash exposure."""
import unittest

from engine_harness import Harness, lua_table


class OperationsPlannerTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.context = self.h.load("src/game/Context.luau").new(self.h.contracts)
        self.reader = self.h.load("src/game/OperationsState.luau")
        self.planner = self.h.load("src/features/OperationsStart.luau")

    def view(self, cash=10000, level=15, active=None, catalog=None,
             crate_catalog=None):
        native = {"fullSync": True, "level": level, "maxLevel": level,
                  "respect": 200, "cash": cash,
                  "derived": {"fourthSlot": False},
                  "operations": {"active": active or []}}
        raw = self.h.snapshot(
            native=native, catalogKey="ops-build-1",
            operationCatalog=[
                {"id": "op_fence", "duration": 600, "cost": 200,
                 "cash": 1500, "xp": 20, "crate": "crate_loot",
                 "crateChance": 0.1},
                {"id": "op_truck", "duration": 3600, "cost": 4000,
                 "cash": 18000, "xp": 180, "level": 8,
                 "crate": "crate_rare", "crateChance": 0.2},
            ] if catalog is None else catalog,
            crateCatalog={
                "crate_loot": {"buckets": [{"weight": 60, "rarity": 1},
                                            {"weight": 30, "rarity": 2},
                                            {"weight": 10, "rarity": 3}]},
                "crate_rare": {"buckets": [{"weight": 70, "rarity": 3},
                                            {"weight": 25, "rarity": 4},
                                            {"weight": 5, "rarity": 5}]},
            } if crate_catalog is None else crate_catalog,
        )
        context, reason = self.context.Read(
            self.context, raw, lua_table(self.h.lua, self.h.session), 0, 2)
        self.assertIsNone(reason)
        return self.reader.read(raw, context)

    def propose(self, view, policy="Best chest", enabled=True,
                reserved=0, uncertain=0):
        return self.planner.propose(
            view, lua_table(self.h.lua, {"enabled": enabled, "policy": policy}),
            lua_table(self.h.lua, {"cash": reserved, "uncertainCash": uncertain}),
        )

    def test_best_chest_uses_chance_weighted_native_bucket_rarity(self):
        view, reason = self.view()
        self.assertIsNone(reason)
        proposal, reason = self.propose(view)
        self.assertIsNone(reason)
        self.assertEqual(proposal["feature"], "operations")
        self.assertEqual(proposal["intent"]["targetId"], "op_truck")
        self.assertEqual(proposal["resources"]["cash"], 4000)
        self.assertEqual(proposal["revision"], view["revision"])

    def test_highest_tier_uses_catalog_progression_order(self):
        view, _ = self.view()
        proposal, reason = self.propose(view, policy="Highest tier")
        self.assertIsNone(reason)
        self.assertEqual(proposal["intent"]["targetId"], "op_truck")

    def test_full_slots_locked_and_cash_reserve_block(self):
        one = {"opId": "op_fence", "remaining": 10, "slot": 1}
        view, _ = self.view(active=[one, {**one, "slot": 2}])
        self.assertIsNone(self.propose(view)[0])
        view, _ = self.view(cash=100)
        self.assertIsNone(self.propose(view)[0])
        view, _ = self.view(cash=4100)
        proposal, _ = self.propose(view, reserved=200)
        self.assertEqual(proposal["intent"]["targetId"], "op_fence")
        proposal, _ = self.propose(view, uncertain=3901)
        self.assertIsNone(proposal)
        view, _ = self.view(level=1)
        proposal, _ = self.propose(view)
        self.assertEqual(proposal["intent"]["targetId"], "op_fence")

    def test_missing_chest_rules_and_unsupported_policy_fail_closed(self):
        view, reason = self.view(crate_catalog={})
        self.assertIsNone(reason)
        self.assertIsNone(self.propose(view, policy="Best chest")[0])
        self.assertEqual(self.propose(view, policy="Highest tier")[0]
                         ["intent"]["targetId"], "op_truck")
        view, _ = self.view()
        for policy in ("Custom", "Mystery", None):
            self.assertIsNone(self.propose(view, policy=policy)[0])
        self.assertIsNone(self.propose(view, enabled=False)[0])
        no_crates = [{"id": "plain", "duration": 600, "cost": 10,
                      "cash": 20, "xp": 1}]
        view, reason = self.view(catalog=no_crates, crate_catalog={})
        self.assertIsNone(reason)
        self.assertIsNone(self.propose(view, policy="Best chest")[0])
        self.assertEqual(self.propose(view, policy="Highest tier")[0]
                         ["intent"]["targetId"], "plain")


if __name__ == "__main__":
    unittest.main()
