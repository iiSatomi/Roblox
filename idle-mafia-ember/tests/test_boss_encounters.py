"""Separate load-local confirmed Boss encounter limits and confirmation delay."""
import unittest
from engine_harness import lua_table
import test_boss_full_selection as selection_fixture

class BossEncounterTests(unittest.TestCase):
    def fixture(self):
        owner=selection_fixture.BossFullSelectionAppTests();f=owner.fixture();self.addCleanup(owner.doCleanups)
        original=f.raw
        def clocked(*args,**kwargs):
            f.h.at(f.h.clock.Now(f.h.clock)+1)
            result=original(*args,**kwargs)
            for stage,hp in getattr(f,"observed_hps",{}).items():result.native.bossStage.hp[stage]=hp
            return result
        f.raw=clocked
        self.assertTrue(f.app.Set(f.app,'bosses.custom.selection','XP reward')[0]);return f
    def limits(self,f,hits=1,stamina=100):
        for key,value in (('confirmedLimitsEnabled',True),('maxConfirmedHits',hits),('maxConfirmedStamina',stamina)):
            self.assertTrue(f.app.Set(f.app,'bosses.custom.'+key,value)[0])
    def confirm(self,f,now=2000001):
        f.observed_hp=400;f.step(2,stamina=11,server_now=now)
        self.assertEqual(f.runtime.Status(f.runtime).outcomes.bosses,'confirmed')
    def test_confirmed_cap_excludes_winner_and_selects_next_stage(self):
        f=self.fixture();self.limits(f);f.begin();self.confirm(f)
        self.assertEqual(f.tab.bossEncounters['35'].hits,1)
        f.step(3,server_now=2000005);f.drain()
        self.assertEqual(f.executor.calls[2].args[2],34)
        self.assertEqual(f.runtime.checkpoint.bossUsage.hits,2)
    def test_optional_defaults_preserve_existing_daily_attempt_caps(self):
        f=self.fixture();self.assertFalse(f.app.model['values']['bosses.custom.confirmedLimitsEnabled'])
        self.assertFalse(f.app.model['values']['bosses.custom.confirmationDelayEnabled'])
        f.begin();self.confirm(f);f.step(3,server_now=2000005);f.drain()
        self.assertEqual(f.executor.calls[2].args[2],35)
    def test_confirmation_delay_starts_at_confirmation_not_send(self):
        f=self.fixture()
        self.assertTrue(f.app.Set(f.app,'bosses.custom.confirmationDelayEnabled',True)[0])
        self.assertTrue(f.app.Set(f.app,'bosses.custom.confirmationDelay',10.5)[0])
        f.begin();self.confirm(f,2000010)
        f.h.at(11.49);f.step(3,server_now=2000020.49);f.drain();self.assertEqual(len(f.executor.calls),1)
        f.h.at(11.5);f.step(4,server_now=2000020.5);f.drain();self.assertEqual(len(f.executor.calls),2)
    def test_sent_rejection_and_unconfirmed_do_not_increment_confirmed_usage(self):
        for rejected in (True,False):
            f=self.fixture();self.limits(f)
            f.executor.reply=lua_table(f.h.lua,{'ok':False} if rejected else {'ok':True,'pending':True})
            f.begin();f.app.Set(f.app,"bosses.enabled",False);f.step(2,server_now=2000005)
            self.assertIsNone(f.tab.bossEncounters['35'])
            self.assertEqual(f.runtime.checkpoint.bossUsage.hits,1)
    def test_new_load_resets_confirmed_counts_without_resetting_daily_attempts(self):
        f=self.fixture();self.limits(f);f.begin();self.confirm(f);f.restart();self.limits(f);f.app.Set(f.app,"bosses.custom.selection","XP reward")
        self.assertIsNone(f.tab.bossEncounters['35'])
        f.choose();f.step(0,server_now=2000005);f.drain()
        self.assertEqual(f.executor.calls[2].args[2],35)
        self.assertEqual(f.runtime.checkpoint.bossUsage.hits,2)
    def test_partial_new_intent_is_rejected_but_original_intent_stays_compatible(self):
        f=self.fixture();f.choose();f.step();saved=f.runtime.checkpoint.Recovery(f.runtime.checkpoint,'bosses:1970024:35:0')[0]
        self.assertIsNotNone(saved)
        saved.proposal.intent.confirmedStaminaBefore=None
        self.assertIsNone(f.h.load('src/features/BossesEvidence.luau').capture(saved.proposal,saved.before)[0])

    def test_each_mode_falls_back_from_capped_winner_without_native_done_mutation(self):
        for mode in selection_fixture.MODES+('Current progression',):
            f=self.fixture();self.limits(f);f.app.Set(f.app,'bosses.custom.selection',mode);f.begin()
            stage=f.executor.calls[1].args[2];hp=f.source.get(stage).hp
            f.observed_hps={str(stage):hp//2};f.step(2,stamina=11,server_now=2000001)
            self.assertEqual(f.runtime.Status(f.runtime).outcomes.bosses,'confirmed')
            raw=f.step(3,server_now=2000005);f.drain()
            self.assertEqual(len(f.executor.calls),2,mode)
            self.assertNotEqual(f.executor.calls[2].args[2],stage,mode)
            self.assertIsNone(raw.native.bossStage.done[str(stage)])
    def test_all_locally_capped_stages_report_confirmed_cap_reason(self):
        f=self.fixture();self.limits(f)
        for key,value in (('limitsEnabled',True),('minLevel',5),('maxLevel',5)):
            f.app.Set(f.app,'bosses.custom.'+key,value)
        f.begin();self.assertEqual(f.executor.calls[1].args[2],17)
        f.observed_hps={'17':850};f.step(2,stamina=11,server_now=2000001)
        f.step(3,server_now=2000005);f.drain()
        self.assertEqual(len(f.executor.calls),1)
        self.assertIn('confirmed encounter caps',f.runtime.Status(f.runtime).reasons.bosses)
    def test_fractional_hit_limit_and_prospective_stamina_limit_remain_distinct(self):
        for hits,stamina,next_stage in ((1.5,100,35),(100,1.5,34)):
            f=self.fixture();self.limits(f,hits,stamina);f.begin();self.confirm(f)
            f.step(3,server_now=2000005);f.drain()
            self.assertEqual(f.executor.calls[2].args[2],next_stage)
            if next_stage==35:
                f.observed_hp=200;f.step(4,stamina=11,server_now=2000006)
                self.assertEqual(f.tab.bossEncounters['35'].hits,2)
                f.step(5,server_now=2000010);f.drain();self.assertEqual(f.executor.calls[3].args[2],34)
    def test_stage_counters_reset_eligibility_on_best_or_day_change(self):
        for day_change in (False,True):
            f=self.fixture();self.limits(f);f.begin();self.confirm(f)
            if not day_change:f.observed_best=201
            f.step(3,server_now=2086400 if day_change else 2000005);f.drain()
            self.assertEqual(f.executor.calls[2].args[2],35)
            self.assertEqual(f.tab.bossEncounters['35'].best,200)
    def test_saved_confirmation_counts_original_scope_once_in_observing_load(self):
        f=self.fixture();self.limits(f);f.begin();f.restart()
        self.assertIsNone(f.tab.bossEncounters['35'])
        f.observed_hp=400;f.observed_best=1000;f.step(0,health=100,stamina=11,server_now=2000005)
        self.assertEqual(f.runtime.Status(f.runtime).recoveries.bosses,'confirmed')
        record=f.tab.bossEncounters['35']
        self.assertEqual((record.day,record.best,record.hits,record.stamina),(1970024,200,1,1))
        f.step(1,health=100,stamina=11,server_now=2000006)
        self.assertEqual(record.hits,1);self.assertEqual(len(f.executor.calls),1)
        proof=f.tab.BossEncounterProof(f.tab,f.raw(2,server_now=2000007))
        self.assertIsNone(proof.counts['35'])
    def test_late_confirmed_effect_after_unknown_skip_counts_once(self):
        f=self.fixture();self.limits(f);f.begin();f.app.Set(f.app,'bosses.enabled',False)
        f.h.at(47);f.step(2,server_now=2000046)
        self.assertEqual(f.runtime.Status(f.runtime).outcomes.bosses,'skipped_unconfirmed')
        self.assertIsNone(f.tab.bossEncounters['35'])
        f.observed_hp=400;f.step(3,stamina=11,server_now=2000050)
        self.assertEqual(f.runtime.Status(f.runtime).recoveries.bosses,'confirmed')
        self.assertEqual(f.tab.bossEncounters['35'].hits,1)
        f.step(4,stamina=11,server_now=2000051)
        self.assertEqual(f.tab.bossEncounters['35'].hits,1)
        self.assertEqual(f.runtime.Status(f.runtime).outcomes.bosses,'skipped_unconfirmed')
    def test_checkpoint_cleanup_failure_retries_without_double_counting(self):
        f=self.fixture();self.limits(f);f.begin();f.app.Set(f.app,'bosses.enabled',False)
        original=f.storage.Write;f.storage.Write=f.h.lua.eval('function() return false end')
        f.observed_hp=400;f.step(2,stamina=11,server_now=2000001)
        self.assertEqual(f.tab.bossEncounters['35'].hits,1)
        self.assertIsNotNone(f.runtime.session.storageFault)
        f.storage.Write=original
        self.assertIsNotNone(f.runtime.checkpoint.Load(f.runtime.checkpoint,f.h.session["account"],f.h.session["place"],f.h.session["release"])[0])
        f.runtime.session.storageFault=None
        f.step(3,stamina=11,server_now=2000002)
        self.assertEqual(f.tab.bossEncounters['35'].hits,1)
        self.assertEqual(len(f.runtime.checkpoint.Records(f.runtime.checkpoint)),0)
        self.assertEqual(len(f.executor.calls),1)
    def test_changed_preferences_do_not_refuse_sent_terminal_settlement(self):
        f=self.fixture();self.limits(f,10,10);f.begin()
        f.app.Set(f.app,'bosses.custom.maxConfirmedHits',1)
        f.app.Set(f.app,'bosses.custom.maxConfirmedStamina',1)
        f.app.Set(f.app,'bosses.custom.confirmationDelayEnabled',True)
        f.app.Set(f.app,'bosses.custom.confirmationDelay',12)
        f.app.Set(f.app,'bosses.enabled',False)
        self.confirm(f,2000003)
        self.assertEqual(f.tab.bossEncounters['35'].hits,1)
        self.assertEqual(f.tab.bossReadyAt,14)
    def test_queued_changes_disable_and_unload_fence_and_refund_known_unsent(self):
        for key,value in (('confirmedLimitsEnabled',False),('maxConfirmedHits',2),('maxConfirmedStamina',2),('confirmationDelayEnabled',True),('confirmationDelay',10),('disable',False),('unload',False)):
            f=self.fixture();self.limits(f);f.choose();f.step()
            self.assertEqual(len(f.executor.queued),1)
            if key=='unload':f.app.Destroy(f.app)
            elif key=='disable':f.app.Set(f.app,'bosses.enabled',False)
            else:f.app.Set(f.app,'bosses.custom.'+key,value)
            f.drain();self.assertEqual(len(f.executor.calls),0,key)
            self.assertIsNone(f.tab.bossEncounters['35'])
            if key!='unload':self.assertEqual(f.runtime.checkpoint.bossUsage.hits,0)
    def test_profile_hydration_keeps_optional_choices_without_starting_work(self):
        f=self.fixture();self.limits(f,1.5,2.5)
        f.app.Set(f.app,'bosses.custom.confirmationDelayEnabled',True);f.app.Set(f.app,'bosses.custom.confirmationDelay',5.5)
        import json
        from test_redundant_store import plain
        exported=json.dumps(plain(f.app.model.Snapshot(f.app.model)))
        f.restart();self.assertFalse(f.app.model['values']['bosses.custom.confirmedLimitsEnabled'])
        self.assertTrue(f.app.ApplyProfile(f.app,lua_table(f.h.lua,json.loads(exported)))[0])
        self.assertTrue(f.app.model['values']['bosses.custom.confirmedLimitsEnabled'])
        self.assertTrue(f.app.model['values']['bosses.custom.confirmationDelayEnabled'])
        self.assertEqual(f.app.model['values']['bosses.custom.maxConfirmedHits'],1.5)
        self.assertEqual(f.app.model['values']['bosses.custom.confirmationDelay'],5.5)
        self.assertFalse(f.app.model['values']['bosses.enabled']);self.assertTrue(f.app.model.paused)
        self.assertEqual(len(f.executor.calls),0)
    def test_legacy_explicit_partial_caps_and_delay_import_inertly(self):
        import test_legacy_remaining_preferences as legacy
        f=legacy.LegacyRemainingPreferencesTests();f.setUp();self.addCleanup(f.tearDown)
        for settings,hits,stamina in (({'bossMaxHits':1.5},1.5,100),({'bossMaxStamina':1.5},100,1.5),({'bossMaxHits':100,'bossMaxStamina':100},100,100)):
            accepted,reason=f.preview(**settings);self.assertTrue(accepted,reason);f.assert_inert()
            values=f.app.staged['values'];self.assertTrue(values['bosses.custom.confirmedLimitsEnabled'])
            self.assertEqual(values['bosses.custom.maxConfirmedHits'],hits)
            self.assertEqual(values['bosses.custom.maxConfirmedStamina'],stamina)
        for delay in (5,5.5,120):
            accepted,reason=f.preview(bossHitDelay=delay);self.assertTrue(accepted,reason);f.assert_inert()
            self.assertTrue(f.app.staged['values']['bosses.custom.confirmationDelayEnabled'])
            self.assertEqual(f.app.staged['values']['bosses.custom.confirmationDelay'],delay)
        for key,value in (('bossMaxHits',0),('bossMaxStamina',100001),('bossMaxHits',True),('bossHitDelay',4.99),('bossHitDelay',120.1)):
            accepted,reason=f.preview(**{key:value});self.assertFalse(accepted)

    def test_native_clock_jump_cannot_shorten_local_confirmation_delay(self):
        f=self.fixture();f.app.Set(f.app,'bosses.custom.confirmationDelayEnabled',True)
        f.app.Set(f.app,'bosses.custom.confirmationDelay',10.5);f.begin();self.confirm(f)
        self.assertEqual(f.tab.bossReadyAt,12.5)
        f.step(3,server_now=2000100);f.drain();self.assertEqual(len(f.executor.calls),1)
        self.assertIn('confirmation delay',f.runtime.Status(f.runtime).reasons.bosses)
        f.h.at(11.5);f.step(4,server_now=2000101);f.drain();self.assertEqual(len(f.executor.calls),2)
    def test_saved_confirmation_starts_cooldown_on_new_local_observation_clock(self):
        f=self.fixture();f.begin();f.restart()
        f.app.Set(f.app,'bosses.custom.confirmationDelayEnabled',True)
        f.app.Set(f.app,'bosses.custom.confirmationDelay',10.5)
        f.observed_hp=400;f.step(0,stamina=11,server_now=2000005)
        self.assertEqual(f.runtime.Status(f.runtime).recoveries.bosses,'confirmed')
        self.assertEqual(f.tab.bossReadyAt,f.h.clock.Now(f.h.clock)+10.5)
        f.choose();f.step(1,server_now=2000100);f.drain();self.assertEqual(len(f.executor.calls),1)
        f.h.at(f.tab.bossReadyAt-1);f.step(2,server_now=2000101);f.drain();self.assertEqual(len(f.executor.calls),2)
    def test_unnumbered_legacy_pending_recovers_and_failed_cleanup_dedupes(self):
        f=self.fixture();f.begin()
        pending=f.h.load('src/storage/PendingAction.luau');evidence=f.h.load('src/features/BossesEvidence.luau')
        fields=('confirmedLimitsEnabled','maxConfirmedHits','maxConfirmedStamina','confirmationDelayEnabled','confirmationDelay','confirmedHitsBefore','confirmedStaminaBefore','confirmationReadyAt')
        for envelope in f.storage.data.values():
            if envelope.records is None:continue
            for record in envelope.records.values():
                data=pending.Decode(record.recovery,record);data.proposal.requestId=None
                for field in fields:data.proposal.intent[field]=None
                data.before.bossEncounterProof=None
                baseline=evidence.capture(data.proposal,data.before)[0];self.assertIsNotNone(baseline)
                record.requestId=None;record.recovery=pending.Capture(data.proposal,data.before,baseline,data.reply)[0]
            envelope.requestHighwater=None
        f.restart();original=f.storage.Write;f.storage.Write=f.h.lua.eval('function() return false end')
        f.observed_hp=400;f.step(0,stamina=11,server_now=2000005)
        self.assertEqual(f.tab.bossEncounters['35'].hits,1)
        f.storage.Write=original
        f.runtime.checkpoint.Load(f.runtime.checkpoint,f.h.session['account'],f.h.session['place'],f.h.session['release'])
        f.runtime.session.storageFault=None
        f.step(1,stamina=11,server_now=2000006)
        self.assertEqual(f.runtime.Status(f.runtime).recoveries.bosses,'confirmed')
        self.assertEqual(f.tab.bossEncounters['35'].hits,1)
        self.assertEqual(len(f.runtime.checkpoint.Records(f.runtime.checkpoint)),0)
        self.assertEqual(len(f.executor.calls),1)

if __name__=='__main__':unittest.main()
