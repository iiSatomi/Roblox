"""Exact native item keys retain separate research, custody and wire arguments."""
import unittest
from engine_harness import lua_table
import test_market_research_view as view_fixture
import test_market_sale_quote as quote_fixture
from test_market_payout_runtime import MarketPayoutRuntimeFixture


class ExactVariantResearchTests(unittest.TestCase):
    def test_unresearched_sibling_cannot_poison_exact_base_quote_or_borrow_its_rap(self):
        f=view_fixture.MarketResearchViewTests();f.setUp()
        f.browse['rows'].append({'id':'variant','item':'w_baton@6','qty':1,'price':1,'mine':False})
        report,reason=f.assess()
        self.assertIsNone(reason)
        self.assertEqual(report.opportunityCount,1)
        self.assertEqual(report.opportunities[1].itemId,'w_baton')
        self.assertEqual(report.rejected[2].itemId,'w_baton@6')
        self.assertFalse(report.pricingComplete)

    def test_exact_variant_uses_only_its_own_rap_and_history(self):
        f=view_fixture.MarketResearchViewTests();f.setUp()
        for row in f.browse['rows']:row['item']='w_baton@6'
        for mapping in (f.rap,f.history,f.items,f.terms):
            mapping['w_baton@6']=mapping.pop('w_baton')
        f.rap['w_baton@6']['itemId']='w_baton@6'
        f.history['w_baton@6']['itemId']='w_baton@6'
        f.items['w_baton@6']['id']='w_baton@6'
        report,reason=f.assess();self.assertIsNone(reason)
        self.assertEqual(report.opportunityCount,1)
        self.assertEqual(report.opportunities[1].itemId,'w_baton@6')
        self.assertTrue(report.pricingComplete)
        for mapping in (f.rap,f.history):
            mapping['w_baton@6']['itemId']='w_baton'
            self.assertEqual(f.assess()[0].opportunityCount,0)
            mapping['w_baton@6']['itemId']='w_baton@6'

    def test_sale_competition_is_exact_key_not_cheaper_or_huge_sibling_supply(self):
        f=quote_fixture.MarketSaleQuoteTests();f.setUp();values=f.inputs()
        values[3].rows[2]=lua_table(f.h.lua,{'id':'variant','item':'w_baton@6','qty':1000000,'price':1,'mine':False})
        values[6].likelyOnly=True
        quote,reason=f.assess(values);self.assertIsNotNone(quote,reason)
        self.assertEqual((quote.ask,quote.competingUnits),(10,2))

    def test_market_only_canonical_exact_keys_are_valid_profile_preferences(self):
        f=view_fixture.MarketResearchViewTests();f.setUp()
        model=f.h.load('src/storage/Settings.luau').new(f.h.load('src/ui/Catalog.luau'))
        for feature in ('marketWatch','marketSell','marketFlip'):
            for value in ('w_baton@1','w_baton@6','w_baton@99'):
                self.assertTrue(model.Set(model,feature+'.custom.selectedItemId',value)[0])
                self.assertTrue(model.Set(model,feature+'.custom.excludedItems',value+',w_baton')[0])
            for value in ('w_baton@0','w_baton@01','w_baton@100','w_baton@6@2','w_baton@+6','@6','w_baton@6\n'):
                self.assertFalse(model.Set(model,feature+'.custom.selectedItemId',value)[0])
        self.assertFalse(model.Set(model,'shop.custom.itemId','w_baton@6')[0])
        saved=model.Snapshot(model)
        reloaded=f.h.load('src/storage/Settings.luau').new(f.h.load('src/ui/Catalog.luau'))
        values,reason=reloaded.Validate(reloaded,saved,True)
        self.assertIsNotNone(values,reason)
        self.assertEqual(values['marketSell.custom.selectedItemId'],'w_baton@99')

    def test_native_zero_sales_missing_average_is_cached_without_creating_a_price(self):
        f=view_fixture.MarketResearchViewTests();f.setUp()
        reader=f.h.load('src/features/MarketRap.luau').new(f.h.clock)
        request=reader.Prepare(reader,lua_table(f.h.lua,['w_baton@6']))[0]
        result,reason=reader.Accept(reader,request,lua_table(f.h.lua,{'ok':True,'values':{
            'w_baton@6':{'quantity':0,'sales':0,'available':True}}}))
        self.assertIsNotNone(result,reason)
        self.assertIsNone(reader.Get(reader,'w_baton@6').average)
        self.assertIsNone(reader.Prepare(reader,lua_table(f.h.lua,['w_baton@6']))[0])
        f.rap['w_baton'].update(quantity=0,sales=0);f.rap['w_baton'].pop('average')
        f.history['w_baton']['recent']=[]
        report,reason=f.assess();self.assertIsNotNone(report,reason)
        self.assertEqual(report.opportunityCount,0)
        self.assertFalse(report.pricingComplete)
        self.assertIn('threshold',report.rejected[1].reason)
        for sales,quantity in ((1,0),(0,1),(1,1)):
            request=reader.Prepare(reader,lua_table(f.h.lua,['unpriced']))[0]
            value=reader.Accept(reader,request,lua_table(f.h.lua,{'ok':True,'values':{
                'unpriced':{'quantity':quantity,'sales':sales,'available':True}}}))[0]
            self.assertIsNone(value)


