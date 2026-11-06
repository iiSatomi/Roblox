"""Native browse budgets return cumulative rows, not disjoint ordinal pages."""
import unittest

from engine_harness import Harness, lua_table


class MarketCumulativeTests(unittest.TestCase):
    def setUp(self):
        self.h=Harness()
        self.query=self.h.load('src/features/MarketBrowse.luau').new(5,self.h.clock)
        self.pages=self.h.load('src/tabs/blackMarket/MarketBrowsePages.luau').new(5,500)

    def test_one_reviewed_budget_retains_partial_metadata_without_followup_merge(self):
        scope,reason=self.pages.Begin(self.pages,'all',None)
        self.assertIsNone(reason)
        self.assertEqual(scope.page,5)
        request=self.query.Prepare(self.query,scope)[0]
        reply=lua_table(self.h.lua,{'ok':True,'pages':5,'more':True,'stale':True,'small':False,
            'rows':[{'id':'a','item':'item_a','qty':1,'price':50}]})
        accepted,reason=self.query.Accept(self.query,request,reply)
        self.assertIsNone(reason)
        followup,report,reason=self.pages.Accept(self.pages,accepted)
        self.assertIsNone(reason)
        self.assertIsNone(followup)
        self.assertEqual((report.pages,report.more,report.stale,report.small),(5,True,True,False))
        # A later cumulative response replaces the prior observation, even when a price changed.
        scope=self.pages.Begin(self.pages,'all',None)[0]
        request=self.query.Prepare(self.query,scope)[0]
        reply.rows[1].price=51;reply.more=False;reply.stale=False
        report=self.pages.Accept(self.pages,self.query.Accept(self.query,request,reply)[0])[1]
        self.assertEqual((len(report.rows),report.rows[1].price),(1,51))

    def test_native_early_exhaustion_is_complete_but_oversized_budget_is_rejected(self):
        request=self.query.Prepare(self.query,lua_table(self.h.lua,{'kind':'item','arg':'item_a','page':5}))[0]
        reply=lua_table(self.h.lua,{'ok':True,'pages':1,'more':False,'rows':[]})
        result,reason=self.query.Accept(self.query,request,reply)
        self.assertIsNone(reason)
        self.assertEqual((result.page,result.pages,result.more),(5,1,False))
        request=self.query.Prepare(self.query,lua_table(self.h.lua,{'kind':'all','page':2}))[0]
        reply.pages=3
        self.assertIsNone(self.query.Accept(self.query,request,reply)[0])

    def test_selected_item_reply_cannot_contain_foreign_item_supply(self):
        request=self.query.Prepare(self.query,lua_table(self.h.lua,{'kind':'item','arg':'item_a','page':5}))[0]
        reply=lua_table(self.h.lua,{'ok':True,'pages':1,'more':False,
            'rows':[{'id':'foreign','item':'item_b','qty':1,'price':50}]})
        self.assertIsNone(self.query.Accept(self.query,request,reply)[0])


class MarketIncompleteAppTests(unittest.TestCase):
    def test_actual_sell_and_flip_never_emit_from_more_stale_or_small_browse(self):
        import test_market_sell_runtime
        import test_market_flip_runtime
        for feature in ('marketSell','marketFlip'):
            for flag in ('more','stale','small'):
                with self.subTest(feature=feature,flag=flag):
                    cls=test_market_sell_runtime.MarketSellRuntimeTests if feature=='marketSell' else test_market_flip_runtime.MarketFlipRuntimeTests
                    f=cls(methodName='runTest');f.setUp()
                    try:
                        f.choose();raw=f.raw();f.warm(raw,{flag:True})
                        f.app.Step(f.app,raw);f.executor.Drain(f.executor)
                        self.assertEqual(len(f.executor.calls),0)
                        self.assertEqual(len(f.runtime.checkpoint.Records(f.runtime.checkpoint)),0)
                        self.assertIsNone(f.tab.transactions.Active(f.tab.transactions))
                    finally: f.tearDown()


if __name__=='__main__': unittest.main()
