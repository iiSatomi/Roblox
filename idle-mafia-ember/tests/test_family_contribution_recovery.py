"""Existing actual Family App/read fixture: saved outcomes and shared custody."""
import unittest,hashlib
import test_family_contribution_read_pipeline as fixture
from engine_harness import lua_table

class FamilyContributionRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.FamilyContributionReadPipelineTests();self.f.setUp();self.h=self.f.h
        self.h.lua.globals().familyRecoveryHash=lambda value:hashlib.sha256(value.encode()).hexdigest()
        self.f.fixture.storage.hash=self.h.lua.eval('function(value) return familyRecoveryHash(value) end')
        self.f.fixture.storage.Write=self.h.lua.eval('function(self,key,value) self.data[key]=value return true end')
        self.h.lua.globals().familyExternalHold=None
        self.f.additional_reservation_sources=[self.h.lua.execute("return {id='otherFunding',read=function() return familyExternalHold end}")]
    def tearDown(self):self.f.tearDown()
    def begin(self,feature='familyCash',kind='cash',amount=100,drain=True,reserve=0,prepare=None):
        self.feature,self.kind,self.amount=feature,kind,amount;self.f.start(feature,kind,amount)
        self.f.app.Set(self.f.app,feature+'.custom.reserve',reserve)
        if prepare:prepare()
        self.f.step();self.f.executor.queued[1]();self.h.at(self.h.lua.globals().testNow+.25)
        self.queued_raw=self.f.reader.Capture(self.f.reader)[0];self.f.app.Step(self.f.app,self.queued_raw)
        self.assertEqual(len(self.f.executor.queued),2,str(dict(self.f.runtime.Status(self.f.runtime).reasons.items())))
        if drain:self.f.executor.queued[2]()
    def observe(self,resource=None,amount=0,now=None):
        self.h.at(self.h.lua.globals().testNow+.75)
        native=self.f.fixture.raw(2,resource,amount).native
        if now is not None:native.serverNow=now
        self.f.reader.ObserveSync(self.f.reader,native);self.f.step()
        return native
    def restart(self,resource=None,amount=0):
        self.h.session['session']='new-family-session';self.h.at(0)
        self.f.start(self.feature,self.kind,self.amount)
        self.f.app.Set(self.f.app,self.feature+'.enabled',False);self.f.app.Pause(self.f.app)
        native=self.f.fixture.raw(0,resource,amount).native;native.serverNow=1005
        self.f.reader.ObserveSync(self.f.reader,native);self.f.step()
    def test_three_resource_saved_exact_receipts_recover_without_replay(self):
        for feature,kind,amount in [('familyCash','cash',100),('familyStamina','stamina',5),('familyGold','gold_bar',1)]:
            with self.subTest(feature=feature):
                if self.f.app:self.f.app.Destroy(self.f.app)
                self.f.fixture.storage.data=self.h.lua.table()
                self.begin(feature,kind,amount);self.restart(kind,amount)
                self.assertEqual(self.f.runtime.Status(self.f.runtime).recoveries[feature],'confirmed')
                self.assertEqual(len(self.f.executor.calls),0)
    def test_named_account_saved_receipts_recover_without_replay(self):
        self.h.session['account']='PlayerName'
        self.test_three_resource_saved_exact_receipts_recover_without_replay()

    def test_large_family_receipt_and_unrelated_native_history_survive_actual_app_reload(self):
        original_raw=self.f.fixture.raw;original_family=self.f.fixture.family
        def raw_with_history(*args,**kwargs):
            raw=original_raw(*args,**kwargs)
            raw.native.tradeHistory=lua_table(self.h.lua,[{'note':str(i)+'x'*3990} for i in range(35)])
            return raw
        def family_with_history(*args,**kwargs):
            family=original_family(*args,**kwargs)
            family.update(level=137,capSlots=10,memberCap=60)
            family['members'].extend({'userId':actor}for actor in range(44,100))
            family['log']=[{'note':str(i)+'y'*3990}for i in range(35)]
            return family
        self.f.fixture.raw=raw_with_history;self.f.fixture.family=family_with_history
        for feature,kind,amount in [('familyCash','cash',100),('familyGold','gold_bar',1),('familyStamina','stamina',5)]:
            with self.subTest(feature=feature):
                if self.f.app:self.f.app.Destroy(self.f.app)
                self.f.fixture.storage.data=self.h.lua.table()
                self.begin(feature,kind,amount)
                self.assertFalse(self.f.runtime.session.Status(self.f.runtime.session).storageFault)
                record=self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)[1]
                saved=self.f.runtime.checkpoint.Recovery(self.f.runtime.checkpoint,record.actionKey)[0]
                self.assertTrue(saved.reply.ok)
                self.assertIsNone(saved.before.native.tradeHistory)
                self.restart(kind,amount)
                self.assertEqual(self.f.runtime.Status(self.f.runtime).recoveries[feature],'confirmed')
                self.assertEqual(len(self.f.executor.calls),0)

    def test_pending_negative_never_rejects_unchanged_resources(self):
        self.begin(drain=False)
        self.h.lua.globals().familyReceipt=lua_table(self.h.lua,{'ok':False,'pending':True})
        self.f.executor.queued[2]();self.observe()
        self.assertIsNone(self.f.runtime.Status(self.f.runtime).outcomes.familyCash)
    def test_busy_exact_receipts_keep_three_saved_attempts_without_replay(self):
        for feature,kind,amount in [('familyCash','cash',100),('familyStamina','stamina',5),('familyGold','gold_bar',1)]:
            with self.subTest(feature=feature):
                if self.f.app:self.f.app.Destroy(self.f.app)
                self.f.fixture.storage.data=self.h.lua.table()
                self.begin(feature,kind,amount,drain=False)
                self.h.lua.globals().familyReceipt.code='busy'
                self.f.executor.queued[2]();self.restart(kind,amount)
                self.assertIsNone(self.f.runtime.Status(self.f.runtime).recoveries[feature])
                self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)),1)
                self.assertEqual(len(self.f.executor.calls),0)
                raw=self.f.reader.Capture(self.f.reader)[0]
                usage=self.f.runtime.checkpoint.FamilyContributionUsage(self.f.runtime.checkpoint,raw)[0].usage[feature]
                self.assertEqual((usage.attempted,usage.spent),(1,amount))
    def test_busy_negative_unchanged_balance_keeps_live_attempt(self):
        self.begin(drain=False)
        self.h.lua.globals().familyReceipt=lua_table(self.h.lua,{'ok':False,'code':'busy'})
        self.f.executor.queued[2]();self.observe()
        self.assertIsNone(self.f.runtime.Status(self.f.runtime).outcomes.familyCash)
        self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)),1)
    def test_same_revision_negative_does_not_resolve_sent_action(self):
        self.begin(drain=False);self.h.lua.globals().familyReceipt=lua_table(self.h.lua,{'ok':False})
        self.f.executor.queued[2]();self.f.step()
        self.assertIsNone(self.f.runtime.Status(self.f.runtime).outcomes.familyCash)
    def test_negative_with_applied_debit_stays_uncertain_on_reload(self):
        self.begin(drain=False);self.h.lua.globals().familyReceipt=lua_table(self.h.lua,{'ok':False})
        self.f.executor.queued[2]();self.restart('cash',100)
        self.assertIsNone(self.f.runtime.Status(self.f.runtime).recoveries.familyCash)
        self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)),1)
    def test_membership_changed_after_queue_blocks_emission(self):
        self.begin(drain=False)
        self.queued_raw.native.family.id='other-family'
        self.f.executor.queued[2]();self.assertEqual(len(self.f.executor.calls),1)
    def test_external_cash_hold_preserves_configured_family_reserve(self):
        self.begin(drain=False,reserve=100)
        self.h.lua.globals().familyExternalHold=lua_table(self.h.lua,{
            'account':self.h.session['account'],'place':self.h.session['place'],'release':self.h.session['release'],
            'feature':'marketFlip','actionKey':'funded-buy','claims':{'allCrew':False,'allItems':False,
                'members':{},'items':{},'funds':{'cash':850}}})
        self.f.executor.queued[2]()
        self.assertEqual(len(self.f.executor.calls),1)
    def test_bound_gold_appearing_after_queue_blocks_gold_donation(self):
        self.begin('familyGold','gold_bar',1,drain=False)
        self.queued_raw.native.inventoryBound.gold_bar=1
        self.f.executor.queued[2]();self.assertEqual(len(self.f.executor.calls),1)
    def test_backward_clock_cannot_confirm_personal_receipt(self):
        self.begin();self.observe('cash',100,now=1000)
        self.assertIsNone(self.f.runtime.Status(self.f.runtime).outcomes.familyCash)

    def test_saved_exact_negative_releases_record_but_keeps_invoked_exposure(self):
        self.begin(drain=False);self.h.lua.globals().familyReceipt=lua_table(self.h.lua,{'ok':False})
        self.f.executor.queued[2]();self.restart()
        self.assertEqual(self.f.runtime.Status(self.f.runtime).recoveries.familyCash,'rejected')
        self.assertEqual(self.f.runtime.checkpoint.Allowance(self.f.runtime.checkpoint,'familyCash')[0].spent,100)
        self.assertEqual(len(self.f.executor.calls),0)
    def test_unload_callback_recovers_only_definitely_unsent_usage(self):
        self.begin(drain=False);self.f.app.Destroy(self.f.app);self.f.executor.queued[2]();self.restart()
        self.assertEqual(self.f.runtime.Status(self.f.runtime).recoveries.familyCash,'known_unsent')
        self.assertEqual(self.f.runtime.checkpoint.Allowance(self.f.runtime.checkpoint,'familyCash')[0].spent,0)
        self.assertEqual(len(self.f.executor.calls),0)
    def test_cash_donation_does_not_depend_on_integer_stamina(self):
        def prepare():
            native=self.f.fixture.raw().native;native.pools.stamina=50.25
            self.f.reader.ObserveSync(self.f.reader,native)
        self.begin(prepare=prepare);self.observe('cash',100)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).outcomes.familyCash,'confirmed')
    def test_stamina_perk_rollover_requires_exact_level_and_progress(self):
        def prepare():
            self.h.lua.globals().familyInfoReply.family.perkProgress.enforcers=25
            receipt=self.h.lua.globals().familyReceipt.family
            receipt.perkProgress.enforcers=0;receipt.perks.enforcers=1
        self.begin('familyStamina','stamina',5,prepare=prepare);self.observe('stamina',5)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).outcomes.familyStamina,'confirmed')
    def test_stamina_one_batch_retains_exact_native_arity(self):
        self.begin('familyStamina','stamina',1);self.observe('stamina',1)
        call=self.f.executor.calls[2]
        self.assertEqual(call.args.n,4);self.assertEqual([call.args[i] for i in range(1,5)],['contribute','enforcers',1,None])
        self.assertEqual(self.f.runtime.Status(self.f.runtime).outcomes.familyStamina,'confirmed')
    def test_over_debit_or_wrong_personal_receipt_never_confirms(self):
        self.begin();self.observe('cash',101)
        self.assertIsNone(self.f.runtime.Status(self.f.runtime).outcomes.familyCash)
    def test_mixed_gold_never_spends_or_resolves_as_loose_only(self):
        def prepare():
            native=self.f.fixture.raw().native;native.inventoryBound.gold_bar=1
            self.f.reader.ObserveSync(self.f.reader,native)
        self.feature,self.kind,self.amount='familyGold','gold_bar',1
        self.f.start(self.feature,self.kind,self.amount);prepare()
        self.f.step();self.f.executor.queued[1]();self.h.at(.25);self.f.step()
        self.assertEqual(len(self.f.executor.calls),1)
        self.assertIn('Mixed',self.f.runtime.Status(self.f.runtime).reasons.familyGold)
    def test_source_change_on_reload_does_not_release_saved_debit(self):
        self.begin();self.h.session['session']='changed-family-source';self.h.at(0)
        self.f.start(self.feature,self.kind,self.amount);self.f.app.Pause(self.f.app)
        self.f.tab.state.key='b'*64
        native=self.f.fixture.raw(0,'cash',100).native;native.serverNow=1005
        self.f.reader.ObserveSync(self.f.reader,native);self.f.step()
        self.assertIsNone(self.f.runtime.Status(self.f.runtime).recoveries.familyCash)
    def test_rejected_retry_has_distinct_attempt_identity_and_stops_at_cap(self):
        self.begin(drain=False)
        self.f.app.Set(self.f.app,'familyCash.custom.maxAttempts',2)
        self.f.app.Set(self.f.app,'familyCash.custom.runBudget',200)
        # Changed queued settings refuse the first unsent stage; the next offer uses the reviewed limits.
        self.f.executor.queued[2]();self.h.at(2);self.f.step()
        self.h.lua.globals().familyReceipt=lua_table(self.h.lua,{'ok':False})
        self.f.executor.queued[3]();self.observe()
        self.h.lua.globals().familyInfoReply=lua_table(self.h.lua,{'ok':True,'family':self.f.fixture.family()})
        self.h.at(5);self.f.reader.ObserveSync(self.f.reader,self.f.fixture.raw(3).native)
        self.f.step();self.f.executor.queued[len(self.f.executor.queued)]()
        self.h.at(5.25);self.f.step();self.f.executor.queued[len(self.f.executor.queued)]()
        mutations=[row for row in self.f.executor.calls.values() if row.args[1]=='donate']
        self.assertEqual(len(mutations),2,str(dict(self.f.runtime.Status(self.f.runtime).reasons.items())))
        usage=self.f.runtime.checkpoint.Allowance(self.f.runtime.checkpoint,'familyCash')[0]
        self.assertEqual((usage.attempted,usage.spent),(2,200))
        self.observe(now=1004)
        self.h.lua.globals().familyInfoReply=lua_table(self.h.lua,{'ok':True,'family':self.f.fixture.family()})
        self.h.at(10);self.f.reader.ObserveSync(self.f.reader,self.f.fixture.raw(4).native)
        self.f.step();self.f.executor.queued[len(self.f.executor.queued)]();self.h.at(10.25);self.f.step()
        self.assertEqual(len([row for row in self.f.executor.calls.values() if row.args[1]=='donate']),2)
        self.assertIn('cap',self.f.runtime.Status(self.f.runtime).reasons.familyCash)
    def test_cash_gold_and_stamina_usage_remain_independent_on_reload(self):
        self.begin();self.observe('cash',100)
        self.h.session['session']='gold-after-cash';self.f.start('familyGold','gold_bar',1)
        raw=self.f.reader.Capture(self.f.reader)[0]
        proof=self.f.runtime.checkpoint.FamilyContributionUsage(self.f.runtime.checkpoint,raw)[0]
        self.assertEqual(proof.usage.familyCash.spent,100)
        self.assertEqual(proof.usage.familyGold.spent,0);self.assertEqual(proof.usage.familyStamina.spent,0)
    def test_external_stamina_hold_preserves_selected_reserve(self):
        self.begin('familyStamina','stamina',5,drain=False,reserve=5)
        self.h.lua.globals().familyExternalHold=lua_table(self.h.lua,{
            'account':self.h.session['account'],'place':self.h.session['place'],'release':self.h.session['release'],
            'feature':'crewHeal','actionKey':'heal-funded','claims':{'allCrew':False,'allItems':False,
                'members':{},'items':{},'funds':{'stamina':41}}})
        self.f.executor.queued[2]();self.assertEqual(len(self.f.executor.calls),1)

    def test_stamina_fractional_pool_keeps_exact_quoted_debit(self):
        def prepare():
            native=self.f.fixture.raw().native;native.pools.stamina=50.25
            self.f.reader.ObserveSync(self.f.reader,native)
        self.begin('familyStamina','stamina',5,prepare=prepare)
        self.h.at(1);native=self.f.fixture.raw(2,'stamina',5).native;native.pools.stamina=45.25
        self.f.reader.ObserveSync(self.f.reader,native);self.f.step()
        self.assertEqual(self.f.runtime.Status(self.f.runtime).outcomes.familyStamina,'confirmed')
    def test_family_gold_zero_default_budget_cannot_spend(self):
        self.f.start('familyGold','gold_bar',1)
        self.f.app.Set(self.f.app,'familyGold.custom.runBudget',0)
        self.f.step();self.f.executor.queued[1]();self.h.at(.25);self.f.step()
        self.assertEqual(len(self.f.executor.calls),1)
        self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)),0)
    def test_wrong_perk_rollover_receipt_stays_unconfirmed(self):
        self.begin('familyStamina','stamina',5,drain=False)
        self.h.lua.globals().familyReceipt.family.perks.enforcers=1
        self.f.executor.queued[2]();self.observe('stamina',5)
        self.assertIsNone(self.f.runtime.Status(self.f.runtime).outcomes.familyStamina)
    def test_saved_unknown_reply_never_releases_even_exact_debit(self):
        self.begin(drain=False);self.h.lua.globals().familyReceipt=lua_table(self.h.lua,{'ok':True,'pending':True})
        self.f.executor.queued[2]();self.restart('cash',100)
        self.assertIsNone(self.f.runtime.Status(self.f.runtime).recoveries.familyCash)
    def test_sent_gold_and_stamina_timeout_keep_independent_allowances(self):
        for feature,kind,amount in [('familyStamina','stamina',5),('familyGold','gold_bar',1)]:
            with self.subTest(feature=feature):
                if self.f.app:self.f.app.Destroy(self.f.app)
                self.f.fixture.storage.data=self.h.lua.table();self.begin(feature,kind,amount)
                self.h.at(self.f.runtime.Status(self.f.runtime).active.sentAt+45);self.f.reader.ObserveSync(self.f.reader,self.f.fixture.raw(2).native);self.f.step()
                self.assertEqual(self.f.runtime.Status(self.f.runtime).outcomes[feature],'skipped_unconfirmed')
                self.assertEqual(self.f.runtime.checkpoint.Allowance(self.f.runtime.checkpoint,feature)[0].spent,amount)
