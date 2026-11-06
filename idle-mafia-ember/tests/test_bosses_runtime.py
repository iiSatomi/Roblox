"""Actual Combat tab, App, native adapter and checkpoint; no live actions."""
import unittest
import hashlib
import test_automation_runtime as runtime_fixture
import test_combat_tab_module as combat_fixture
import test_bosses as boss_fixture
from engine_harness import lua_table


class BossesRuntimeTests(unittest.TestCase):
    def setUp(self):
        base = runtime_fixture.AutomationRuntimeTests()
        base.setUp()
        self.h, self.modules, self.storage = base.h, base.runtime.modules, base.storage
        base.runtime.Close(base.runtime)
        self.h.lua.globals().bossHash=lambda value:hashlib.sha256(value.encode()).hexdigest()
        self.storage.hash=self.h.lua.eval('function(value) return bossHash(value) end')
        self.storage.Write = self.h.lua.eval('function(self,key,value) self.data[key]=value return true end')
        self.source = self.h.lua.execute('''return {
            MAX_STAGE=100000,
            get=function(stage) return {stage=stage,level=stage*5,hp=stage*100,hitBackMax=stage*10} end,
            crateUnlocked=function() return true end,
            SHOP={gear={{item='w_policebaton',price=2500}},crates={{item='crate_loot',price=14}}}}
        ''')
        self.config = lua_table(self.h.lua, {'BOSS': {'staminaCost': 1}})
        self.executor = self.h.lua.execute('''return {queued={},calls={},
            Schedule=function(self,fn) self.queued[#self.queued+1]=fn return true end,
            Invoke=function(self,remote,method,...)
                self.calls[#self.calls+1]={remote=remote,method=method,args=table.pack(...)}
                return self.reply or {ok=true} end}''')
        self.h.lua.globals().bossExternalHold=None
        self.start_current()

    def start_current(self):
        deps = {'identity':self.h.session, 'clock':self.h.clock, 'NativeBossCatalog':self.h.load('src/tabs/combat/NativeBossCatalog.luau'),
            'bossStages':self.source,'config':self.config,'fingerprint':'a'*64,'release':'release-a',
            'combatRules':{'hospitalHealth':20,'staminaCost':1,'dailyTargetCap':5}}
        if getattr(self,'boss_game_data',None) is not None:
            deps['gameData']=self.boss_game_data;deps['clientGame']=self.boss_client_game
        for name in ('HitListQuery','PlayerTargetState','BlockedFight'):
            deps[name]=self.h.load('src/tabs/combat/'+name+'.luau')
        if getattr(self,'global_rule',None) is not None:
            deps['globalBossSource']=self.h.load('src/tabs/combat/NativeGlobalBossSource.luau').new(
                self.global_rule,self.h.lua.eval('function() return globalAttributes end'),
                self.h.load('src/game/GlobalBossState.luau'),42,'a'*64,'release-a')[0]
        for _,reader,planner,evidence in combat_fixture.ROWS:
            deps[reader]=self.h.load('src/game/'+reader+'.luau')
            deps[planner]=self.h.load('src/features/'+planner+'.luau')
            deps[evidence]=self.h.load('src/features/'+evidence+'.luau')
        self.tab_module=self.h.load('src/tabs/combat/Module.luau')
        self.tab=self.tab_module.new(lua_table(self.h.lua,deps))
        selected=getattr(self,'feature_id','bosses')
        self.descriptor=next(row for row in self.tab.Descriptors(self.tab).values() if row.id==selected)
        native=self.h.load('src/transport/NativeCallPlan.luau')
        plan=native.withCombat(native,self.h.load('src/tabs/combat/CombatCallPlan.luau'))
        self.adapter=self.h.load('src/transport/NativeDispatchAdapter.luau').new(plan,self.executor)
        self.runtime=self.h.load('src/engine/AutomationRuntime.luau').new(lua_table(self.h.lua,{
            'clock':self.h.clock,'transport':self.adapter,'storage':self.storage,'identity':self.h.session,
            'modules':self.modules,'features':[self.descriptor],'featurePages':{selected:'combat'},
            'tabInstances':[self.tab],
            'reservationSources':[self.h.lua.execute("return {id='externalCombatHold',read=function() return bossExternalHold end}")],
            'snapshotAssembler':self.h.load('src/tabs/TabSnapshotAssembler.luau').new(lua_table(self.h.lua,[self.tab]))}))
        self.app=self.h.load('src/App.luau').start(lua_table(self.h.lua,{
            'Ember':self.h.load('tests/ember_double.lua')(),'Catalog':self.h.load('src/ui/Catalog.luau'),
            'Settings':self.h.load('src/storage/Settings.luau'),'EmberAdapter':self.h.load('src/ui/EmberAdapter.luau'),
            'CombatTab':self.tab_module,'automationRuntimeInstance':self.runtime}))

    def tearDown(self): self.app.Destroy(self.app)
    def raw(self,revision=1,hp=200,stamina=12,health=80,server_now=None):
        f=boss_fixture.BossesTests();f.h=self.h;f.now=2000000 if server_now is None else server_now;f.day=1970024
        raw=f.raw(revision=revision,hp=hp,stamina=stamina,health=health)
        # The real catalog and checkpoint must supply these, never fixture data.
        raw.bossStageProof=None;raw.bossUsageProof=None
        return raw
    def step(self,revision=1,**kw):
        raw=self.raw(revision,**kw);self.h.at(raw.capturedAt)
        self.app.Step(self.app,raw);return raw
    def choose(self):
        self.assertTrue(self.app.Set(self.app,'bosses.enabled',True)[0]);self.app.Resume(self.app)
    def drain(self):
        queued,self.executor.queued=self.executor.queued,self.h.lua.table()
        for callback in queued.values(): callback()
    def begin(self):
        self.choose();self.step()
        self.assertEqual(len(self.executor.queued),1,str(dict(self.runtime.Status(self.runtime).reasons.items())))
        self.drain()
    def restart(self):
        self.app.Destroy(self.app);self.h.session['session']='session-reloaded';self.h.at(0);self.start_current()
    def test_actual_stage_call_and_exact_effect_use_trusted_usage(self):
        self.begin();call=self.executor.calls[1]
        self.assertEqual(call.remote,'BossAction');self.assertEqual(call.args.n,2)
        self.assertEqual([call.args[i] for i in (1,2)],['stageAttack',2])
        self.step(2,hp=150,stamina=11)
        self.assertEqual(self.runtime.Status(self.runtime).outcomes.bosses,'confirmed')
        self.assertEqual(self.runtime.checkpoint.bossUsage.hits,1)
        self.assertEqual(self.runtime.checkpoint.bossUsage.stamina,1)
    def test_restart_recovers_exact_saved_attack_without_replay(self):
        self.begin();self.restart();self.step(0,hp=150,stamina=11,server_now=2000005)
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.bosses,'confirmed')
        self.assertEqual(len(self.executor.calls),1)
    def test_pending_negative_does_not_resolve_applied_effect(self):
        self.executor.reply=lua_table(self.h.lua,{'ok':False,'pending':True});self.begin();self.step(2,hp=150,stamina=11)
        self.assertIsNone(self.runtime.Status(self.runtime).outcomes.bosses)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),1)
    def test_native_controller_appearing_after_queue_prevents_emit(self):
        self.choose();raw=self.step();raw.native.bossStage.auto=True
        self.drain();self.assertEqual(len(self.executor.calls),0)
    def test_queued_disable_and_unload_never_emit(self):
        self.choose();self.step();self.app.Set(self.app,'bosses.enabled',False);self.drain()
        self.assertEqual(len(self.executor.calls),0)
        self.app.Set(self.app,'bosses.enabled',True);self.step(2);self.app.Destroy(self.app);self.drain()
        self.assertEqual(len(self.executor.calls),0)
    def test_missing_native_quote_cannot_reuse_caller_stage_proof(self):
        self.source.get=self.h.lua.eval('function() return nil end')
        self.choose();raw=self.raw();f=boss_fixture.BossesTests();f.h=self.h;f.now=2000000;f.day=1970024
        raw.bossStageProof=f.raw().bossStageProof
        self.app.Step(self.app,raw);self.drain();self.assertEqual(len(self.executor.calls),0)
    def test_fractional_native_clock_is_supported(self):
        self.choose();self.step(server_now=2000000.25);self.drain()
        self.assertEqual(len(self.executor.calls),1,str(dict(self.runtime.Status(self.runtime).reasons.items())))

    def test_all_off_does_not_write_or_emit(self):
        self.step();self.drain()
        self.assertEqual(len(self.executor.calls),0);self.assertEqual(len(self.storage.data),0)
    def test_unknown_timeout_retains_exposure_and_never_replays(self):
        self.executor.reply=lua_table(self.h.lua,{'ok':True,'pending':True});self.begin()
        self.h.at(45);raw=self.raw(2);self.app.Step(self.app,raw)
        self.assertEqual(self.runtime.Status(self.runtime).outcomes.bosses,'skipped_unconfirmed')
        self.assertEqual(self.runtime.checkpoint.bossUsage.hits,1)
        self.restart();self.step(0,hp=150,stamina=11,server_now=2000005)
        self.assertIsNone(self.runtime.Status(self.runtime).recoveries.bosses)
        self.assertEqual(len(self.executor.calls),1)
    def test_rejection_is_exact_and_keeps_exposure(self):
        self.executor.reply=lua_table(self.h.lua,{'ok':False});self.begin();self.step(2)
        self.assertEqual(self.runtime.Status(self.runtime).outcomes.bosses,'rejected')
        self.assertEqual(self.runtime.checkpoint.bossUsage.hits,1)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),0)
    def test_negative_with_applied_hp_stays_held_on_reload(self):
        self.executor.reply=lua_table(self.h.lua,{'ok':False});self.begin();self.step(2,hp=150,stamina=11)
        self.assertIsNone(self.runtime.Status(self.runtime).outcomes.bosses)
        self.restart();self.step(0,hp=150,stamina=11,server_now=2000005)
        self.assertIsNone(self.runtime.Status(self.runtime).recoveries.bosses)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),1)
    def test_saved_rejection_and_fractional_usage_survive_new_session(self):
        self.executor.reply=lua_table(self.h.lua,{'ok':False});self.choose()
        self.step(server_now=2000000.25);self.drain();self.restart()
        self.step(0,server_now=2000000.5)
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.bosses,'rejected')
        self.assertEqual(self.runtime.checkpoint.bossUsage.lastServerNow,2000000.25)
    def test_same_clock_cannot_confirm_saved_hit_on_reload(self):
        self.begin();self.restart();self.step(0,hp=150,stamina=11)
        self.assertIsNone(self.runtime.Status(self.runtime).recoveries.bosses)
    def test_changed_current_quote_after_queue_fences_native_call(self):
        self.choose();self.step();self.source.get=self.h.lua.eval(
            'function(stage) return {stage=stage,level=stage*5,hp=stage*100,hitBackMax=49} end')
        self.drain();self.assertEqual(len(self.executor.calls),0)
    def test_low_resources_and_native_auto_never_emit(self):
        self.choose();self.step(health=60,stamina=1);self.drain()
        self.assertEqual(len(self.executor.calls),0)
        raw=self.raw(2);raw.native.bossStage.auto=True;self.app.Step(self.app,raw);self.drain()
        self.assertEqual(len(self.executor.calls),0)
    def test_storage_failure_never_charges_or_emits(self):
        self.storage.Write=self.h.lua.eval('function() return false end')
        self.choose();self.step();self.drain()
        self.assertEqual(len(self.executor.calls),0);self.assertIsNone(self.runtime.checkpoint.bossUsage)
    def hold(self,funds):
        self.h.lua.globals().bossExternalHold=lua_table(self.h.lua,{
            **{key:self.h.session[key] for key in ('account','place','release')},
            'feature':'otherCombat','actionKey':'saved-other',
            'claims':{'allCrew':False,'allItems':False,'members':{},'items':{},'funds':funds}})
    def test_shared_stamina_hold_preserves_one_stamina_floor_at_emission(self):
        self.choose();self.step(stamina=12);self.hold({'stamina':11});self.drain()
        self.assertEqual(len(self.executor.calls),0)
    def test_shared_health_hold_preserves_half_health_floor(self):
        self.hold({'health':20});self.choose();self.step(health=80);self.drain()
        self.assertEqual(len(self.executor.calls),0)
    def test_known_unsent_queue_refusal_does_not_consume_daily_budget(self):
        self.choose();self.step();self.app.Set(self.app,'bosses.enabled',False);self.drain()
        self.assertEqual(len(self.executor.calls),0)
        self.assertEqual(self.runtime.checkpoint.bossUsage.hits,0)
        self.assertEqual(self.runtime.checkpoint.bossUsage.stamina,0)
    def test_successful_result_with_backward_clock_stays_uncertain(self):
        self.begin();self.step(2,hp=150,stamina=11,server_now=1999999)
        self.assertIsNone(self.runtime.Status(self.runtime).outcomes.bosses)

    def seed_usage(self,hits,spent,last=0):
        usage=lua_table(self.h.lua,{'day':1970024,'hits':hits,'stamina':spent,'lastServerNow':last})
        self.assertTrue(self.runtime.checkpoint.Commit(self.runtime.checkpoint,self.h.lua.table(),None,usage)[0])
    def test_daily_hit_cap_and_caller_counter_reset_are_fenced(self):
        self.seed_usage(99,99);self.begin();self.step(2,hp=150,stamina=11)
        self.restart();self.choose();raw=self.raw(0,server_now=2000010)
        raw.bossUsageProof=lua_table(self.h.lua,{'account':'user-a','capturedAt':0,'day':1970024,
            'hits':0,'stamina':0,'lastServerNow':0})
        self.app.Step(self.app,raw);self.drain()
        self.assertEqual(len(self.executor.calls),1);self.assertEqual(self.runtime.checkpoint.bossUsage.hits,100)
    def test_daily_stamina_cap_is_independent_of_hit_cap(self):
        self.config.BOSS.staminaCost=2
        self.app.Destroy(self.app);self.start_current();self.seed_usage(49,98)
        self.begin();self.step(2,hp=150,stamina=10)
        self.restart();self.choose();self.step(0,server_now=2000010);self.drain()
        self.assertEqual(len(self.executor.calls),1)
        self.assertEqual(self.runtime.checkpoint.bossUsage.hits,50)
        self.assertEqual(self.runtime.checkpoint.bossUsage.stamina,100)
    def test_confirmed_hit_retains_native_five_second_spacing(self):
        self.begin();self.step(2,hp=150,stamina=11,server_now=2000004);self.drain()
        self.assertEqual(len(self.executor.calls),1)
        self.h.at(3);raw=self.raw(3,hp=150,stamina=11,server_now=2000005);self.app.Step(self.app,raw);self.drain()
        self.assertEqual(len(self.executor.calls),2)
    def test_unload_after_queue_recovers_unsent_budget_exactly_once(self):
        self.choose();self.step();self.app.Destroy(self.app);self.drain();self.restart();self.step(0,server_now=2000005)
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.bosses,'known_unsent')
        self.assertEqual(self.runtime.checkpoint.bossUsage.hits,0)
        self.assertEqual(self.runtime.checkpoint.bossUsage.stamina,0)
        self.step(1,server_now=2000006);self.assertEqual(self.runtime.checkpoint.bossUsage.hits,0)
        self.assertEqual(len(self.executor.calls),0)
    def test_source_quote_changed_before_outcome_stays_uncertain(self):
        self.begin();self.source.get=self.h.lua.eval(
            'function(stage) return {stage=stage,level=stage*5,hp=stage*100,hitBackMax=21} end')
        self.step(2,hp=150,stamina=11)
        self.assertIsNone(self.runtime.Status(self.runtime).outcomes.bosses)
    def test_health_hold_appearing_after_queue_is_checked_before_emit(self):
        self.choose();self.step();self.hold({'health':20});self.drain()
        self.assertEqual(len(self.executor.calls),0)
