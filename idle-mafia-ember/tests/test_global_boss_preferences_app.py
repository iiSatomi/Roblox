"""Five Global preferences through actual App, native queue and strict checkpoint owner."""
import unittest
import test_global_boss_attack_runtime as attack_fixture
import test_global_boss_claim_runtime as claim_fixture
from engine_harness import lua_table

class GlobalBossPreferencesAppTests(unittest.TestCase):
    def setUp(self):
        self.g=attack_fixture.GlobalBossAttackRuntimeTests();self.g.setUp();self.f=self.g.f;self.h=self.g.h
        self.f.app.Destroy(self.f.app)
        self.f.modules.GlobalBossLoadUsage=self.h.load('src/tabs/combat/GlobalBossLoadUsage.luau')
        self.f.start_current()
    def tearDown(self): self.f.tearDown()
    def setting(self,name,value,feature='globalBossAttack'):
        ok,reason=self.f.app.Set(self.f.app,feature+'.custom.'+name,value);self.assertTrue(ok,reason)
    def capped(self,cap=1): self.setting('useLoadCap',True);self.setting('maxPerLoad',cap)
    def confirm(self,revision=2,now=2000101):
        self.h.at(revision-1);self.g.step(revision,hits=3,damage=125,stamina=9,now=now)
    def second_run(self,revision=3,now=2000110):
        self.h.lua.globals().globalEvent.id='judge';self.h.at(max(revision-1,now-2000100))
        raw=self.g.raw(revision,now=now)
        raw.native.gb=lua_table(self.h.lua,{'run':'judge_2000000','hits':0,'dmg':0,'claimed':False})
        self.f.app.Step(self.f.app,raw);self.f.drain();return raw
    def test_zero_and_fractional_cap_live_in_actual_numeric_input_and_profile(self):
        self.capped(0);self.g.choose();self.g.step();self.f.drain();self.assertEqual(len(self.f.executor.calls),0)
        profile=self.f.app.model.Snapshot(self.f.app.model)
        profile['values']['globalBossAttack.custom.maxPerLoad']=1.5
        self.assertTrue(self.f.app.ApplyProfile(self.f.app,profile)[0])
        self.assertEqual(self.f.app.model['values']['globalBossAttack.custom.maxPerLoad'],1.5)
        self.assertEqual(self.f.app.ui.handles['globalBossAttack.custom.maxPerLoad'].Get(self.f.app.ui.handles['globalBossAttack.custom.maxPerLoad']),'1.5')
        self.g.begin();self.confirm();self.second_run(now=2000110)
        self.assertEqual(len(self.f.executor.calls),2)
    def test_cap_survives_event_toggle_pause_stop_and_profile_apply(self):
        self.capped();self.g.begin();self.confirm()
        self.f.app.Set(self.f.app,'globalBossAttack.enabled',False)
        self.f.app.Stop(self.f.app);profile=self.f.app.model.Snapshot(self.f.app.model)
        profile['values']['globalBossAttack.enabled']=True
        self.f.app.ApplyProfile(self.f.app,profile);self.f.app.Resume(self.f.app)
        self.second_run();self.assertEqual(len(self.f.executor.calls),1)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).globalBossLoad.attackAttempts,1)
    def test_fresh_load_resets_local_count_but_preserves_durable_event_usage(self):
        self.capped();self.g.begin();self.confirm();self.f.restart();self.capped();self.g.choose()
        self.second_run(now=2000110);self.assertEqual(len(self.f.executor.calls),2)
        self.assertEqual(self.f.runtime.checkpoint.GlobalAttackUsage(self.f.runtime.checkpoint,'hellfire_2000000',0).hits,1)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).globalBossLoad.attackAttempts,1)
    def test_rejected_and_timeout_remain_charged(self):
        self.capped();self.f.executor.reply=lua_table(self.h.lua,{'ok':False})
        self.g.begin();self.h.at(1);self.g.step(2,now=2000101)
        self.second_run();self.assertEqual(len(self.f.executor.calls),1)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).globalBossLoad.attackAttempts,1)
        self.f.restart();self.capped();self.g.choose();self.f.executor.reply=lua_table(self.h.lua,{'ok':True,'pending':True})
        self.second_run(now=2000110);self.h.at(47);self.g.step(4,now=2000157)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).globalBossLoad.attackAttempts,1)
    def test_queued_disable_refunds_once_only_after_checkpoint_release(self):
        self.capped();self.g.choose();self.g.step()
        self.assertEqual(self.f.runtime.Status(self.f.runtime).globalBossLoad.attackAttempts,1)
        self.f.app.Set(self.f.app,'globalBossAttack.enabled',False);self.f.drain()
        self.assertEqual(self.f.runtime.Status(self.f.runtime).globalBossLoad.attackAttempts,0)
        self.f.drain();self.assertEqual(self.f.runtime.Status(self.f.runtime).globalBossLoad.attackAttempts,0)
        self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)),0)
    def test_failed_checkpoint_clear_does_not_refund_local_charge(self):
        self.capped();self.g.choose();self.g.step()
        self.f.storage.Write=self.h.lua.eval('function() return false end')
        self.f.app.Set(self.f.app,'globalBossAttack.enabled',False);self.f.drain()
        self.assertEqual(self.f.runtime.Status(self.f.runtime).globalBossLoad.attackAttempts,1)
        self.assertEqual(len(self.f.executor.calls),0)
    def test_failed_prepare_does_not_mint_local_attempt(self):
        self.capped();self.f.storage.Write=self.h.lua.eval('function() return false end')
        self.g.choose();self.g.step();self.f.drain()
        self.assertEqual(self.f.runtime.Status(self.f.runtime).globalBossLoad.attackAttempts,0)
        self.assertEqual(len(self.f.executor.calls),0)
    def test_longer_delay_crosses_event_boundaries_and_queued_edits_fence(self):
        self.setting('minimumDelay',12.5);self.g.begin();self.confirm()
        self.second_run(now=2000110);self.assertEqual(len(self.f.executor.calls),1)
        self.h.at(13);self.second_run(14,now=2000114);self.assertEqual(len(self.f.executor.calls),2)
    def test_fractional_floor_plus_buffer_planning_evidence_and_reservations(self):
        self.setting('healthFloor',50.25);self.setting('hitBufferPct',25.25)
        self.g.choose();self.g.step(health=75.49);self.f.drain();self.assertEqual(len(self.f.executor.calls),0)
        self.h.at(1);self.g.step(2,health=75.5,now=2000101);self.f.drain()
        self.assertEqual(len(self.f.executor.calls),1)
    def test_sum_over_one_hundred_blocks_without_clamping(self):
        self.setting('healthFloor',80);self.setting('hitBufferPct',25)
        self.g.choose();self.g.step(health=100);self.f.drain();self.assertEqual(len(self.f.executor.calls),0)
    def test_queued_health_preference_change_fences_call_and_refunds(self):
        self.capped();self.g.choose();self.g.step();self.setting('healthFloor',90)
        self.f.drain();self.assertEqual(len(self.f.executor.calls),0)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).globalBossLoad.attackAttempts,0)
    def test_lower_delay_requires_source_proof(self):
        self.setting('minimumDelay',2);self.g.choose();self.g.step();self.f.drain()
        self.assertEqual(len(self.f.executor.calls),0)
        self.assertIn('native cooldown',self.f.runtime.Status(self.f.runtime).reasons.globalBossAttack)

    def with_cooldown(self,value=1.25):
        self.f.app.Destroy(self.f.app);self.f.global_rule.ATTACK_COOLDOWN=value;self.f.start_current()

    def test_source_owned_two_second_delay_and_reload_preserve_event_cap(self):
        self.with_cooldown();self.setting('minimumDelay',2);self.g.begin();self.confirm()
        self.h.at(1.99);self.g.step(3,hits=3,damage=125,stamina=9,now=2000101.99);self.f.drain()
        self.assertEqual(len(self.f.executor.calls),1)
        self.h.at(2);self.g.step(4,hits=3,damage=125,stamina=9,now=2000102);self.f.drain()
        self.assertEqual(len(self.f.executor.calls),2)
        self.f.restart();self.g.step(0,hits=4,damage=200,stamina=8,now=2000103)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).recoveries.globalBossAttack,'confirmed')
        self.assertEqual(self.f.runtime.checkpoint.GlobalAttackUsage(self.f.runtime.checkpoint,'hellfire_2000000',0).hits,2)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).globalBossLoad.attackAttempts,0)

    def test_native_cooldown_above_choice_wins_and_changed_rule_fences_queue(self):
        self.with_cooldown(7.5);self.setting('minimumDelay',2);self.g.begin();self.confirm()
        self.h.at(7.49);self.g.step(3,hits=3,damage=125,now=2000107.49);self.f.drain()
        self.assertEqual(len(self.f.executor.calls),1)
        self.h.at(7.5);self.g.step(4,hits=3,damage=125,now=2000107.5)
        self.f.global_rule.ATTACK_COOLDOWN=1.25;self.f.drain()
        self.assertEqual(len(self.f.executor.calls),1)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).globalBossLoad.attackAttempts,1)

    def test_exact_unsent_unload_recovers_without_transfer_refund(self):
        self.capped();self.g.choose();self.g.step();old=self.f.runtime
        self.f.app.Destroy(self.f.app);self.f.drain();self.f.restart();self.capped();self.g.step(0,now=2000105)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).recoveries.globalBossAttack,'known_unsent')
        self.assertEqual(self.f.runtime.Status(self.f.runtime).globalBossLoad.attackAttempts,0)
        self.assertEqual(old.Status(old).globalBossLoad.attackAttempts,1)
        self.assertEqual(len(self.f.executor.calls),0)

    def test_save_yield_then_unload_never_emits_or_charges_new_load(self):
        self.capped();self.g.choose()
        self.h.lua.globals().yieldApp=self.f.app;self.h.lua.globals().yieldRaw=self.g.raw()
        self.f.storage.Write=self.h.lua.eval("function(self,key,value) if not self.yielded then self.yielded=true;coroutine.yield('saving') end;self.data[key]=value;return true end")
        self.h.lua.execute('globalSave=coroutine.create(function() yieldApp:Step(yieldRaw) end)')
        self.assertEqual(self.h.lua.eval('coroutine.resume(globalSave)'),(True,'saving'))
        self.f.app.Destroy(self.f.app);self.assertTrue(self.h.lua.eval('coroutine.resume(globalSave)'))
        self.f.drain();self.f.restart();self.g.step(0,now=2000105)
        self.assertEqual(len(self.f.executor.calls),0)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).globalBossLoad.attackAttempts,0)

    def test_caller_load_proof_cannot_bypass_actual_owner_counter(self):
        self.capped();self.g.begin();self.confirm();self.h.at(10)
        raw=self.g.raw(3,now=2000110)
        raw.globalBossLoadProof=lua_table(self.h.lua,{**self.h.session,'revision':3,'capturedAt':10,'attackAttempts':0,'now':10})
        self.f.app.Step(self.f.app,raw);self.f.drain()
        self.assertEqual(len(self.f.executor.calls),1)

    def test_same_load_cooldown_change_does_not_strand_confirmed_attack(self):
        self.with_cooldown();self.setting('minimumDelay',2);self.g.begin()
        self.f.global_rule.ATTACK_COOLDOWN=7.5;self.confirm()
        self.assertEqual(self.f.runtime.Status(self.f.runtime).outcomes.globalBossAttack,'confirmed')
        self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)),0)
        self.assertEqual(len(self.f.executor.calls),1)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).globalBossLoad.attackAttempts,1)

    def test_same_load_invalid_cooldown_does_not_strand_exact_rejection(self):
        self.with_cooldown();self.setting('minimumDelay',2);self.f.executor.reply=lua_table(self.h.lua,{'ok':False})
        self.g.begin();self.f.global_rule.ATTACK_COOLDOWN='malformed';self.h.at(1);self.g.step(2,now=2000101)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).outcomes.globalBossAttack,'rejected')
        self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)),0)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).globalBossLoad.attackAttempts,1)
        self.h.at(10);self.g.step(3,now=2000110);self.f.drain()
        self.assertEqual(len(self.f.executor.calls),1)

    def test_changed_missing_cooldown_blocks_new_default_delay_attack(self):
        self.with_cooldown();self.f.global_rule.ATTACK_COOLDOWN=None
        self.g.choose();self.g.step();self.f.drain()
        self.assertEqual(len(self.f.executor.calls),0)
        self.assertIn('cooldown',self.f.runtime.Status(self.f.runtime).reasons.globalBossAttack.lower())

    def test_changed_malformed_cooldown_fences_queued_default_delay_attack(self):
        self.with_cooldown();self.g.choose();self.g.step()
        self.f.global_rule.ATTACK_COOLDOWN=900;self.f.drain()
        self.assertEqual(len(self.f.executor.calls),0)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).globalBossLoad.attackAttempts,0)
        self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)),0)

    def test_terminal_settlement_uses_original_intent_after_preference_and_cooldown_change(self):
        self.with_cooldown();self.setting('minimumDelay',2);self.g.begin()
        self.setting('healthFloor',100);self.setting('hitBufferPct',75);self.setting('minimumDelay',120)
        self.confirm();self.assertEqual(self.f.runtime.Status(self.f.runtime).outcomes.globalBossAttack,'confirmed')
        self.f.restart();self.setting('minimumDelay',2);self.g.choose();self.h.at(1)
        self.g.step(0,hits=3,damage=125,now=2000110);self.f.drain()
        self.assertEqual(len(self.f.executor.calls),2)
        self.f.app.Destroy(self.f.app);self.f.global_rule.ATTACK_COOLDOWN=7.5
        self.h.session['session']='second-fresh-load';self.h.at(0);self.f.start_current()
        self.setting('minimumDelay',120);self.setting('healthFloor',100)
        self.g.step(0,hits=4,damage=200,stamina=8,health=50,now=2000120)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).recoveries.globalBossAttack,'confirmed')
        self.assertEqual(self.f.runtime.Status(self.f.runtime).globalBossLoad.attackAttempts,0)

    def test_saved_partial_or_forged_delay_is_not_recovered(self):
        self.with_cooldown();self.setting('minimumDelay',2);self.g.begin()
        saved=self.f.runtime.checkpoint.Recovery(self.f.runtime.checkpoint,'globalBossAttack:hellfire_2000000:0')[0]
        evidence=self.h.load('src/features/GlobalBossAttackEvidence.luau')
        for field,bad in (('effectiveDelay',1),('nativeAttackCooldown',0.1),('minimumDelay',None),('hitBufferPct',None)):
            original=saved.proposal.intent[field];saved.proposal.intent[field]=bad
            self.assertIsNone(evidence.capture(saved.proposal,saved.before)[0])
            saved.proposal.intent[field]=original

    def test_checkpoint_rejects_forged_effective_delay_before_any_charge(self):
        self.with_cooldown();self.setting('minimumDelay',2)
        self.h.lua.globals().forgedRuntime=self.f.runtime
        self.h.lua.execute("local save=forgedRuntime.checkpoint.Save;forgedRuntime.checkpoint.Save=function(self,p,b,base) p.intent.effectiveDelay=1;return save(self,p,b,base) end")
        self.g.choose();self.g.step();self.f.drain()
        self.assertEqual(len(self.f.executor.calls),0)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).globalBossLoad.attackAttempts,0)

    def test_cancelled_token_cannot_refund_a_new_same_action_charge(self):
        self.capped();self.g.choose();self.g.step()
        p=self.f.runtime.session.broker.active.proposal
        self.f.app.Set(self.f.app,'globalBossAttack.enabled',False);self.f.drain()
        self.h.at(1);self.g.choose();self.g.step(2,now=2000101)
        self.f.runtime.globalBossLoad.Finish(self.f.runtime.globalBossLoad,p,True,True)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).globalBossLoad.attackAttempts,1)
        self.f.drain();self.assertEqual(len(self.f.executor.calls),1)

    def test_checkpoint_save_yield_then_profile_change_cancels_and_refunds_after_release(self):
        self.capped();self.g.choose();self.h.lua.globals().yieldApp=self.f.app;self.h.lua.globals().yieldRaw=self.g.raw()
        self.f.storage.Write=self.h.lua.eval("function(self,key,value) if not self.yielded then self.yielded=true;coroutine.yield('saving') end;self.data[key]=value;return true end")
        self.h.lua.execute('globalEdit=coroutine.create(function() yieldApp:Step(yieldRaw) end)')
        self.assertEqual(self.h.lua.eval('coroutine.resume(globalEdit)'),(True,'saving'))
        self.setting('maxPerLoad',0);self.h.lua.eval('coroutine.resume(globalEdit)');self.f.drain()
        self.assertEqual(len(self.f.executor.calls),0)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).globalBossLoad.attackAttempts,0)
        self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)),0)

    def test_durable_event_twenty_five_limit_survives_large_per_load_cap(self):
        self.capped(10000)
        usage=lua_table(self.h.lua,{'runKey':'hellfire_2000000','hits':25,'lastServerNow':0})
        self.assertTrue(self.f.runtime.checkpoint.Commit(self.f.runtime.checkpoint,self.h.lua.table(),None,None,None,None,usage)[0])
        self.g.choose();self.g.step();self.f.drain();self.assertEqual(len(self.f.executor.calls),0)


