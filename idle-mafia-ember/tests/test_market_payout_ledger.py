"""Durable earned payout totals are idempotent and never authorize a call."""
import unittest
import test_market_earnings as earnings_fixture
from engine_harness import lua_table


class MarketPayoutLedgerTests(unittest.TestCase):
    def setUp(self):
        self.f = earnings_fixture.MarketEarningsTests()
        self.f.setUp()
        self.h = self.f.h
        self.module = self.h.load('src/tabs/blackMarket/MarketPayoutLedger.luau')
        self.storage = self.h.lua.execute('''return {strictRecovery=true,data={},
            Read=function(self,key) return self.data[key] end,
            Write=function(self,key,value) if self.fail then return false end; self.data[key]=value; return true end}''')
        self.ledger,self.reason = self.module.new(self.storage,lua_table(self.h.lua,self.h.session),self.f.evidence)
        self.assertIsNone(self.reason)

    def data(self,request_id=1):
        before,proposal = self.f.proposal()
        before.native.serverNow = 1000
        proposal.requestId = request_id
        baseline = self.f.evidence.capture(proposal,before)[0]
        data = lua_table(self.h.lua,{'proposal':proposal,'before':before,'baseline':baseline,'reply':{'ok':True}})
        after = self.f.raw(revision=2,earnings=0,gold=60)
        after.native.serverNow = 1001
        return data,after

    def test_confirmed_claim_is_counted_once_across_reload_and_rejects_conflicting_id(self):
        data,after = self.data()
        self.assertTrue(self.ledger.Record(self.ledger,data,after)[0])
        self.assertTrue(self.ledger.Record(self.ledger,data,after)[0])
        restored,why = self.module.new(self.storage,lua_table(self.h.lua,self.h.session),self.f.evidence)
        self.assertIsNone(why)
        self.assertTrue(restored.Record(restored,data,after)[0])
        self.assertEqual(restored.Summary(restored).claims,1)
        self.assertEqual(restored.Summary(restored).gold,50)
        data.proposal.actionKey = 'different'
        self.assertFalse(restored.Record(restored,data,after)[0])

    def test_unknown_result_failed_save_and_stale_owner_do_not_inflate_totals(self):
        data,after = self.data()
        data.reply.pending = True
        self.assertFalse(self.ledger.Record(self.ledger,data,after)[0])
        data.reply.pending = None
        self.storage.fail = True
        self.assertFalse(self.ledger.Record(self.ledger,data,after)[0])
        self.assertEqual(self.ledger.Summary(self.ledger).claims,0)
        self.storage.fail = False
        newer,_ = self.module.new(self.storage,lua_table(self.h.lua,self.h.session),self.f.evidence)
        self.assertTrue(newer.Record(newer,data,after)[0])
        later,_ = self.data(2)
        self.assertFalse(self.ledger.Record(self.ledger,later,after)[0])
        self.assertEqual(newer.Summary(newer).gold,50)


    def test_corrupt_aggregate_or_incomplete_recent_window_refuses_load(self):
        data,after = self.data()
        self.assertTrue(self.ledger.Record(self.ledger,data,after)[0])
        key = self.ledger.key
        self.storage.data[key].claims = 2
        self.storage.data[key].gold = 100
        self.assertIsNone(self.module.new(self.storage,lua_table(self.h.lua,self.h.session),self.f.evidence)[0])
        self.storage.data[key].lastRequestId = 2
        self.storage.data[key].recent[1].requestId = 2
        self.assertIsNone(self.module.new(self.storage,lua_table(self.h.lua,self.h.session),self.f.evidence)[0])

    def test_nil_payout_write_cannot_advance_in_memory_totals_even_if_bytes_landed(self):
        for landed in (False,True):
            with self.subTest(landed=landed):
                self.setUp();data,after=self.data()
                self.storage.landed=landed
                self.storage.Write=self.h.lua.eval('function(self,k,v) if self.landed then self.data[k]=v end;return nil end')
                self.assertFalse(self.ledger.Record(self.ledger,data,after)[0])
                self.assertEqual(self.ledger.Summary(self.ledger).claims,0)
                restored,reason=self.module.new(self.storage,lua_table(self.h.lua,self.h.session),self.f.evidence)
                self.assertIsNone(reason)
                self.assertEqual(restored.Summary(restored).claims,1 if landed else 0)

    def test_recent_window_is_bounded_but_cumulative_totals_survive_reload(self):
        for request_id in range(1,35):
            data,after = self.data(request_id)
            self.assertTrue(self.ledger.Record(self.ledger,data,after)[0])
        summary = self.ledger.Summary(self.ledger)
        self.assertEqual((summary.claims,summary.gold,len(summary.recent)),(34,1700,32))
        self.assertEqual(summary.recent[1].requestId,3)
        restored,why = self.module.new(self.storage,lua_table(self.h.lua,self.h.session),self.f.evidence)
        self.assertIsNone(why)
        self.assertEqual(restored.Summary(restored).gold,1700)


if __name__ == '__main__': unittest.main()
