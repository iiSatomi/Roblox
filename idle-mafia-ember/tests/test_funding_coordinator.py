"""Enabled ordinary purchases derive exact funding without sending them."""
import unittest

from engine_harness import Harness, lua_table


TIERS = [{"name": "Tier " + str(i), "level": i,
          "cost": (i - 1) * 1000} for i in range(1, 19)]


class FundingCoordinatorTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.context = self.h.load("src/game/Context.luau").new(self.h.contracts)
        self.coordinator = self.h.load("src/engine/FundingCoordinator.luau")
        self.modules = lua_table(self.h.lua, {
            "SafehouseState": self.h.load("src/game/SafehouseState.luau"),
            "SafehouseUpgrades": self.h.load("src/features/SafehouseUpgrades.luau"),
            "OperationsState": self.h.load("src/game/OperationsState.luau"),
            "OperationsStart": self.h.load("src/features/OperationsStart.luau"),
        })

    def raw(self, cash=1000, banked=10000, active=None):
        return self.h.snapshot(native={
            "fullSync": True, "cash": cash, "banked": banked,
            "safehouse": 3, "level": 15, "maxLevel": 15,
            "respect": 100, "derived": {"fourthSlot": False},
            "operations": {"active": active if active is not None else []}},
            catalogKey="build-1", safehouseCatalog=TIERS,
            operationCatalog=[{"id": "op_fence", "duration": 600,
                "cost": 2000, "cash": 3000, "xp": 20}],
            crateCatalog={})

    def derive(self, raw=None, operations=False, safehouse=True,
               withdraw=True):
        raw = raw or self.raw()
        context, reason = self.context.Read(self.context, raw,
            lua_table(self.h.lua, self.h.session), 0, 2)
        self.assertIsNone(reason)
        settings = lua_table(self.h.lua, {
            "withdraw": {"enabled": withdraw},
            "operations": {"enabled": operations,
                           "policy": "Highest tier"},
            "safehouse": {"enabled": safehouse, "maxTier": 18,
                          "maxCost": 1000000, "cashReserve": 500}})
        reserves = lua_table(self.h.lua, {"cash": 0, "uncertainCash": 0})
        return self.coordinator.derive(raw, context, settings,
                                       reserves, self.modules)

    def test_safehouse_exact_shortfall(self):
        request, reason = self.derive()
        self.assertIsNone(reason)
        self.assertEqual(request["purpose"], "safehouse")
        self.assertEqual(request["requiredCash"], 3500)
        self.assertIn("safehouse", request["purchaseKey"])

    def test_operations_priority_and_no_need_when_affordable(self):
        request, reason = self.derive(operations=True)
        self.assertIsNone(reason)
        self.assertEqual(request["purpose"], "operations")
        self.assertEqual(request["requiredCash"], 2000)
        self.assertIsNone(self.derive(self.raw(cash=5000),
                                     operations=True)[0])

    def test_disabled_origin_or_funding_never_derives(self):
        self.assertIsNone(self.derive(safehouse=False)[0])
        self.assertIsNone(self.derive(withdraw=False)[0])
        self.assertIsNone(self.derive(self.raw(banked=500))[0])
        self.assertIsNone(self.derive(self.raw(active=[
            {"opId": "op_fence", "remaining": 100},
            {"opId": "op_fence", "remaining": 100}]),
            operations=True, safehouse=False)[0])


if __name__ == "__main__":
    unittest.main()
