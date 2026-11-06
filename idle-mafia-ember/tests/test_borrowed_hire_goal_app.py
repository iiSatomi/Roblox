"""Contract hiring borrows an already enabled ordinary proposal and its durable limits."""
import hashlib
import unittest

from engine_harness import lua_table
import test_contract_goal_runtime as contract_fixture


class BorrowedHireGoalAppTests(unittest.TestCase):
    def setUp(self):
        self.seed=contract_fixture.ContractGoalRuntimeTests();self.seed.setup_goal('hires')
        self.seed.app.Destroy(self.seed.app)
        self.h=self.seed.h
        h=self.h
        h.lua.globals().hireGoalHash=lambda text:hashlib.sha256(text.encode()).hexdigest()
        self.storage=self.seed.f.storage
        self.storage.hash=h.lua.eval('function(text) return hireGoalHash(text) end')
        hire=h.load('src/tabs/crew/CrewHire.luau')
        catalog=h.load('src/tabs/crew/NativeHireCatalog.luau').new(lua_table(h.lua,
            {'CREW':{'hireTiers':[{'id':'street','cost':10000}]}}),'b'*64,'release-a')
        self.crew=h.lua.eval('''function(hire,catalog) return {id='crew',
            Enrich=function(_,raw) return catalog:Enrich(raw) end,
            Descriptors=function() return {{id='crewHire',reader=hire,planner=hire,evidence=hire,
                recoverSaved=hire.recoverSaved}} end} end''')(hire,catalog)
        self.tabs=lua_table(h.lua,[self.seed.tab,self.crew])
        composed,reason=h.load('src/tabs/TabComposition.luau').build(self.tabs,h.load('src/ui/Catalog.luau'),
            h.load('src/engine/FeatureRegistry.luau'),h.load('src/tabs/TabSnapshotAssembler.luau'))
        self.assertIsNone(reason)
        composed.features[len(composed.features)+1]=self.seed.f.runtime.features.operations
        composed.featurePages.operations='operations'
        self.executor=h.lua.execute('''return {calls={},queued={},
            Schedule=function(self,fn) self.queued[#self.queued+1]=fn;return true end,
            Invoke=function(self,remote,method,...)
                self.calls[#self.calls+1]={remote=remote,args=table.pack(...)}
                return self.reply or {ok=true,index=2,member={name='New',rarity=3,atk=8,def=9,healId='new'}}
            end,
            Drain=function(self) local q=self.queued;self.queued={};for _,fn in ipairs(q) do fn() end end}''')
        plan=h.load('src/transport/NativeCallPlan.luau').withCrew(h.load('src/tabs/crew/CrewCallPlan.luau'))
        adapter=h.load('src/transport/NativeDispatchAdapter.luau').new(plan,self.executor)
        self.runtime=h.load('src/engine/AutomationRuntime.luau').new(lua_table(h.lua,{
            'clock':h.clock,'transport':adapter,'storage':self.storage,'identity':h.session,
            'modules':self.seed.f.runtime.modules,'features':composed.features,'featurePages':composed.featurePages,
            'tabInstances':self.tabs,'snapshotAssembler':composed.snapshotAssembler}))
        self.app=h.load('src/App.luau').start(lua_table(h.lua,{
            'Ember':h.load('tests/ember_double.lua')(),'Catalog':h.load('src/ui/Catalog.luau'),
            'Settings':h.load('src/storage/Settings.luau'),'EmberAdapter':h.load('src/ui/EmberAdapter.luau'),
            'ContractsTab':h.load('src/tabs/contracts/Module.luau'),'CrewTab':h.load('src/tabs/crew/Module.luau'),
            'automationRuntimeInstance':self.runtime}))
        initial=self.seed.raw()
        self.day_reset,self.week_reset=initial.native.derived.contractDayReset,initial.native.derived.contractWeekReset

    def tearDown(self):self.app.Destroy(self.app)

    def raw(self,revision=1,progress=0,hired=False,paid=False,done=False):
        raw=self.seed.raw(revision,progress,done)
        raw.native.cash=19000.25 if paid else 30000.25
        raw.native.crew=lua_table(self.h.lua,[{'name':'Player'},
            {'name':'New','rarity':3,'atk':8,'def':9,'healId':'new'} if hired else {},
            {'name':'Home','rarity':4,'healId':'home'}])
        raw.economyProof.hirePct=10
        raw.native.derived.contractDayReset=self.day_reset
        raw.native.derived.contractWeekReset=self.week_reset
        return raw

    def select(self,borrow=True,hire=True,goal=True,ops=True,cap=1,reserve=10000):
        values={'crewHire.enabled':hire,'crewHire.policy':'street','crewHire.custom.maxCost':20000,
            'crewHire.custom.cashReserve':reserve,'crewHire.custom.maxAttempts':cap,'crewHire.custom.maxSpend':20000,
            'operations.enabled':ops,'operations.policy':'Highest tier','autoContracts.enabled':goal}
        if borrow is not None:values['autoContracts.custom.borrowHires']=borrow
        for key,value in values.items():self.assertTrue(self.app.Set(self.app,key,value)[0],key)
        self.app.Resume(self.app)

    def step(self,raw):
        self.h.at(raw.capturedAt)
        self.assertTrue(self.app.Step(self.app,raw)[0])

    def test_borrow_prioritizes_exact_ordinary_hire_and_preserves_native_signature_and_quota(self):
        self.select();self.step(self.raw());self.executor.Drain(self.executor)
        self.assertEqual(len(self.executor.calls),1)
        call=self.executor.calls[1]
        self.assertEqual((call.remote,call.args.n),('CrewAction',4))
        self.assertEqual([call.args[i] for i in range(1,5)],['hire','street',11000,None])
        self.assertTrue(self.runtime.Status(self.runtime).goals.autoContracts.routed)
        usage=self.runtime.checkpoint.Allowance(self.runtime.checkpoint,'crewHire')[0]
        self.assertEqual((usage.attempted,usage.spent),(1,11000))

    def test_default_off_keeps_existing_ordinary_priority(self):
        self.select(borrow=None);self.step(self.raw());self.executor.Drain(self.executor)
        self.assertFalse(self.app.model['values']['autoContracts.custom.borrowHires'])
        self.assertEqual(self.executor.calls[1].remote,'StartOperation')

    def test_disabled_goal_keeps_existing_ordinary_priority(self):
        self.select(goal=False);self.step(self.raw());self.executor.Drain(self.executor)
        self.assertEqual(self.executor.calls[1].remote,'StartOperation')

    def test_borrow_never_enables_hiring_or_bypasses_zero_attempts_and_cash_reserve(self):
        for changes in ({'hire':False},{'cap':0},{'reserve':30000}):
            with self.subTest(changes=changes):
                self.select(ops=False,**changes);self.step(self.raw());self.executor.Drain(self.executor)
                self.assertEqual(len(self.executor.calls),0)

    def test_goal_off_still_allows_independently_enabled_standalone_hiring(self):
        self.select(goal=False,ops=False);self.step(self.raw());self.executor.Drain(self.executor)
        self.assertEqual(self.executor.calls[1].remote,'CrewAction')
        self.assertIsNone(self.runtime.Status(self.runtime).goals.autoContracts)

    def test_queued_hire_disable_refunds_exact_unsent_usage(self):
        self.select();self.step(self.raw());self.app.Set(self.app,'crewHire.enabled',False)
        self.executor.Drain(self.executor)
        self.assertEqual(len(self.executor.calls),0)
        usage=self.runtime.checkpoint.Allowance(self.runtime.checkpoint,'crewHire')[0]
        self.assertEqual((usage.attempted,usage.spent),(0,0))
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),0)

    def test_exact_hire_does_not_claim_contract_progress_without_new_native_objective(self):
        self.select(ops=False);self.step(self.raw());self.executor.Drain(self.executor)
        self.step(self.raw(2,hired=True,paid=True))
        status=self.runtime.Status(self.runtime)
        self.assertEqual(status.outcomes.crewHire,'confirmed')
        self.assertEqual(status.goals.autoContracts.state,'waiting')
        self.step(self.raw(3,progress=1,hired=True,paid=True))
        self.assertEqual(self.runtime.Status(self.runtime).goals.autoContracts.state,'progressed')
        self.step(self.raw(4,progress=2,hired=True,paid=True,done=True))
        self.assertEqual(self.runtime.Status(self.runtime).goals.autoContracts.state,'complete')
        self.executor.Drain(self.executor);self.assertEqual(len(self.executor.calls),1)

    def test_new_reset_cannot_masquerade_as_old_objective_progress(self):
        self.select(ops=False);self.step(self.raw());self.executor.Drain(self.executor)
        after=self.raw(2,progress=1,hired=True,paid=True)
        after.native.derived.contractDayReset+=86400
        self.step(after)
        self.assertNotEqual(self.runtime.Status(self.runtime).goals.autoContracts.state,'progressed')
        self.assertNotEqual(self.runtime.Status(self.runtime).goals.autoContracts.state,'complete')
        self.assertEqual(len(self.executor.calls),1)


if __name__=='__main__':unittest.main()
