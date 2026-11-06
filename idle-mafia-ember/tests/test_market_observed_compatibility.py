"""Earlier observed/nonterminal Market records remain intact and fully reserved."""
import unittest

import test_market_callback_custody as fixture
import test_market_transactions as transaction_fixture


class MarketObservedCompatibilityTests(unittest.TestCase):
    def setUp(self):self.f=fixture.MarketCallbackCustodyTests()

    def legacy_observed(self,f,kind):
        f.app.Destroy(f.app)
        key=f.tab.transactions.key
        envelope=f.storage.data[key]
        record=envelope.transaction
        # Exact fields written by the earlier Reconcile path, which promoted
        # an ok=true/code=pending response on observed native custody alone.
        record.stage='observed';envelope.generation+=1
        if kind in ('buy','withdraw'):
            record.confirmedSession=record.session
            record.confirmedRevision=3
            record.confirmedServerNow=1003
        self.f.json_roundtrip(f)
        self.equal=f.h.lua.eval('function(a,b) local function eq(x,y) if type(x)~=type(y) then return false end if type(x)~="table" then return x==y end for k,v in pairs(x) do if not eq(v,y[k]) then return false end end for k in pairs(y) do if x[k]==nil then return false end end return true end return eq(a,b) end')
        self.clone=f.h.lua.eval('function(x) local function c(v) if type(v)~="table" then return v end local t={} for k,a in pairs(v) do t[k]=c(a) end return t end return c(x) end')
        self.original=self.clone(f.storage.data[key])
        f.restart()
        self.assertIsNotNone(f.tab.transactions)
        return key

    def test_actual_json_observed_transients_keep_records_exposure_and_no_cleanup(self):
        for kind in ('list','buy','withdraw','flipList'):
            with self.subTest(kind=kind),self.f.fixture(kind,True,'pending') as f:
                key=self.legacy_observed(f,kind)
                owner=f.tab.transactions
                active=owner.Active(owner)
                self.assertEqual(active.stage,'observed')
                claims=owner.ReservationClaims(owner)
                if isinstance(claims,tuple):claims=claims[0]
                self.assertIsNotNone(claims)
                self.assertEqual(claims.actionKey,active.actionKey)
                self.assertEqual(claims.claims['items']['L:w_baton'],1)
                if kind=='buy':self.assertEqual(claims.claims['items']['L:gold_bar'],8)
                if kind=='withdraw':self.assertTrue(claims.claims.allItems)
                raw=self.f.after(f,kind,True,0);raw.native.serverNow=1005
                self.f.observe(f,raw)
                self.assertEqual(owner.Reconcile(owner,raw)[0],'uncertain')
                self.assertFalse(owner.ClearObserved(owner)[0])
                context=owner.ListingContext(owner,raw,0)
                self.assertIsNone(context[0] if isinstance(context,tuple) else context)
                review=owner.ObservedIntermediateReview(owner,raw,0)
                self.assertIsNone(review[0] if isinstance(review,tuple) else review)
                f.choose();self.f.observe(f,raw);f.executor.Drain(f.executor)
                self.assertEqual(len(f.executor.calls),self.f.calls)
                self.assertTrue(self.equal(f.storage.data[key],self.original))
                self.assertEqual(len(f.runtime.checkpoint.Records(f.runtime.checkpoint)),1)

    def test_nested_uncertain_purchase_origin_cannot_launder_its_gold_hold(self):
        with self.f.fixture('flipList',True,'ok') as f:
            key=self.legacy_observed(f,'flipList')
            f.app.Destroy(f.app)
            f.storage.data[key].transaction.origin.reply.code='pending'
            self.original=self.clone(f.storage.data[key]);self.f.json_roundtrip(f);f.restart()
            owner=f.tab.transactions
            claims=owner.ReservationClaims(owner)
            if isinstance(claims,tuple):claims=claims[0]
            self.assertIsNotNone(claims)
            self.assertEqual(claims.claims['items']['L:gold_bar'],8)
            self.assertEqual(claims.claims['items']['L:w_baton'],1)
            after=self.f.after(f,'flipList',True,0);after.native.serverNow=1005
            self.f.observe(f,after)
            self.assertFalse(owner.ClearObserved(owner)[0])
            self.assertTrue(self.equal(f.storage.data[key],self.original))
            self.assertEqual(len(f.runtime.checkpoint.Records(f.runtime.checkpoint)),1)

    def test_nested_prepared_followup_cannot_discard_or_authorize_uncertain_origin(self):
        with self.f.fixture('flipList',True,'ok') as f:
            key=self.legacy_observed(f,'flipList')
            f.app.Destroy(f.app)
            envelope=f.storage.data[key];record=envelope.transaction
            record.stage='prepared';record.reply=None;record.origin.reply.code='pending'
            envelope.generation=record.preparedGeneration;envelope.flipListingAttempts=0
            self.original=self.clone(envelope);self.f.json_roundtrip(f);f.restart()
            owner=f.tab.transactions
            self.assertIsNotNone(owner)
            review=owner.PreparedReview(owner)
            self.assertIsNone(review[0] if isinstance(review,tuple) else review)
            self.assertFalse(owner.DiscardPrepared(owner,self.original)[0])
            self.assertFalse(owner.MarkSending(owner,1)[0])
            self.assertTrue(self.equal(f.storage.data[key],self.original))
            claims=owner.ReservationClaims(owner)
            if isinstance(claims,tuple):claims=claims[0]
            self.assertEqual(claims.claims['items']['L:gold_bar'],8)

    def test_observed_rental_with_explicit_transient_reply_keeps_gold_and_record(self):
        f=transaction_fixture.MarketTransactionsTests();f.setUp()
        self.assertTrue(f.tx.PrepareRent(f.tx,f.proposal(),f.raw())[0])
        self.assertTrue(f.tx.MarkSending(f.tx)[0])
        after=f.raw(revision=2,loose=7,until=44200,now=1002)
        self.assertEqual(f.tx.Reconcile(f.tx,after)[0],'observed')
        key=f.tx.key;f.storage.data[key].transaction.reply=fixture.lua_table(f.h.lua,{'ok':True,'code':'pending'})
        self.f.json_roundtrip(f)
        owner,reason=f.module.new(f.storage,f.scope)
        self.assertIsNotNone(owner,reason)
        claims=owner.ReservationClaims(owner)
        if isinstance(claims,tuple):claims=claims[0]
        self.assertEqual(claims.claims['items']['L:gold_bar'],1)
        self.assertEqual(owner.Reconcile(owner,after)[0],'uncertain')
        self.assertFalse(owner.ClearObserved(owner)[0])
        self.assertEqual(f.storage.data[key].transaction.stage,'observed')