class GlobalBossClaimLoadAppTests(unittest.TestCase):
    def setUp(self):
        self.g=claim_fixture.GlobalBossClaimRuntimeTests();self.g.setUp();self.f=self.g.f;self.h=self.g.h
        self.f.app.Destroy(self.f.app);self.f.modules.GlobalBossLoadUsage=self.h.load('src/tabs/combat/GlobalBossLoadUsage.luau');self.f.start_current()
    def tearDown(self):self.f.tearDown()
    def cap(self,value):
        self.assertTrue(self.f.app.Set(self.f.app,'globalBossClaim.custom.useLoadCap',True)[0])
        self.assertTrue(self.f.app.Set(self.f.app,'globalBossClaim.custom.maxPerLoad',value)[0])
    def test_same_load_cooldown_change_does_not_strand_claim_settlement(self):
        self.f.app.Destroy(self.f.app);self.f.global_rule.ATTACK_COOLDOWN=1.25;self.f.start_current()
        self.g.begin();self.f.global_rule.ATTACK_COOLDOWN=7.5
        self.h.at(1);self.g.step(2,claimed=True,medals=3,crates=5,now=2000101)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).outcomes.globalBossClaim,'confirmed')
        self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)),0)
        self.assertEqual(len(self.f.executor.calls),1)

    def test_invalid_attack_cooldown_does_not_block_independent_claim(self):
        self.f.app.Destroy(self.f.app);self.f.global_rule.ATTACK_COOLDOWN='malformed';self.f.start_current()
        self.g.begin();self.h.at(1);self.g.step(2,claimed=True,medals=3,crates=5,now=2000101)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).outcomes.globalBossClaim,'confirmed')
        self.assertEqual(len(self.f.executor.calls),1)

    def test_claim_zero_then_one_across_events_and_fresh_load(self):
        self.cap(0);self.g.choose();self.g.step();self.f.drain();self.assertEqual(len(self.f.executor.calls),0)
        self.cap(1);self.g.begin();self.h.at(1);self.g.step(2,claimed=True,medals=3,crates=5,now=2000101)
        self.h.lua.globals().globalEvent.id='judge';self.h.at(2)
        raw=self.g.raw(3,medals=3,crates=5,now=2000102);raw.native.gb.run='judge_2000000'
        self.f.app.Step(self.f.app,raw);self.f.drain();self.assertEqual(len(self.f.executor.calls),1)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).globalBossLoad.claimAttempts,1)
        self.f.restart();self.cap(1);self.g.choose();raw=self.g.raw(0,now=2000110);raw.native.gb.run='judge_2000000'
        self.f.app.Step(self.f.app,raw);self.f.drain();self.assertEqual(len(self.f.executor.calls),2)
    def test_claim_rejected_retains_load_and_durable_event_caps(self):
        self.cap(1);self.f.executor.reply=lua_table(self.h.lua,{'ok':False});self.g.begin()
        self.h.at(1);self.g.step(2,now=2000101)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).globalBossLoad.claimAttempts,1)
        self.assertEqual(self.f.runtime.checkpoint.globalClaimUsage.attempts,1)
    def test_claim_disable_refunds_once_and_unknown_timeout_keeps_charge(self):
        self.cap(1);self.g.choose();self.g.step();self.f.app.Set(self.f.app,'globalBossClaim.enabled',False);self.f.drain()
        self.assertEqual(self.f.runtime.Status(self.f.runtime).globalBossLoad.claimAttempts,0)
        self.f.executor.reply=lua_table(self.h.lua,{'ok':True,'pending':True});self.h.at(1);self.g.choose();self.g.step(2,now=2000101);self.f.drain()
        self.h.at(46);self.g.step(3,now=2000146)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).globalBossLoad.claimAttempts,1)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).outcomes.globalBossClaim,'skipped_unconfirmed')

