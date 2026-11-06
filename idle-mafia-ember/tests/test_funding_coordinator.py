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
            "HeistBoardState": self.h.load("src/game/HeistBoardState.luau"),
            "HeistStart": self.h.load("src/features/HeistStart.luau"),
            "PropertiesState": self.h.load("src/game/PropertiesState.luau"),
            "Properties": self.h.load("src/features/Properties.luau"),
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
               withdraw=True, permissions=None, heists=False, properties=False,
               choices=None, reserves=None, owners=None):
        raw = raw or self.raw()
        context, reason = self.context.Read(self.context, raw,
            lua_table(self.h.lua, self.h.session), 0, 2)
        self.assertIsNone(reason)
        settings = lua_table(self.h.lua, {
            "withdraw": {"enabled": withdraw, "allowOperations": True,
                         "allowSafehouse": True, **(permissions or {})},
            "heists": {"enabled": heists, "policy": "Best chest"},
            "properties": {"enabled": properties, "policy": "Best value",
                           "purchaseCap": 10000, "cashReserve": 500,
                           "ownedLimit": 10},
            "operations": {"enabled": operations,
                           "policy": "Highest tier"},
            "safehouse": {"enabled": safehouse, "maxTier": 18,
                          "maxCost": 1000000, "cashReserve": 500}})
        for feature, fields in (choices or {}).items():
            for key, value in fields.items():
                settings[feature][key] = value
        reserves = lua_table(self.h.lua, reserves or {"cash": 0, "uncertainCash": 0})
        return self.coordinator.derive(raw, context, settings,
                                       reserves, self.modules, owners)

    def heist_raw(self, cash=0, banked=10000):
        raw = self.raw(cash, banked)
        raw.native.serverNow = 2000000
        raw.native.pools = lua_table(self.h.lua, {"energy": 10})
        raw.heistCatalog = lua_table(self.h.lua, [{"id": "h_a", "level": 1,
            "stake": 2000, "energy": 5, "duration": 1200, "cash": 4000,
            "xp": 20, "crateCount": 1, "crateChance": 1,
            "crateRarity": 3, "helpGoal": 2}])
        raw.heistBoardProof = lua_table(self.h.lua, {"account": "user-a",
            "capturedAt": 0, "board": {"ok": True, "serverNow": 2000000,
            "rows": [], "startsLeft": 2, "bustWait": 0}})
        return raw

    def property_raw(self, cash=0, banked=10000):
        raw = self.raw(cash, banked)
        raw.native.properties = lua_table(self.h.lua, {"p_a": {"owned": 1}})
        raw.propertyCatalog = lua_table(self.h.lua, [{"id": "p_a", "level": 1,
            "baseCost": 1000, "incomePerHour": 100}])
        raw.propertyProof = lua_table(self.h.lua, {"account": "user-a",
            "capturedAt": 0, "occupied": 1, "capacity": 3, "buildDiscount": .1})
        return raw

    def test_each_scoped_permission_blocks_derivation_without_starving_next(self):
        self.assertIsNone(self.derive(permissions={"allowSafehouse": False})[0])
        request, _ = self.derive(operations=True, permissions={"allowOperations": False})
        self.assertEqual(request.purpose, "safehouse")

    def test_new_purposes_require_explicit_permission(self):
        for purpose, raw, permission in (("heists", self.heist_raw(), "allowHeists"),
                ("properties", self.property_raw(), "allowProperties")):
            with self.subTest(purpose=purpose):
                args = {purpose: True, "safehouse": False}
                self.assertIsNone(self.derive(raw, **args)[0])
                request, reason = self.derive(raw, permissions={permission: True}, **args)
                self.assertIsNone(reason)
                self.assertEqual(request.purpose, purpose)
                self.assertEqual(request.requiredCash, 2000 if purpose == "heists" else 1562)

    def test_heist_non_cash_guards_and_selected_limits_precede_funding(self):
        for change in ("energy", "starts", "bust", "selection", "level", "quote", "reserve"):
            with self.subTest(change=change):
                raw, choices = self.heist_raw(), {}
                if change == "energy": raw.native.pools.energy = 4
                if change == "starts": raw.heistBoardProof.board.startsLeft = 0
                if change == "bust": raw.heistBoardProof.board.bustWait = 1
                if change == "level": raw.native.level = 0
                if change == "quote": raw.heistCatalog[1].duration = None
                if change == "selection": choices = {"selection": "Only selected", "selectedIds": "missing"}
                if change == "reserve": choices = {"energyReserve": 6}
                self.assertIsNone(self.derive(raw, safehouse=False, heists=True,
                    permissions={"allowHeists": True}, choices={"heists": choices})[0])

    def test_property_capacity_limits_selection_and_native_discount_precede_funding(self):
        for change in ("capacity", "owned", "cap", "selection", "level", "discount"):
            with self.subTest(change=change):
                raw, choices = self.property_raw(), {}
                if change == "capacity": raw.propertyProof.occupied = 3
                if change == "owned": choices = {"ownedLimit": 1}
                if change == "cap": choices = {"purchaseCap": 1061}
                if change == "selection": choices = {"selection": "Only selected", "selectedIds": "missing"}
                if change == "level": choices = {"limitsEnabled": True, "minLevel": 2}
                if change == "discount": raw.propertyProof.buildDiscount = .5
                self.assertIsNone(self.derive(raw, safehouse=False, properties=True,
                    permissions={"allowProperties": True}, choices={"properties": choices})[0])

    def test_new_purposes_keep_cash_and_energy_reservations(self):
        request, _ = self.derive(self.heist_raw(), safehouse=False, heists=True,
            permissions={"allowHeists": True}, reserves={"cash": 300, "uncertainCash": 200})
        self.assertEqual(request.requiredCash, 2500)
        self.assertIsNone(self.derive(self.heist_raw(), safehouse=False, heists=True,
            permissions={"allowHeists": True}, reserves={"energy": 4, "uncertainEnergy": 2})[0])
        request, _ = self.derive(self.property_raw(), safehouse=False, properties=True,
            permissions={"allowProperties": True}, reserves={"cash": 300, "uncertainCash": 200})
        self.assertEqual(request.requiredCash, 2062)

    def test_withdrawal_cap_skips_unfundable_higher_priority_purchase(self):
        raw = self.raw()
        raw.operationCatalog[1].cost = 5000
        request, reason = self.derive(raw, operations=True,
            permissions={"maxWithdrawal": 2500})
        self.assertIsNone(reason)
        self.assertEqual(request.purpose, "safehouse")
        self.assertIsNone(self.derive(raw, operations=True, safehouse=False,
            permissions={"maxWithdrawal": 2500})[0])

    def test_fractional_bank_must_cover_rounded_native_withdrawal(self):
        self.assertIsNone(self.derive(self.raw(cash=1000.25, banked=999.75),
            operations=True, safehouse=False)[0])

    def test_safehouse_exact_shortfall(self):
        request, reason = self.derive()
        self.assertIsNone(reason)
        self.assertEqual(request["purpose"], "safehouse")
        self.assertEqual(request["requiredCash"], 3500)
        self.assertIn("safehouse", request["purchaseKey"])
        self.assertEqual(request["session"], "run-a")
        self.assertEqual(request["place"], "73897506680154")
        self.assertEqual(request["release"], "release-a")
        self.assertEqual(request["revision"], 1)

    def test_operations_priority_and_no_need_when_affordable(self):
        request, reason = self.derive(operations=True)
        self.assertIsNone(reason)
        self.assertEqual(request["purpose"], "operations")
        self.assertEqual(request["requiredCash"], 2000)
        self.assertIsNone(self.derive(self.raw(cash=5000),
                                     operations=True)[0])

    def test_fractional_native_balances_can_fund_operation(self):
        request, reason = self.derive(
            self.raw(cash=1000.25, banked=10000.75),
            operations=True, safehouse=False)
        self.assertIsNone(reason)
        self.assertEqual(request["requiredCash"], 2000)

    def test_fractional_native_balances_can_fund_safehouse(self):
        request, reason = self.derive(
            self.raw(cash=1000.25, banked=10000.75),
            operations=False, safehouse=True)
        self.assertIsNone(reason)
        self.assertEqual(request["requiredCash"], 3500)

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
