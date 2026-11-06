"""Read-only native hire quotes reach the real Crew planner without injected proofs."""
import unittest
import test_runtime_host as host_fixture
import test_native_client_bindings as binding_fixture
import test_crew_hire_runtime as crew_fixture
from engine_harness import Harness, lua_table


class NativeHireHostTests(unittest.TestCase):
    def test_current_host_constructs_and_closes_owned_hire_source_with_isolated_read(self):
        f = host_fixture.RuntimeHostTests(); f.setUp(); f.current_client(); h = f.h
        h.lua.globals().hireHostStart = f.app_module.start
        f.app_module.start = h.lua.eval("function(deps) hireHostDeps=deps; return hireHostStart(deps) end")
        h.lua.globals().hireHostBindings = f.deps.NativeClientBindings.read
        f.deps.NativeClientBindings.read = h.lua.eval("function(...) local b=hireHostBindings(...); b.placeVersion=654; return b end")
        f.deps.NativeHireQuoteSource = h.lua.execute("""return {
            bind=function(deps) assert(deps.nativeState==real_state); return {native=true} end,
            new=function(current,identity,key,readNative)
                assert(current.native and type(readNative)=='function')
                return {sourceKey=key,release=identity.release,account=identity.account,
                    Enrich=function(_,raw)return raw end,CanDispatch=function()return true end,
                    Close=function(self) self.closed=true end} end} """)
        owner, reason = f.host_module.start(f.deps)
        self.assertIsNotNone(owner, reason)
        try:
            source = h.lua.globals().hireHostDeps.hireQuoteSource
            self.assertIsNotNone(source, 'Production Host must supply the owned Crew hire proof producer')
            self.assertEqual(source.account, 'user-a')
            owner.Destroy(owner)
            self.assertTrue(source.closed)
        finally: owner.Destroy(owner)


