"""Real Market custody owner: direct listing, acquisitions, continuation and recovery."""
import unittest
from engine_harness import Harness, lua_table


class MarketTransactionLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.h=Harness()
        self.store=self.h.lua.execute('''return {data={},strictRecovery=true,fail=false,
            Read=function(self,k) return self.data[k] end,
            Write=function(self,k,v) if self.fail then return false end self.data[k]=v;return true end}''')
        self.module=self.h.load('src/tabs/blackMarket/MarketTransactions.luau')
        self.evidence={kind:self.h.load('src/tabs/blackMarket/'+name+'.luau') for kind,name in
            [('list','MarketListEvidence'),('withdraw','MarketCollectionWithdrawEvidence'),('buy','MarketBuyEvidence')]}
        self.owner=self.new_owner()

    def new_owner(self):
        owner,reason=self.module.new(self.store,lua_table(self.h.lua,self.h.session),
            self.evidence['list'],self.evidence['withdraw'],self.evidence['buy'])
        self.assertIsNone(reason)
        return owner

    def raw(self,revision=1,item=2,gold=10,collected=3,listing=False):
        rows={'new-a':{'state':'live','item':'item_a','indexed':0,'price':10,'qty':1,
            'left':1,'createdAt':100+revision,'itemOrigin':{'total':1,'free':1}}} if listing else {}
        return self.h.snapshot(revision=revision,native={'fullSync':True,'serverNow':100+revision,
            'inventory':{'item_a':item,'gold_bar':gold},'inventoryBound':{},
            'collection':{'item_a':collected},'collectionBound':{},'market':{'listings':rows}})

    def proposal(self,kind='list',before=None):
        before=self.raw() if before is None else before
        feature='marketFlip' if kind=='buy' else 'marketSell'
        proposal=self.h.proposal(feature=feature,key=kind+':owned:'+str(self.owner.generation+1),
            revision=before.revision)
        intent={'kind':{'list':'marketList','withdraw':'marketCollectionWithdraw','buy':'marketBuy'}[kind],
            'itemId':'item_a','quantity':1,'ask':10,'expectedAsk':10,'sourceKey':'a'*64,
            'ownerGeneration':self.owner.generation+1,'attemptedBefore':0,'maxAttempts':1}
        if kind=='withdraw':
            intent.update(checkpointFloor=1,collectionBefore=3,looseBefore=2,plannedListingQuantity=1)
        if kind=='buy':
            intent.update(listingId='foreign-a',quotedPrice=2,spentBefore=0,sessionBudget=2)
        proposal.intent=lua_table(self.h.lua,intent)
        proposal.resources=lua_table(self.h.lua,{'gold_bar':2} if kind=='buy' else {} if kind=='withdraw' else {'item_a':1})
        return proposal,before

    def prepare(self,kind='list'):
        p,before=self.proposal(kind)
        method={'list':'PrepareRuntimeOwnedList','withdraw':'PrepareRuntimeWithdraw','buy':'PrepareRuntimeBuy'}[kind]
        result=self.owner[method](self.owner,p,before,1) if kind!='buy' else self.owner[method](self.owner,p,before)
        self.assertTrue(result[0],result)
        return p,before

    def authorize(self,p,kind='list'):
        if kind=='buy': result=self.owner.AuthorizeRuntimeBuy(self.owner,p)
        else:
            method='AuthorizeRuntimeWithdraw' if kind=='withdraw' else 'AuthorizeRuntimeOwnedList'
            result=self.owner[method](self.owner,p.actionKey,p.intent.ownerGeneration,1,'a'*64)
        self.assertTrue(result[0],result)

    def returned(self,p,reply=None):
        self.assertTrue(self.owner.RecordRuntimeReturn(self.owner,p.actionKey,p.intent.ownerGeneration,
            lua_table(self.h.lua,reply or {'ok':True}))[0])

    def test_direct_listing_needs_reply_and_exact_new_owned_listing_then_preserves_attempt(self):
        p,before=self.prepare()
        self.authorize(p)
        after=self.raw(revision=2,item=1,listing=True)
        self.assertEqual(self.owner.Reconcile(self.owner,after)[0],'uncertain')
        self.returned(p)
        self.assertEqual(self.owner.Reconcile(self.owner,after)[0],'observed')
        self.assertTrue(self.owner.ClearObserved(self.owner)[0])
        restored=self.new_owner()
        self.assertIsNone(restored.Active(restored))
        self.assertEqual(restored.ListingAttempts(restored)[0],1)
        second,_=self.proposal()
        self.assertFalse(restored.PrepareRuntimeOwnedList(restored,second,before,1)[0])

    def test_failure_cas_and_source_generation_cannot_authorize_a_listing(self):
        other=self.new_owner()
        p,before=self.prepare()
        self.assertFalse(other.PrepareRuntimeOwnedList(other,p,before,1)[0])
        self.assertFalse(self.owner.AuthorizeRuntimeOwnedList(self.owner,p.actionKey,1,1,'b'*64)[0])
        self.store.fail=True
        self.assertFalse(self.owner.AuthorizeRuntimeOwnedList(self.owner,p.actionKey,1,1,'a'*64)[0])
        self.assertEqual(self.owner.Active(self.owner).stage,'prepared')
        self.assertEqual(self.owner.ListingAttempts(self.owner)[0],0)

    def test_withdrawal_holds_only_acquired_output_and_survives_restart(self):
        p,before=self.prepare('withdraw')
        self.authorize(p,'withdraw')
        self.returned(p,{'ok':True,'moved':1})
        after=self.raw(revision=2,item=3,collected=2)
        self.assertEqual(self.owner.Reconcile(self.owner,after)[0],'observed')
        restored=self.new_owner()
        claims=restored.ReservationClaims(restored)[0]
        self.assertEqual(claims.claims['items']['L:item_a'],1)
        self.assertFalse(restored.ClearObserved(restored)[0])
        after.native.inventory.item_a=4
        self.assertIsNone(restored.ListingContext(restored,after,0)[0])

    def test_purchase_reserves_gold_before_outcome_then_only_bought_copy(self):
        p,before=self.prepare('buy')
        self.authorize(p,'buy')
        before_claims=self.owner.ReservationClaims(self.owner)[0]
        self.assertEqual(before_claims.claims['items']['L:gold_bar'],2)
        self.returned(p)
        after=self.raw(revision=2,item=3,gold=8)
        self.assertEqual(self.owner.Reconcile(self.owner,after)[0],'observed')
        claims=self.owner.ReservationClaims(self.owner)[0]
        self.assertEqual(claims.claims['items']['L:item_a'],1)
        restored=self.new_owner()
        usage=restored.BuyUsage(restored)
        self.assertEqual((usage.attempted,usage.spent),(1,2))
        after.native.inventory.gold_bar=9
        self.assertIsNone(self.owner.ListingContext(self.owner,after,0)[0])

    def acquired(self,kind='buy'):
        p,before=self.prepare(kind)
        self.authorize(p,kind)
        self.returned(p,{'ok':True,'moved':1} if kind=='withdraw' else {'ok':True})
        after=self.raw(revision=2,item=3,gold=8 if kind=='buy' else 10,
            collected=2 if kind=='withdraw' else 3)
        self.assertEqual(self.owner.Reconcile(self.owner,after)[0],'observed')
        return after

    def continuation(self,kind='buy'):
        after=self.acquired(kind)
        view,reason=self.owner.ListingContext(self.owner,after,0)
        self.assertIsNone(reason)
        proposal,_=self.proposal(before=after)
        proposal.feature='marketFlip' if kind=='buy' else 'marketSell'
        proposal.intent.sourceListingId='foreign-a' if kind=='buy' else None
        proposal.intent.buyPrice=2 if kind=='buy' else None
        proposal.intent.collectionWithdrawn=1 if kind=='withdraw' else None
        self.assertTrue(self.owner.PrepareRuntimeFollowupList(self.owner,proposal,after,0,1)[0])
        self.authorize(proposal)
        return proposal,after

    def test_both_acquisition_lanes_list_only_owned_output_and_keep_independent_usage(self):
        for kind in ('buy','withdraw'):
            with self.subTest(kind=kind):
                self.setUp()
                proposal,_=self.continuation(kind)
                self.returned(proposal)
                after=self.raw(revision=3,item=2,listing=True,gold=8 if kind=='buy' else 10,
                    collected=2 if kind=='withdraw' else 3)
                self.assertEqual(self.owner.Reconcile(self.owner,after)[0],'observed')
                self.assertTrue(self.owner.ClearObserved(self.owner)[0])
                restored=self.new_owner()
                self.assertIsNone(restored.Active(restored))
                feature='marketFlip' if kind=='buy' else 'marketSell'
                self.assertEqual(restored.ListingAttempts(restored,feature)[0],1)
                self.assertEqual(restored.BuyUsage(restored).attempted,1 if kind=='buy' else 0)
                self.assertEqual(restored.WithdrawAttempts(restored)[0],1 if kind=='withdraw' else 0)

    def test_rejected_flip_listing_retains_bought_copy_and_consumed_attempt(self):
        p,before=self.continuation()
        self.returned(p,{'ok':False,'code':'price_changed'})
        after=self.raw(revision=3,item=3,gold=8)
        review,reason=self.owner.RejectedRuntimeReview(self.owner,after)
        self.assertIsNone(reason)
        self.assertTrue(self.owner.ReleaseRejectedRuntimeList(self.owner,review,after)[0])
        restored=self.new_owner()
        active=restored.Active(restored)
        self.assertEqual((active.kind,active.stage,active.listAttempts),('buy','observed',1))
        self.assertEqual(restored.ReservationClaims(restored)[0].claims['items']['L:item_a'],1)

    def test_known_unsent_side_fact_cannot_follow_a_saved_pending_reply(self):
        p,_=self.prepare()
        self.authorize(p)
        self.returned(p,{'ok':True,'pending':True})
        self.assertFalse(self.owner.RecordRuntimeUnsent(self.owner,p.actionKey,p.intent.ownerGeneration)[0])
        self.assertEqual(self.owner.ListingAttempts(self.owner)[0],1)
        self.assertIsNotNone(self.new_owner().Active(self.owner))


if __name__=='__main__': unittest.main()
