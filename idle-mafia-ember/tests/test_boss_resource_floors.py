"""Resource-floor parity through the existing real App fixtures (offline)."""
import unittest
import math
from engine_harness import lua_table
import test_bosses as city_unit
import test_global_boss_attack as global_unit
import test_combat_target_selection as player
import test_native_client_bindings as native
import test_player_combat_planner_app as player_app
import test_legacy_remaining_preferences as legacy
import test_bosses_runtime as city
import test_global_boss_attack_runtime as global_boss

class BossFloorTests(unittest.TestCase):
    def test_city_lower_floor_and_zero_reserve(self):
        f=city.BossesRuntimeTests(); f.setUp()
        try:
            self.assertTrue(f.app.Set(f.app, 'bosses.custom.healthFloor', 20)[0])
            self.assertTrue(f.app.Set(f.app, 'bosses.custom.staminaReserve', 0)[0])
            f.choose(); f.step(health=40, stamina=1); f.drain()
            self.assertEqual(len(f.executor.calls), 1)
        finally: f.tearDown()
    def test_global_fractional_reserve_exact_boundary(self):
        g=global_boss.GlobalBossAttackRuntimeTests(); g.setUp(); f=g.f
        try:
            self.assertTrue(f.app.Set(f.app, 'globalBossAttack.custom.staminaReserve', .25)[0])
            g.begin(stamina=1.25)
        finally: g.tearDown()

    def city(self, health=20.25, stamina=.25):
        f=city.BossesRuntimeTests(); f.setUp(); self.addCleanup(f.tearDown)
        self.assertTrue(f.app.Set(f.app,'bosses.custom.healthFloor',health)[0])
        self.assertTrue(f.app.Set(f.app,'bosses.custom.staminaReserve',stamina)[0])
        return f

    def global_fixture(self, reserve=.25):
        g=global_boss.GlobalBossAttackRuntimeTests();g.setUp();self.addCleanup(g.tearDown)
        self.assertTrue(g.f.app.Set(g.f.app,'globalBossAttack.custom.staminaReserve',reserve)[0])
        return g

    def test_city_fractional_health_and_stamina_exact_inclusive_boundaries(self):
        f=self.city();f.choose();f.step(health=40.25,stamina=1.25);f.drain()
        self.assertEqual(len(f.executor.calls),1)
        self.assertEqual(f.executor.calls[1].args[2],2)

    def test_city_below_fractional_stamina_boundary_refuses(self):
        f=self.city();f.choose();f.step(health=40.25,stamina=1.249);f.drain()
        self.assertEqual(len(f.executor.calls),0)

    def test_city_higher_floor_is_enforced_and_next_stage_requires_exact_health(self):
        for health,expected_stage in ((90.25,2),(90.249,1),(80.249,None)):
            with self.subTest(health=health):
                f=self.city(70.25,0);f.choose();f.step(health=health,stamina=1);f.drain()
                self.assertEqual(len(f.executor.calls),int(expected_stage is not None))
                if expected_stage:self.assertEqual(f.executor.calls[1].args[2],expected_stage)

    def test_city_fractional_external_holds_checked_at_emission(self):
        for held,expected in (({'health':.25,'stamina':.25},1),({'health':.251},0),({'stamina':.251},0)):
            with self.subTest(held=held):
                f=self.city();f.choose();f.step(health=40.5,stamina=1.5);f.hold(held);f.drain()
                self.assertEqual(len(f.executor.calls),expected)

    def test_city_queued_preference_change_disable_and_unload_fence_emission(self):
        for change in ('healthFloor','staminaReserve','disable','unload'):
            with self.subTest(change=change):
                f=self.city();f.choose();f.step(health=40.25,stamina=1.25)
                self.assertEqual(len(f.executor.queued),1)
                if change=='unload':f.app.Destroy(f.app)
                elif change=='disable':f.app.Set(f.app,'bosses.enabled',False)
                else:f.app.Set(f.app,'bosses.custom.'+change,21 if change=='healthFloor' else 0)
                f.drain();self.assertEqual(len(f.executor.calls),0)
                if change!='unload':self.assertEqual(f.runtime.checkpoint.bossUsage.hits,0)

    def test_city_sent_confirmation_uses_original_floors_after_preferences_change(self):
        f=self.city(20,0);f.choose();f.step(health=40,stamina=1);f.drain()
        self.assertEqual(len(f.executor.calls),1)
        f.app.Set(f.app,'bosses.custom.healthFloor',100);f.app.Set(f.app,'bosses.custom.staminaReserve',100)
        f.step(2,hp=150,health=20,stamina=0)
        self.assertEqual(f.runtime.Status(f.runtime).outcomes.bosses,'confirmed')

    def test_city_reload_uses_sent_low_floors_not_new_default_preferences(self):
        f=self.city(20,0);f.choose();f.step(health=40,stamina=1);f.drain();f.restart()
        self.assertEqual(f.app.model['values']['bosses.custom.healthFloor'],50)
        f.step(0,hp=150,health=20,stamina=0,server_now=2000005)
        self.assertEqual(f.runtime.Status(f.runtime).recoveries.bosses,'confirmed')
        self.assertEqual(len(f.executor.calls),1)

    def test_global_zero_and_higher_fractional_reserves_are_inclusive(self):
        for reserve,pool,calls in ((0,1,1),(2.25,3.25,1),(2.25,3.249,0)):
            with self.subTest(reserve=reserve,pool=pool):
                g=self.global_fixture(reserve);g.choose();g.step(stamina=pool);g.f.drain()
                self.assertEqual(len(g.f.executor.calls),calls)

    def test_global_75_percent_health_buffer_remains_independent_and_fractional(self):
        for health,calls in ((75.75,1),(75.749,0)):
            g=self.global_fixture(0);g.choose();raw=g.raw(stamina=1,health=health)
            raw.native.stats.maxHealth=101;g.f.app.Step(g.f.app,raw);g.f.drain()
            self.assertEqual(len(g.f.executor.calls),calls)

    def test_global_fractional_external_holds_checked_at_emission(self):
        for held,calls in (({'health':.25,'stamina':.25},1),({'health':.251},0),({'stamina':.251},0)):
            g=self.global_fixture();g.choose();g.step(health=75.25,stamina=1.5)
            g.f.hold(held);g.f.drain();self.assertEqual(len(g.f.executor.calls),calls)

    def test_global_queued_preference_disable_unload_fence_emission(self):
        for change in ('preference','disable','unload'):
            g=self.global_fixture();f=g.f;g.choose();g.step(stamina=1.25)
            self.assertEqual(len(f.executor.queued),1)
            if change=='unload':f.app.Destroy(f.app)
            elif change=='disable':f.app.Set(f.app,'globalBossAttack.enabled',False)
            else:f.app.Set(f.app,'globalBossAttack.custom.staminaReserve',0)
            f.drain();self.assertEqual(len(f.executor.calls),0)
            if change!='unload':self.assertEqual(f.runtime.checkpoint.globalAttackUsage.hits,0)

    def test_global_sent_confirmation_and_reload_keep_original_reserve(self):
        for restart in (False,True):
            g=self.global_fixture(0);f=g.f;g.begin(stamina=1)
            if restart:f.restart()
            else:f.app.Set(f.app,'globalBossAttack.custom.staminaReserve',10)
            g.step(0 if restart else 2,hits=3,damage=125,stamina=0,now=2000105)
            status=f.runtime.Status(f.runtime)
            self.assertEqual((status.recoveries if restart else status.outcomes).globalBossAttack,'confirmed')
            self.assertEqual(len(f.executor.calls),1)

    def test_no_policy_controls_visible_independent_and_off_by_default(self):
        f=self.city()
        for feature in ('bosses','globalBossAttack'):
            self.assertTrue(f.app.ui.features[feature].custom.visible)
            self.assertFalse(f.app.model['values'][feature+'.enabled'])
        values=f.app.model['values']
        self.assertEqual(values['combat.custom.healthFloor'],50)
        self.assertEqual(values['warCombat.custom.staminaReserve'],1)
        self.assertEqual(values['globalBossAttack.custom.staminaReserve'],1)
        self.assertTrue(f.app.Set(f.app,'globalBossAttack.custom.staminaReserve',2.5)[0])
        self.assertEqual(values['bosses.custom.staminaReserve'],.25)

    def test_invalid_controls_never_coerce_and_upper_bounds_are_inclusive(self):
        f=self.city()
        for feature,key,invalid in (
            ('bosses','healthFloor',(0,100.1,True,'20',float('nan'),float('inf'))),
            ('bosses','staminaReserve',(-.1,1e12+.25,True,'0',float('nan'),float('inf'))),
            ('globalBossAttack','staminaReserve',(-.1,1e12+.25,True,'0',float('nan'),float('inf')))):
            for value in invalid:
                self.assertFalse(f.app.Set(f.app,feature+'.custom.'+key,value)[0])
        for feature in ('combat','warCombat','bosses','globalBossAttack'):
            self.assertTrue(f.app.Set(f.app,feature+'.custom.staminaReserve',1e12)[0])
        self.assertTrue(f.app.Set(f.app,'bosses.custom.healthFloor',100)[0])

    def test_malformed_saved_intent_refuses_capture_and_final_reservation(self):
        for fixture_type in (city_unit.BossesTests,global_unit.GlobalBossAttackTests):
            f=fixture_type();f.setUp();before=f.raw();p=f.propose(before)[0]
            reservations=f.h.load('src/engine/ResourceReservations.luau').new(lua_table(f.h.lua,f.h.session),f.h.lua.eval('function() return {} end'))
            for field,bad in [('staminaReserve',v) for v in (-1,True,'0',float('nan'),float('inf'),1e12+.25)]+(
                [('healthFloor',v) for v in (0,True,'20',float('nan'),float('inf'),100.1)] if p.feature=='bosses' else []):
                original=p.intent[field];p.intent[field]=bad
                self.assertIsNone(f.evidence.capture(p,before)[0])
                self.assertIsNone(reservations.Check(reservations,p,before)[0])
                p.intent[field]=original

    def test_old_saved_intent_without_floor_fields_uses_original_defaults(self):
        for fixture_type in (city_unit.BossesTests,global_unit.GlobalBossAttackTests):
            f=fixture_type();f.setUp();before=f.raw();p=f.propose(before)[0]
            p.intent.staminaReserve=None;p.intent.healthFloor=None
            if p.feature=='globalBossAttack':
                for field in ('hitBufferPct','minimumDelay','nativeAttackCooldown','effectiveDelay','useLoadCap','maxPerLoad','loadCountBefore','loadLastAttackAt'):
                    p.intent[field]=None
            self.assertIsNotNone(f.evidence.capture(p,before)[0])
            before.native.pools.stamina=1
            self.assertIsNone(f.evidence.capture(p,before)[0])

    def test_player_modes_and_scout_accept_fractional_reserves_only_for_that_limit(self):
        f=player.CombatTargetSelectionTests();f.setUp()
        for mode in ('combat','warCombat'):
            v=f.view();v.stamina=2.25
            if mode=='warCombat':v.targets[1].familyId=10;v.targets[1].warFamilyId=10
            self.assertIsNotNone(f.choose(v,f.settings(staminaReserve=.25),mode=mode)[0])
            v.stamina=2.249;self.assertIsNone(f.choose(v,f.settings(staminaReserve=.25),mode=mode)[0])
            v.stamina=20
            for field in ('minimumPayout','maxScoutSpend','maxAttackSpend','minSamples'):
                self.assertIsNone(f.choose(v,f.settings(staminaReserve=.25,**{field:.25}),mode=mode)[0])
            for bad in (-1,True,'0',float('nan'),float('inf'),1e12+.25):
                self.assertIsNone(f.choose(v,f.settings(staminaReserve=bad),mode=mode)[0])
        v=f.view();v.targets[1].stats=None;v.stamina=3.25
        s=f.settings(staminaReserve=.25,allowScout=True,maxScoutSpend=1)
        self.assertEqual(f.choose(v,s)[0].kind,'scout')
        v.stamina=3.249;self.assertIsNone(f.choose(v,s)[0])

    def test_native_attack_guard_preserves_fractional_reserve_and_uncertainty(self):
        f=native.NativeClientBindingsTests();h,game,state,probe,source,p=f.fight_client()
        p.intent.staminaReserve=.25;p.intent.uncertainStamina=.25
        state.data.pools.stamina=5.5
        self.assertTrue(source.CanAttack(source,p,99)[0])
        state.data.pools.stamina=5.499;self.assertFalse(source.CanAttack(source,p,99)[0])
        state.data.pools.stamina=10
        for bad in (-1,True,'0',float('nan'),float('inf'),1e12+.25):
            p.intent.staminaReserve=bad;self.assertFalse(source.CanAttack(source,p,99)[0])

    def test_legacy_shared_floors_fan_out_exactly_without_enabling_any_consumer(self):
        f=legacy.LegacyRemainingPreferencesTests();f.setUp();self.addCleanup(f.tearDown)
        for health,stamina in ((20,0),(20.25,.25),(80,12.5),(50,1)):
            accepted,reason=f.preview(healthFloor=health,staminaReserve=stamina)
            self.assertTrue(accepted,reason);f.assert_inert()
            values=f.app.staged['values']
            for feature in ('combat','warCombat','bosses'):
                self.assertEqual(values[feature+'.custom.healthFloor'],health)
                self.assertEqual(values[feature+'.custom.staminaReserve'],stamina)
            self.assertEqual(values['globalBossAttack.custom.staminaReserve'],stamina)
            self.assertTrue(f.app.ApplyProfile(f.app,f.app.staged)[0])
            self.assertTrue(f.app.model.paused)
            self.assertFalse(any(v for k,v in f.app.model['values'].items() if k.endswith('.enabled')))
        for key,bad in (('healthFloor',0),('healthFloor',100.25),('healthFloor',True),('staminaReserve',-.25),('staminaReserve',1e12+1),('staminaReserve',True)):
            accepted,reason=f.preview(**{key:bad});self.assertFalse(accepted);self.assertIn(key,reason)

    def test_planners_reject_malformed_floors_without_fallback_to_defaults(self):
        for fixture_type in (city_unit.BossesTests,global_unit.GlobalBossAttackTests):
            f=fixture_type();f.setUp();raw=f.raw()
            if isinstance(f,city_unit.BossesTests):view=f.view(raw)[0]
            else:
                context=f.context.Read(f.context,raw,lua_table(f.h.lua,f.h.session),0,2)[0]
                view=f.reader.read(raw,context)[0]
            for field,bad in [('staminaReserve',v) for v in (-1,True,'0',float('nan'),float('inf'),1e12+.25)]+(
                [('healthFloor',v) for v in (0,True,'20',float('nan'),float('inf'),100.1)] if isinstance(f,city_unit.BossesTests) else []):
                settings=lua_table(f.h.lua,{'enabled':True,field:bad})
                self.assertIsNone(f.planner.propose(view,settings,f.h.lua.table())[0])

    def test_original_saved_proposals_recover_with_missing_new_fields(self):
        for fixture_type in (city_unit.BossesTests,global_unit.GlobalBossAttackTests):
            f=fixture_type();f.setUp();before=f.raw();p=f.propose(before)[0]
            p.intent.healthFloor=None;p.intent.staminaReserve=None
            if p.feature=='globalBossAttack':
                for field in ('hitBufferPct','minimumDelay','nativeAttackCooldown','effectiveDelay','useLoadCap','maxPerLoad','loadCountBefore','loadLastAttackAt'):
                    p.intent[field]=None
            baseline=f.evidence.capture(p,before)[0]
            if p.feature=='bosses':after=f.raw(revision=2,hp=150,hits=1,spent=1,last=f.now,stamina=11)
            else:after=f.raw(revision=2,usage=1,last=2000100,mine_hits=3,mine_damage=125)
            after.session='new-session';after.native.serverNow+=5
            saved=lua_table(f.h.lua,{'proposal':p,'before':before,'baseline':baseline,'reply':{'ok':True,'dmg':75}})
            self.assertEqual(f.evidence.recoverSaved(saved,after),'confirmed')

    def test_player_actual_app_fractional_floor_at_dispatch_and_queued_change(self):
        for change in (False,True):
            p=player_app.PlayerCombatPlannerAppTests();p.setUp();self.addCleanup(p.tearDown)
            self.assertTrue(p.app.Set(p.app,'combat.custom.staminaReserve',.25)[0])
            p.f.result.before.native.pools.stamina=5.25;p.f.begin()
            if change:
                p.app.Set(p.app,'combat.custom.staminaReserve',0);p.f.step()
                p.f.executor.queued[1]();self.assertEqual(p.f.executor.calls,0)
            else:
                p.f.send();self.assertEqual(p.f.executor.calls,1)
                record=p.f.runtime.checkpoint.Records(p.f.runtime.checkpoint)[1]
                saved=p.f.runtime.checkpoint.Recovery(p.f.runtime.checkpoint,record.actionKey)[0]
                self.assertEqual(saved.proposal.intent.staminaReserve,.25)

    def test_native_scout_guard_fractional_reserve_boundary(self):
        f=native.NativeClientBindingsTests();h,game,state,probe,source,p=f.scout_client()
        p.intent.staminaReserve=.25;p.intent.uncertainStamina=.25
        state.data.pools.stamina=10.5
        self.assertTrue(source.CanScout(source,p,99)[0])
        state.data.pools.stamina=10.499
        self.assertFalse(source.CanScout(source,p,99)[0])

    def test_decimal_city_and_global_stamina_exact_boundary_and_one_ulp_below(self):
        for reserve in (.2,.4):
            for exact in (True,False):
                pool=1+reserve
                if not exact:pool=math.nextafter(pool,0)
                with self.subTest(reserve=reserve,exact=exact):
                    f=self.city(stamina=reserve);f.choose();f.step(stamina=pool);f.drain()
                    self.assertEqual(len(f.executor.calls),int(exact))
                    g=self.global_fixture(reserve);g.choose();g.step(stamina=pool);g.f.drain()
                    self.assertEqual(len(g.f.executor.calls),int(exact))

    def test_decimal_city_health_selects_next_stage_exactly_and_repeat_just_below(self):
        for floor in (20.3,20.4):
            for exact in (True,False):
                health=20+floor
                if not exact:health=math.nextafter(health,0)
                with self.subTest(floor=floor,exact=exact):
                    f=self.city(health=floor);f.choose();f.step(health=health);f.drain()
                    self.assertEqual(len(f.executor.calls),1)
                    self.assertEqual(f.executor.calls[1].args[2],2 if exact else 1)

    def test_decimal_player_attack_and_scout_boundaries_include_held_stamina(self):
        f=player.CombatTargetSelectionTests();f.setUp()
        for mode in ('combat','warCombat'):
            for reserve in (.2,.4):
                for scout in (False,True):
                    for exact in (True,False):
                        v=f.view();v.stamina=2+1+int(scout)+reserve
                        if not exact:v.stamina=math.nextafter(v.stamina,0)
                        if mode=='warCombat':v.targets[1].familyId=10;v.targets[1].warFamilyId=10
                        if scout:v.targets[1].stats=None
                        settings=f.settings(staminaReserve=reserve,allowScout=scout,maxScoutSpend=1)
                        held={'stamina':1,'health':0,'attackSpent':0,'scoutSpent':0}
                        selected=f.choose(v,settings,mode=mode,held=held)[0]
                        self.assertEqual(selected is not None,exact,(mode,reserve,scout,exact))

    def test_decimal_boss_planners_include_current_and_uncertain_holds(self):
        for fixture_type in (city_unit.BossesTests,global_unit.GlobalBossAttackTests):
            f=fixture_type();f.setUp()
            for reserve in (.2,.4):
                for exact in (True,False):
                    pool=3+reserve
                    if not exact:pool=math.nextafter(pool,0)
                    raw=f.raw(stamina=pool)
                    if isinstance(f,city_unit.BossesTests):view=f.view(raw)[0]
                    else:
                        context=f.context.Read(f.context,raw,lua_table(f.h.lua,f.h.session),0,2)[0]
                        view=f.reader.read(raw,context)[0]
                    settings=lua_table(f.h.lua,{'enabled':True,'staminaReserve':reserve})
                    held=lua_table(f.h.lua,{'stamina':1,'uncertainStamina':1})
                    self.assertEqual(f.planner.propose(view,settings,held)[0] is not None,exact)

    def test_decimal_player_actual_app_dispatch_boundary(self):
        for reserve in (.2,.4):
            for exact in (True,False):
                p=player_app.PlayerCombatPlannerAppTests();p.setUp();self.addCleanup(p.tearDown)
                self.assertTrue(p.app.Set(p.app,'combat.custom.staminaReserve',reserve)[0])
                pool=5+reserve
                p.f.result.before.native.pools.stamina=pool if exact else math.nextafter(pool,0)
                p.app.Set(p.app,'combat.enabled',True);p.app.Resume(p.app);p.f.step()
                self.assertEqual(len(p.f.executor.queued),int(exact))
                if exact:p.f.send();self.assertEqual(p.f.executor.calls,1)

    def test_decimal_player_unheld_attack_and_scout_inclusive_boundaries(self):
        f=player.CombatTargetSelectionTests();f.setUp()
        for mode in ('combat','warCombat'):
            for reserve in (.2,.4):
                for scout in (False,True):
                    for exact in (True,False):
                        v=f.view();v.stamina=2+int(scout)+reserve
                        if not exact:v.stamina=math.nextafter(v.stamina,0)
                        if mode=='warCombat':v.targets[1].familyId=10;v.targets[1].warFamilyId=10
                        if scout:v.targets[1].stats=None
                        settings=f.settings(staminaReserve=reserve,allowScout=scout,maxScoutSpend=1)
                        self.assertEqual(f.choose(v,settings,mode=mode)[0] is not None,exact,(mode,reserve,scout,exact))

    def test_decimal_player_health_boundary_includes_held_health(self):
        f=player.CombatTargetSelectionTests();f.setUp()
        for exact in (True,False):
            v=f.view();v.health=40.3 if exact else math.nextafter(40.3,0)
            held={'stamina':0,'health':20,'attackSpent':0,'scoutSpent':0}
            self.assertEqual(f.choose(v,f.settings(healthFloor=20.3),held=held)[0] is not None,exact)