class NativeHireBindingTests(unittest.TestCase):
    def setUp(self):
        b=binding_fixture.NativeClientBindingsTests()
        self.h,self.game,self.state,self.remotes,_,self.require,self.bindings,_=b.make_client()
        h=self.h;self.mw=self.remotes.Parent;self.config=self.mw.children.Config.Value
        self.game.PlaceVersion=654;self.game.PlaceId=73897506680154
        self.state.data=lua_table(h.lua,{'cityId':'city-a','family':{'id':'family-a'},'userId':42,
            'cash':30000,'crew':[{'name':'Player'},{},{'name':'Home','rarity':4,'healId':'home-id'}]})
        h.lua.globals().hireTestState=self.state
        self.state.latest=h.lua.eval('function() return hireTestState.data end')
        self.config.CREW=lua_table(h.lua,{'hireTiers':[{'id':'street','cost':10000}]})
        self.config.DECREES=lua_table(h.lua,{'hire':{'min':-25,'max':25,'default':0}})
        self.config.hireCost=h.lua.eval('function(tier,pct) return math.max(1,math.floor(tier.cost*(100+pct)/100+0.5)) end')
        self.mw.attributes.DecreeHirePct=10;self.mw.attributes.DecreeHireAt=990;self.mw.attributes.DecreeRulerId='other-family'
        self.decree=self.mw.children.DecreeRules.Value
        self.decree.BY_KEY=lua_table(h.lua,{'hire':{'attr':'DecreeHirePct'}})
        h.lua.globals().hireTestDecree=self.decree
        self.decree.default=h.lua.eval('function()return 0 end')
        self.decree.pct=h.lua.eval('function(mw) local v=mw:GetAttribute("DecreeHirePct"); if v==nil then return 0 end; return math.max(-25,math.min(25,math.floor(tonumber(v)))) end')
        self.decree.isPenalty=h.lua.eval('function(_,pct)return pct>0 end')
        self.decree.inRulingFamily=h.lua.eval('function(mw,family)return type(family)=="string" and family~="" and mw:GetAttribute("DecreeRulerId")==family end')
        self.decree.pctFor=h.lua.eval('function(mw,kind,family) local d=hireTestDecree;local pct=d.pct(mw,kind); if d.isPenalty(kind,pct) and d.inRulingFamily(mw,family) then return d.default(kind) end;return pct end')
        h.lua.globals().hireTestNow=1001
        self.clock=self.mw.children.ServerClock.Value
        self.clock.now=h.lua.eval('function() return hireTestNow end')
        self.module=h.load('src/tabs/crew/NativeHireQuoteSource.luau')
        self.bound,self.reason=self.module.bind(lua_table(h.lua,{'game':self.game,'requireModule':self.require,
            'nativeState':self.state,'config':self.config,'placeVersion':654}))
        self.assertIsNotNone(self.bound,self.reason)
        self.source,self.reason=self.module.new(self.bound,lua_table(h.lua,h.session),'a'*64,h.lua.eval('function(fn,...)return pcall(fn,...)end'))
        self.assertIsNone(self.reason)
        self.raw=h.snapshot(native={'fullSync':True,'serverNow':1001,'cityId':'city-a','family':{'id':'family-a'},'userId':42,
            'cash':30000,'crew':[{'name':'Player'},{},{'name':'Home','rarity':4,'healId':'home-id'}]})

    def enrich(self):return self.source.Enrich(self.source,self.raw)

    def test_native_quote_and_ruling_exemption_have_exact_owned_headers(self):
        enriched,reason=self.enrich();self.assertIsNone(reason)
        proof=enriched.economyProof
        self.assertEqual((proof.hirePct,proof.quotes.street,proof.revision),(10,11000,1))
        self.assertEqual(proof.account,self.h.session['account'])
        self.mw.attributes.DecreeRulerId='family-a'
        self.raw.revision=2
        enriched,reason=self.enrich();self.assertIsNone(reason)
        self.assertEqual((enriched.economyProof.hirePct,enriched.economyProof.quotes.street),(0,10000))
        self.mw.attributes.DecreeHirePct=-10;self.raw.revision=3
        self.assertEqual(self.enrich()[0].economyProof.quotes.street,9000)

    def test_actual_binding_proof_drives_existing_hire_and_queued_roster_change_refuses(self):
        enriched,reason=self.enrich();self.assertIsNone(reason)
        catalog=self.h.load('src/tabs/crew/NativeHireCatalog.luau').new(self.config,'a'*64,'release-a')
        enriched,reason=catalog.Enrich(catalog,enriched);self.assertIsNone(reason)
        enriched.crewHireUsageProof=lua_table(self.h.lua,{**self.h.session,'revision':1,'capturedAt':0,'attempted':0,'spent':0})
        context=lua_table(self.h.lua,{**self.h.session,'revision':1,'capturedAt':0,'hireCatalogKey':'a'*64})
        hire=self.h.load('src/tabs/crew/CrewHire.luau')
        view,reason=hire.read(enriched,context);self.assertIsNone(reason)
        proposal,reason=hire.propose(view,lua_table(self.h.lua,{'enabled':True,'policy':'street',
            'custom':{'maxCost':12500,'cashReserve':1000,'maxSpend':12500,'maxAttempts':1}}))
        self.assertIsNone(reason);self.assertEqual(proposal.intent.cost,11000)
        self.assertIsNotNone(hire.capture(proposal,enriched)[0])
        self.assertTrue(self.source.CanDispatch(self.source,proposal,self.raw))
        self.state.data.crew[2]=lua_table(self.h.lua,{'name':'Already hired','rarity':2,'healId':'new-id'})
        self.assertFalse(self.source.CanDispatch(self.source,proposal,self.raw))

    def test_stale_clock_wrong_family_city_account_or_place_never_make_proof(self):
        for change in ('clock','family','city','account','place','partial','userid'):
            with self.subTest(change=change):
                self.setUp()
                if change=='clock':self.h.lua.globals().hireTestNow=1004
                elif change=='family':self.state.data.family.id='foreign'
                elif change=='city':self.state.data.cityId='other'
                elif change=='account':self.raw.account='other'
                elif change=='place':self.raw.place='other'
                elif change=='partial':self.raw.native.fullSync=False
                else:self.state.data.userId=99
                self.assertIsNone(self.enrich()[0])

    def test_changed_helpers_modules_or_build_retire_source_without_reactivation(self):
        for change in ('helper','nestedHelper','config','tier','module','state','build'):
            with self.subTest(change=change):
                self.setUp()
                if change=='helper':self.config.hireCost=self.h.lua.eval('function()return 10000 end')
                elif change=='nestedHelper':self.decree.default=self.h.lua.eval('function()return 0 end')
                elif change=='config':self.config.DECREES.hire.default=1
                elif change=='tier':self.config.CREW.hireTiers[1].cost=1
                elif change=='module':self.mw.children.DecreeRules.Parent=None
                elif change=='state':self.state.latest=self.h.lua.eval('function()return {}end')
                else:self.game.PlaceVersion=655
                self.assertIsNone(self.enrich()[0])
                if change=='build':self.game.PlaceVersion=654;self.assertIsNone(self.enrich()[0])

    def test_current_native_roster_change_or_new_cash_loss_refuses_snapshot_quote(self):
        for change in ('crew', 'cash'):
            with self.subTest(change=change):
                self.setUp()
                if change=='crew':self.state.data.crew[2]=lua_table(self.h.lua,{'name':'Already hired','rarity':2,'healId':'new-id'})
                else:self.state.data.cash=29999
                self.assertIsNone(self.enrich()[0])

    def test_owned_dispatch_ignores_mutated_returned_proof_but_rejects_current_decree_change(self):
        enriched,reason=self.enrich();self.assertIsNone(reason)
        proposal=lua_table(self.h.lua,{**self.h.session,'revision':1,'feature':'crewHire',
            'intent':{'kind':'crewHire','tier':'street','cost':11000,'hirePct':10,'decreeRevision':1}})
        self.assertTrue(self.source.CanDispatch(self.source,proposal,self.raw))
        enriched.economyProof.quotes.street=1
        self.assertTrue(self.source.CanDispatch(self.source,proposal,self.raw))
        self.mw.attributes.DecreeHirePct=20
        self.assertFalse(self.source.CanDispatch(self.source,proposal,self.raw))

    def test_helper_changes_attributes_during_capture_or_yielded_read_refuses(self):
        self.h.lua.globals().hirePriorPctFor=self.decree.pctFor
        self.decree.pctFor=self.h.lua.eval('function(mw,...) local pct=hirePriorPctFor(mw,...);mw.attributes.DecreeHireAt=991;return pct end')
        self.bound,reason=self.module.bind(lua_table(self.h.lua,{'game':self.game,'requireModule':self.require,
            'nativeState':self.state,'config':self.config,'placeVersion':654}))
        self.source,_=self.module.new(self.bound,lua_table(self.h.lua,self.h.session),'a'*64,self.h.lua.eval('function(fn,...)return pcall(fn,...)end'))
        self.assertIsNone(self.enrich()[0])
        self.setUp()
        self.source,_=self.module.new(self.bound,lua_table(self.h.lua,self.h.session),'a'*64,self.h.lua.eval('function()return false,"Native calculation yielded"end'))
        self.assertIsNone(self.enrich()[0])


