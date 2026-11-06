"""Native browse budgets return cumulative rows, not disjoint ordinal pages."""
import unittest

from engine_harness import Harness, lua_table
import test_market_sell_runtime


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


class MarketIncompleteTradingTests(unittest.TestCase):
    def test_reviewed_config_budget_is_copied_and_not_hardcoded(self):
        helper=test_market_sell_runtime.MarketSellRuntimeTests(methodName='runTest')
        helper.setUp()
        _,raw,options=helper.market('marketFlip')
        helper.deps.config.MARKET.maxPages=3
        owner=helper.deps.MarketResearchController.new(helper.deps)
        helper.deps.config.MARKET.maxPages=1
        source=owner.Sources(owner)[1]
        requested=lua_table(helper.h.lua,{'marketWatch':options})
        # Watch settings use their independent listing-review fields.
        options.maxReviews=1;options.minAgeHours=1;options.demandMultiplier=1
        for field in ('maxBuy','sessionBudget','goldReserve','maxAttempts','maxListAttempts'):
            options[field]=None
        self.assertTrue(source.enabled(requested))
        request=source.prepare(raw)[0]
        self.assertEqual(request.args[4],3)

    def test_sale_and_flip_cannot_quote_more_stale_or_small_results(self):
        for feature in ('marketSell','marketFlip'):
            for flag in ('more','stale','small'):
                with self.subTest(feature=feature,flag=flag):
                    helper=test_market_sell_runtime.MarketSellRuntimeTests(methodName='runTest')
                    helper.setUp()
                    tab,raw,options=helper.market(feature)
                    runtime=tab.sellRuntime if feature=='marketSell' else tab.flipRuntime
                    view,reason=runtime.read(raw,raw)
                    self.assertIsNone(reason)
                    self.assertIsNotNone(runtime.propose(view,options)[0])
                    prefix='marketSell' if feature=='marketSell' else 'marketFlip'
                    helper.h.at(16);raw.capturedAt=16;raw.revision=2
                    raw.collectionProtection=helper.h.load('src/engine/CollectionProtection.luau').derive(
                        raw,raw,helper.h.lua.table(),helper.h.lua.table())[0]
                    source=next(s for s in tab.ReadSources(tab).values() if s.id==prefix+'Browse')
                    self.assertTrue(source.enabled(lua_table(helper.h.lua,{feature:options})))
                    prepared=source.prepare(raw)
                    request=prepared[0] if isinstance(prepared,tuple) else prepared
                    rows=[] if feature=='marketSell' else [
                        {'id':'foreign-a','item':'item_a','qty':1,'price':50,'mine':False,'sellerId':99},
                        {'id':'competitor-a','item':'item_a','qty':1,'price':100,'mine':False,'sellerId':100}]
                    reply={'ok':True,'pages':5,'more':False,'stale':False,'small':False,'rows':rows,flag:True}
                    staged,reason=source.accept(raw,request,lua_table(helper.h.lua,reply))
                    self.assertIsNone(reason)
                    self.assertTrue(source.commit(staged))
                    view,reason=runtime.read(raw,raw)
                    if feature=='marketSell':
                        self.assertIsNone(view)
                        self.assertIn('complete',reason)
                    if view is not None:
                        self.assertIsNone(runtime.propose(view,options)[0])
                    self.assertIsNone(tab.transactions.Active(tab.transactions))


if __name__=='__main__': unittest.main()
