"""Optional high-first scheduling falls back without weakening the chosen policy."""
import unittest
import test_combat_target_selection as policy_fixture
import test_high_value_app as app_fixture
import test_legacy_profile_preview as legacy_fixture
from engine_harness import lua_table

class HighValuePreferenceTests(unittest.TestCase):
    def setUp(self):
        self.p=policy_fixture.CombatTargetSelectionTests();self.p.setUp();self.h=self.p.h
        self.view=self.p.view();self.view.highValueKnown=True;self.view.targets[1].highValue=True
        other=self.p.view().targets[1];other.userId=3;other.history[1].cash=1000000;self.view.targets[2]=other
        self.settings=self.p.settings(preferHighValue=True)
    def choose(self):return self.p.choose(self.view,self.settings)[0]
    def test_preference_is_lexicographic_after_safety_and_falls_back(self):
        self.assertEqual(self.choose().userId,2)
        self.view.targets[1].shieldUntil=2000;self.assertEqual(self.choose().userId,3)
        self.view.targets[1].shieldUntil=0;self.view.highValueKnown=False;self.assertEqual(self.choose().userId,3)
        self.view.highValueKnown=True;self.settings.preferHighValue=False;self.assertEqual(self.choose().userId,3)
    def test_preference_preserves_samples_saved_only_and_scout_consent(self):
        self.view.targets[1].history=self.h.lua.table();self.settings.minSamples=0;self.settings.minimumPayout=0
        self.settings.targetSource='Saved only';self.assertEqual(self.choose().userId,3)
        self.settings.targetSource='Saved and new';self.assertEqual(self.choose().userId,2)
        self.view.targets[1].stats=None;self.assertEqual(self.choose().userId,3)
        self.settings.allowScout=True;self.settings.maxScoutSpend=5;self.assertEqual(self.choose().kind,'scout')
        self.settings.maxAttackSpend=0;self.assertIsNone(self.choose())
    def test_invalid_preference_is_not_coerced_into_permission(self):
        for value in ('true',1):self.settings.preferHighValue=value;self.assertIsNone(self.choose())
    def test_legacy_parallel_setting_imports_only_inert_preference(self):
        f=legacy_fixture.LegacyProfilePreviewTests();f.setUp()
        try:
            ok,why=f.preview({'version':17,'combatHighEnabled':True});self.assertTrue(ok,why)
            self.assertTrue(f.app.staged['values']['combat.memory.preferHighValue'])
            self.assertFalse(f.app.model['values']['combat.enabled']);self.assertFalse(f.app.model['values']['combat.custom.allowScout'])
            self.assertEqual(f.app.staged['values']['combat.custom.targetSource'],'Saved and new')
        finally:f.tearDown()

class HighValuePreferenceAppTests(unittest.TestCase):
    def setUp(self):
        self.b=app_fixture.HighValueAppTests();self.b.setUp();self.f=self.b.f;self.h=self.b.h
        self.b.promote();self.app=self.b.app
        self.b.append(2,900000000,42,age=86400);self.b.append(3,999999999,43,age=86400)
        self.b.b.seed(False,extra=True)
    def test_actual_app_prefers_tagged_target_but_default_still_uses_payout_priority(self):
        self.assertTrue(self.app.Set(self.app,'combat.memory.preferHighValue',True)[0]);self.f.begin()
        record=self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)[1]
        data=self.f.runtime.checkpoint.Recovery(self.f.runtime.checkpoint,record.actionKey)[0]
        self.assertEqual(data.proposal.intent.target,42);self.assertTrue(data.proposal.intent.highValueOnly)
    def test_queued_preferred_tag_demotion_fences_native_adapter(self):
        self.app.Set(self.app,'combat.memory.preferHighValue',True);self.f.begin()
        for n in (4,5,6):self.b.append(n,0,age=86400)
        self.f.executor.queued[1]();self.assertEqual(self.f.executor.calls,0)
    def tearDown(self):
        if hasattr(self,'b'):self.b.tearDown()