class NativeHireAppTests(unittest.TestCase):
    def setUp(self):
        self.c=crew_fixture.CrewHireRuntimeTests();self.c.setUp();self.f=self.c.f;self.h=self.c.h
        self.f.app.Destroy(self.f.app)
        h=self.h;h.lua.globals().hireAppPct=10
        current=h.lua.eval("{account='user-a',place='73897506680154',Current=function()return true end,Read=function(native) return {city=native.cityId,familyId='',rulerId='',hirePct=hireAppPct,attributes={DecreeHirePct=hireAppPct},quotes={street=math.floor(10000*(100+hireAppPct)/100+0.5)}} end}")
        self.source,reason=h.load('src/tabs/crew/NativeHireQuoteSource.luau').new(current,lua_table(h.lua,h.session),'a'*64,h.lua.eval('function(fn,...)return pcall(fn,...)end'))
        self.assertIsNone(reason)
        self.f.tab_dependencies['hireQuoteSource']=self.source
        self.f.tab_dependencies['activateCurrentClient']=True
        self.f.start_current()
    def tearDown(self):self.f.tearDown()
    def raw(self,revision=1,hired=False,cash=30000):
        raw=self.c.raw(revision,hired,cash);raw.economyProof=None
        return raw
    def choose(self):
        self.c.choose();self.f.app.Set(self.f.app,'crewHire.custom.maxCost',12500)
        self.f.app.Set(self.f.app,'crewHire.custom.maxSpend',12500)
    def step(self,raw):self.h.at(raw.capturedAt);return self.f.app.Step(self.f.app,raw)
    def test_owned_source_fills_absent_proof_and_sends_exact_native_quote(self):
        self.choose();self.step(self.raw());self.f.drain()
        self.assertEqual(len(self.f.executor.calls),1,str(dict(self.f.runtime.Status(self.f.runtime).reasons.items())))
        call=self.f.executor.calls[1]
        self.assertEqual([call.args[i] for i in range(1,5)],['hire','street',11000,None])
        self.step(self.raw(2,True,19000))
        self.assertEqual(self.f.runtime.Status(self.f.runtime).outcomes.crewHire,'confirmed')
        self.assertEqual(self.f.runtime.checkpoint.Allowance(self.f.runtime.checkpoint,'crewHire')[0].spent,11000)
    def test_queued_decree_change_refuses_native_send_and_refunds_known_unsent(self):
        self.choose();self.step(self.raw())
        self.assertEqual(len(self.f.executor.queued),1)
        self.assertEqual(self.f.runtime.checkpoint.Allowance(self.f.runtime.checkpoint,'crewHire')[0].spent,11000)
        self.h.lua.globals().hireAppPct=20;self.f.drain()
        self.assertEqual(len(self.f.executor.calls),0)
        self.assertEqual(self.f.runtime.checkpoint.Allowance(self.f.runtime.checkpoint,'crewHire')[0].spent,0)
    def test_source_proof_survives_checkpoint_and_saved_hire_recovery_without_replay(self):
        self.choose();self.step(self.raw());self.f.drain()
        record=self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)[1]
        saved,reason=self.f.runtime.checkpoint.Recovery(self.f.runtime.checkpoint,record.actionKey)
        self.assertIsNone(reason)
        self.assertEqual(saved.before.economyProof.quotes.street,11000)
        self.assertEqual(saved.before.economyProof.sourceKey,'a'*64)
        self.f.restart()
        after=self.raw(0,True,19000);after.native.serverNow=1005
        self.f.app.Step(self.f.app,after)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).recoveries.crewHire,'confirmed')
        self.assertEqual(len(self.f.executor.calls),1)
        self.assertEqual(self.f.runtime.checkpoint.Allowance(self.f.runtime.checkpoint,'crewHire')[0].spent,11000)

    def test_replacement_still_needs_dismissal_consent_and_rechecks_funded_hire_quote(self):
        self.f.app.Destroy(self.f.app);self.f.feature_id='crewRoll';self.f.start_current()
        self.f.choose()
        for key,value in {'maxCost':12500,'maxSpend':12500,'allowDismiss':False}.items():
            self.f.app.Set(self.f.app,'crewRoll.custom.'+key,value)
        raw=self.f.f.raw();raw.economyProof=None
        self.step(raw);self.f.drain();self.assertEqual(len(self.f.executor.calls),0)
        self.f.app.Set(self.f.app,'crewRoll.custom.allowDismiss',True)
        raw=self.f.f.raw(revision=2);raw.economyProof=None
        self.step(raw);self.assertEqual(len(self.f.executor.queued),1)
        self.h.lua.globals().hireAppPct=20
        self.f.drain();self.assertEqual(len(self.f.executor.calls),0)

    def test_source_close_and_forged_caller_proof_cannot_authorize(self):
        self.source.Close(self.source);self.choose();raw=self.raw()
        raw.economyProof=lua_table(self.h.lua,{'account':raw.account,'capturedAt':raw.capturedAt,
            'city':raw.native.cityId,'revision':1,'familyId':'','rulerId':'','hirePct':0})
        self.step(raw);self.f.drain();self.assertEqual(len(self.f.executor.calls),0)
