"""Rental caps charge atomically with pending custody and survive restart."""
import unittest
from engine_harness import Harness, lua_table


class MarketRentUsageTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.usage = self.h.load('src/tabs/blackMarket/MarketRentUsage.luau')
        self.pending = self.h.load('src/storage/PendingAction.luau')
        self.module = self.h.load('src/storage/Checkpoint.luau')
        self.storage = self.h.lua.execute('''return {strictRecovery=true,data={},
            Read=function(self,key) return self.data[key] end,
            Write=function(self,key,value) self.data[key]=value; return true end}''')
        self.cp = self.new()

    def new(self):
        cp = self.module.new(self.storage,None,None,self.pending,None,self.usage)
        self.assertIsNone(cp.Load(cp,'user-a',self.h.session['place'],'release-a')[1])
        return cp

    def proposal(self,key='rent',attempted=0,spent=0):
        proposal = self.h.proposal('marketRent',key)
        proposal.resources = lua_table(self.h.lua,{'gold_bar':2})
        proposal.intent = lua_table(self.h.lua,{'kind':'marketRent','periods':1,'cost':2,
            'attemptedBefore':attempted,'spentBefore':spent,'maxAttempts':2,'maxGoldSpend':4})
        return proposal

    def save(self,cp=None,proposal=None):
        cp = cp or self.cp
        return cp.Save(cp,proposal or self.proposal(),self.h.snapshot(native={'fullSync':True}),self.h.lua.table())

    def test_usage_persists_and_caller_zero_cannot_bypass_confirmed_exposure(self):
        self.assertTrue(self.save()[0])
        self.assertTrue(self.cp.Resolve(self.cp,'rent','confirmed')[0])
        cp = self.new()
        proof,why = cp.MarketRentUsage(cp,self.h.snapshot())
        self.assertIsNone(why)
        self.assertEqual((proof.attempted,proof.spent),(1,2))
        self.assertFalse(self.save(cp,self.proposal('again'))[0])
        self.assertTrue(self.save(cp,self.proposal('again',1,2))[0])
        self.assertTrue(cp.Resolve(cp,'again','rejected')[0])
        self.assertFalse(self.save(cp,self.proposal('over',2,4))[0])

    def test_only_known_unsent_refunds_and_unrelated_commit_preserves_totals(self):
        self.assertTrue(self.save()[0])
        self.assertTrue(self.cp.Resolve(self.cp,'rent','schedule_failed')[0])
        self.assertEqual(self.cp.MarketRentUsage(self.cp,self.h.snapshot())[0].spent,0)
        self.assertTrue(self.save()[0])
        self.assertTrue(self.cp.Resolve(self.cp,'rent','rejected')[0])
        other = self.h.proposal('jobs','ordinary')
        self.assertTrue(self.save(proposal=other)[0])
        self.assertEqual(self.new().MarketRentUsage(self.new(),self.h.snapshot())[0].spent,2)

    def test_missing_usage_owner_or_lowered_charge_refuses_reload(self):
        self.assertTrue(self.save()[0])
        downgraded = self.module.new(self.storage,None,None,self.pending)
        self.assertIsNone(downgraded.Load(downgraded,'user-a',self.h.session['place'],'release-a')[0])
        self.storage.data[self.cp.ScopeKey(self.cp)].marketRentUsage.spent = 1
        cp = self.module.new(self.storage,None,None,self.pending,None,self.usage)
        self.assertIsNone(cp.Load(cp,'user-a',self.h.session['place'],'release-a')[0])

    def test_reset_requires_no_pending_and_preserves_request_highwater(self):
        self.assertTrue(self.save()[0])
        expected = self.cp.Allowance(self.cp,'marketRent')[0]
        self.assertFalse(self.cp.ResetAllowance(self.cp,expected)[0])
        self.cp.Resolve(self.cp,'rent','rejected')
        self.assertTrue(self.cp.ResetAllowance(self.cp,expected)[0])
        cp = self.new()
        self.assertEqual(cp.requestHighwater,1)
        self.assertEqual(cp.MarketRentUsage(cp,self.h.snapshot())[0].spent,0)


if __name__ == '__main__': unittest.main()
