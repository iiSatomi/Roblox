"""Saved native returns and missing recovery cannot mint a refunded allowance."""
import unittest
from engine_harness import Harness, lua_table


class CheckpointUnsentGuardTests(unittest.TestCase):
    def setUp(self):
        self.h=Harness()
        self.pending=self.h.load('src/storage/PendingAction.luau')
        self.module=self.h.load('src/storage/Checkpoint.luau')
        self.family=self.h.load('src/tabs/family/FamilyContributionUsage.luau')
        self.event=self.h.load('src/tabs/events/EventShopUsage.luau')
        self.rent=self.h.load('src/tabs/blackMarket/MarketRentUsage.luau')
        self.hire=self.h.load('src/tabs/crew/CrewHireUsage.luau')
        self.store=self.h.lua.execute('''return {strictRecovery=true,data={},
            Read=function(self,k) return self.data[k] end,
            Write=function(self,k,v) self.data[k]=v;return true end}''')
        self.cp=self.owner()

    def owner(self):
        cp=self.module.new(self.store,self.family,None,self.pending,self.event,self.rent,self.hire)
        self.assertIsNone(cp.Load(cp,self.h.session['account'],self.h.session['place'],'release-a')[1])
        return cp

    def save(self,feature):
        if feature=='familyCash':
            resource,amount='cash',100
            intent={'kind':'familyContribution','resource':'cash','actorId':42,'actorAccount':'user-a',
                'familyId':'family-a','amount':100,'attemptsBefore':0,'spentBefore':0,'runBudget':100,'maxAttempts':1}
        elif feature=='eventShop':
            resource,amount='event_medal',10
            intent={'kind':'eventShopBuy','quantity':1,'price':10,'attemptedBefore':0,'spentBefore':0,
                'maxAttempts':1,'maxSpend':10}
        elif feature=='crewHire':
            resource,amount='cash',100
            intent={'kind':'crewHire','cost':100,'attemptedBefore':0,'spentBefore':0,'maxAttempts':1,'maxSpend':100}
        else:
            resource,amount='gold_bar',2
            intent={'kind':'marketRent','periods':1,'cost':2,'attemptedBefore':0,'spentBefore':0,
                'maxAttempts':1,'maxGoldSpend':2}
        p=self.h.proposal(feature,feature+':one')
        p.resources=lua_table(self.h.lua,{resource:amount});p.intent=lua_table(self.h.lua,intent)
        before=self.h.snapshot(native={'fullSync':True,'serverNow':100,'family':{'id':'family-a'},
            'pools':{},'inventory':{},'inventoryBound':{}})
        self.assertTrue(self.cp.Save(self.cp,p,before,lua_table(self.h.lua,{'original':True}))[0])
        self.assertEqual(self.cp.records[1].recovery.version,2)
        return p,amount

    def usage(self,cp,feature):
        if feature=='familyCash':
            proof=cp.FamilyContributionUsage(cp,self.h.snapshot())[0]
            return proof.usage.familyCash.attempted,proof.usage.familyCash.spent
        getter={'eventShop':cp.EventShopUsage,'crewHire':cp.CrewHireUsage,'marketRent':cp.MarketRentUsage}[feature]
        proof=getter(cp,self.h.snapshot())[0]
        return proof.attempted,proof.spent

    def test_any_saved_reply_prevents_unsent_refund_across_reload(self):
        for feature in ('familyCash','eventShop','crewHire','marketRent'):
            for reply in ({'ok':True},{'ok':False},{'ok':True,'pending':True}):
                with self.subTest(feature=feature,reply=reply):
                    self.setUp();p,amount=self.save(feature)
                    self.assertTrue(self.cp.RecordReply(self.cp,p.actionKey,lua_table(self.h.lua,reply))[0])
                    restored=self.owner()
                    self.assertFalse(restored.Resolve(restored,p.actionKey,'schedule_failed')[0])
                    self.assertEqual(len(restored.Records(restored)),1)
                    self.assertEqual(self.usage(self.owner(),feature),(1,amount))

    def test_absent_or_malformed_recovery_does_not_release_custody(self):
        for feature in ('familyCash','eventShop','crewHire','marketRent'):
            for malformed in (None,{'version':99}):
                with self.subTest(feature=feature,recovery=malformed):
                    self.setUp();p,amount=self.save(feature)
                    self.cp=self.owner()
                    self.cp.records[1].recovery=lua_table(self.h.lua,malformed)
                    self.assertFalse(self.cp.Resolve(self.cp,p.actionKey,'schedule_failed')[0])
                    self.assertEqual(len(self.cp.Records(self.cp)),1)
                    self.assertEqual(self.usage(self.owner(),feature),(1,amount))

    def test_intact_reply_free_recovery_refunds_exact_charge_once_and_keeps_highwater(self):
        for feature in ('familyCash','eventShop','crewHire','marketRent'):
            with self.subTest(feature=feature):
                self.setUp();p,_=self.save(feature)
                self.assertTrue(self.cp.Resolve(self.cp,p.actionKey,'schedule_failed')[0])
                restored=self.owner()
                self.assertEqual(self.usage(restored,feature),(0,0))
                self.assertEqual(restored.requestHighwater,1)
                self.assertEqual(len(restored.Records(restored)),0)
                self.assertFalse(restored.Resolve(restored,p.actionKey,'schedule_failed')[0])


class RecoveredLedgerReplyGuardTests(unittest.TestCase):
    def test_actual_chest_and_cash_shop_returns_cannot_refund_their_recovered_ledgers(self):
        import test_chest_allowance
        import test_shop_cash_app
        for kind in ('chests','shop'):
            with self.subTest(kind=kind):
                cls=test_chest_allowance.ChestAllowanceTests if kind=='chests' else test_shop_cash_app.ShopCashAppTests
                f=cls(methodName='runTest');f.setUp()
                try:
                    if kind=='chests':
                        f.enable();f.send(reply={'ok':True,'pending':True})
                    else:
                        f.select();f.step()
                        f.executor.reply=lua_table(f.h.lua,{'ok':True,'pending':True});f.drain()
                    cp=f.runtime.checkpoint
                    self.assertEqual(len(f.executor.calls),1)
                    record=cp.Records(cp)[1]
                    before=cp.Allowance(cp,kind)[0]
                    self.assertGreater(before.spent,0)
                    self.assertFalse(cp.Resolve(cp,record.actionKey,'schedule_failed')[0])
                    after=cp.Allowance(cp,kind)[0]
                    self.assertEqual((after.attempted,after.spent),(before.attempted,before.spent))
                    self.assertEqual(len(cp.Records(cp)),1)
                finally: f.tearDown()


if __name__=='__main__': unittest.main()