class ExactVariantRuntimeTests(MarketPayoutRuntimeFixture,unittest.TestCase):
    feature_id='marketSell'
    item='w_baton@6'
    def start(self):
        self.deps['config']['UPGRADE']={'maxLevel':getattr(self,'nativeCap',6)}
        # Models native lazy exact-ID lookup; never pre-materialize the variant.
        self.deps.update(clock=self.h.clock,gameData=self.h.lua.execute('''
            local base={id='w_baton',kind='weapon',rarity=5,tradable=true,atk=1,def=1}
            local rows={w_baton=base}
            setmetatable(rows,{__index=function(t,id)
                if id~='w_baton@6' then return nil end
                local v={id=id,baseId='w_baton',upgradeLevel=6,kind='weapon',rarity=5,tradable=true,atk=8,def=0}
                rawset(t,id,v);return v end})
            return {ITEMS_BY_ID=rows}'''),
            marketPresence=self.h.lua.execute('local g={};g.check=function() return true end;g.handle=function() return true end;return g'))
        MarketPayoutRuntimeFixture.start(self)

    def raw(self,revision=1,loose=3,listed=False):
        listing={'listed':{'state':'live','item':self.item,'indexed':1,'price':14,'qty':1,'left':1,
            'createdAt':1002,'itemOrigin':{'total':1,'free':0}}} if listed else {}
        return self.h.snapshot(revision=revision,captured_at=revision,native={
            'fullSync':True,'serverNow':1001+revision,'level':50,
            'market':{'extraSlots':0,'shopUntil':2000,'listings':listing},'derived':{'marketShop':False},
            'inventory':{'w_baton':99,self.item:loose},'inventoryBound':{self.item:50},
            'collection':{'w_baton':100,self.item:7},'collectionBound':{self.item:9},
            'crew':[{'weapon':self.item},{'weapon':self.item}]})

    def choose(self):
        for key,value in {'enabled':True,'custom.scope':'Selected item','custom.selectedItemId':self.item,
            'custom.maxListings':1,'custom.maxListAttempts':1,'custom.keepLoose':1,'custom.maxQuantity':1,
            'custom.minNet':1,'custom.likelyOnly':False,'custom.undercutGold':0,'custom.floorPct':90}.items():
            self.assertTrue(self.app.Set(self.app,'marketSell.'+key,value)[0])
        self.app.Resume(self.app)

    def warm(self,raw):
        self.h.at(raw.capturedAt)
        custom={k.removeprefix('marketSell.custom.'):v for k,v in self.app.model['values'].items() if k.startswith('marketSell.custom.')}
        settings=lua_table(self.h.lua,{'marketSell':{'enabled':True,'custom':custom}})
        reads=[]
        for source in self.tab.ReadSources(self.tab).values():
            if not source.id.startswith('marketSell') or not source.enabled(settings):continue
            request=source.prepare(raw)
            if isinstance(request,tuple):request=request[0]
            self.assertIsNotNone(request,source.id)
            reads.append(request.args[3] if source.id.endswith('Browse') else request.args[2])
            if source.id.endswith('Browse'):
                self.assertEqual(request.args[3],'w_baton')
                rows=[{'id':'competitor','item':self.item,'qty':1,'price':14,'mine':False},
                    {'id':'base','item':'w_baton','qty':9999,'price':1,'mine':False}]
                # Native654 indexes browse by base family, exact @ query is empty.
                reply={'ok':True,'scope':'item','arg':request.args[3],'pages':1,'more':False,
                    'rows':rows if request.args[3]=='w_baton' else []}
            elif source.id.endswith('Rap'):
                reply={'ok':True,'values':{self.item:{'sales':15,'quantity':30,'average':14,'available':True}}}
            else:reply={'ok':True,'item':self.item,'recent':[{'price':14},{'price':15},{'price':16}],'days':[]}
            staged=source.accept(raw,request,lua_table(self.h.lua,reply))
            if isinstance(staged,tuple):staged=staged[0]
            self.assertIsNotNone(staged,source.id);self.assertTrue(source.commit(staged))
        self.assertEqual(len(reads),3)

    def test_actual_app_lists_only_exact_loose_surplus_and_recovers_saved_receipt(self):
        raw=self.raw();self.choose();self.warm(raw)
        self.app.Step(self.app,raw);self.executor.Drain(self.executor)
        self.assertEqual(len(self.executor.calls),1,str(dict(self.runtime.Status(self.runtime).reasons.items())))
        self.assertEqual([self.executor.calls[1].args[i] for i in range(1,5)],['list',self.item,1,14])
        self.restart();after=self.raw(0,loose=2,listed=True);after.native.serverNow=1005
        self.app.Step(self.app,after)
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.marketSell,'confirmed')
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),0)
        self.assertEqual(len(self.executor.calls),1)
        self.assertEqual(after.native.inventory.w_baton,99)
        self.assertEqual(after.native.inventoryBound[self.item],50)
        self.assertEqual(after.native.collection[self.item],7)

    def test_equipped_copies_and_bound_or_base_siblings_never_fund_variant_sale(self):
        raw=self.raw(loose=2);self.choose();self.warm(raw);self.app.Step(self.app,raw);self.executor.Drain(self.executor)
        self.assertEqual(len(self.executor.calls),0)

    def test_queued_exact_variant_custody_change_is_known_unsent(self):
        raw=self.raw();self.choose();self.warm(raw);self.app.Step(self.app,raw)
        changed=self.raw(2,loose=2);self.h.at(2);self.app.Step(self.app,changed);self.executor.Drain(self.executor)
        self.assertEqual(len(self.executor.calls),0)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),0)

    def test_collection_permission_does_not_block_loose_sale_or_authorize_withdrawal(self):
        for loose,expected in ((3,1),(2,0)):
            with self.subTest(loose=loose):
                if loose==2:self.tearDown();self.setUp()
                self.choose()
                self.app.Set(self.app,'marketSell.custom.fromCollection',True)
                self.app.Set(self.app,'marketSell.custom.maxWithdrawAttempts',1)
                raw=self.raw(loose=loose);self.warm(raw);self.app.Step(self.app,raw);self.executor.Drain(self.executor)
                self.assertEqual(len(self.executor.calls),expected)
                if expected:self.assertEqual(self.executor.calls[1].args[1],'list')
                self.assertTrue(all(row.remote=='MarketAction' for row in self.executor.calls.values()))

    def test_changed_native_resolver_retires_metadata_even_after_restoration(self):
        raw=self.raw();self.choose();self.warm(raw)
        self.h.lua.globals().variantItems=self.deps['gameData'].ITEMS_BY_ID
        original=self.h.lua.eval('getmetatable(variantItems).__index')
        self.h.lua.execute('getmetatable(variantItems).__index=function() return nil end')
        self.app.Step(self.app,raw)
        self.h.lua.globals().originalVariantIndex=original
        self.h.lua.execute('getmetatable(variantItems).__index=originalVariantIndex')
        self.app.Step(self.app,raw);self.executor.Drain(self.executor)
        self.assertEqual(len(self.executor.calls),0)

    def test_missing_cap_wrong_exact_metadata_or_unsupported_variant_stays_unavailable(self):
        for field,value in (('upgradeLevel',5),('baseId','w_other'),('kind','animal'),('id','w_baton')):
            with self.subTest(field=field):
                row=self.deps['gameData'].ITEMS_BY_ID[self.item]
                original=row[field];row[field]=value
                self.choose();raw=self.raw();self.h.at(1)
                custom={k.removeprefix('marketSell.custom.'):v for k,v in self.app.model['values'].items() if k.startswith('marketSell.custom.')}
                settings=lua_table(self.h.lua,{'marketSell':{'enabled':True,'custom':custom}})
                source=next(s for s in self.tab.ReadSources(self.tab).values() if s.id=='marketSellBrowse')
                self.assertTrue(source.enabled(settings))
                result=source.prepare(raw)
                self.assertIsNone(result[0] if isinstance(result,tuple) else result)
                row[field]=original

    def test_native_cap_is_required_before_variant_research_or_trade(self):
        for cap in (None,5,float('nan'),100):
            with self.subTest(cap=cap):
                self.tearDown();self.nativeCap=cap;self.setUp()
                self.choose();raw=self.raw();self.h.at(1)
                custom={k.removeprefix('marketSell.custom.'):v for k,v in self.app.model['values'].items() if k.startswith('marketSell.custom.')}
                settings=lua_table(self.h.lua,{'marketSell':{'enabled':True,'custom':custom}})
                source=next(s for s in self.tab.ReadSources(self.tab).values() if s.id=='marketSellBrowse')
                self.assertTrue(source.enabled(settings))
                result=source.prepare(raw)
                self.assertIsNone(result[0] if isinstance(result,tuple) else result)
                self.app.Step(self.app,raw);self.executor.Drain(self.executor)
                self.assertEqual(len(self.executor.calls),0)


