"""Earned Event Shop allowance is charged with pending custody, not caller totals."""
import unittest
from engine_harness import Harness, lua_table


class EventShopUsageTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.usage = self.h.load("src/tabs/events/EventShopUsage.luau")
        self.module = self.h.load("src/storage/Checkpoint.luau")
        self.storage = self.h.lua.execute("""return {strictRecovery=true,data={},
            Read=function(self,key) return self.data[key] end,
            Write=function(self,key,value) self.data[key]=value return true end}""")
        self.checkpoint = self.restart()

    def restart(self):
        checkpoint = self.module.new(self.storage, None, None, None, self.usage)
        self.assertIsNone(checkpoint.Load(checkpoint, "user-a", self.h.session["place"], "release-a")[1])
        return checkpoint

    def proposal(self, attempted=0, spent=0, max_attempts=1, max_spend=15):
        proposal = self.h.proposal("eventShop", "event:" + str(attempted))
        proposal.resources = lua_table(self.h.lua, {"event_medal": 15})
        proposal.intent = lua_table(self.h.lua, {"kind": "eventShopBuy", "price": 15, "quantity": 1,
            "attemptedBefore": attempted, "spentBefore": spent, "maxAttempts": max_attempts, "maxSpend": max_spend})
        return proposal

    def proof(self, checkpoint=None):
        checkpoint = checkpoint or self.checkpoint
        return checkpoint.EventShopUsage(checkpoint, self.h.snapshot())[0]

    def test_sent_charge_survives_reload_and_confirmed_resolution_does_not_reset_it(self):
        proposal = self.proposal()
        self.assertTrue(self.checkpoint.Save(self.checkpoint, proposal)[0])
        restored = self.restart()
        self.assertEqual((self.proof(restored).attempted, self.proof(restored).spent), (1, 15))
        self.assertTrue(restored.Resolve(restored, proposal.actionKey, "confirmed")[0])
        self.assertFalse(restored.Save(restored, self.proposal(1, 15))[0])
        self.assertEqual(self.proof(self.restart()).spent, 15)

    def test_only_known_unsent_resolution_refunds_the_exact_charge(self):
        self.checkpoint=self.module.new(self.storage,None,None,
            self.h.load('src/storage/PendingAction.luau'),self.usage)
        self.checkpoint.Load(self.checkpoint,'user-a',self.h.session['place'],'release-a')
        before=self.h.snapshot(native={'fullSync':True})
        proposal = self.proposal()
        self.assertTrue(self.checkpoint.Save(self.checkpoint, proposal, before, self.h.lua.table())[0])
        self.assertTrue(self.checkpoint.Resolve(self.checkpoint, proposal.actionKey, "schedule_failed")[0])
        self.assertEqual((self.proof().attempted, self.proof().spent), (0, 0))
        self.assertTrue(self.checkpoint.Save(self.checkpoint, proposal, before, self.h.lua.table())[0])
        self.checkpoint.Resolve(self.checkpoint, proposal.actionKey, "rejected")
        self.assertEqual(self.proof().spent, 15)

    def test_stale_totals_extra_currency_or_zero_limit_cannot_charge(self):
        self.assertIsNone(self.usage.copy(lua_table(self.h.lua, {"version": 1, "attempted": 0, "spent": 15})))
        self.assertIsNone(self.usage.copy(lua_table(self.h.lua, {"version": 1, "attempted": 1, "spent": 0})))
        for proposal in (self.proposal(attempted=1), self.proposal(spent=15), self.proposal(max_attempts=0), self.proposal(max_spend=0)):
            self.assertFalse(self.checkpoint.Save(self.checkpoint, proposal)[0])
        proposal = self.proposal()
        proposal.resources.cash = 1
        self.assertFalse(self.checkpoint.Save(self.checkpoint, proposal)[0])
        self.assertEqual(self.proof().spent, 0)

    def test_saved_charge_cannot_be_loaded_without_its_owner_or_with_erased_totals(self):
        self.checkpoint.Save(self.checkpoint, self.proposal())
        old = self.module.new(self.storage)
        self.assertIsNone(old.Load(old, "user-a", self.h.session["place"], "release-a")[0])
        key = self.checkpoint.ScopeKey(self.checkpoint)
        self.storage.data[key].eventShopUsage.spent = 0
        restored = self.module.new(self.storage, None, None, None, self.usage)
        self.assertIsNone(restored.Load(restored, "user-a", self.h.session["place"], "release-a")[0])

    def test_proof_scope_and_copies_cannot_change_persistent_usage(self):
        proof = self.proof()
        proof.spent = 999
        self.assertEqual(self.proof().spent, 0)
        raw = self.h.snapshot()
        raw.account = "other"
        self.assertIsNone(self.checkpoint.EventShopUsage(self.checkpoint, raw)[0])
