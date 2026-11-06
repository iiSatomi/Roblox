"""Family contributions use personal counters, never a shared vault delta."""
import unittest

from engine_harness import Harness, lua_table


class FamilyContributionsTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.h.session["account"] = "42"
        self.module = self.h.load("src/tabs/family/FamilyContributions.luau")

    def view(self, **changes):
        value = {**self.h.session, "revision": 1, "capturedAt": 0,
            "familyId": "fam-a", "actorId": 42,
            "cash": 1000.25, "stamina": 50, "gold": 10, "boundGold": 0,
            "donateMin": 100, "contributeMax": 25,
            "ledger": {"cash": 500, "stamina": 10, "gold_bar": 2},
            "perks": {"enforcers": 0}, "progress": {"enforcers": 20},
            "staminaCosts": [30, 60], "staminaTracks": {"enforcers": True},
            "usage": {"familyCash": {"attempted": 0, "spent": 0},
                      "familyStamina": {"attempted": 0, "spent": 0},
                      "familyGold": {"attempted": 0, "spent": 0}}}
        value.update(changes)
        return lua_table(self.h.lua, value)

    def settings(self, **changes):
        value = {"enabled": True, "amount": 100, "reserve": 100,
                 "runBudget": 200, "maxAttempts": 2}
        value.update(changes)
        return lua_table(self.h.lua, value)

    def test_cash_uses_exact_configured_amount_and_personal_ledger(self):
        proposal, reason = self.module.cash.propose(self.view(), self.settings(),
                                                   lua_table(self.h.lua, {}))
        self.assertIsNone(reason)
        self.assertEqual(proposal.feature, "familyCash")
        self.assertEqual(proposal.intent.amount, 100)
        self.assertEqual(proposal.intent.ledgerBefore, 500)
        self.assertEqual(proposal.resources.cash, 100)
        self.assertIsNotNone(self.h.contracts.validateProposal(proposal, self.view())[0])

    def test_separate_run_caps_reserve_and_uncertain_exposure(self):
        for setting in (self.settings(enabled=False), self.settings(runBudget=0),
                        self.settings(maxAttempts=0), self.settings(amount=99),
                        self.settings(reserve=950)):
            self.assertIsNone(self.module.cash.propose(self.view(), setting,
                lua_table(self.h.lua, {}))[0])
        view = self.view()
        view.usage.familyCash.attempted = 2
        self.assertIsNone(self.module.cash.propose(view, self.settings(),
            lua_table(self.h.lua, {}))[0])
        view.usage.familyCash.attempted = 0
        view.usage.familyCash.spent = 101
        self.assertIsNone(self.module.cash.propose(view, self.settings(),
            lua_table(self.h.lua, {}))[0])
        self.assertIsNone(self.module.cash.propose(self.view(), self.settings(),
            lua_table(self.h.lua, {"uncertainCash": 801}))[0])

    def test_stamina_only_saved_batches_and_exact_perk_boundary(self):
        settings = self.settings(amount=5, reserve=10, runBudget=10,
                                 selectedPerk="enforcers")
        proposal, reason = self.module.stamina.propose(self.view(), settings,
                                                     lua_table(self.h.lua, {}))
        self.assertIsNone(reason)
        self.assertEqual(proposal.intent.perkProgressBefore, 20)
        self.assertEqual(proposal.resources.stamina, 5)
        for amount in (0, 2, 25):
            settings.amount = amount
            self.assertIsNone(self.module.stamina.propose(self.view(), settings,
                lua_table(self.h.lua, {}))[0])
        settings.amount = 5
        view = self.view(progress={"enforcers": 28})
        self.assertIsNone(self.module.stamina.propose(view, settings,
            lua_table(self.h.lua, {}))[0])
        settings.selectedPerk = "jobCut"
        self.assertIsNone(self.module.stamina.propose(self.view(), settings,
            lua_table(self.h.lua, {}))[0])

    def test_gold_has_its_own_budget_and_requires_known_loose_custody(self):
        settings = self.settings(amount=1, reserve=5, runBudget=2)
        proposal, reason = self.module.gold.propose(self.view(), settings,
                                                  lua_table(self.h.lua, {}))
        self.assertIsNone(reason)
        self.assertEqual(proposal.resources.gold_bar, 1)
        self.assertIsNone(self.module.gold.propose(self.view(boundGold=1), settings,
            lua_table(self.h.lua, {}))[0])
        self.assertIsNone(self.module.gold.propose(self.view(usage=None), settings,
            lua_table(self.h.lua, {}))[0])


if __name__ == "__main__":
    unittest.main()
