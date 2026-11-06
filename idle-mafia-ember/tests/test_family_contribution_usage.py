"""Budget reservations persist atomically with pending contributions."""
import unittest

from engine_harness import Harness, lua_table


class FamilyContributionUsageTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.h.session["account"] = "42"
        self.usage = self.h.load("src/tabs/family/FamilyContributionUsage.luau")
        self.storage = self.h.lua.execute("""return {data={},strictRecovery=true,
            Read=function(self,key) return self.data[key] end,
            Write=function(self,key,value) if self.fail then return false end; self.data[key]=value; return true end}""")
        self.module = self.h.load("src/storage/Checkpoint.luau")
        self.checkpoint = self.module.new(self.storage, self.usage)
        self.checkpoint.Load(self.checkpoint, "42", self.h.session["place"], "release-a")

    def proposal(self, feature="familyCash", amount=100, attempted=0, spent=0, key="one"):
        resource = {"familyCash": "cash", "familyGold": "gold_bar", "familyStamina": "stamina"}[feature]
        value = self.h.proposal(feature, feature + ":" + key)
        value.resources = lua_table(self.h.lua, {resource: amount})
        value.intent = lua_table(self.h.lua, {"kind": "familyContribution", "resource": resource,
            "actorId": 42, "familyId": "fam-a", "amount": amount, "spentBefore": spent,
            "attemptsBefore": attempted, "runBudget": 200, "maxAttempts": 2})
        return value

    def proof(self, checkpoint=None):
        checkpoint = checkpoint or self.checkpoint
        return checkpoint.FamilyContributionUsage(checkpoint, self.h.snapshot())[0]

    def test_named_account_charge_requires_exact_actor_account_binding(self):
        proposal=self.proposal();proposal.account="PlayerName"
        for binding in (None, "OtherName", False):
            proposal.intent.actorAccount=binding
            self.assertIsNone(self.usage.charge(None,proposal)[0])
        proposal.intent.actorAccount="PlayerName"
        usage,charge,reason=self.usage.charge(None,proposal)
        self.assertIsNone(reason)
        self.assertEqual(usage.lanes.familyCash.spent,100)
        proposal.intent.actorId=0
        self.assertIsNone(self.usage.charge(None,proposal)[0])

    def test_budget_and_pending_record_survive_reload_and_exact_caps(self):
        first = self.proposal()
        self.assertTrue(self.checkpoint.Save(self.checkpoint, first)[0])
        recovered = self.module.new(self.storage, self.usage)
        self.assertIsNone(recovered.Load(recovered, "42", self.h.session["place"], "release-a")[1])
        proof = self.proof(recovered)
        self.assertEqual((proof.usage.familyCash.attempted, proof.usage.familyCash.spent), (1, 100))
        self.assertEqual(len(recovered.Records(recovered)), 1)
        self.assertFalse(recovered.Save(recovered, self.proposal(key="stale"))[0])
        self.assertTrue(recovered.Resolve(recovered, first.actionKey, "confirmed")[0])
        self.assertTrue(recovered.Save(recovered, self.proposal(attempted=1, spent=100, key="two"))[0])
        self.assertFalse(recovered.Save(recovered, self.proposal(attempted=2, spent=200, key="three"))[0])

    def test_each_currency_has_independent_usage_and_pending_data_is_copied(self):
        self.checkpoint.Save(self.checkpoint, self.proposal())
        self.checkpoint.Save(self.checkpoint, self.proposal("familyGold", 1))
        self.checkpoint.Save(self.checkpoint, self.proposal("familyStamina", 5))
        proof = self.proof()
        self.assertEqual((proof.usage.familyCash.spent, proof.usage.familyGold.spent,
            proof.usage.familyStamina.spent), (100, 1, 5))
        proof.usage.familyCash.spent = 0
        records = self.checkpoint.Records(self.checkpoint)
        records[1].familyCharge.amount = 1
        self.assertEqual(self.proof().usage.familyCash.spent, 100)
        self.assertEqual(self.checkpoint.Records(self.checkpoint)[1].familyCharge.amount, 100)

    def test_only_definite_unsent_refusal_refunds_budget(self):
        for outcome, expected in (("schedule_failed", 0), ("rejected", 100), ("confirmed", 100)):
            with self.subTest(outcome=outcome):
                store = self.h.lua.execute("""return {strictRecovery=true,data={},
                    Read=function(self,key) return self.data[key] end,
                    Write=function(self,key,value) self.data[key]=value; return true end}""")
                checkpoint = self.module.new(store, self.usage, None, self.h.load('src/storage/PendingAction.luau'))
                checkpoint.Load(checkpoint, "42", self.h.session["place"], "release-a")
                proposal = self.proposal()
                before=self.h.snapshot(native={'fullSync':True,'family':{'id':'fam-a'},
                    'pools':{},'inventory':{},'inventoryBound':{}})
                self.assertTrue(checkpoint.Save(checkpoint, proposal, before, self.h.lua.table())[0])
                self.assertTrue(checkpoint.Resolve(checkpoint, proposal.actionKey, outcome)[0])
                self.assertEqual(self.proof(checkpoint).usage.familyCash.spent, expected)

    def test_corruption_or_missing_usage_module_cannot_erase_saved_limits(self):
        proposal = self.proposal()
        self.checkpoint.Save(self.checkpoint, proposal)
        downgraded = self.module.new(self.storage)
        self.assertIsNotNone(downgraded.Load(downgraded, "42", self.h.session["place"], "release-a")[1])
        key = self.checkpoint.ScopeKey(self.checkpoint)
        self.storage.data[key].familyContributionUsage.lanes.familyCash.spent = -1
        recovered = self.module.new(self.storage, self.usage)
        self.assertIsNotNone(recovered.Load(recovered, "42", self.h.session["place"], "release-a")[1])

    def test_failed_write_and_malformed_exposure_cannot_advance_memory(self):
        proposal = self.proposal()
        proposal.resources.cash = 99
        self.assertFalse(self.checkpoint.Save(self.checkpoint, proposal)[0])
        self.assertEqual(self.proof().usage.familyCash.spent, 0)
        self.storage.fail = True
        self.assertFalse(self.checkpoint.Save(self.checkpoint, self.proposal())[0])
        self.assertEqual(len(self.checkpoint.Records(self.checkpoint)), 0)
        self.assertIsNone(self.checkpoint.FamilyContributionUsage(self.checkpoint, self.h.snapshot())[0])

    def test_usage_proof_is_bound_to_the_current_scope(self):
        raw = self.h.snapshot()
        raw.account = "43"
        self.assertIsNone(self.checkpoint.FamilyContributionUsage(self.checkpoint, raw)[0])

    def test_missing_or_false_saved_lane_cannot_reset_a_budget(self):
        self.checkpoint.Save(self.checkpoint, self.proposal())
        key = self.checkpoint.ScopeKey(self.checkpoint)
        self.storage.data[key].familyContributionUsage.lanes.familyCash = False
        recovered = self.module.new(self.storage, self.usage)
        self.assertIsNotNone(recovered.Load(recovered, "42", self.h.session["place"], "release-a")[1])


if __name__ == "__main__":
    unittest.main()
