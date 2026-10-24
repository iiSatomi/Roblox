"""Next-tier Safehouse upgrade respects level, caps and cash reserve."""
import unittest

from engine_harness import Harness, lua_table


TIERS = [{"name": "Tier " + str(i), "level": i,
          "cost": (i - 1) * 1000} for i in range(1, 19)]


class SafehouseUpgradeTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.context = self.h.load("src/game/Context.luau").new(self.h.contracts)
        self.reader = self.h.load("src/game/SafehouseState.luau")
        self.planner = self.h.load("src/features/SafehouseUpgrades.luau")
        self.evidence = self.h.load("src/features/SafehouseUpgradesEvidence.luau")

    def raw(self, revision=1, tier=3, cash=10000, level=10,
            catalog=None):
        return self.h.snapshot(revision=revision,
            native={"fullSync": True, "safehouse": tier,
                    "cash": cash, "level": level, "maxLevel": level},
            safehouseCatalog=catalog if catalog is not None else TIERS,
            catalogKey="safehouse-build-1")

    def view(self, raw):
        context, reason = self.context.Read(self.context, raw,
            lua_table(self.h.lua, self.h.session), 0, 2)
        self.assertIsNone(reason)
        return self.reader.read(raw, context)

    def proposal(self, raw=None, max_tier=18, max_cost=1000000,
                 reserve=1000, uncertain=0, enabled=True):
        view, reason = self.view(raw or self.raw())
        self.assertIsNone(reason)
        return self.planner.propose(view, lua_table(self.h.lua, {
            "enabled": enabled, "maxTier": max_tier,
            "maxCost": max_cost, "cashReserve": reserve}),
            lua_table(self.h.lua, {"cash": 0,
                                   "uncertainCash": uncertain}))

    def test_next_tier_cost_and_exact_tier_proof(self):
        before = self.raw()
        proposal, reason = self.proposal(before)
        self.assertIsNone(reason)
        self.assertEqual(proposal["intent"]["nextTier"], 4)
        self.assertEqual(proposal["resources"]["cash"], 3000)
        baseline, reason = self.evidence.capture(proposal, before)
        self.assertIsNone(reason)
        header, _ = self.h.contracts.validateSnapshot(before,
            lua_table(self.h.lua, self.h.session))
        ok = lua_table(self.h.lua, {"ok": True})
        self.assertEqual(self.evidence.evaluate(proposal, header,
            self.raw(2), ok, baseline), "pending")
        self.assertEqual(self.evidence.evaluate(proposal, header,
            self.raw(2, tier=4, cash=7700), ok, baseline), "confirmed")

    def test_level_cap_cash_and_disable_block(self):
        self.assertIsNone(self.proposal(enabled=False)[0])
        self.assertIsNone(self.proposal(max_tier=3)[0])
        self.assertIsNone(self.proposal(max_cost=2999)[0])
        self.assertIsNone(self.proposal(reserve=8000)[0])
        self.assertIsNone(self.proposal(uncertain=7000)[0])
        self.assertIsNone(self.proposal(self.raw(level=3))[0])
        self.assertIsNone(self.proposal(self.raw(tier=18))[0])

    def test_missing_or_changed_catalog_blocks(self):
        self.assertIsNone(self.view(self.raw(catalog=TIERS[:17]))[0])
        bad = [dict(row) for row in TIERS]
        bad[3]["cost"] = bad[2]["cost"]
        self.assertIsNone(self.view(self.raw(catalog=bad))[0])
        bad = self.raw()
        bad["native"]["fullSync"] = False
        self.assertIsNone(self.view(bad)[0])

    def test_rejected_or_unexpected_tier_jump_is_not_success(self):
        before = self.raw()
        proposal, _ = self.proposal(before)
        baseline, _ = self.evidence.capture(proposal, before)
        header, _ = self.h.contracts.validateSnapshot(before,
            lua_table(self.h.lua, self.h.session))
        self.assertEqual(self.evidence.evaluate(proposal, header,
            self.raw(2, tier=5), lua_table(self.h.lua, {"ok": True}), baseline),
            "pending")
        self.assertEqual(self.evidence.evaluate(proposal, header,
            self.raw(2), lua_table(self.h.lua, {"ok": False}), baseline),
            "rejected")

    def test_source_catalog_and_send_time_cash_reserve(self):
        source = self.h.load(
            "src/tabs/safehouse/NativeSafehouseCatalog.luau")
        catalog = source.new(lua_table(self.h.lua, {"SAFEHOUSE": [
            dict(row, mult=1 + i / 100)
            for i, row in enumerate(TIERS, 1)]}),
            "a" * 64, "release-a")
        raw = self.raw()
        enriched, reason = catalog.Enrich(catalog, raw)
        self.assertIsNone(reason)
        self.assertEqual(enriched["safehouseCatalog"][17]["level"], 17)
        proposal, reason = self.proposal(enriched, reserve=7000)
        self.assertIsNone(reason)
        enriched["native"]["cash"] = 9000
        self.assertIsNone(self.evidence.capture(proposal, enriched)[0])


if __name__ == "__main__":
    unittest.main()
