"""Native base-item searches include upgraded exact IDs without authorizing their prices."""
import unittest
import test_market_research_controller as controller_fixture
import test_market_research_view as view_fixture
import test_market_sale_quote as sale_fixture
import test_market_watch_opportunity as watch_fixture
from engine_harness import Harness, lua_table


class MarketVariantBrowseTests(unittest.TestCase):
    def setUp(self):
        self.h=Harness()
        self.module=self.h.load('src/features/MarketBrowse.luau')
        self.browse=self.module.new(5,self.h.clock)
        self.pages=self.h.load('src/tabs/blackMarket/MarketBrowsePages.luau').new(5,500,self.module.matchesItemScope)

    def reply(self):
        # Sanitized public shape: nine exact base rows and one upgraded sibling.
        return {'ok':True,'scope':'item','arg':'w_pipe','pages':1,
            'rows':[{'id':f'base-{i}','item':'w_pipe','qty':1,'price':10+i,'mine':False} for i in range(1,10)]
                +[{'id':'variant-1','item':'w_pipe@6','qty':1,'price':999,'mine':False}]}

    def accept(self,reply=None):
        scope=self.pages.Begin(self.pages,'item','w_pipe')[0]
        request=self.browse.Prepare(self.browse,scope)[0]
        value,reason=self.browse.Accept(self.browse,request,lua_table(self.h.lua,reply or self.reply()))
        self.assertIsNotNone(value,reason)
        _,result,reason=self.pages.Accept(self.pages,value)
        self.assertIsNotNone(result,reason)
        return result

    def test_cumulative_base_search_retains_all_exact_ids_and_native_completeness(self):
        result=self.accept()
        self.assertEqual((len(result.rows),result.rows[10].item,result.pages),(10,'w_pipe@6',1))
        self.assertFalse(result.more)
        self.assertEqual(result.variantCount,1)
        self.assertEqual(result.rows[10].price,999)

    def test_unrelated_base_malformed_variant_and_wrong_native_scope_are_rejected(self):
        for item in ('w_other@6','w_pipe_extra@6','w_pipe@0','w_pipe@01','w_pipe@100',
                     'w_pipe@-1','w_pipe@6@2','w_pipe@6x','@6','w_pipe@','w_pipe@6\n'):
            with self.subTest(item=item):
                request=self.browse.Prepare(self.browse,lua_table(self.h.lua,{'kind':'item','arg':'w_pipe','page':5}))[0]
                reply=self.reply();reply['rows'][-1]['item']=item
                self.assertIsNone(self.browse.Accept(self.browse,request,lua_table(self.h.lua,reply))[0])
        for field,value in (('scope','all'),('arg','w_other')):
            with self.subTest(field=field):
                request=self.browse.Prepare(self.browse,lua_table(self.h.lua,{'kind':'item','arg':'w_pipe','page':5}))[0]
                reply=self.reply();reply['rows']=[];reply[field]=value
                self.assertIsNone(self.browse.Accept(self.browse,request,lua_table(self.h.lua,reply))[0])

    def test_native_variant_range_boundaries_preserve_ids_and_old_exact_page_api(self):
        for level in (1,9,10,99):
            with self.subTest(level=level):
                reply=self.reply();reply['rows'][-1]['item']=f'w_pipe@{level}'
                self.assertEqual(self.accept(reply).rows[10].item,f'w_pipe@{level}')
        pages=self.h.load('src/tabs/blackMarket/MarketBrowsePages.luau').new(5,500)
        pages.Begin(pages,'item','w_pipe')
        _,result,reason=pages.Accept(pages,lua_table(self.h.lua,{'kind':'item','arg':'w_pipe','page':5,'pages':1,
            'capturedAt':0,'more':False,'stale':False,'small':False,'rows':[{'id':'old','item':'w_pipe','qty':1,'price':10,'mine':False}]}))
        self.assertIsNone(reason);self.assertEqual(result.rows[1].item,'w_pipe')

    def test_variant_report_has_complete_pagination_but_no_base_price_substitution(self):
        f=view_fixture.MarketResearchViewTests();f.setUp()
        f.browse['kind']='item';f.browse['arg']='w_baton'
        f.browse['rows'].append({'id':'UP1','item':'w_baton@6','qty':1,'price':1,'mine':False})
        matcher=f.h.load('src/features/MarketBrowse.luau').matchesItemScope
        result,reason=f.view.assess(*[lua_table(f.h.lua,v) for v in (f.browse,f.rap,f.history,f.items,f.terms,f.settings,11)],f.watch,matcher)
        self.assertIsNotNone(result,reason)
        self.assertTrue(result.paginationComplete)
        self.assertFalse(result.pricingComplete)
        self.assertEqual((result.totalRows,result.variantCount,result.opportunityCount),(3,1,0))
        self.assertIn('variant',result.rejected[3].reason.lower())
        self.assertEqual(result.rejected[3].itemId,'w_baton@6')

    def test_variants_beyond_presentation_limit_still_withhold_all_quotes(self):
        f=view_fixture.MarketResearchViewTests();f.setUp()
        f.browse['rows']=[{'id':f'L{i}','item':'w_baton','qty':1,'price':8,'mine':False} for i in range(100)]
        f.browse['rows'].append({'id':'LAST','item':'w_baton@6','qty':1,'price':1,'mine':False})
        result,reason=f.assess();self.assertIsNone(reason)
        self.assertEqual((result.totalRows,result.evaluated,result.variantCount,result.opportunityCount),(101,100,1,0))
        self.assertTrue(result.paginationComplete);self.assertFalse(result.pricingComplete)
        self.assertTrue(result.truncated)

    def test_partial_variant_reply_preserves_each_native_completeness_flag(self):
        for field in ('more','stale','small'):
            with self.subTest(field=field):
                reply=self.reply();reply[field]=True
                result=self.accept(reply)
                self.assertTrue(result[field]);self.assertEqual(result.variantCount,1)

    def test_sale_and_watch_helpers_refuse_even_base_quotes_from_variant_browse(self):
        sale=sale_fixture.MarketSaleQuoteTests();sale.setUp();values=sale.inputs()
        values[3].rows[2]=lua_table(sale.h.lua,{'id':'variant','item':'w_baton@6','qty':1,'price':1,'mine':False})
        with self.subTest(helper='sale'):
            self.assertIsNone(sale.assess(values)[0])
        watch=watch_fixture.MarketWatchOpportunityTests();watch.setUp();values=watch.inputs()
        values[0].rows[3]=lua_table(watch.h.lua,{'id':'variant','item':'w_baton@6','qty':1,'price':1,'mine':False})
        with self.subTest(helper='watch'):
            self.assertIsNone(watch.watch.assess(*values)[0])


