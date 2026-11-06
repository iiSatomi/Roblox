"""Real Market research, tab descriptors and SellRuntime admission use owned caches."""
import json
import unittest
from engine_harness import ROOT, lua_table
import test_market_transaction_lifecycle


class MarketSellRuntimeTests(unittest.TestCase):
    setUp=test_market_transaction_lifecycle.MarketTransactionLifecycleTests.setUp
    raw=test_market_transaction_lifecycle.MarketTransactionLifecycleTests.raw
    new_owner=test_market_transaction_lifecycle.MarketTransactionLifecycleTests.new_owner

    def market(self,feature='marketSell'):
        deps={'clock':self.h.clock,'identity':self.h.session,'fingerprint':'a'*64,
            'release':'release-a','storage':self.store,'marketPresence':self.h.lua.eval('{check=function() return true end,handle=function() end}')}
        for path in (ROOT/'src/tabs/blackMarket').glob('*.luau'):
            if path.stem!='Module': deps[path.stem]=self.h.load(path.relative_to(ROOT).as_posix())
        for name,folder in [('MarketEarningsState','game'),('MarketEarnings','features'),
                ('MarketEarningsEvidence','features'),('MarketBrowse','features'),('MarketPrices','features'),
                ('MarketRap','features'),('MarketReadRuntime','features')]:
            deps[name]=self.h.load('src/'+folder+'/'+name+'.luau')
        deps['gameData']={'ITEMS_BY_ID':{'item_a':{'kind':'consumable','rarity':1,'tradable':True}}}
        deps['config']={'MARKET':{'maxPages':5,'minLevel':1,'slots':5,'maxSlots':5,'rentPerPeriod':2,
            'rentPeriodHours':24,'rentMaxDays':30,'feePct':0.1,'permanentFeePct':0.05,
            'minFee':1,'minPrice':2,'maxPrice':9999999,'maxQuantity':999,'minPriceByRarity':{}}}
        self.deps=lua_table(self.h.lua,deps)
        tab=self.h.load('src/tabs/blackMarket/Module.luau').new(self.deps)
        self.assertIsNone(tab.transactionFault)
        raw=self.raw()
        raw.native.crew=lua_table(self.h.lua,[{}])
        raw.native.level=20
        raw.native.market.extraSlots=0;raw.native.market.shopUntil=0
        raw.native.derived=lua_table(self.h.lua,{'marketShop':True})
        raw=tab.Enrich(tab,raw)[0]
        raw.collectionProtection=self.h.load('src/engine/CollectionProtection.luau').derive(
            raw,raw,self.h.lua.table(),self.h.lua.table())[0]
        options={field['id']:field['value'] for row in json.loads((ROOT/'preview/catalog.json').read_text(encoding='utf-8'))['features']
            if row['id']==feature for field in row['custom']}
        options.update(enabled=True,scope='Selected item',selectedItemId='item_a',excludedItems='',excludedKinds='',
            excludedRarities='',maxListAttempts=1,minSales=3,minUnits=3,floorPct=95)
        if feature=='marketSell':
            options.update(keepLoose=1,maxQuantity=1,maxListings=1,likelyOnly=False,minNet=1)
        else:
            options.update(maxBuy=50,sessionBudget=50,goldReserve=10,maxAttempts=1,
                minMargin=1,minMarginPct=1,requireCoverage=False)
            raw.native.inventory.gold_bar=100
        settings=lua_table(self.h.lua,{feature:options})
        selector='marketSell' if feature=='marketSell' else 'marketFlip'
        self.feed(tab,raw,settings,selector)
        return tab,raw,settings[feature]

    def feed(self,tab,raw,settings,selector):
        for source in tab.ReadSources(tab).values():
            if source.id not in [selector+kind for kind in ('Browse','Rap','Prices')]: continue
            self.assertTrue(source.enabled(settings))
            prepared=source.prepare(raw)
            request,reason=prepared if isinstance(prepared,tuple) else (prepared,None)
            self.assertIsNone(reason)
            kind=request.args[1]
            rows=[] if selector!='marketFlip' else [
                {'id':'foreign-a','item':'item_a','qty':1,'price':50,'mine':False,'sellerId':99},
                {'id':'competitor-a','item':'item_a','qty':1,'price':100,'mine':False,'sellerId':100}]
            if selector=='marketFlipList':
                rows=[{'id':'competitor-a','item':'item_a','qty':1,'price':100,'mine':False,'sellerId':100}]
            reply={'ok':True,'rows':rows,'pages':1,'more':False} if kind=='browse' else (
                {'ok':True,'values':{'item_a':{'quantity':20,'sales':10,'average':100,'available':True}}}
                if kind=='rap' else {'ok':True,'item':'item_a','recent':[{'price':100}]*3,'days':[]})
            staged,reason=source.accept(raw,request,lua_table(self.h.lua,reply));self.assertIsNone(reason)
            self.assertTrue(source.commit(staged))

    def test_owned_research_admits_bounded_sale_and_exact_owner_lifecycle(self):
        tab,raw,settings=self.market()
        runtime=tab.sellRuntime
        view,reason=runtime.read(raw,raw);self.assertIsNone(reason)
        proposal,reason=runtime.propose(view,settings);self.assertIsNone(reason)
        self.assertEqual((proposal.intent.itemId,proposal.intent.quantity,proposal.intent.ask),('item_a',1,98))
        baseline,reason=runtime.capture(proposal,raw);self.assertIsNone(reason)
        self.assertTrue(runtime.lifecycle.prepare(proposal,raw,baseline)[0])
        call,reason=runtime.lifecycle.authorize(proposal);self.assertIsNone(reason)
        self.assertEqual([call.args[i] for i in range(1,5)],['list','item_a',1,98])
        self.assertEqual(tab.transactions.ListingAttempts(tab.transactions)[0],1)
        self.assertTrue(runtime.lifecycle.returned(proposal,lua_table(self.h.lua,{'ok':True}))[0])
        after=self.raw(revision=2,item=1,listing=True)
        after.native.market.listings['new-a'].price=98
        self.assertTrue(runtime.lifecycle.resolve(proposal,'confirmed',after)[0])
        self.assertIsNone(tab.transactions.Active(tab.transactions))

    def test_changed_filters_or_missing_presence_block_preparation(self):
        tab,raw,settings=self.market()
        runtime=tab.sellRuntime
        view=runtime.read(raw,raw)[0]
        settings.excludedItems='item_a'
        self.assertIsNone(runtime.propose(view,settings)[0])
        settings.excludedItems=''
        self.deps.marketPresence.check=self.h.lua.eval('function() return false end')
        self.assertIsNone(runtime.propose(view,settings)[0])

    def engine(self,tab):
        composed,reason=self.h.load('src/tabs/TabComposition.luau').build(
            lua_table(self.h.lua,[tab]),self.h.load('src/ui/Catalog.luau'),
            self.h.load('src/engine/FeatureRegistry.luau'),self.h.load('src/tabs/TabSnapshotAssembler.luau'))
        self.assertIsNone(reason)
        modules=self.deps
        modules.Contracts=self.h.contracts
        for name,folder in [('Broker','engine'),('Journal','engine'),('Context','game'),
                ('Scheduler','engine'),('Session','engine'),('Checkpoint','storage'),
                ('PendingAction','storage'),('CollectionProtection','engine'),('ResourceReservations','engine')]:
            modules[name]=self.h.load('src/'+folder+'/'+name+'.luau')
        executor=self.h.lua.execute('''return {queued={},calls={},
            Schedule=function(self,fn) self.queued[#self.queued+1]=fn end,
            Invoke=function(self,remote,method,...) self.calls[#self.calls+1]=table.pack(...);return {ok=true} end,
            Drain=function(self) local q=self.queued;self.queued={};for _,fn in ipairs(q) do fn() end end}''')
        plan=self.h.load('src/transport/NativeCallPlan.luau')
        adapter=self.h.load('src/transport/NativeDispatchAdapter.luau').new(
            plan.withMarket(plan,self.deps.MarketCallPlan),executor)
        runtime=self.h.load('src/engine/AutomationRuntime.luau').new(lua_table(self.h.lua,{
            'clock':self.h.clock,'transport':adapter,'storage':self.store,'identity':self.h.session,
            'modules':modules,'features':composed.features,'featurePages':composed.featurePages,
            'snapshotAssembler':composed.snapshotAssembler,'reservationSources':tab.ReservationSources(tab)}))
        return runtime,executor

    def test_real_tab_engine_broker_and_adapter_send_and_settle_one_listing(self):
        tab,raw,settings=self.market()
        runtime,executor=self.engine(tab)
        raw.native.cash=1000;raw.native.pools=lua_table(self.h.lua,{'energy':20})
        requested=lua_table(self.h.lua,{'marketSell':settings})
        runtime.Resume(runtime)
        status=runtime.Step(runtime,raw,requested)
        executor.Drain(executor)
        self.assertEqual(len(executor.calls),1,(status.globalReason,dict(status.reasons.items())))
        self.assertEqual([executor.calls[1][i] for i in range(1,5)],['list','item_a',1,98])
        after=self.raw(revision=2,item=1,listing=True)
        after.native.market.listings['new-a'].price=98
        runtime.Step(runtime,after,requested)
        self.assertEqual(len(runtime.checkpoint.Records(runtime.checkpoint)),0)
        self.assertIsNone(tab.transactions.Active(tab.transactions))
        self.assertEqual(tab.transactions.ListingAttempts(tab.transactions)[0],1)
        executor.Drain(executor)
        self.assertEqual(len(executor.calls),1)

    def test_real_engine_payout_records_durable_numbered_earnings_once(self):
        tab,raw,_=self.market()
        runtime,executor=self.engine(tab)
        raw.native.cash=1000;raw.native.pools=lua_table(self.h.lua,{'energy':20})
        raw.native.market.earnings=50
        requested=lua_table(self.h.lua,{'marketManage':{'enabled':True,'minEarnings':20}})
        runtime.Resume(runtime)
        runtime.Step(runtime,raw,requested)
        executor.Drain(executor)
        self.assertEqual(len(executor.calls),1)
        self.assertEqual(executor.calls[1][1],'collect')
        after=self.raw(revision=2,gold=60)
        after.native.market.earnings=0
        runtime.Step(runtime,after,requested)
        self.assertEqual(len(runtime.checkpoint.Records(runtime.checkpoint)),0)
        summary=tab.payoutLedger.Summary(tab.payoutLedger)
        self.assertEqual((summary.claims,summary.gold),(1,50))
        runtime.Step(runtime,after,requested)
        self.assertEqual(tab.payoutLedger.Summary(tab.payoutLedger).claims,1)

    def test_real_engine_rent_charges_once_and_observes_one_exact_period(self):
        tab,raw,_=self.market()
        runtime,executor=self.engine(tab)
        raw.native.cash=1000;raw.native.pools=lua_table(self.h.lua,{'energy':20})
        raw.native.derived.marketShop=False
        raw.native.inventoryBound.gold_bar=0
        requested=lua_table(self.h.lua,{'marketRent':{'enabled':True,'goldReserve':5,
            'maxAttempts':1,'maxGoldSpend':2}})
        runtime.Resume(runtime)
        status=runtime.Step(runtime,raw,requested)
        executor.Drain(executor)
        self.assertEqual(len(executor.calls),1,(status.globalReason,dict(status.reasons.items())))
        self.assertEqual([executor.calls[1][i] for i in (1,2)],['rent',1])
        after=self.raw(revision=2,gold=8)
        after.native.inventoryBound.gold_bar=0
        after.native.market.shopUntil=86501
        runtime.Step(runtime,after,requested)
        self.assertEqual(len(runtime.checkpoint.Records(runtime.checkpoint)),0)
        usage=runtime.checkpoint.MarketRentUsage(runtime.checkpoint,after)[0]
        self.assertEqual((usage.attempted,usage.spent),(1,2))

    def test_real_engine_settles_bound_debit_and_keeps_one_attempt_cap(self):
        tab,raw,_=self.market()
        runtime,executor=self.engine(tab)
        raw.native.cash=1000;raw.native.pools=lua_table(self.h.lua,{'energy':20})
        raw.native.derived.marketShop=False
        raw.native.inventory.gold_bar=0;raw.native.inventoryBound.gold_bar=7
        requested=lua_table(self.h.lua,{'marketRent':{'enabled':True,'goldReserve':5,
            'maxAttempts':1,'maxGoldSpend':2}})
        runtime.Resume(runtime)
        status=runtime.Step(runtime,raw,requested)
        executor.Drain(executor)
        self.assertEqual(len(executor.calls),1,(status.globalReason,dict(status.reasons.items())))
        record=runtime.checkpoint.Records(runtime.checkpoint)[1]
        self.assertEqual(record.custody.funds.gold_bar,2)
        self.assertIsNone(record.custody['items']['L:gold_bar'])
        after=self.raw(revision=2,gold=0)
        after.native.inventoryBound.gold_bar=5;after.native.market.shopUntil=86501
        runtime.Step(runtime,after,requested)
        self.assertEqual(len(runtime.checkpoint.Records(runtime.checkpoint)),0)
        usage=runtime.checkpoint.MarketRentUsage(runtime.checkpoint,after)[0]
        self.assertEqual((usage.attempted,usage.spent),(1,2))
        later=self.raw(revision=3,gold=0)
        later.native.inventoryBound.gold_bar=5
        runtime.Step(runtime,later,requested)
        executor.Drain(executor)
        self.assertEqual(len(executor.calls),1)

    def test_real_flip_research_and_engine_buy_only_current_candidate(self):
        tab,raw,settings=self.market('marketFlip')
        runtime,executor=self.engine(tab)
        raw.native.cash=1000;raw.native.pools=lua_table(self.h.lua,{'energy':20})
        requested=lua_table(self.h.lua,{'marketFlip':settings})
        runtime.Resume(runtime)
        status=runtime.Step(runtime,raw,requested)
        executor.Drain(executor)
        self.assertEqual(len(executor.calls),1,(status.globalReason,dict(status.reasons.items())))
        self.assertEqual([executor.calls[1][i] for i in range(1,5)],['buy','foreign-a',1,50])
        after=self.raw(revision=2,item=3,gold=50)
        after.native.cash=1000;after.native.level=20;after.native.crew=lua_table(self.h.lua,[{}])
        after.native.pools=lua_table(self.h.lua,{'energy':20})
        after.native.market.extraSlots=0;after.native.market.shopUntil=0
        after.native.derived=lua_table(self.h.lua,{'marketShop':True})
        runtime.Step(runtime,after,requested)
        self.assertEqual(len(runtime.checkpoint.Records(runtime.checkpoint)),0)
        self.assertEqual(tab.transactions.Active(tab.transactions).stage,'observed')
        self.assertEqual(tab.transactions.BuyUsage(tab.transactions).spent,50)
        held=runtime.reservationOwner.Held(runtime.reservationOwner,after)[0]
        self.assertEqual(held['items']['L:item_a'],1)
        self.feed(tab,after,requested,'marketFlipList')
        self.h.at(1)
        status=runtime.Step(runtime,after,requested)
        executor.Drain(executor)
        self.assertEqual(len(executor.calls),2,(status.globalReason,dict(status.reasons.items())))
        self.assertEqual([executor.calls[2][i] for i in range(1,5)],['list','item_a',1,99])
        listed=self.raw(revision=3,item=2,gold=50,listing=True)
        listed.native.market.listings['new-a'].price=99
        runtime.Step(runtime,listed,requested)
        self.assertEqual(len(runtime.checkpoint.Records(runtime.checkpoint)),0)
        self.assertIsNone(tab.transactions.Active(tab.transactions))
        self.assertEqual(tab.transactions.BuyUsage(tab.transactions).spent,50)
        self.assertEqual(tab.transactions.ListingAttempts(tab.transactions,'marketFlip')[0],1)


if __name__=='__main__': unittest.main()
