"""Source-backed ordinary property build, offline only."""
import unittest

from engine_harness import Harness, lua_table


class PropertiesTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.context = self.h.load("src/game/Context.luau").new(self.h.contracts)
        self.reader = self.h.load("src/game/PropertiesState.luau")
        self.planner = self.h.load("src/features/Properties.luau")
        self.evidence = self.h.load("src/features/PropertiesEvidence.luau")

    def raw(self, owned=1, revision=1, cash=2000, occupied=1,
            discount=0.1):
        return self.h.snapshot(revision=revision,
            native={"fullSync": True, "level": 10, "cash": cash,
                "properties": {"p_a": {"owned": owned},
                               "p_b": {"owned": 0}}},
            catalogKey="build-1",
            propertyCatalog=[{"id": "p_a", "level": 1,
                              "baseCost": 1000, "incomePerHour": 100},
                             {"id": "p_b", "level": 5,
                              "baseCost": 1500, "incomePerHour": 300}],
            propertyProof={"account": "user-a", "capturedAt": 0,
                           "occupied": occupied, "capacity": 3,
                           "buildDiscount": discount})

    def view(self, raw):
        context = self.context.Read(self.context, raw,
            lua_table(self.h.lua, self.h.session), 0, 2)[0]
        return self.reader.read(raw, context)

    def settings(self, policy="Best value", reserve=0, cap=2000,
                 limit=10):
        return lua_table(self.h.lua, {"enabled": True, "policy": policy,
            "cashReserve": reserve, "purchaseCap": cap,
            "ownedLimit": limit})

    def test_quote_and_best_value_choice(self):
        view, reason = self.view(self.raw())
        self.assertIsNone(reason)
        self.assertEqual(view["options"][1]["cost"], 1062)
        proposal, reason = self.planner.propose(view, self.settings(),
            lua_table(self.h.lua, {"cash": 0, "uncertainCash": 0}))
        self.assertIsNone(reason)
        self.assertEqual(proposal["intent"]["propId"], "p_b")
        self.assertEqual(proposal["intent"]["expectedCost"], 1350)

    def test_reserve_cap_capacity_and_selection(self):
        view, _ = self.view(self.raw())
        proposal, _ = self.planner.propose(view,
            self.settings(policy="Next tier", cap=1100),
            lua_table(self.h.lua, {"cash": 0, "uncertainCash": 0}))
        self.assertEqual(proposal["intent"]["propId"], "p_a")
        blocked, _ = self.planner.propose(view,
            self.settings(reserve=1000, cap=1100),
            lua_table(self.h.lua, {"cash": 0, "uncertainCash": 0}))
        self.assertIsNone(blocked)
        full, _ = self.view(self.raw(occupied=3))
        self.assertIsNone(self.planner.propose(full, self.settings(),
            lua_table(self.h.lua, {"cash": 0, "uncertainCash": 0}))[0])

    def test_missing_proof_or_catalog_fails_closed(self):
        raw = self.raw(discount=0.5)
        self.assertIsNone(self.view(raw)[0])
        raw = self.raw()
        raw["propertyProof"]["account"] = "other"
        self.assertIsNone(self.view(raw)[0])

    def test_reply_and_newer_owned_count_prove_only_one_build(self):
        before = self.raw()
        view, _ = self.view(before)
        proposal, _ = self.planner.propose(view, self.settings(),
            lua_table(self.h.lua, {"cash": 0, "uncertainCash": 0}))
        baseline, reason = self.evidence.capture(proposal, before)
        self.assertIsNone(reason)
        after = self.raw(revision=2)
        self.assertEqual(self.evidence.evaluate(proposal, before, after,
            lua_table(self.h.lua, {"ok": True}), baseline), "pending")
        after["native"]["properties"]["p_b"]["owned"] = 1
        self.assertEqual(self.evidence.evaluate(proposal, before, after,
            lua_table(self.h.lua, {"ok": True}), baseline), "confirmed")

    def test_preflight_rejects_changed_discount_or_proof_identity(self):
        before = self.raw()
        view, _ = self.view(before)
        proposal, _ = self.planner.propose(view, self.settings(),
            lua_table(self.h.lua, {"cash": 0, "uncertainCash": 0}))
        before["propertyProof"]["buildDiscount"] = 0.2
        self.assertIsNone(self.evidence.capture(proposal, before)[0])
        before["propertyProof"]["buildDiscount"] = 0.1
        before["propertyProof"]["account"] = "other"
        self.assertIsNone(self.evidence.capture(proposal, before)[0])

    def test_preflight_rechecks_cash_reserve(self):
        before = self.raw()
        view, _ = self.view(before)
        proposal, _ = self.planner.propose(view,
            self.settings(reserve=500),
            lua_table(self.h.lua, {"cash": 0, "uncertainCash": 0}))
        self.assertIsNotNone(proposal)
        before["native"]["cash"] = 1800
        self.assertIsNone(self.evidence.capture(proposal, before)[0])

    def test_native_catalog_derives_cap_discount_and_excludes_gold_ranking(self):
        module = self.h.load("src/tabs/property/NativePropertyCatalog.luau")
        catalog = module.new(lua_table(self.h.lua, {"PROPERTIES": [
            {"id": "p_a", "level": 1, "baseCost": 1000,
             "incomePerHour": 100},
            {"id": "p_gold", "level": 1, "baseCost": 100,
             "goldPerDay": 1}]}),
            lua_table(self.h.lua, {"PROPERTY": {"costGrowth": 1.18,
                                                "maxOwned": 10}}),
            "a" * 64, "release-a")
        raw = self.h.snapshot(native={"fullSync": True, "level": 10,
            "cash": 2000, "properties": {"p_a": {"owned": 1}},
            "propertyCap": 2, "derived": {"territoryBonuses": {
                "buildDiscount": 0.1}}})
        enriched, reason = catalog.Enrich(catalog, raw)
        self.assertIsNone(reason)
        self.assertEqual(enriched["propertyProof"]["occupied"], 1)
        self.assertEqual(enriched["propertyProof"]["capacity"], 2)
        view, reason = self.view(enriched)
        self.assertIsNone(reason)
        proposal, reason = self.planner.propose(view, self.settings(),
            lua_table(self.h.lua, {"cash": 0, "uncertainCash": 0}))
        self.assertIsNone(reason)
        self.assertEqual(proposal["intent"]["propId"], "p_a")
        raw["native"]["derived"] = lua_table(self.h.lua, {})
        self.assertIsNone(catalog.Enrich(catalog, raw)[0])


if __name__ == "__main__":
    unittest.main()
