"""Actual empty-slot hire App path with independent durable Cash/attempt limits."""
import unittest,hashlib
import test_crew_equip_runtime as equip_fixture
from engine_harness import lua_table
class CrewHireRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.e=equip_fixture.CrewEquipRuntimeTests();self.e.setUp();self.f=self.e.f;self.h=self.e.h
        self.f.app.Destroy(self.f.app);self.f.feature_id='crewHire'
        self.f.tab_dependencies['CrewHire']=self.h.load('src/tabs/crew/CrewHire.luau')
        self.f.tab_dependencies['NativeHireCatalog']=self.h.load('src/tabs/crew/NativeHireCatalog.luau')
        self.f.executor.reply=lua_table(self.h.lua,{'ok':True,'index':2,'member':{'name':'New','rarity':3,'atk':8,'def':9,'healId':'new-member'}})
        self.h.lua.globals().hireHash=lambda value:hashlib.sha256(value.encode()).hexdigest()
        self.f.storage.hash=self.h.lua.eval('function(v) return hireHash(v) end');self.f.start_current()
    def tearDown(self):self.f.tearDown()
    def raw(self,revision=1,hired=False,cash=30000):
        raw=self.f.f.raw(revision=revision,stage='empty',cash=cash)
        if hired:raw.native.crew[2]=lua_table(self.h.lua,{'name':'New','rarity':3,'atk':8,'def':9,'healId':'new-member'})
        return raw
    def step(self,revision=1,hired=False,cash=30000):
        raw=self.raw(revision,hired,cash);self.h.at(raw.capturedAt);self.f.app.Step(self.f.app,raw);return raw
    def choose(self):
        for key,value in {'enabled':True,'policy':'street','custom.maxCost':10000,'custom.cashReserve':1000,
            'custom.maxAttempts':1,'custom.maxSpend':10000}.items():self.f.app.Set(self.f.app,'crewHire.'+key,value)
        self.f.app.Resume(self.f.app)
    def begin(self):self.choose();self.step();self.f.drain()
    def test_zero_default_run_limits_prevent_hire(self):
        self.f.app.Set(self.f.app,'crewHire.enabled',True);self.f.app.Resume(self.f.app);self.step();self.f.drain()
        self.assertEqual(len(self.f.executor.calls),0)
    def test_actual_quoted_hire_charges_and_confirms_exact_new_member(self):
        self.begin();call=self.f.executor.calls[1]
        self.assertEqual(call.remote,'CrewAction');self.assertEqual(call.args.n,4)
        self.assertEqual([call.args[i] for i in range(1,5)],['hire','street',10000,None])
        self.step(2,True,20000)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).outcomes.crewHire,'confirmed')
        self.assertEqual(self.f.runtime.checkpoint.Allowance(self.f.runtime.checkpoint,'crewHire')[0].spent,10000)
    def test_restart_recovers_exact_saved_hire_without_replay(self):
        self.begin();self.f.restart();after=self.raw(0,True,20000);after.native.serverNow=1005;self.f.app.Step(self.f.app,after)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).recoveries.crewHire,'confirmed')
        self.assertEqual(len(self.f.executor.calls),1)
    def test_saved_exposure_cannot_be_reset_by_caller_proof_or_reload(self):
        self.begin();self.step(2,True,20000);self.f.restart();self.choose()
        after=self.raw(0,False,30000);after.native.serverNow=1005
        after.crewHireUsageProof=lua_table(self.h.lua,{**self.h.session,'revision':0,'capturedAt':0,'attempted':0,'spent':0})
        self.f.app.Step(self.f.app,after);self.f.drain()
        self.assertEqual(len(self.f.executor.calls),1)
        self.assertEqual(self.f.runtime.checkpoint.Allowance(self.f.runtime.checkpoint,'crewHire')[0].spent,10000)
    def test_explicit_paused_allowance_review_resets_only_local_usage(self):
        self.begin();self.step(2,True,20000);self.f.app.Pause(self.f.app)
        preview,why=self.f.app.PreviewAllowance(self.f.app,'crewHire');self.assertIsNotNone(preview,why)
        self.assertTrue(self.f.app.ConfirmAllowance(self.f.app,'crewHire')[0])
        self.assertEqual(self.f.runtime.checkpoint.Allowance(self.f.runtime.checkpoint,'crewHire')[0].spent,0)
        self.assertTrue(self.f.app.model.paused);self.assertEqual(len(self.f.executor.calls),1)
    def test_pending_negative_reply_does_not_release_funded_slot(self):
        self.f.executor.reply=lua_table(self.h.lua,{'ok':False,'pending':True})
        self.begin();self.step(2)
        self.assertIsNone(self.f.runtime.Status(self.f.runtime).outcomes.crewHire)

    def test_queued_disable_refunds_only_definitely_unsent_hire_exposure(self):
        self.choose();self.step();self.f.app.Set(self.f.app,'crewHire.enabled',False);self.f.drain()
        self.assertEqual(len(self.f.executor.calls),0)
        self.assertEqual(self.f.runtime.checkpoint.Allowance(self.f.runtime.checkpoint,'crewHire')[0].spent,0)
        self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)),0)
    def test_changed_spend_cap_blocks_queued_hire(self):
        self.choose();self.step();self.f.app.Set(self.f.app,'crewHire.custom.maxSpend',9999);self.f.drain()
        self.assertEqual(len(self.f.executor.calls),0)
        self.assertEqual(self.f.runtime.checkpoint.Allowance(self.f.runtime.checkpoint,'crewHire')[0].spent,0)
    def test_unload_callback_recovers_exact_unsent_budget_without_replay(self):
        self.choose();self.step();self.f.app.Destroy(self.f.app);self.f.drain();self.f.restart()
        after=self.raw(0);after.native.serverNow=1005;self.f.app.Step(self.f.app,after)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).recoveries.crewHire,'known_unsent')
        self.assertEqual(self.f.runtime.checkpoint.Allowance(self.f.runtime.checkpoint,'crewHire')[0].spent,0)
        self.assertEqual(len(self.f.executor.calls),0)
    def test_exact_rejection_keeps_attempt_exposure_without_success(self):
        self.f.executor.reply=lua_table(self.h.lua,{'ok':False});self.begin();self.step(2)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).outcomes.crewHire,'rejected')
        self.assertEqual(self.f.runtime.checkpoint.Allowance(self.f.runtime.checkpoint,'crewHire')[0].spent,10000)
        self.assertEqual(len(self.f.executor.calls),1)
    def test_unconfirmed_timeout_keeps_budget_and_prevents_reset(self):
        self.begin();self.step(46);self.f.drain()
        self.assertEqual(self.f.runtime.Status(self.f.runtime).outcomes.crewHire,'skipped_unconfirmed')
        self.assertEqual(self.f.runtime.checkpoint.Allowance(self.f.runtime.checkpoint,'crewHire')[0].spent,10000)
        self.f.app.Pause(self.f.app)
        self.assertIsNone(self.f.app.PreviewAllowance(self.f.app,'crewHire')[0])
        self.assertEqual(len(self.f.executor.calls),1)
    def test_cash_hold_appearing_after_queue_preserves_hire_reserve(self):
        self.choose();self.step()
        self.h.lua.globals().crewExternalHold=lua_table(self.h.lua,{
            'account':self.h.session['account'],'place':self.h.session['place'],'release':self.h.session['release'],
            'feature':'other','actionKey':'cash-hold','claims':{'allCrew':False,'allItems':False,
                'members':{},'items':{},'funds':{'cash':19500}}})
        self.f.drain();self.assertEqual(len(self.f.executor.calls),0)
        self.assertEqual(self.f.runtime.checkpoint.Allowance(self.f.runtime.checkpoint,'crewHire')[0].spent,0)
    def test_returned_member_identity_must_match_replication(self):
        self.begin();after=self.raw(2,True,20000);after.native.crew[2].healId='other-new-member'
        self.h.at(2);self.f.app.Step(self.f.app,after)
        self.assertIsNone(self.f.runtime.Status(self.f.runtime).outcomes.crewHire)
    def test_expired_allowance_ticket_does_not_reset_exposure(self):
        self.begin();self.step(2,True,20000);self.f.app.Pause(self.f.app)
        self.assertIsNotNone(self.f.app.PreviewAllowance(self.f.app,'crewHire')[0])
        self.step(35,True,20000)
        self.assertFalse(self.f.app.ConfirmAllowance(self.f.app,'crewHire')[0])
        self.assertEqual(self.f.runtime.checkpoint.Allowance(self.f.runtime.checkpoint,'crewHire')[0].spent,10000)