class MarketVariantControllerTests(unittest.TestCase):
    def setUp(self):
        self.f=controller_fixture.MarketResearchControllerTests();self.f.setUp()
        f=self.f
        f.settings.Set(f.settings,'marketWatch.custom.scope','Selected item')
        f.settings.Set(f.settings,'marketWatch.custom.selectedItemId','w_baton')
        f.h.lua.globals().variantPriorInvoke=f.executor.InvokeOwned
        f.executor.InvokeOwned=f.h.lua.eval("""function(self,lease,remote,method,...)
            local args=table.pack(...);local reply=variantPriorInvoke(self,lease,remote,method,...)
            if args[1]=='browse' then reply.scope=args[2];reply.arg=args[3]
                reply.rows[#reply.rows+1]={id='UP1',item='w_baton@6',qty=1,price=1,mine=false} end
            return reply end""")
    def tearDown(self):self.f.tearDown()
    def test_shared_read_coordinator_produces_honest_variant_report_without_any_trade(self):
        f=self.f;f.warm();view,reason=f.view()
        self.assertIsNotNone(view,reason)
        self.assertEqual((view.research.totalRows,view.research.variantCount,view.research.opportunityCount),(3,1,0))
        self.assertTrue(view.research.paginationComplete)
        self.assertFalse(view.research.pricingComplete)
        self.assertEqual({call[1] for call in f.executor.calls.values()},{'browse','rap','prices'})
        self.assertEqual({call[3] for call in f.executor.calls.values() if call[1]=='browse'},{'w_baton'})
        self.assertTrue(all('@' not in call[2] for call in f.executor.calls.values() if call[1]=='prices'))

    def test_actual_watch_descriptor_explains_variant_pricing_withheld(self):
        f=self.f;f.warm();view,reason=f.view();self.assertIsNotNone(view,reason)
        descriptor=f.owner.Descriptor(f.owner)
        proposal,report=descriptor.planner.propose(view,lua_table(f.h.lua,{'enabled':True}))
        self.assertIsNone(proposal)
        self.assertIn('1 upgraded variant',report)
        self.assertIn('pricing and trading withheld',report)
        self.assertEqual(len(f.h.transport.sent),0)

    def test_sale_source_accepts_native_family_reply_but_refuses_any_sale_view(self):
        f=self.f
        f.native.inventory=lua_table(f.h.lua,{'w_baton':2});f.native.inventoryBound=f.h.lua.table()
        f.reader.ObserveSync(f.reader,f.native)
        settings=lua_table(f.h.lua,{'marketSell':{'enabled':True,'custom':{'scope':'Selected item',
            'selectedItemId':'w_baton','excludedItems':'','excludedKinds':'','excludedRarities':'',
            'keepLoose':1,'fromCollection':False}}})
        raw=f.reader.Capture(f.reader)[0]
        for source in f.sources.values():
            if not source.id.startswith('marketSell'):continue
            self.assertTrue(source.enabled(settings,None))
            request=source.prepare(raw)
            if isinstance(request,tuple):request=request[0]
            self.assertIsNotNone(request)
            reply=f.executor.InvokeOwned(f.executor,None,request.remote,request.method,*[request.args[i] for i in range(1,5)])
            accepted=source.accept(raw,request,reply)
            if isinstance(accepted,tuple):accepted=accepted[0]
            self.assertIsNotNone(accepted)
            self.assertTrue(source.commit(accepted))
        view,reason=f.owner.SaleView(f.owner,raw,raw)
        self.assertIsNone(view);self.assertIn('Variant',reason)
        self.assertTrue(all(call[1] in ('browse','rap','prices') for call in f.executor.calls.values()))
