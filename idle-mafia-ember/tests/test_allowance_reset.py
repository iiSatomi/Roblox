"""Explicit reviewed local allowance reset never sends or discards pending work."""
import unittest
from engine_harness import Harness, lua_table


class AllowanceResetTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        family = self.h.load("src/tabs/family/FamilyContributionUsage.luau")
        event = self.h.load("src/tabs/events/EventShopUsage.luau")
        self.store = self.h.lua.execute("""return {strictRecovery=true,data={},
            Read=function(self,key) return self.data[key] end,
            Write=function(self,key,value) self.data[key]=value return true end}""")
        self.cp = self.h.load("src/storage/Checkpoint.luau").new(self.store, family, None, None, event)
        self.cp.Load(self.cp, "user-a", self.h.session["place"], "release-a")
        self.h.lua.globals().resetStatus = lua_table(self.h.lua, {"state": "paused", "uncertainCount": 0, "storageFault": False})
        self.h.lua.globals().resetRequested = False
        self.h.lua.globals().resetHeld = lua_table(self.h.lua, {"members": {}, "items": {}, "funds": {}, "allCrew": False})
        self.h.lua.globals().resetSnapshot = self.h.snapshot(native={"fullSync": True})
        self.owner = self.h.load("src/engine/AllowanceReset.luau").new(lua_table(self.h.lua, {
            "checkpoint": self.cp, "clock": self.h.clock, "identity": self.h.session,
            "session": {"Status": self.h.lua.eval("function() return resetStatus end")},
            "requested": self.h.lua.eval("function() return resetRequested end"),
            "reservations": {"Held": self.h.lua.eval("function() return resetHeld end")},
            "currentSnapshot": self.h.lua.eval("function() return resetSnapshot end")}))

    def charge(self):
        proposal = self.h.proposal("eventShop", "event:0")
        proposal.resources = lua_table(self.h.lua, {"event_medal": 15})
        proposal.intent = lua_table(self.h.lua, {"kind": "eventShopBuy", "price": 15, "quantity": 1,
            "attemptedBefore": 0, "spentBefore": 0, "maxAttempts": 1, "maxSpend": 15})
        self.assertTrue(self.cp.Save(self.cp, proposal)[0])
        return proposal

    def test_explicit_preview_and_one_time_confirmation_reset_only_selected_allowance(self):
        proposal = self.charge()
        self.cp.Resolve(self.cp, proposal.actionKey, "confirmed")
        preview, reason = self.owner.Preview(self.owner, "eventShop")
        self.assertIsNone(reason)
        self.assertEqual((preview.attempted, preview.spent), (1, 15))
        self.assertTrue(self.owner.Confirm(self.owner, preview.ticket)[0])
        self.assertEqual(self.cp.Allowance(self.cp, "eventShop")[0].spent, 0)
        self.assertFalse(self.owner.Confirm(self.owner, preview.ticket)[0])
        self.assertEqual(len(self.h.transport.sent), 0)

    def test_running_pending_or_durable_custody_cannot_be_reset(self):
        self.h.lua.globals().resetStatus.state = "running"
        self.assertIsNone(self.owner.Preview(self.owner, "eventShop")[0])
        self.h.lua.globals().resetStatus.state = "paused"
        proposal = self.charge()
        self.assertIsNone(self.owner.Preview(self.owner, "eventShop")[0])
        self.cp.Resolve(self.cp, proposal.actionKey, "confirmed")
        self.h.lua.globals().resetHeld["items"]["L:w_a"] = 1
        self.assertIsNone(self.owner.Preview(self.owner, "eventShop")[0])
        self.assertEqual(self.cp.Allowance(self.cp, "eventShop")[0].spent, 15)
        self.h.lua.globals().resetHeld["items"]["L:w_a"] = None
        self.h.lua.globals().resetHeld.allCrew = "unknown"
        self.assertIsNone(self.owner.Preview(self.owner, "eventShop")[0])

    def test_changed_scope_counts_or_expired_preview_refuses_confirmation(self):
        preview = self.owner.Preview(self.owner, "eventShop")[0]
        proposal = self.charge()
        self.cp.Resolve(self.cp, proposal.actionKey, "confirmed")
        self.assertFalse(self.owner.Confirm(self.owner, preview.ticket)[0])
        preview = self.owner.Preview(self.owner, "eventShop")[0]
        self.h.at(31)
        self.assertFalse(self.owner.Confirm(self.owner, preview.ticket)[0])
        self.h.lua.globals().resetSnapshot.account = "other"
        self.assertIsNone(self.owner.Preview(self.owner, "eventShop")[0])

    def test_native_resume_or_close_invalidates_a_preview_and_forged_ticket_is_rejected(self):
        preview = self.owner.Preview(self.owner, "eventShop")[0]
        self.assertFalse(self.owner.Confirm(self.owner, self.h.lua.table())[0])
        preview = self.owner.Preview(self.owner, "eventShop")[0]
        self.h.lua.globals().resetRequested = True
        self.assertFalse(self.owner.Confirm(self.owner, preview.ticket)[0])
        self.h.lua.globals().resetRequested = False
        self.owner.Close(self.owner)
        self.assertIsNone(self.owner.Preview(self.owner, "eventShop")[0])

    def test_checkpoint_scope_and_pending_records_remain_independent_guards(self):
        proposal = self.charge()
        expected = self.cp.Allowance(self.cp, "eventShop")[0]
        self.assertFalse(self.cp.ResetAllowance(self.cp, expected)[0])
        self.cp.Resolve(self.cp, proposal.actionKey, "confirmed")
        expected.account = "other"
        self.assertFalse(self.cp.ResetAllowance(self.cp, expected)[0])

    def test_family_reset_preserves_the_other_currency_allowance(self):
        module = self.h.load("src/storage/Checkpoint.luau")
        family = self.h.load("src/tabs/family/FamilyContributionUsage.luau")
        checkpoint = module.new(self.store, family)
        checkpoint.Load(checkpoint, "17", self.h.session["place"], "release-a")
        for feature, resource, amount in (("familyCash", "cash", 100), ("familyGold", "gold_bar", 1)):
            proposal = self.h.proposal(feature, feature + ":budget")
            proposal.account = "17"
            proposal.resources = lua_table(self.h.lua, {resource: amount})
            proposal.intent = lua_table(self.h.lua, {"kind": "familyContribution", "resource": resource,
                "actorId": 17, "familyId": "F", "amount": amount, "runBudget": amount,
                "maxAttempts": 1, "attemptsBefore": 0, "spentBefore": 0})
            self.assertTrue(checkpoint.Save(checkpoint, proposal)[0])
            checkpoint.Resolve(checkpoint, proposal.actionKey, "confirmed")
        expected = checkpoint.Allowance(checkpoint, "familyCash")[0]
        self.assertTrue(checkpoint.ResetAllowance(checkpoint, expected)[0])
        self.assertEqual(checkpoint.Allowance(checkpoint, "familyCash")[0].spent, 0)
        self.assertEqual(checkpoint.Allowance(checkpoint, "familyGold")[0].spent, 1)

    def test_unreadable_review_clock_cannot_bypass_expiry(self):
        preview = self.owner.Preview(self.owner, "eventShop")[0]
        self.h.clock.Now = self.h.lua.eval("function() return 0/0 end")
        self.assertFalse(self.owner.Confirm(self.owner, preview.ticket)[0])
        self.assertIsNone(self.owner.Preview(self.owner, "eventShop")[0])
