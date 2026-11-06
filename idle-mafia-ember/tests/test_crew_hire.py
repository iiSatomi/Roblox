"""Empty-slot Crew hires require a current tier and decree quote."""
import unittest

from engine_harness import Harness, lua_table


class CrewHireTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.source = self.h.load("src/tabs/crew/NativeHireCatalog.luau")
        self.feature = self.h.load("src/tabs/crew/CrewHire.luau")
        self.config = lua_table(self.h.lua, {"CREW": {"hireTiers": [
            {"id": "street", "name": "STREET", "cost": 10000},
            {"id": "elite", "name": "ELITE", "cost": 100000} ]}})
        self.catalog = self.source.new(self.config, "b" * 64, "release-a")
        self.before = self.h.snapshot(native={"fullSync": True,
            "cash": 30000, "crew": [{"name": "Player"}, {},
                                       {"name": "Home", "rarity": 4}]},
            economyProof={"account": "user-a", "capturedAt": 0,
                "city": "ny", "revision": 3, "familyId": "",
                "rulerId": "", "shopPct": 0, "hirePct": 10,
                "marketPct": 10, "territoryShopDiscount": 0,
                "globalShopSale": 0})
        self.before["native"]["cityId"] = "ny"
        self.before.crewHireUsageProof=lua_table(self.h.lua,{**self.h.session,"revision":1,"capturedAt":0,"attempted":0,"spent":0})
        self.before, reason = self.catalog.Enrich(self.catalog, self.before)
        self.assertIsNone(reason)
        self.context = lua_table(self.h.lua, {**self.h.session,
            "revision": 1, "capturedAt": 0, "hireCatalogKey": "b" * 64})

    def plan(self):
        view, reason = self.feature.read(self.before, self.context)
        self.assertIsNone(reason)
        proposal, reason = self.feature.propose(view, lua_table(self.h.lua,
            {"enabled": True, "policy": "street", "custom":
             {"maxCost": 20000, "cashReserve": 10000,"maxAttempts":1,"maxSpend":20000}}))
        self.assertIsNone(reason)
        return proposal

    def test_quote_and_exact_new_member_evidence(self):
        proposal = self.plan()
        self.assertEqual(proposal["intent"]["kind"], "crewHire")
        self.assertEqual(proposal["intent"]["tier"], "street")
        self.assertEqual(proposal["intent"]["cost"], 11000)
        baseline, reason = self.feature.capture(proposal, self.before)
        self.assertIsNone(reason)
        after = self.h.snapshot(revision=2, native={"fullSync": True,
            "cash": 19000, "crew": [{"name": "Player"},
                {"name": "New", "rarity": 3, "atk": 8, "def": 9},
                {"name": "Home", "rarity": 4}]})
        reply = lua_table(self.h.lua, {"ok": True, "index": 2,
            "member": {"name": "New", "rarity": 3, "atk": 8, "def": 9}})
        self.assertEqual(self.feature.evaluate(proposal, self.before,
            after, reply, baseline), "confirmed")
        after["native"]["crew"][2]["name"] = "Other"
        self.assertEqual(self.feature.evaluate(proposal, self.before,
            after, reply, baseline), "pending")

    def test_quote_or_slot_change_blocks_send(self):
        proposal = self.plan()
        self.before["economyProof"]["hirePct"] = 11
        self.assertIsNone(self.feature.capture(proposal, self.before)[0])
        self.before["economyProof"]["hirePct"] = 10
        self.before["native"]["crew"][2]["rarity"] = 2
        self.assertIsNone(self.feature.capture(proposal, self.before)[0])

    def test_no_replacement_or_unaffordable_tier(self):
        view, _ = self.feature.read(self.before, self.context)
        self.assertIsNone(self.feature.propose(view, lua_table(self.h.lua,
            {"enabled": True, "policy": "elite", "custom":
             {"maxCost": 20000, "cashReserve": 0}}))[0])
        self.before["native"]["crew"][2]["rolling"] = True
        self.assertIsNone(self.feature.read(self.before, self.context)[0])

    def test_fractional_cash_keeps_integer_hire_quote(self):
        self.before["native"]["cash"] = 30000.25
        proposal = self.plan()
        self.assertEqual(proposal["intent"]["cost"], 11000)
        baseline, reason = self.feature.capture(proposal, self.before)
        self.assertIsNone(reason)
        self.assertEqual(baseline["cost"], 11000)

    def test_reply_member_without_invented_index_can_confirm_exact_cash_debit(self):
        proposal = self.plan()
        baseline = self.feature.capture(proposal, self.before)[0]
        member = {"name": "New", "rarity": 3, "atk": 8, "def": 9}
        after = self.h.snapshot(revision=2, native={"fullSync": True, "cash": 19000,
            "crew": [{"name": "Player"}, member, {"name": "Home", "rarity": 4}]})
        reply = lua_table(self.h.lua, {"ok": True, "member": member})
        self.assertEqual(self.feature.evaluate(proposal, self.before, after, reply, baseline), "confirmed")
        after.native.cash = 30000
        self.assertEqual(self.feature.evaluate(proposal, self.before, after, reply, baseline), "pending")

    def test_reply_and_new_member_without_cash_debit_never_confirm(self):
        proposal = self.plan()
        baseline = self.feature.capture(proposal, self.before)[0]
        member = {"name": "New", "rarity": 3, "atk": 8, "def": 9}
        after = self.h.snapshot(revision=2, native={"fullSync": True, "cash": 30000,
            "crew": [{"name": "Player"}, member, {"name": "Home", "rarity": 4}]})
        reply = lua_table(self.h.lua, {"ok": True, "index": 2, "member": member})
        self.assertEqual(self.feature.evaluate(proposal, self.before, after, reply, baseline), "pending")

    def test_capture_rechecks_declared_exposure_and_selected_price_ceiling(self):
        proposal = self.plan()
        proposal.resources.cash = 0
        self.assertIsNone(self.feature.capture(proposal, self.before)[0])
        proposal = self.plan()
        proposal.intent.maxCost = 10000
        self.assertIsNone(self.feature.capture(proposal, self.before)[0])


if __name__ == "__main__":
    unittest.main()