class ExactVariantFlipRuntimeTests(MarketPayoutRuntimeFixture,unittest.TestCase):
    feature_id='marketFlip'
    item='w_baton@6'
    start=ExactVariantRuntimeTests.start

    def raw(self,revision=1,gold=20,loose=2,listed=False):
        raw=ExactVariantRuntimeTests.raw(self,revision,loose,listed)
        raw.native.inventory.gold_bar=gold
        return raw

    def choose(self):
        for key,value in {'enabled':True,'custom.scope':'Selected item','custom.selectedItemId':self.item,
            'custom.maxBuy':8,'custom.sessionBudget':8,'custom.goldReserve':5,'custom.maxAttempts':1,
            'custom.maxListAttempts':1,'custom.minMargin':1,'custom.minMarginPct':0,
            'custom.undercutGold':0,'custom.floorPct':90,'custom.requireCoverage':True}.items():
            self.assertTrue(self.app.Set(self.app,'marketFlip.'+key,value)[0])
        self.app.Resume(self.app)

    def warm(self,raw):
        self.h.at(raw.capturedAt)
        custom={k.removeprefix('marketFlip.custom.'):v for k,v in self.app.model['values'].items() if k.startswith('marketFlip.custom.')}
        settings=lua_table(self.h.lua,{'marketFlip':{'enabled':True,'custom':custom}})
        for source in self.tab.ReadSources(self.tab).values():
            if not source.id.startswith('marketFlip') or not source.enabled(settings):continue
            request=source.prepare(raw)
            if isinstance(request,tuple):request=request[0]
            if request is None:continue
            if source.id.endswith('Browse'):
                self.assertEqual(request.args[3],'w_baton')
                rows=[{'id':'cheap','item':self.item,'qty':1,'price':8,'mine':False},
                    {'id':'other','item':self.item,'qty':1,'price':14,'mine':False}]
                if source.id.startswith('marketFlipList'):rows=rows[1:]
                rows.append({'id':'base','item':'w_baton','qty':9999,'price':1,'mine':False})
                reply={'ok':True,'scope':'item','arg':request.args[3],'pages':1,'more':False,
                    'rows':rows if request.args[3]=='w_baton' else []}
            elif source.id.endswith('Rap'):
                self.assertEqual(request.args[2][1],self.item)
                reply={'ok':True,'values':{self.item:{'sales':15,'quantity':30,'average':14,'available':True}}}
            else:
                self.assertEqual(request.args[2],self.item)
                reply={'ok':True,'item':self.item,'recent':[{'price':14},{'price':15},{'price':16}],'days':[]}
            staged=source.accept(raw,request,lua_table(self.h.lua,reply))
            if isinstance(staged,tuple):staged=staged[0]
            self.assertIsNotNone(staged,source.id);self.assertTrue(source.commit(staged))

    def test_buy_then_list_retains_old_equipped_copies_and_exact_variant_id(self):
        self.choose();raw=self.raw();self.warm(raw);self.app.Step(self.app,raw);self.executor.Drain(self.executor)
        self.assertEqual(len(self.executor.calls),1,str(dict(self.runtime.Status(self.runtime).reasons.items())))
        self.assertEqual([self.executor.calls[1].args[i] for i in range(1,5)],['buy','cheap',1,8])
        after=self.raw(2,gold=12,loose=3);self.h.at(2);self.app.Step(self.app,after)
        self.warm(after);self.app.Step(self.app,after);self.executor.Drain(self.executor)
        self.assertEqual(len(self.executor.calls),2,str(dict(self.runtime.Status(self.runtime).reasons.items())))
        self.assertEqual([self.executor.calls[2].args[i] for i in range(1,5)],['list',self.item,1,14])
        self.restart();after=self.raw(0,gold=12,loose=2,listed=True);after.native.serverNow=1007
        self.app.Step(self.app,after)
        self.assertEqual(len(self.executor.calls),2)
        self.assertIsNone(self.tab.transactions.Active(self.tab.transactions))
        self.assertEqual(self.tab.transactions.BuyUsage(self.tab.transactions).spent,8)
        self.assertEqual(self.tab.transactions.ListingAttempts(self.tab.transactions,'marketFlip')[0],1)

    def test_restart_after_purchase_re_resolves_exact_native_metadata_without_rebuy(self):
        self.choose();raw=self.raw();self.warm(raw);self.app.Step(self.app,raw);self.executor.Drain(self.executor)
        self.restart()
        after=self.raw(0,gold=12,loose=3);after.native.serverNow=1005;self.app.Step(self.app,after)
        self.assertEqual(self.tab.transactions.Active(self.tab.transactions).stage,'observed')
        self.choose();self.warm(after);self.app.Step(self.app,after);self.executor.Drain(self.executor)
        self.assertEqual(len(self.executor.calls),2,str(dict(self.runtime.Status(self.runtime).reasons.items())))
        self.assertEqual([self.executor.calls[2].args[i] for i in range(1,5)],['list',self.item,1,14])
