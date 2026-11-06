"""Crew tab -> real engine -> broker -> adapter for an explicitly funded cycle."""
import unittest

from engine_harness import ROOT, lua_table
import test_crew_replacement_lifecycle as lifecycle


class CrewReplacementCompositionTests(unittest.TestCase):
    setUp=lifecycle.CrewReplacementLifecycleTests.setUp
    new_runtime=lifecycle.CrewReplacementLifecycleTests.new_runtime
    raw=lifecycle.CrewReplacementLifecycleTests.raw

    def engine(self):
        odds=[0,100,0,0,0,0,0,0]
        deps={'clock':self.h.clock,'identity':self.h.session,'storage':self.store,
            'fingerprint':'a'*64,'release':'release-a',
            'config':{'CREW':{'hireTiers':[{'id':'street','cost':100,'odds':odds,'oddsLucky':odds}],
                'training':{'minRarity':8,'maxLevel':1,'maxConcurrent':1,'cost':{8:[100]},'minutes':{8:[5]}}},
                'TERRITORY':{'healStaminaCost':1,'healSeconds':30,'injurySeconds':60},
                'CONSUMABLES':{'henchmanCooldownSeconds':30}},
            'gameData':{'ITEMS_BY_ID':{key:{'id':key,'kind':'consumable','restore':{'pool':'health','percent':pct}}
                for key,pct in [('con_bandages',25),('con_medkit_small',50),('con_medkit_large',100)]}},
            'gearSets':self.h.lua.eval('{slotBonus=function() return 0,0 end}')}
        for path in (ROOT/'src/tabs/crew').glob('*.luau'):
            if path.stem!='Module': deps[path.stem]=self.h.load(path.relative_to(ROOT).as_posix())
        deps['ResourceReservations']=self.h.load('src/engine/ResourceReservations.luau')
        deps=lua_table(self.h.lua,deps)
        tab=self.h.load('src/tabs/crew/Module.luau').new(deps)
        self.assertIsNone(tab.replacementFault)
        self.runtime,self.helper=tab.replacementRuntime,tab.replacement
        composed,reason=self.h.load('src/tabs/TabComposition.luau').build(lua_table(self.h.lua,[tab]),
            self.h.load('src/ui/Catalog.luau'),self.h.load('src/engine/FeatureRegistry.luau'),
            self.h.load('src/tabs/TabSnapshotAssembler.luau'))
        self.assertIsNone(reason)
        modules={'Contracts':self.h.contracts}
        for name,folder in [('Broker','engine'),('Journal','engine'),('Context','game'),
                ('Scheduler','engine'),('Session','engine'),('Checkpoint','storage'),
                ('PendingAction','storage'),('CollectionProtection','engine'),('ResourceReservations','engine')]:
            modules[name]=self.h.load('src/'+folder+'/'+name+'.luau')
        executor=self.h.lua.execute('''return {calls={},queued={},
            Schedule=function(self,fn) self.queued[#self.queued+1]=fn end,
            Invoke=function(self,remote,method,...)
                local args=table.pack(...);self.calls[#self.calls+1]=args
                if args[1]=='dismiss' then return {ok=true} end
                return {ok=true,index=2,member={name='New',rarity=2,atk=7,def=8,healId='new'}}
            end,
            Drain=function(self) local rows=self.queued;self.queued={};for _,fn in ipairs(rows) do fn() end end}''')
        router=self.h.load('src/transport/NativeCallPlan.luau').withCrew(deps.CrewCallPlan,deps.CrewReplacement)
        adapter=self.h.load('src/transport/NativeDispatchAdapter.luau').new(router,executor)
        runtime=self.h.load('src/engine/AutomationRuntime.luau').new(lua_table(self.h.lua,{
            'clock':self.h.clock,'transport':adapter,'storage':self.store,'identity':self.h.session,
            'modules':modules,'features':composed.features,'featurePages':composed.featurePages,
            'snapshotAssembler':composed.snapshotAssembler,'reservationSources':tab.ReservationSources(tab)}))
        return tab,runtime,executor

    def snapshot(self,revision=1,stage='original',cash=1000):
        raw=self.raw(revision,stage,cash)
        raw.native.inventory=self.h.lua.table();raw.native.inventoryBound=self.h.lua.table()
        raw.native.pools=lua_table(self.h.lua,{'energy':20})
        return raw

    def choices(self,permission=True):
        custom={key:value for key,value in self.settings.items() if key not in ('enabled','policy')}
        custom['allowDismiss']=permission
        return lua_table(self.h.lua,{'crewRoll':{'enabled':True,'policy':'Custom','custom':custom}})

    def test_real_composition_sends_one_dismiss_then_only_its_funded_hire(self):
        tab,runtime,executor=self.engine()
        requested=self.choices()
        runtime.Resume(runtime)
        status=runtime.Step(runtime,self.snapshot(),requested)
        executor.Drain(executor)
        self.assertEqual(len(executor.calls),1,(status.globalReason,dict(status.reasons.items())))
        self.assertEqual([executor.calls[1][i] for i in (1,2)],['dismiss',2])
        self.assertEqual(tab.replacementOwner.Usage(tab.replacementOwner).attempted,1)
        self.h.at(1)
        status=runtime.Step(runtime,self.snapshot(2,'empty'),requested)
        executor.Drain(executor)
        self.assertEqual(len(executor.calls),2,(status.globalReason,dict(status.reasons.items())))
        self.assertEqual([executor.calls[2][i] for i in (1,2,3)],['hire','street',100])
        self.assertEqual(tab.replacementOwner.Usage(tab.replacementOwner).spent,100)
        self.h.at(2)
        runtime.Step(runtime,self.snapshot(3,'member',900),requested)
        self.assertEqual(len(runtime.checkpoint.Records(runtime.checkpoint)),0)
        self.assertIsNone(tab.replacementOwner.Active(tab.replacementOwner))
        executor.Drain(executor)
        self.assertEqual(len(executor.calls),2)

    def test_enabled_without_explicit_dismissal_permission_sends_nothing(self):
        tab,runtime,executor=self.engine()
        runtime.Resume(runtime)
        runtime.Step(runtime,self.snapshot(),self.choices(False))
        executor.Drain(executor)
        self.assertEqual(len(executor.calls),0)
        self.assertIsNone(tab.replacementOwner.Active(tab.replacementOwner))


if __name__=='__main__': unittest.main()