class LegacyGlobalPreferencesTests(unittest.TestCase):
    def setUp(self):
        import test_profile_management as fixture
        self.f=fixture.ProfileManagementTests();self.f.setUp();self.app=self.f.app
    def tearDown(self):self.f.tearDown()
    def test_all_five_keys_preview_fractionally_without_starting_or_writing(self):
        import json
        values={'version':17,'globalBossHealthFloor':50.25,'globalBossHitBufferPct':25.25,
            'globalBossAttackDelay':2,'globalBossAttackMaxPerLoad':1.5,'globalBossClaimMaxPerLoad':0}
        accepted,reason=self.app.PreviewImport(self.app,json.dumps(values));self.assertTrue(accepted,reason)
        expected={'globalBossAttack.custom.healthFloor':50.25,'globalBossAttack.custom.hitBufferPct':25.25,
            'globalBossAttack.custom.minimumDelay':2,'globalBossAttack.custom.maxPerLoad':1.5,
            'globalBossAttack.custom.useLoadCap':True,'globalBossClaim.custom.maxPerLoad':0,'globalBossClaim.custom.useLoadCap':True}
        for key,value in expected.items(): self.assertEqual(self.app.staged['values'][key],value)
        self.assertEqual(len(self.f.base.storage.data),0)
        self.assertTrue(self.app.ApplyProfile(self.app,self.app.staged)[0]);self.assertTrue(self.app.model.paused)
        self.assertEqual(self.app.model['values']['globalBossAttack.custom.maxPerLoad'],1.5)
        self.assertFalse(any(v for k,v in self.app.model['values'].items() if k.endswith('.enabled')))
    def test_equal_default_caps_are_mapped_with_optional_guard_enabled(self):
        accepted,reason=self.app.PreviewImport(self.app,'{"version":17,"globalBossAttackMaxPerLoad":25,"globalBossClaimMaxPerLoad":1}')
        self.assertTrue(accepted,reason)
        for feature in ('globalBossAttack','globalBossClaim'):
            self.assertTrue(self.app.importReview.mapped[feature+'.custom.useLoadCap'])
    def test_invalid_legacy_cap_or_delay_never_stages(self):
        import json
        for field,value in (('globalBossAttackMaxPerLoad',-1),('globalBossClaimMaxPerLoad',10.5),('globalBossAttackDelay',1.99),('globalBossHitBufferPct',75.1)):
            accepted,reason=self.app.PreviewImport(self.app,json.dumps({'version':17,field:value}))
            self.assertFalse(accepted);self.assertIn(field,reason)

if __name__=='__main__': unittest.main()
