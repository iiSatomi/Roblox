"""Numbered confirmed Market payouts are durable and accounted once."""
import unittest
from engine_harness import Harness, lua_table


class MarketPayoutLedgerTests(unittest.TestCase):
    def setUp(self):
        self.h=Harness()
        self.evidence=self.h.load('src/features/MarketEarningsEvidence.luau')
        self.module=self.h.load('src/tabs/blackMarket/MarketPayoutLedger.luau')
        self.store=self.h.lua.execute('''return {data={},strictRecovery=true,fail=false,
            Read=function(self,k) return self.data[k] end,
            Write=function(self,k,v) if self.fail then return false end self.data[k]=v;return true end}''')
        self.ledger=self.new_ledger()
        self.before=self.raw()
        view=self.h.load('src/game/MarketEarningsState.luau').read(self.before,self.before)[0]
        self.p=self.h.load('src/features/MarketEarnings.luau').propose(view,
            lua_table(self.h.lua,{'enabled':True,'minEarnings':1}))[0]
        self.p.requestId=7
        self.baseline=self.evidence.capture(self.p,self.before)[0]
        self.data=lua_table(self.h.lua,{'proposal':self.p,'before':self.before,
            'baseline':self.baseline,'reply':{'ok':True}})
        self.after=self.raw(revision=2,earnings=0,gold=60)

    def raw(self,revision=1,earnings=50,gold=10):
        return self.h.snapshot(revision=revision,native={'fullSync':True,'serverNow':100+revision,
            'market':{'earnings':earnings},'inventory':{'gold_bar':gold}})

    def new_ledger(self):
        ledger,reason=self.module.new(self.store,lua_table(self.h.lua,self.h.session),self.evidence)
        self.assertIsNone(reason)
        return ledger

    def test_exact_transfer_records_once_across_restart_and_later_observation(self):
        self.assertTrue(self.ledger.Record(self.ledger,self.data,self.after)[0])
        restored=self.new_ledger()
        self.after.session='new-session';self.after.revision=0
        self.assertTrue(restored.Record(restored,self.data,self.after)[0])
        summary=restored.Summary(restored)
        self.assertEqual((summary.claims,summary.gold,summary.lastRequestId),(1,50,7))
        self.assertEqual(len(summary.recent),1)

    def test_failed_write_and_stale_writer_cannot_advance_accounting(self):
        other=self.new_ledger()
        self.store.fail=True
        self.assertFalse(self.ledger.Record(self.ledger,self.data,self.after)[0])
        self.assertEqual(self.ledger.Summary(self.ledger).claims,0)
        self.store.fail=False
        self.assertTrue(other.Record(other,self.data,self.after)[0])
        self.assertFalse(self.ledger.Record(self.ledger,self.data,self.after)[0])
        self.assertEqual(self.ledger.Summary(self.ledger).claims,0)

    def test_unconfirmed_nil_write_cannot_advance_durable_accounting(self):
        self.store.Write = self.h.lua.eval("function() return nil end")
        self.assertFalse(self.ledger.Record(self.ledger,self.data,self.after)[0])
        self.assertEqual(self.ledger.Summary(self.ledger).claims,0)
        self.assertEqual(self.new_ledger().Summary(self.new_ledger()).claims,0)

    def test_mismatched_amount_identity_or_number_remains_unrecorded(self):
        self.after.native.inventory.gold_bar=61
        self.assertFalse(self.ledger.Record(self.ledger,self.data,self.after)[0])
        self.after.native.inventory.gold_bar=60
        self.p.requestId=None
        self.assertFalse(self.ledger.Record(self.ledger,self.data,self.after)[0])
        self.p.requestId=7;self.after.account='foreign'
        self.assertFalse(self.ledger.Record(self.ledger,self.data,self.after)[0])

    def test_returned_summary_is_detached_and_corrupt_storage_refuses_reload(self):
        self.assertTrue(self.ledger.Record(self.ledger,self.data,self.after)[0])
        summary=self.ledger.Summary(self.ledger)
        summary.gold=999
        self.assertEqual(self.ledger.Summary(self.ledger).gold,50)
        stored=self.store.data[self.ledger.key]
        stored.recent[1].goldAfter=999
        ledger,reason=self.module.new(self.store,lua_table(self.h.lua,self.h.session),self.evidence)
        self.assertIsNone(ledger)
        self.assertIn('Corrupt',reason)

    def test_transient_negative_payout_reply_does_not_release_pending(self):
        after=self.raw(revision=2)
        for code in ('rate_limited','presence','busy'):
            with self.subTest(code=code):
                reply=lua_table(self.h.lua,{'ok':False,'code':code})
                self.assertEqual(self.evidence.evaluate(self.p,self.before,after,reply,self.baseline),'pending')


if __name__=='__main__': unittest.main()
