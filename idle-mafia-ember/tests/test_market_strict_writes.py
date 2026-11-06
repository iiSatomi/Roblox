"""Only literal durable success permits Market ownership transitions."""
import unittest
from engine_harness import lua_table
import test_market_transaction_flows as flows


class MarketStrictWriteTests(unittest.TestCase):
    def setUp(self):
        self.f=flows.MarketTransactionFlowTests(methodName='runTest');self.f.setUp()
        self.h,self.tx,self.store=self.f.h,self.f.tx,self.f.storage

    def fail_writes(self,mode,needle=''):
        self.store.mode,self.store.needle=mode,needle
        self.store.Write=self.h.lua.eval('''function(self,k,v)
            if not k:find(self.needle,1,true) then self.data[k]=v;return true end
            if self.mode=='write_nil' or self.mode=='write_throw' then self.data[k]=v end
            if self.mode=='throw' or self.mode=='write_throw' then error('interrupted') end
            if self.mode=='false' then return false end
            return nil
        end''')

    def prepare(self):
        p,before=self.f.runtime_buy()
        self.assertTrue(self.tx.PrepareRuntimeBuy(self.tx,p,before)[0])
        return p,before

    def test_nontrue_prepare_and_authorize_never_grant_and_reload_retains_landed_custody(self):
        for step in ('prepare','authorize'):
            for mode in ('nil','false','throw','write_nil','write_throw'):
                with self.subTest(step=step,mode=mode):
                    self.setUp()
                    p,before=self.f.runtime_buy()
                    if step=='authorize':self.assertTrue(self.tx.PrepareRuntimeBuy(self.tx,p,before)[0])
                    self.fail_writes(mode)
                    result=self.tx.PrepareRuntimeBuy(self.tx,p,before) if step=='prepare' else self.tx.AuthorizeRuntimeBuy(self.tx,p)
                    self.assertFalse(result[0])
                    self.assertEqual(self.tx.BuyUsage(self.tx).attempted,0)
                    restored=self.f.restart()
                    active=restored.Active(restored)
                    expected='sent' if step=='authorize' else 'prepared'
                    self.assertEqual(active.stage if active else None,expected if mode.startswith('write_') else ('prepared' if step=='authorize' else None))

    def test_unsent_and_rejection_receipts_require_literal_true_before_main_custody_cleanup(self):
        for receipt in ('unsent','rejected'):
            for mode in ('nil','false','throw','write_nil','write_throw'):
                with self.subTest(receipt=receipt,mode=mode):
                    self.setUp();p,_=self.prepare()
                    self.assertTrue(self.tx.AuthorizeRuntimeBuy(self.tx,p)[0])
                    if receipt=='rejected':
                        self.assertTrue(self.tx.RecordRuntimeReturn(self.tx,p.actionKey,p.intent.ownerGeneration,
                            lua_table(self.h.lua,{'ok':False}))[0])
                        after=self.f.raw('buy',revision=5,server=1002)
                        review,reason=self.tx.RejectedRuntimeReview(self.tx,after);self.assertIsNone(reason)
                    self.fail_writes(mode,':'+receipt+':')
                    result=self.tx.RecordRuntimeUnsent(self.tx,p.actionKey,p.intent.ownerGeneration) if receipt=='unsent' else self.tx.ReleaseRejectedRuntimeList(self.tx,review,after)
                    self.assertFalse(result[0])
                    self.assertEqual(self.tx.Active(self.tx).stage,'sent')
                    self.assertEqual(self.f.restart().BuyUsage(self.f.restart()).spent,8)


if __name__=='__main__': unittest.main()
