"""Rental allowance and exact effects survive ambiguity and restart."""
import unittest
from engine_harness import Harness, lua_table


class MarketRentLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.h=Harness()
        self.store=self.h.lua.execute('''return {data={},strictRecovery=true,
            Read=function(self,k) return self.data[k] end,
            Write=function(self,k,v) self.data[k]=v;return true end}''')
        self.pending=self.h.load('src/storage/PendingAction.luau')
        self.usage=self.h.load('src/tabs/blackMarket/MarketRentUsage.luau')
        self.checkpointModule=self.h.load('src/storage/Checkpoint.luau')
        self.cp=self.checkpointModule.new(self.store,None,None,self.pending,None,self.usage)
        self.cp.Load(self.cp,self.h.session['account'],self.h.session['place'],self.h.session['release'])
        self.feature=self.h.load('src/tabs/blackMarket/MarketRentRuntime.luau').new(lua_table(self.h.lua,{
            'MarketRentQuote':self.h.load('src/tabs/blackMarket/MarketRentQuote.luau'),
            'MarketRentEvidence':self.h.load('src/tabs/blackMarket/MarketRentEvidence.luau'),
            'MarketSettings':self.h.load('src/tabs/blackMarket/MarketSettings.luau')}))
        self.before=self.raw()
        view,reason=self.feature.read(self.before,self.before);self.assertIsNone(reason)
        self.proposal,reason=self.feature.propose(view,lua_table(self.h.lua,{
            'enabled':True,'goldReserve':5,'maxAttempts':1,'maxGoldSpend':2}));self.assertIsNone(reason)
        self.baseline,reason=self.feature.capture(self.proposal,self.before);self.assertIsNone(reason)

    def raw(self,revision=1,now=100,until=0,gold=10):
        raw=self.h.snapshot(revision=revision,native={'fullSync':True,'serverNow':now,'level':20,
            'market':{'shopUntil':until},'derived':{'marketShop':False},
            'inventory':{'gold_bar':gold},'inventoryBound':{'gold_bar':0}})
        header={k:raw[k] for k in ('session','account','place','release','revision','capturedAt')}
        raw.marketRentTermsProof=lua_table(self.h.lua,{**header,'terms':{'release':'release-a',
            'sourceKey':'a'*64,'minLevel':1,'rentPerPeriod':2,'rentPeriodHours':24,'rentMaxDays':30}})
        raw.marketRentUsageProof=self.cp.MarketRentUsage(self.cp,raw)[0]
        return raw

    def save(self):
        self.assertTrue(self.cp.Save(self.cp,self.proposal,self.before,self.baseline)[0])

    def test_known_unsent_rolls_back_only_its_exact_charge(self):
        self.save()
        self.assertEqual(self.cp.MarketRentUsage(self.cp,self.before)[0].attempted,1)
        self.assertTrue(self.cp.Resolve(self.cp,self.proposal.actionKey,'schedule_failed')[0])
        usage=self.cp.MarketRentUsage(self.cp,self.before)[0]
        self.assertEqual((usage.attempted,usage.spent),(0,0))

    def test_saved_pending_return_cannot_refund_or_remove_attempt_as_unsent(self):
        self.save()
        self.assertTrue(self.cp.RecordReply(self.cp,self.proposal.actionKey,
            lua_table(self.h.lua,{'ok':True,'pending':True}))[0])
        self.assertFalse(self.cp.Resolve(self.cp,self.proposal.actionKey,'schedule_failed')[0])
        self.assertEqual(len(self.cp.Records(self.cp)),1)
        usage=self.cp.MarketRentUsage(self.cp,self.before)[0]
        self.assertEqual((usage.attempted,usage.spent),(1,2))

    def test_exact_lease_extension_and_gold_debit_confirm_and_survive_restart(self):
        self.save()
        reply=lua_table(self.h.lua,{'ok':True})
        self.cp.RecordReply(self.cp,self.proposal.actionKey,reply)
        after=self.raw(revision=2,now=101,until=86500,gold=8)
        self.assertEqual(self.feature.evaluate(self.proposal,self.before,after,reply,self.baseline),'confirmed')
        data=self.cp.Recovery(self.cp,self.proposal.actionKey)[0]
        after.session='run-b'
        after.revision=0
        for field in ('marketRentTermsProof','marketRentUsageProof'):
            after[field].session='run-b';after[field].revision=0
        self.assertEqual(self.feature.recoverSaved(data,after),'confirmed')
        restored=self.checkpointModule.new(self.store,None,None,self.pending,None,self.usage)
        restored.Load(restored,self.h.session['account'],self.h.session['place'],self.h.session['release'])
        self.assertEqual(restored.MarketRentUsage(restored,after)[0].spent,2)
        after.native.inventory.gold_bar=9
        self.assertIsNone(self.feature.recoverSaved(data,after))

    def test_transient_rental_reply_does_not_establish_terminal_outcome(self):
        after=self.raw(revision=2,now=101)
        for code in ('rate_limited','presence','busy'):
            with self.subTest(code=code):
                self.assertEqual(self.feature.evaluate(self.proposal,self.before,after,
                    lua_table(self.h.lua,{'ok':False,'code':code}),self.baseline),'pending')

    def test_reviewed_native_sparse_gold_maps_treat_missing_keys_as_zero(self):
        self.before.native.inventoryBound.gold_bar=None
        view,reason=self.feature.read(self.before,self.before);self.assertIsNone(reason)
        proposal,reason=self.feature.propose(view,lua_table(self.h.lua,{
            'enabled':True,'goldReserve':5,'maxAttempts':1,'maxGoldSpend':2}))
        self.assertIsNone(reason)
        baseline,reason=self.feature.capture(proposal,self.before);self.assertIsNone(reason)
        self.assertEqual(baseline.bound,0)
        after=self.raw(revision=2,now=101,until=86500,gold=8)
        after.native.inventoryBound.gold_bar=None
        self.assertEqual(self.feature.evaluate(proposal,self.before,after,
            lua_table(self.h.lua,{'ok':True}),baseline),'confirmed')
        after.native.inventoryBound.gold_bar=False
        self.assertEqual(self.feature.evaluate(proposal,self.before,after,
            lua_table(self.h.lua,{'ok':True}),baseline),'pending')

    def test_rental_confirms_exact_combined_debit_without_assuming_pool_priority(self):
        self.before.native.inventoryBound.gold_bar=5
        baseline,reason=self.feature.capture(self.proposal,self.before);self.assertIsNone(reason)
        reply=lua_table(self.h.lua,{'ok':True})
        for loose,bound,expected in ((8,5,'confirmed'),(10,3,'confirmed'),
                (9,4,'confirmed'),(11,2,'pending'),(7,6,'pending'),
                (10,4,'pending'),(9,3,'pending')):
            with self.subTest(loose=loose,bound=bound):
                after=self.raw(revision=2,now=101,until=86500,gold=loose)
                after.native.inventoryBound.gold_bar=bound
                self.assertEqual(self.feature.evaluate(self.proposal,self.before,after,reply,baseline),expected)

    def test_bound_funded_rental_holds_total_gold_and_preserves_reserve_against_other_custody(self):
        self.before.native.inventory.gold_bar=0
        self.before.native.inventoryBound.gold_bar=7
        view,reason=self.feature.read(self.before,self.before);self.assertIsNone(reason)
        proposal,reason=self.feature.propose(view,lua_table(self.h.lua,{
            'enabled':True,'goldReserve':5,'maxAttempts':1,'maxGoldSpend':2}))
        self.assertIsNone(reason)
        baseline,reason=self.feature.capture(proposal,self.before);self.assertIsNone(reason)
        self.assertEqual((baseline.loose,baseline.bound),(0,7))
        module=self.h.load('src/engine/ResourceReservations.luau')
        claims,reason=module.ForProposal(proposal,self.before)
        self.assertIsNone(reason)
        self.assertEqual(claims.funds.gold_bar,2)
        self.assertIsNone(claims['items']['L:gold_bar'])
        records=self.h.lua.table()
        owner=module.new(lua_table(self.h.lua,self.h.session),
            self.h.lua.eval('function(rows) return function() return rows end end')(records))
        self.assertIsNotNone(owner.Check(owner,proposal,self.before)[0])
        records[1]=lua_table(self.h.lua,{**self.h.session,'feature':'familyGold','actionKey':'other',
            'custody':{'members':{},'items':{'B:gold_bar':1},'funds':{},'allCrew':False,'allItems':False}})
        self.assertIsNone(owner.Check(owner,proposal,self.before)[0])
        self.before.native.inventoryBound.gold_bar=8
        self.assertIsNotNone(owner.Check(owner,proposal,self.before)[0])

    def test_bound_debit_recovers_saved_original_baseline_without_refunding_usage(self):
        self.before.native.inventoryBound.gold_bar=5
        self.baseline,reason=self.feature.capture(self.proposal,self.before);self.assertIsNone(reason)
        self.save()
        self.cp.RecordReply(self.cp,self.proposal.actionKey,lua_table(self.h.lua,{'ok':True}))
        restored=self.checkpointModule.new(self.store,None,None,self.pending,None,self.usage)
        restored.Load(restored,self.h.session['account'],self.h.session['place'],self.h.session['release'])
        data=restored.Recovery(restored,self.proposal.actionKey)[0]
        after=self.raw(revision=0,now=101,until=86500,gold=10)
        after.native.inventoryBound.gold_bar=3
        after.session='run-b'
        for field in ('marketRentTermsProof','marketRentUsageProof'): after[field].session='run-b'
        self.assertEqual(self.feature.recoverSaved(data,after),'confirmed')
        self.assertEqual((data.baseline.loose,data.baseline.bound),(10,5))
        self.assertEqual(restored.MarketRentUsage(restored,after)[0].spent,2)

    def test_total_rent_cannot_spend_either_origin_specific_holder_even_with_other_pool_funded(self):
        module=self.h.load('src/engine/ResourceReservations.luau')
        self.proposal.intent.goldReserve=0
        for origin in ('L','B'):
            with self.subTest(origin=origin):
                record=lua_table(self.h.lua,{**self.h.session,'feature':'familyGold','actionKey':'other',
                    'custody':{'members':{},'items':{origin+':gold_bar':1},'funds':{},'allCrew':False,'allItems':False}})
                owner=module.new(lua_table(self.h.lua,self.h.session),
                    self.h.lua.eval('function(row) return function() return {row} end end')(record))
                small=self.before.native.inventory if origin=='L' else self.before.native.inventoryBound
                large=self.before.native.inventoryBound if origin=='L' else self.before.native.inventory
                small.gold_bar=1;large.gold_bar=100
                self.assertIsNone(owner.Check(owner,self.proposal,self.before)[0])
                small.gold_bar=3
                self.assertIsNotNone(owner.Check(owner,self.proposal,self.before)[0])


if __name__=='__main__': unittest.main()