class HighValuePreferenceLookupAppTests(unittest.TestCase):
    def setUp(self):
        import test_high_value_lookup_app as lookup_fixture
        self.b=lookup_fixture.HighValueLookupAppTests();self.b.setUp();self.f=self.b.f;self.h=self.b.h;self.app=self.b.app
        self.b.append(2,1000000000)
        for n in range(3,36):self.b.append(n,1,100+n)
        self.app.Set(self.app,'combat.memory.preferHighValue',True)
    def enable(self,lookup=True):
        self.app.Set(self.app,'combat.custom.targetSource','Saved and new + lookup' if lookup else 'Saved and new')
        self.app.Set(self.app,'combat.enabled',True);self.app.Resume(self.app);self.f.step()
    def test_preferred_lookup_reaches_persistent_tag_outside_global_window_without_spending(self):
        self.enable();self.assertEqual(len(self.f.executor.queued),1);self.f.executor.queued[1]()
        self.assertEqual(self.f.executor.log[1].arg,'Target B')
        self.b.b.tick(2);self.f.executor.queued[2]();self.b.b.tick(3)
        self.assertEqual(self.f.runtime.allowanceSnapshot.hitListProof.rows[1].userId,42)
        self.assertEqual(len(self.f.executor.log),2);self.assertEqual(self.app.model['values']['combat.custom.maxAttackSpend'],0)
    def test_preference_alone_cannot_authorize_lookup_or_catalog_scan(self):
        self.f.ledger.HighValueTargets=self.h.lua.eval('function() error("Unexpected catalog scan") end')
        self.enable(False);self.assertEqual(len(self.f.executor.queued),0);self.assertEqual(len(self.f.executor.log),0)
    def test_catalog_scan_is_only_due_prepare_not_each_enabled_tick(self):
        self.h.lua.globals().scanLedger=self.f.ledger
        self.h.lua.execute('local old=scanLedger.HighValueTargets;scanLedger.HighValueTargets=function(self,...) self.scans=(self.scans or 0)+1;return old(self,...) end')
        self.enable();self.assertEqual(self.f.ledger.scans,1)
        for _ in range(5):self.f.step()
        self.assertEqual(self.f.ledger.scans,1)
    def test_queued_high_lookup_loses_its_extra_seed_permission_when_preference_is_disabled(self):
        self.enable();self.assertEqual(len(self.f.executor.queued),1)
        self.app.Set(self.app,'combat.memory.preferHighValue',False);self.f.step();self.f.executor.queued[1]()
        self.assertEqual(len(self.f.executor.log),0)
    def test_preference_change_while_lookup_reply_yields_cannot_commit_extra_seed(self):
        self.enable();self.f.executor.yieldReply=True;self.h.lua.globals().preferredLookupCallback=self.f.executor.queued[1]
        value=self.h.lua.execute('preferredLookupThread=coroutine.create(preferredLookupCallback);local ok,v=coroutine.resume(preferredLookupThread);assert(ok);return v')
        self.assertEqual(value,'lookup-return');self.app.Set(self.app,'combat.memory.preferHighValue',False);self.f.step()
        self.h.lua.execute('assert(coroutine.resume(preferredLookupThread))')
        self.assertEqual(len(self.f.tab.hitListQuery.Read(self.f.tab.hitListQuery,self.b.b.raw).rows),0)
    def test_mixed_lookup_alternates_high_and_ordinary_reads_under_shared_wait(self):
        self.f.executor.InvokeOwned=self.h.lua.eval("""function(self,token,remote,method,arg)
            self.calls=self.calls+1;self.log[#self.log+1]={remote=remote,arg=arg}
            if remote=='SearchTarget' then return {ok=true,search=arg,list={}} end
            if remote=='GetHitList' then savedEmptyList.warStatus.serverNow=savedSearchRaw.native.serverNow;return savedEmptyList end
            error('Only readonly lookup allowed')
        end""")
        self.enable();self.f.executor.queued[1]();self.assertEqual(self.f.executor.log[1].arg,'Target B')
        self.b.b.tick(2);self.b.b.tick(61);self.f.executor.queued[2]();self.b.b.tick(62)
        self.f.executor.queued[3]();searches=[r.arg for r in self.f.executor.log.values() if r.remote=='SearchTarget']
        self.assertEqual(len(searches),2);self.assertEqual(searches[0],'Target B');self.assertNotEqual(searches[1],'Target B')
        self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)),0)
    def tearDown(self):
        if hasattr(self,'b'):self.b.tearDown()
