"""Actual Global event attribute source, Combat App, usage and native call."""
import unittest
import test_bosses_runtime as fixture
from engine_harness import lua_table

class GlobalBossAttackRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.BossesRuntimeTests();self.f.setUp();self.f.app.Destroy(self.f.app);self.h=self.f.h
        self.f.feature_id='globalBossAttack'
        self.h.lua.globals().globalAttributes=lua_table(self.h.lua,{'GlobalBossState':'public'})
        self.h.lua.globals().globalEvent=lua_table(self.h.lua,{'id':'hellfire','startAt':2000000,
            'endAt':2001000,'hp':10000,'dmg':100,'status':'live'})
        self.f.global_rule=self.h.lua.execute("""return {ATTR='GlobalBossState',PRIVATE_ATTR='GlobalBossPrivateState',
            decode=function(encoded) if encoded=='public' then return globalEvent end end,
            canAccess=function(event,user) return event.testUserId==nil or event.testUserId==user end}""")
        self.f.executor.reply=lua_table(self.h.lua,{'ok':True,'dmg':75});self.f.start_current()
    def tearDown(self): self.f.tearDown()
    def raw(self,revision=1,hits=2,damage=50,stamina=10,health=80,now=2000100):
        raw=self.f.raw(revision,stamina=stamina,health=health,server_now=now)
        raw.native.gb=lua_table(self.h.lua,{'run':'hellfire_2000000','hits':hits,'dmg':damage,'claimed':False})
        return raw
    def step(self,revision=1,**kw):
        raw=self.raw(revision,**kw);self.f.app.Step(self.f.app,raw);return raw
    def choose(self):self.f.app.Set(self.f.app,'globalBossAttack.enabled',True);self.f.app.Resume(self.f.app)
    def begin(self,**kw):
        self.choose();self.step(**kw);self.f.drain()
        self.assertEqual(len(self.f.executor.calls),1,str(dict(self.f.runtime.Status(self.f.runtime).reasons.items())))
    def test_exact_personal_hit_and_one_argument_native_call(self):
        self.begin();call=self.f.executor.calls[1]
        self.assertEqual(call.remote,'GlobalBossAction');self.assertEqual(call.args.n,1);self.assertEqual(call.args[1],'attack')
        self.h.at(1);self.step(2,hits=3,damage=125,stamina=9,now=2000101)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).outcomes.globalBossAttack,'confirmed')
    def test_saved_exact_personal_hit_recovers_without_replay(self):
        self.begin();self.f.restart();self.step(0,hits=3,damage=125,stamina=9,now=2000105)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).recoveries.globalBossAttack,'confirmed')
        self.assertEqual(len(self.f.executor.calls),1)
    def test_fractional_native_clock_persists_and_reloads(self):
        self.begin(now=2000100.25);self.f.restart()
        self.assertEqual(self.f.runtime.checkpoint.globalAttackUsage.lastServerNow,2000100.25)
    def test_pending_reply_never_confirms_replicated_damage(self):
        self.f.executor.reply=lua_table(self.h.lua,{'ok':True,'dmg':75,'pending':True});self.begin()
        self.h.at(1);self.step(2,hits=3,damage=125,stamina=9,now=2000101)
        self.assertIsNone(self.f.runtime.Status(self.f.runtime).outcomes.globalBossAttack)
    def test_changed_run_after_queue_cannot_emit(self):
        self.choose();self.step();self.h.lua.globals().globalEvent.id='judge';self.f.drain()
        self.assertEqual(len(self.f.executor.calls),0)
    def test_private_restriction_after_queue_cannot_emit(self):
        self.choose();self.step();self.h.lua.globals().globalEvent.testUserId=99;self.f.drain()
        self.assertEqual(len(self.f.executor.calls),0)
    def test_negative_reply_with_partial_personal_effect_stays_held(self):
        self.f.executor.reply=lua_table(self.h.lua,{'ok':False});self.begin();self.h.at(1)
        self.step(2,hits=3,damage=50,stamina=9,now=2000101)
        self.assertIsNone(self.f.runtime.Status(self.f.runtime).outcomes.globalBossAttack)
    def test_shared_stamina_hold_keeps_one_in_reserve(self):
        self.choose();self.step();self.f.hold({'stamina':9});self.f.drain()
        self.assertEqual(len(self.f.executor.calls),0)
    def test_shared_health_hold_preserves_three_quarter_buffer(self):
        self.f.hold({'health':10});self.choose();self.step();self.f.drain()
        self.assertEqual(len(self.f.executor.calls),0)
    def test_definitely_unsent_disable_refunds_only_local_hit(self):
        self.choose();self.step();self.f.app.Set(self.f.app,'globalBossAttack.enabled',False);self.f.drain()
        self.assertEqual(len(self.f.executor.calls),0)
        self.assertEqual(self.f.runtime.checkpoint.globalAttackUsage.hits,0)
    def test_timed_hp_decay_is_not_personal_hit_evidence(self):
        self.begin();self.h.lua.globals().globalEvent.dmg=8000;self.h.at(1);self.step(2,now=2000101)
        self.assertIsNone(self.f.runtime.Status(self.f.runtime).outcomes.globalBossAttack)
    def test_other_run_cannot_confirm_old_personal_hit(self):
        self.begin();self.h.lua.globals().globalEvent.id='judge';self.h.at(1)
        self.step(2,hits=3,damage=125,now=2000101)
        self.assertIsNone(self.f.runtime.Status(self.f.runtime).outcomes.globalBossAttack)

    def test_capped_public_run_is_not_reset_by_another_accessible_run(self):
        usage=lua_table(self.h.lua,{'runKey':'hellfire_2000000','hits':24,'lastServerNow':0})
        self.assertTrue(self.f.runtime.checkpoint.Commit(self.f.runtime.checkpoint,self.h.lua.table(),None,None,None,None,usage)[0])
        self.begin();self.h.at(1);self.step(2,hits=3,damage=125,now=2000101)
        self.h.lua.globals().globalEvent.id='judge';self.h.at(2)
        raw=self.raw(3,now=2000102);raw.native.gb=lua_table(self.h.lua,{'run':'judge_2000000','hits':0,'dmg':0,'claimed':False})
        self.f.app.Step(self.f.app,raw);self.f.drain()
        self.h.at(3);raw=self.raw(4,now=2000103)
        raw.native.gb=lua_table(self.h.lua,{'run':'judge_2000000','hits':1,'dmg':75,'claimed':False})
        self.f.app.Step(self.f.app,raw)
        self.h.lua.globals().globalEvent.id='hellfire';self.h.at(4)
        self.step(5,hits=3,damage=125,now=2000110);self.f.drain()
        self.assertEqual(len(self.f.executor.calls),2)
        self.f.restart()
        self.assertEqual(self.f.runtime.checkpoint.GlobalAttackUsage(self.f.runtime.checkpoint,'hellfire_2000000',0).hits,25)
    def test_exact_rejected_attempt_keeps_run_usage(self):
        self.f.executor.reply=lua_table(self.h.lua,{'ok':False});self.begin();self.h.at(1);self.step(2,now=2000101)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).outcomes.globalBossAttack,'rejected')
        self.assertEqual(self.f.runtime.checkpoint.globalAttackUsage.hits,1)
    def test_unload_before_invoke_recovers_only_unsent_budget(self):
        self.choose();self.step();self.f.app.Destroy(self.f.app);self.f.drain();self.f.restart()
        self.step(0,now=2000105)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).recoveries.globalBossAttack,'known_unsent')
        self.assertEqual(self.f.runtime.checkpoint.globalAttackUsage.hits,0)
    def test_timeout_preserves_pending_and_invoked_budget(self):
        self.f.executor.reply=lua_table(self.h.lua,{'ok':True,'pending':True,'dmg':75});self.begin();self.h.at(45)
        self.step(2,now=2000145)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).outcomes.globalBossAttack,'skipped_unconfirmed')
        self.assertEqual(self.f.runtime.checkpoint.globalAttackUsage.hits,1)
        self.assertEqual(len(self.f.executor.calls),1)

    def test_health_drop_after_queue_fences_native_call(self):
        self.choose();raw=self.step();raw.native.pools.health=74;self.f.drain()
        self.assertEqual(len(self.f.executor.calls),0)
    def test_corrupt_duplicate_run_history_cannot_reset_usage(self):
        self.begin();self.h.at(1);self.step(2,hits=3,damage=125,now=2000101)
        key=self.f.runtime.checkpoint.key
        self.f.storage.data[key].globalAttackUsage.history=lua_table(self.h.lua,[{
            'runKey':'hellfire_2000000','hits':0,'lastServerNow':0}])
        self.f.restart();self.choose();self.step(0,now=2000110);self.f.drain()
        self.assertIsNotNone(self.f.runtime.checkpoint.fault)
        self.assertEqual(len(self.f.executor.calls),1)
    def test_sixty_four_run_capacity_holds_without_evicting_counts(self):
        history=[{'runKey':'other_'+str(i),'hits':25,'lastServerNow':0} for i in range(63)]
        usage=lua_table(self.h.lua,{'runKey':'last_1','hits':25,'lastServerNow':0,'history':history})
        self.assertTrue(self.f.runtime.checkpoint.Commit(self.f.runtime.checkpoint,self.h.lua.table(),None,None,None,None,usage)[0])
        self.choose();self.step();self.f.drain();self.assertEqual(len(self.f.executor.calls),0)
        self.assertEqual(self.f.runtime.checkpoint.GlobalAttackUsage(self.f.runtime.checkpoint,'other_1',0).hits,25)
