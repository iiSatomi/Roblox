"""Only literal true confirms a Market write; ambiguous failures retain custody."""
import unittest
import test_market_transaction_lifecycle as transactions


class MarketStrictWriteTests(unittest.TestCase):
    setUp=transactions.MarketTransactionLifecycleTests.setUp
    new_owner=transactions.MarketTransactionLifecycleTests.new_owner
    raw=transactions.MarketTransactionLifecycleTests.raw
    proposal=transactions.MarketTransactionLifecycleTests.proposal
    prepare=transactions.MarketTransactionLifecycleTests.prepare
    authorize=transactions.MarketTransactionLifecycleTests.authorize
    returned=transactions.MarketTransactionLifecycleTests.returned

    def fail_writes(self,mode,needle=''):
        self.store.mode,self.store.needle=mode,needle
        self.store.Write=self.h.lua.eval('''function(self,key,value)
            if not key:find(self.needle,1,true) then self.data[key]=value;return true end
            if self.mode=='write_nil' or self.mode=='write_throw' then self.data[key]=value end
            if self.mode=='throw' or self.mode=='write_throw' then error('storage interrupted') end
            if self.mode=='false' then return false end
            if self.mode=='nil' or self.mode=='write_nil' then return nil end
            self.data[key]=value;return true
        end''')

    def test_preparation_never_reports_a_nontrue_write_as_durable(self):
        for mode in ('nil','false','throw','write_nil','write_throw'):
            with self.subTest(mode=mode):
                self.setUp();self.fail_writes(mode)
                p,before=self.proposal()
                result=self.owner.PrepareRuntimeOwnedList(self.owner,p,before,1)
                self.assertFalse(result[0])
                self.assertIsNone(self.owner.Active(self.owner))
                restored=self.new_owner()
                self.assertEqual(restored.Active(restored) is not None,mode.startswith('write_'))

    def test_authorization_nontrue_write_cannot_enter_native_and_reload_keeps_ambiguity(self):
        for mode in ('nil','false','throw','write_nil','write_throw'):
            with self.subTest(mode=mode):
                self.setUp();p,_=self.prepare();self.fail_writes(mode)
                result=self.owner.AuthorizeRuntimeOwnedList(self.owner,p.actionKey,1,1,'a'*64)
                self.assertFalse(result[0])
                self.assertEqual(self.owner.Active(self.owner).stage,'prepared')
                self.assertEqual(self.owner.ListingAttempts(self.owner)[0],0)
                restored=self.new_owner()
                self.assertEqual(restored.Active(restored).stage,'sent' if mode.startswith('write_') else 'prepared')
                self.assertEqual(restored.ListingAttempts(restored)[0],1 if mode.startswith('write_') else 0)

    def test_unsent_side_fact_requires_literal_success_even_when_bytes_may_have_landed(self):
        for mode in ('nil','false','throw','write_nil','write_throw'):
            with self.subTest(mode=mode):
                self.setUp();p,_=self.prepare();self.authorize(p);self.fail_writes(mode,':unsent:')
                self.assertFalse(self.owner.RecordRuntimeUnsent(self.owner,p.actionKey,1)[0])
                self.assertEqual(self.owner.Active(self.owner).stage,'sent')
                self.assertEqual(self.owner.ListingAttempts(self.owner)[0],1)

    def test_rejection_receipt_failure_does_not_clear_main_custody(self):
        for mode in ('nil','false','throw','write_nil','write_throw'):
            with self.subTest(mode=mode):
                self.setUp();p,_=self.prepare();self.authorize(p)
                self.returned(p,{'ok':False,'code':'price_changed'})
                after=self.raw(revision=2)
                review,reason=self.owner.RejectedRuntimeReview(self.owner,after);self.assertIsNone(reason)
                self.fail_writes(mode,':rejected:')
                self.assertFalse(self.owner.ReleaseRejectedRuntimeList(self.owner,review,after)[0])
                self.assertEqual(self.owner.Active(self.owner).stage,'sent')
                restored=self.new_owner()
                self.assertEqual(restored.Active(restored).stage,'sent')
                self.assertEqual(restored.ListingAttempts(restored)[0],1)

    def test_close_during_authorization_write_returns_no_grant_and_reload_holds_sent(self):
        p,_=self.prepare()
        self.store.owner=self.owner
        self.store.Write=self.h.lua.eval('''function(self,key,value)
            self.data[key]=value;self.owner:Close();return true
        end''')
        self.assertFalse(self.owner.AuthorizeRuntimeOwnedList(self.owner,p.actionKey,1,1,'a'*64)[0])
        restored=self.new_owner()
        self.assertEqual(restored.Active(restored).stage,'sent')
        self.assertEqual(restored.ListingAttempts(restored)[0],1)
        self.assertIsNone(restored.RuntimeUnsentReview(restored)[0])

    def test_literal_successful_unsent_receipt_releases_only_exact_charge(self):
        p,_=self.prepare();self.authorize(p)
        self.assertTrue(self.owner.RecordRuntimeUnsent(self.owner,p.actionKey,1)[0])
        review,reason=self.owner.RuntimeUnsentReview(self.owner);self.assertIsNone(reason)
        self.assertTrue(self.owner.ReleaseRuntimeUnsent(self.owner,review)[0])
        restored=self.new_owner()
        self.assertIsNone(restored.Active(restored))
        self.assertEqual(restored.ListingAttempts(restored)[0],0)
        self.assertIsNotNone(restored.RuntimeUnsentReceipt(restored,p.actionKey,1))


if __name__=='__main__': unittest.main()
