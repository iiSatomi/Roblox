"""Real Market watch research reports through composition and the shared read lane."""
import json
import unittest

from engine_harness import ROOT, lua_table
import test_market_sell_runtime


class MarketWatchIntegrationTests(unittest.TestCase):
    def setUp(self):
        helper = test_market_sell_runtime.MarketSellRuntimeTests(methodName='runTest')
        helper.setUp()
        self.tab,self.raw,_ = helper.market()
        self.h,self.store,self.deps = helper.h,helper.store,helper.deps
        h = self.h
        options = {field['id']:field['value'] for row in json.loads(
            (ROOT/'preview/catalog.json').read_text(encoding='utf-8'))['features']
            if row['id']=='marketWatch' for field in row['custom']}
        options.update(enabled=True,scope='Selected item',selectedItemId='item_a',
            minSales=3,minUnits=3,minMargin=1,minMarginPct=0,undercutGold=1,
            floorPct=95,requireCoverage=False)
        self.settings = lua_table(h.lua,{'marketWatch':options})
        self.sources = self.tab.ReadSources(self.tab)
        self.lane = h.load('src/engine/RequestLane.luau').new(h.clock)
        h.lua.globals().watchLane = self.lane
        self.executor = h.lua.execute("""return {queued={},calls={},conflict=false,latency=0,
            more=false,stale=false,small=false,responsePages=5,
            Schedule=function(self,fn) self.queued[#self.queued+1]=fn;return true end,
            InFlight=function() return false end,
            InvokeOwned=function(self,token,remote,method,...)
                assert(watchLane:Owns(token),'Read requires the shared lease')
                local args=table.pack(...)
                assert(remote=='MarketAction' and method=='InvokeServer' and args.n==4)
                assert(args[1]=='browse' or args[1]=='rap' or args[1]=='prices','Watch cannot trade')
                self.calls[#self.calls+1]=args
                testNow=testNow+self.latency
                if args[1]=='browse' then
                    local rows={{id='cheap',item='item_a',qty=1,price=50,mine=false,sellerId=99},
                        {id='competitor',item='item_a',qty=1,price=100,mine=false,sellerId=100}}
                    if self.conflict then rows[3]={id='cheap',item='item_a',qty=1,price=51,mine=false,sellerId=99} end
                    return {ok=true,pages=self.responsePages,more=self.more,stale=self.stale,small=self.small,rows=rows}
                elseif args[1]=='rap' then
                    return {ok=true,values={item_a={quantity=20,sales=10,average=100,available=true}}}
                end
                return {ok=true,item=args[2],recent={{price=100},{price=100},{price=100}},days={}}
            end,
            Drain=function(self) local q=self.queued;self.queued={};for _,fn in ipairs(q) do fn() end end}""")
        specs = [{'id':s.id,'interval':s.interval} for s in self.sources.values()]
        budget = h.load('src/engine/ReadBudget.luau').new(h.clock,lua_table(h.lua,specs),5,60)
        self.reads = h.load('src/transport/ReadCoordinator.luau').new(lua_table(h.lua,{
            'clock':h.clock,'lane':self.lane,'budget':budget,'executor':self.executor,
            'sources':self.sources,'currentSnapshot':h.lua.eval('function() return watchRaw end')}))
        composed,reason = h.load('src/tabs/TabComposition.luau').build(lua_table(h.lua,[self.tab]),
            h.load('src/ui/Catalog.luau'),h.load('src/engine/FeatureRegistry.luau'),
            h.load('src/tabs/TabSnapshotAssembler.luau'))
        self.assertIsNone(reason)
        modules = self.deps
        modules.Contracts = h.contracts
        for name,folder in [('Broker','engine'),('Journal','engine'),('Context','game'),
                ('Scheduler','engine'),('Session','engine'),('Checkpoint','storage'),
                ('PendingAction','storage'),('CollectionProtection','engine'),('ResourceReservations','engine')]:
            modules[name] = h.load(f'src/{folder}/{name}.luau')
        self.runtime = h.load('src/engine/AutomationRuntime.luau').new(lua_table(h.lua,{
            'modules':modules,'identity':h.session,'clock':h.clock,'transport':h.transport,'storage':self.store,
            'features':composed.features,'featurePages':composed.featurePages,
            'snapshotAssembler':composed.snapshotAssembler,'tabInstances':composed.tabs,
            'readCoordinator':self.reads,'readSources':self.sources,
            'reservationSources':self.tab.ReservationSources(self.tab)}))
        self.runtime.Resume(self.runtime)

    def step(self, at, drain=True, sync_at=None):
        h = self.h
        h.at(at)
        sync_at = at if sync_at is None else sync_at
        self.raw.revision,self.raw.capturedAt,self.raw.native.serverNow = sync_at+1,sync_at,101+sync_at
        self.raw.native.cash = 1000
        self.raw.native.pools = lua_table(h.lua,{'energy':20})
        h.lua.globals().watchRaw = self.raw
        status = self.runtime.Step(self.runtime,self.raw,self.settings)
        if drain: self.executor.Drain(self.executor)
        return status

    def complete(self):
        for at in range(4): self.step(at)
        status = self.step(4)
        view,reason = self.tab.research.View(self.tab.research,self.raw,self.raw)
        self.assertIsNone(reason)
        return status,view

    def test_complete_cumulative_reply_rap_and_prices_produce_visible_read_only_report(self):
        self.step(0)
        for at in (1,2,3): self.step(at)
        status = self.step(4)
        view,reason = self.tab.research.View(self.tab.research,self.raw,self.raw)
        self.assertIsNone(reason)
        self.assertTrue(view.readOnly)
        self.assertTrue(view.research.paginationComplete)
        self.assertEqual((view.researchedItems,view.selectedItems,view.research.totalRows),(1,1,2))
        candidate = view.research.opportunities[1]
        self.assertEqual((candidate.listingId,candidate.buy,candidate.ask,candidate.margin),('cheap',50,99,45))
        self.assertIn('2 listings; 1 research candidates; prices ready 1/1',status.reasons.marketWatch)
        self.assertEqual([call[1] for call in self.executor.calls.values()],['browse','rap','prices'])
        self.assertEqual([self.executor.calls[1][i] for i in range(1,5)],['browse','item','item_a',5])
        self.assertEqual(len(self.h.transport.sent),0)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),0)
        self.assertIsNone(self.tab.transactions.Active(self.tab.transactions))

    def test_current_filters_and_expired_browse_cannot_keep_a_stale_opportunity(self):
        self.complete()
        self.settings.marketWatch.excludedItems = 'item_a'
        status = self.step(5)
        view,reason = self.tab.research.View(self.tab.research,self.raw,self.raw)
        self.assertIsNone(reason)
        self.assertEqual((view.selectedItems,view.research.opportunityCount),(0,0))
        self.assertIn('0 research candidates',status.reasons.marketWatch)
        self.step(17,drain=False)
        self.assertIsNone(self.tab.research.View(self.tab.research,self.raw,self.raw)[0])
        self.assertEqual(len(self.h.transport.sent),0)

    def test_duplicate_listing_in_cumulative_reply_never_becomes_a_report(self):
        self.executor.conflict = True
        self.step(0)
        self.step(1)
        view,reason = self.tab.research.View(self.tab.research,self.raw,self.raw)
        self.assertIsNone(view)
        self.assertIn('complete',reason)
        self.assertEqual(len(self.h.transport.sent),0)

    def test_real_fifteen_second_sync_cadence_finishes_without_cross_frame_page_merge(self):
        self.settings.marketWatch.scope='All eligible items'
        self.executor.latency=1.3
        self.step(0)
        initial,reason=self.tab.research.View(self.tab.research,self.raw,self.raw)
        self.assertIsNone(reason)
        self.assertEqual((initial.research.totalRows,initial.researchedItems),(2,0))
        # Only authentic Sync frames refresh the header. A stale frame admits no reads.
        self.step(8,sync_at=0)
        self.assertEqual(len(self.executor.calls),1)
        for at in (15,30,45): self.step(at)
        view,reason=self.tab.research.View(self.tab.research,self.raw,self.raw)
        self.assertIsNone(reason)
        self.assertEqual((view.researchedItems,view.research.opportunityCount),(1,1))
        browse=[call for call in self.executor.calls.values() if call[1]=='browse']
        self.assertEqual([[call[i] for i in range(1,5)] for call in browse],
                         [['browse','all',None,5],['browse','all',None,5]])
        self.assertEqual(len(self.h.transport.sent),0)

    def test_bounded_partial_report_never_offers_a_trade_quote(self):
        for flag in ('more','stale','small'):
            with self.subTest(flag=flag):
                self.setUp()
                setattr(self.executor,flag,True)
                status,view=self.complete()
                self.assertFalse(view.research.paginationComplete)
                self.assertTrue(view.research.truncated)
                self.assertEqual((view.research.totalRows,view.research.opportunityCount),(2,0))
                self.assertIn('bounded partial coverage',status.reasons.marketWatch)
                self.assertEqual(len(self.h.transport.sent),0)

    def test_selected_scope_change_rejects_old_owned_reply_before_cache_attachment(self):
        source=next(s for s in self.sources.values() if s.id=='marketBrowse')
        self.assertTrue(source.enabled(self.settings))
        request=source.prepare(self.raw)[0]
        self.settings.marketWatch.selectedItemId='item_b'
        self.assertTrue(source.enabled(self.settings))
        reply=lua_table(self.h.lua,{'ok':True,'pages':1,'more':False,'rows':[
            {'id':'old','item':'item_a','qty':1,'price':50}]})
        self.assertIsNone(source.accept(self.raw,request,reply))
        self.assertIsNone(self.tab.research.View(self.tab.research,self.raw,self.raw)[0])
        replacement=source.prepare(self.raw)[0]
        self.assertEqual([replacement.args[i] for i in range(1,5)],['browse','item','item_b',5])

    def test_reply_outside_owned_sync_window_cannot_attach_even_a_complete_cumulative_result(self):
        self.executor.latency=2.1
        self.step(0)
        self.assertEqual(len(self.executor.calls),1)
        self.assertIsNone(self.tab.research.View(self.tab.research,self.raw,self.raw)[0])
        self.assertEqual(len(self.h.transport.sent),0)

    def test_mutation_lease_then_close_fences_queued_watch_callback(self):
        token,reason = self.lane.TryAcquire(self.lane,'mutation','other-feature',45)
        self.assertIsNone(reason)
        self.step(0)
        self.assertEqual(len(self.executor.calls),0)
        self.assertEqual(len(self.executor.queued),0)
        self.lane.Release(self.lane,token,'test-complete')
        self.step(1,drain=False)
        self.assertEqual(len(self.executor.queued),1)
        self.runtime.Close(self.runtime)
        self.executor.Drain(self.executor)
        self.assertEqual(len(self.executor.calls),0)
        self.assertIsNone(self.tab.research.View(self.tab.research,self.raw,self.raw)[0])


if __name__ == '__main__': unittest.main()
