"""Goal hints stay read-only; cash quotes use current derived values."""
import unittest

from engine_harness import Harness, lua_table


class ContractsTabTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.context = self.h.load("src/game/Context.luau").new(
            self.h.contracts)
        self.goals = self.h.load(
            "src/tabs/contracts/ContractGoalState.luau")
        self.quotes = self.h.load(
            "src/tabs/contracts/ContractCashQuote.luau")
        self.blocked = self.h.load(
            "src/tabs/contracts/ContractGoalBlocked.luau")

    def snapshot(self):
        daily = [{"id": "job-a", "done": False,
                  "claimed": False, "progress": 2, "goal": 10}]
        daily += [{"id": "fight-a", "done": False,
                   "claimed": False, "progress": 0, "goal": 2}]
        daily += [{"id": "time-a", "done": False,
                   "claimed": False, "progress": 1, "goal": 5}]
        daily += [{"id": "unknown-a", "done": False,
                   "claimed": False, "progress": 1, "goal": 3}]
        daily += [{"id": "done-a", "done": True,
                   "claimed": False, "progress": 3, "goal": 3}]
        weekly = [{"id": "job-b", "done": False,
                   "claimed": False, "progress": 1, "goal": 30}]
        weekly += [{"id": "x" + str(i), "done": False,
                    "claimed": False, "progress": 0, "goal": 10}
                   for i in range(2, 6)]
        return self.h.snapshot(native={"fullSync": True,
            "contracts": {"daily": daily, "weekly": weekly},
            "derived": {"contractCash": [300, 700, 1500, 5000]}},
            contractTemplates=[{"id": "job-a", "key": "jobs"},
                               {"id": "job-b", "key": "jobs"},
                               {"id": "fight-a", "key": "fightwins"},
                               {"id": "time-a", "key": "playtime"},
                               {"id": "done-a", "key": "properties"}],
            catalogKey="contracts-release-a")

    def test_goal_classification_never_borrows_without_coordinator(self):
        raw = self.snapshot()
        context = self.context.Read(self.context, raw,
            lua_table(self.h.lua, self.h.session), 0, 2)[0]
        view, reason = self.goals.read(raw, context)
        self.assertIsNone(reason)
        rows = list(view["rows"].values())
        self.assertEqual([r["status"] for r in rows[:5]],
                         ["mapped", "blocked", "waiting",
                          "unsupported", "complete"])
        self.assertEqual(rows[0]["feature"], "jobs")
        self.assertIsNone(self.blocked.propose(view,
            lua_table(self.h.lua, {"enabled": True}))[0])
        raw["contractTemplates"][1]["key"] = "trades"
        changed, _ = self.goals.read(raw, context)
        self.assertEqual(changed["rows"][1]["status"], "unsupported")

    def test_derived_cash_quote_required(self):
        raw = self.snapshot()
        context = self.context.Read(self.context, raw,
            lua_table(self.h.lua, self.h.session), 0, 2)[0]
        quote, reason = self.quotes.read(raw, context)
        self.assertIsNone(reason)
        self.assertEqual(quote["cashByTier"][4], 5000)
        raw["native"]["derived"]["contractCash"] = None
        self.assertIsNone(self.quotes.read(raw, context)[0])

    def test_native_catalog_copies_reviewed_source(self):
        module = self.h.load(
            "src/tabs/contracts/NativeContractCatalog.luau")
        catalog = module.new(lua_table(self.h.lua, {"CONTRACTS": {
            "DAILY_TIERS": [1, 1, 2, 2, 3],
            "WEEKLY_TIERS": [4, 4, 4, 4, 4],
            "TEMPLATES": [{"id": "c_jobs", "key": "jobs"}],
            "BONUS": {"seals": 2, "energyRefill": True},
            "WEEKLY_BONUS": {"seals": 12,
                             "crate": "crate_fixervault"}}}),
            "a" * 64, "release-a")
        raw = self.h.snapshot(release="release-a",
                              native={"fullSync": True})
        enriched, reason = catalog.Enrich(catalog, raw)
        self.assertIsNone(reason)
        self.assertEqual(enriched["contractTemplates"][1]["key"], "jobs")
        self.assertEqual(enriched["contractConfig"]["dailyTiers"][5], 3)
        self.assertEqual(enriched["contractBonusConfig"]["weekly"]
                         ["crate"], "crate_fixervault")
        raw["release"] = "other"
        self.assertIsNone(catalog.Enrich(catalog, raw)[0])


if __name__ == "__main__":
    unittest.main()
