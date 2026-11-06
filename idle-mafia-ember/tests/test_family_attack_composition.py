"""Owned Family state and native preflight reach the ordinary engine path."""
import unittest

from engine_harness import lua_table
import test_native_family_boss_controller as native_fixture
from test_combat_tab_module import ROWS


class FamilyAttackCompositionTests(unittest.TestCase):
    def setUp(self):
        fixture=native_fixture.NativeFamilyBossControllerTests()
        fixture.setUp()
        self.h,self.f=fixture.h,fixture.f
        self.controller=fixture.bind()
        source=self.h.lua.eval('''function(controller) return {
            Current=function() return controller.Current() end,
            FamilyBossFrame=function(_,native) return controller.Read(native) end} end''')(self.controller)
        deps={'identity':self.h.session,'fingerprint':'a'*64,'release':'release-a',
            'nativeReadSource':source,'combatRules':{'hospitalHealth':20,'staminaCost':1,'dailyTargetCap':5}}
        for name,folder in [('HitListQuery','tabs/combat'),('PlayerTargetState','tabs/combat'),
                ('BlockedFight','tabs/combat'),('FamilyBossQuery','tabs/combat'),('FamilyTakedownState','game')]:
            deps[name]=self.h.load('src/'+folder+'/'+name+'.luau')
        for _,reader,planner,evidence in ROWS:
            for name,folder in ((reader,'game'),(planner,'features'),(evidence,'features')):
                deps[name]=self.h.load('src/'+folder+'/'+name+'.luau')
        self.tab=self.h.load('src/tabs/combat/Module.luau').new(lua_table(self.h.lua,deps))
        self.f.data.serverNow=1050
        self.settings=lua_table(self.h.lua,{'familyBossAttacks':{'enabled':True,'allowUncalculatedHitBack':True}})
        self.family={'ok':True,'week':100,'famId':9,'stage':6,'inFamily':True,'resetAt':2000,
            'serverNow':1050,'freeMax':10,'freeUsed':0,'freeRegen':3600,'tickets':0,
            'myDmg':100,'claims':[],'claimedStages':[1,2,3,4,5]}

    def snapshot(self,revision=1):
        native=self.h.lua.eval('''function(f) return {fullSync=true,userId=123,serverNow=f.data.serverNow,
            stats={maxHealth=100},pools={health=f.data.pools.health,stamina=f.data.pools.stamina},
            family={id=9},inventory={},inventoryBound={}} end''')(self.f)
        raw=self.h.snapshot(revision=revision,native=native)
        request,reason=self.tab.PrepareFamilyBossRead(self.tab,raw);self.assertIsNone(reason)
        self.family['serverNow']=self.f.data.serverNow
        staged,reason=self.tab.AcceptFamilyBossRead(self.tab,raw,request,lua_table(self.h.lua,self.family))
        self.assertIsNone(reason)
        return staged

    def engine(self):
        self.store=getattr(self,'store',None) or self.h.lua.execute('''return {data={},strictRecovery=true,
            Read=function(self,k) return self.data[k] end,
            Write=function(self,k,v) self.data[k]=v;return true end}''')
        composed,reason=self.h.load('src/tabs/TabComposition.luau').build(lua_table(self.h.lua,[self.tab]),
            self.h.load('src/ui/Catalog.luau'),self.h.load('src/engine/FeatureRegistry.luau'),
            self.h.load('src/tabs/TabSnapshotAssembler.luau'))
        self.assertIsNone(reason)
        modules={'Contracts':self.h.contracts,'FamilyTakedownState':self.h.load('src/game/FamilyTakedownState.luau')}
        for name,folder in [('Broker','engine'),('Journal','engine'),('Context','game'),('Scheduler','engine'),
                ('Session','engine'),('Checkpoint','storage'),('PendingAction','storage'),
                ('CollectionProtection','engine'),('ResourceReservations','engine')]:
            modules[name]=self.h.load('src/'+folder+'/'+name+'.luau')
        executor=self.h.lua.execute('''return {calls={},queued={},
            Schedule=function(self,fn) self.queued[#self.queued+1]=fn end,
            Invoke=function(self,remote,method,...)
                self.calls[#self.calls+1]={remote=remote,method=method,args=table.pack(...)}
                return self.reply or {ok=true,dmg=50,freeLeft=9,tickets=0}
            end,
            Drain=function(self) local rows=self.queued;self.queued={};for _,fn in ipairs(rows) do fn() end end}''')
        base=self.h.load('src/transport/NativeCallPlan.luau')
        router=base.withCombat(base,self.h.load('src/tabs/combat/CombatCallPlan.luau'))
        adapter=self.h.load('src/transport/NativeDispatchAdapter.luau').new(router,executor)
        runtime=self.h.load('src/engine/AutomationRuntime.luau').new(lua_table(self.h.lua,{
            'clock':self.h.clock,'transport':adapter,'storage':self.store,'identity':self.h.session,
            'modules':modules,'features':composed.features,'featurePages':composed.featurePages,
            'snapshotAssembler':composed.snapshotAssembler}))
        runtime.Resume(runtime)
        return runtime,executor

    def choices(self,permission=True):
        return lua_table(self.h.lua,{'familyBossAttacks':{'enabled':True,'policy':'Custom',
            'allowUncalculatedHitBack':permission}})

    def test_real_composition_sends_once_and_confirms_exact_personal_overtime_hit(self):
        runtime,executor=self.engine()
        status=runtime.Step(runtime,self.snapshot(),self.choices())
        executor.Drain(executor)
        self.assertEqual(len(executor.calls),1,(status.globalReason,dict(status.reasons.items())))
        call=executor.calls[1]
        self.assertEqual((call.remote,call.method,call.args.n,call.args[1]),('FamilyBossAction','InvokeServer',1,'attack'))
        self.assertEqual(runtime.checkpoint.FamilyAttackUsage(runtime.checkpoint,100,9,0).hits,1)
        self.h.at(1);self.f.data.serverNow=1051
        self.f.data.pools.health=50;self.f.data.pools.stamina=4
        self.family.update(myDmg=150,freeUsed=1)
        runtime.Step(runtime,self.snapshot(2),self.choices())
        self.assertEqual(len(runtime.checkpoint.Records(runtime.checkpoint)),0)
        self.assertEqual(len(executor.calls),1)
        # Restoring HP and restarting must not restore this weekly permission.
        self.f.data.pools.health=100
        restarted,another=self.engine()
        restarted.Step(restarted,self.snapshot(3),self.choices())
        another.Drain(another)
        self.assertEqual(len(another.calls),0)
        self.assertEqual(restarted.checkpoint.FamilyAttackUsage(restarted.checkpoint,100,9,1).hits,1)

    def test_queued_native_busy_blocks_and_returns_only_known_unsent_weekly_attempt(self):
        runtime,executor=self.engine()
        runtime.Step(runtime,self.snapshot(),self.choices())
        self.assertEqual(runtime.checkpoint.FamilyAttackUsage(runtime.checkpoint,100,9,0).hits,1)
        self.f.familyAttack[2]=True
        executor.Drain(executor)
        self.assertEqual(len(executor.calls),0)
        self.assertEqual(runtime.checkpoint.FamilyAttackUsage(runtime.checkpoint,100,9,0).hits,0)
        self.assertEqual(len(runtime.checkpoint.Records(runtime.checkpoint)),0)

    def test_pending_reply_survives_restart_until_exact_new_personal_state(self):
        runtime,executor=self.engine()
        executor.reply=lua_table(self.h.lua,{'ok':True,'pending':True})
        runtime.Step(runtime,self.snapshot(),self.choices());executor.Drain(executor)
        self.assertEqual(len(executor.calls),1)
        restarted,other=self.engine()
        self.h.at(1);self.f.data.serverNow=1051
        self.family.update(myDmg=150,freeUsed=1)
        restarted.Step(restarted,self.snapshot(2),self.choices());other.Drain(other)
        self.assertEqual(len(other.calls),0)
        self.assertEqual(len(restarted.checkpoint.Records(restarted.checkpoint)),1)
        self.assertEqual(restarted.checkpoint.FamilyAttackUsage(restarted.checkpoint,100,9,0).hits,1)
        record=restarted.checkpoint.Records(restarted.checkpoint)[1]
        self.assertEqual((record.custody.funds.health,record.custody.funds.stamina),(100,1))

    def test_saved_success_is_reconciled_after_new_session_without_replaying(self):
        runtime,executor=self.engine()
        runtime.Step(runtime,self.snapshot(),self.choices());executor.Drain(executor)
        self.h.session['session']='run-b'
        restarted,other=self.engine()
        self.h.at(1);self.f.data.serverNow=1051
        self.family.update(myDmg=150,freeUsed=1)
        restarted.Step(restarted,self.snapshot(1),self.choices());other.Drain(other)
        self.assertEqual(len(other.calls),0)
        self.assertEqual(len(restarted.checkpoint.Records(restarted.checkpoint)),0)
        self.assertEqual(restarted.checkpoint.FamilyAttackUsage(restarted.checkpoint,100,9,0).hits,1)

    def test_permission_revoked_while_queued_prevents_native_send_and_refunds_unsent(self):
        runtime,executor=self.engine()
        runtime.Step(runtime,self.snapshot(),self.choices())
        runtime.Step(runtime,self.snapshot(),self.choices(False))
        executor.Drain(executor)
        self.assertEqual(len(executor.calls),0)
        self.assertEqual(len(runtime.checkpoint.Records(runtime.checkpoint)),0)
        self.assertEqual(runtime.checkpoint.FamilyAttackUsage(runtime.checkpoint,100,9,0).hits,0)

    def test_fractional_native_clock_survives_save_reply_restart_and_weekly_cap(self):
        self.f.data.serverNow=1050.25
        runtime,executor=self.engine()
        status=runtime.Step(runtime,self.snapshot(),self.choices());executor.Drain(executor)
        self.assertEqual(len(executor.calls),1,(status.globalReason,dict(status.reasons.items())))
        restarted,other=self.engine()
        self.h.at(1);self.f.data.serverNow=1051.25
        self.family.update(myDmg=150,freeUsed=1)
        restarted.Step(restarted,self.snapshot(2),self.choices());other.Drain(other)
        self.assertEqual(len(other.calls),0)
        self.assertEqual(len(restarted.checkpoint.Records(restarted.checkpoint)),0)
        self.assertEqual(restarted.checkpoint.FamilyAttackUsage(restarted.checkpoint,100,9,1).lastServerNow,1050.25)

    def test_saved_reply_cannot_be_relabelled_as_unsent_to_restore_permission(self):
        runtime,executor=self.engine()
        runtime.Step(runtime,self.snapshot(),self.choices());executor.Drain(executor)
        record=runtime.checkpoint.Records(runtime.checkpoint)[1]
        ok,reason=runtime.checkpoint.Resolve(runtime.checkpoint,record.actionKey,'schedule_failed')
        self.assertFalse(ok)
        self.assertEqual(runtime.checkpoint.FamilyAttackUsage(runtime.checkpoint,100,9,0).hits,1)
        self.assertEqual(len(runtime.checkpoint.Records(runtime.checkpoint)),1)

    def test_persisted_family_health_custody_blocks_real_player_and_war_attacks_but_not_scout(self):
        from test_war_combat import WarCombatPlannerTests
        self.f.data.pools.stamina=20
        runtime,executor=self.engine()
        runtime.Step(runtime,self.snapshot(),self.choices());executor.Drain(executor)
        restarted,_=self.engine()
        reservations=self.h.load('src/engine/ResourceReservations.luau')
        shared=reservations.new(lua_table(self.h.lua,self.h.session),
            self.h.lua.eval('function(cp) return function() return cp:Records() end end')(restarted.checkpoint))
        view=WarCombatPlannerTests.view(self)
        settings=lua_table(self.h.lua,{'enabled':True,'policy':'Custom','targetSource':'Saved and new',
            'minimumPayout':0,'staminaReserve':0,'healthFloor':20,'maxAttackSpend':5,'maxScoutSpend':5,
            'minSamples':0,'minWinRate':0,'minWinChance':90,'minPowerRatio':1.25,'scoutMaxAge':30,
            'maxStaminaCost':5,'minTargetLevel':1,'maxTargetLevel':1000,'allowScout':True})
        for feature in ('warCombat','combat'):
            with self.subTest(feature=feature):
                if feature=='combat':view.war.active=False
                planner=self.h.load('src/tabs/combat/PlayerFightPlanner.luau').new(
                    self.h.load('src/tabs/combat/TargetSelection.luau'),feature)
                held=lua_table(self.h.lua,{'stamina':0,'uncertainStamina':0})
                proposal,reason=planner.propose(view,settings,held);self.assertIsNone(reason)
                self.assertEqual(proposal.intent.kind,'playerAttack')
                raw=self.snapshot()
                self.assertIsNone(shared.Check(shared,proposal,raw)[0])
                view.targets[1].stats=None
                scout,reason=planner.propose(view,settings,held);self.assertIsNone(reason)
                self.assertEqual(scout.intent.kind,'playerScout')
                self.assertIsNotNone(shared.Check(shared,scout,raw)[0])
                view.targets[1].stats=lua_table(self.h.lua,{'at':100,'kind':'scout','level':10,'defense':10})

    def test_bounded_family_health_custody_is_durable_and_cannot_be_borrowed_by_attacks(self):
        from test_family_takedown_attacks import FamilyTakedownAttackTests
        fixture=FamilyTakedownAttackTests();fixture.setUp()
        h=fixture.h;before=fixture.raw(health=100,stamina=20)
        proposal=fixture.propose(before)[0]
        reservations=h.load('src/engine/ResourceReservations.luau')
        proposal.custody=reservations.ForProposal(proposal,before)[0]
        store=h.lua.execute('''return {data={},strictRecovery=true,Read=function(self,k) return self.data[k] end,
            Write=function(self,k,v) self.data[k]=v;return true end}''')
        module=h.load('src/storage/Checkpoint.luau')
        cp=module.new(store,None,reservations)
        cp.Load(cp,h.session['account'],h.session['place'],h.session['release'])
        self.assertTrue(cp.Save(cp,proposal)[0])
        restored=module.new(store,None,reservations)
        self.assertIsNone(restored.Load(restored,h.session['account'],h.session['place'],h.session['release'])[1])
        self.assertEqual(restored.Records(restored)[1].custody.funds.health,20)
        shared=reservations.new(lua_table(h.lua,h.session),
            h.lua.eval('function(cp) return function() return cp:Records() end end')(restored))
        for feature in ('combat','warCombat'):
            with self.subTest(feature=feature):
                attack=h.proposal(feature,feature+':attack')
                attack.resources=lua_table(h.lua,{'stamina':1});attack.intent.kind='playerAttack'
                self.assertIsNone(shared.Check(shared,attack,before)[0])
                attack.intent.kind='playerScout'
                self.assertIsNotNone(shared.Check(shared,attack,before)[0])
        shared=reservations.new(lua_table(h.lua,h.session),h.lua.eval('function() error("unavailable") end'))
        self.assertIsNone(shared.Check(shared,attack,before)[0])

    def test_missing_explicit_permission_never_queues(self):
        runtime,executor=self.engine()
        runtime.Step(runtime,self.snapshot(),self.choices(False));executor.Drain(executor)
        self.assertEqual(len(executor.calls),0)
        self.assertEqual(len(runtime.checkpoint.Records(runtime.checkpoint)),0)

    def test_tab_produces_owned_current_preflight_and_discards_caller_attack_proof(self):
        raw=self.snapshot()
        raw.familyAttackProof=lua_table(self.h.lua,{'hitBackMax':0,'controllersClear':True})
        enriched,reason=self.tab.Enrich(self.tab,raw,self.settings);self.assertIsNone(reason)
        self.assertIsNotNone(enriched.familyAttackProof)
        self.assertTrue(enriched.familyAttackProof.nativePreflight)
        self.assertFalse(enriched.familyAttackProof.hitBackKnown)
        self.assertIsNone(enriched.familyAttackProof.hitBackMax)
        self.assertEqual(enriched.familyAttackProof.stage,6)
        self.assertEqual(enriched.familyAttackProof.staminaCost,1)


if __name__=='__main__':unittest.main()
