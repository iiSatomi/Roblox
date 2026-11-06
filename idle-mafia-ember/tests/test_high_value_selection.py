"""High-only filtering consumes scoped owned tags and keeps normal safety limits."""
import unittest
import test_combat_target_selection as policy_fixture
import test_player_target_view as view_fixture
import test_high_value_memory as memory_fixture
from engine_harness import lua_table

class HighValueSelectionTests(unittest.TestCase):
    def setUp(self):
        self.p=policy_fixture.CombatTargetSelectionTests();self.p.setUp();self.h=self.p.h
    def test_explicit_sources_require_known_membership_and_keep_existing_caps(self):
        for source in ('High value only','High value only + lookup'):
            view=self.p.view();settings=self.p.settings(targetSource=source)
            self.assertIsNone(self.p.choose(view,settings)[0])
            view.highValueKnown=True;view.targets[1].highValue=False
            self.assertIsNone(self.p.choose(view,settings)[0])
            view.targets[1].highValue=True
            self.assertIsNotNone(self.p.choose(view,settings)[0])
            view.targets[1].friend=True;self.assertIsNone(self.p.choose(view,settings)[0])
            view.targets[1].friend=False;settings.maxAttackSpend=0
            self.assertIsNone(self.p.choose(view,settings)[0])
    def test_high_membership_does_not_authorize_scout_or_war(self):
        view=self.p.view();view.highValueKnown=True;row=view.targets[1];row.highValue=True;row.stats=None
        settings=self.p.settings(targetSource='High value only')
        self.assertIsNone(self.p.choose(view,settings)[0])
        settings.allowScout=True;settings.maxScoutSpend=5
        self.assertEqual(self.p.choose(view,settings)[0].kind,'scout')
        row.familyId=10;row.warFamilyId=10
        self.assertIsNone(self.p.choose(view,settings,mode='warCombat')[0])
    def test_aging_tag_does_not_automatically_relax_sample_or_payout_limits(self):
        view=self.p.view();view.highValueKnown=True;view.targets[1].highValue=True;view.targets[1].history=self.h.lua.table()
        settings=self.p.settings(targetSource='High value only');self.assertIsNone(self.p.choose(view,settings)[0])
        settings.minSamples=0;settings.minimumPayout=0;self.assertIsNotNone(self.p.choose(view,settings)[0])
    def test_tagged_history_composes_daily_and_cooldown_without_double_counting(self):
        f=view_fixture.PlayerTargetViewTests();f.setUp()
        high={'known':True,'count':1,'lastRequestId':1,'targets':{'2':{'userId':2,'history':[{'requestId':1,'at':990,'cash':1000000000,'won':True}]}}}
        f.raw.playerFightHistoryProof.recent[1].receipt.cashConfirmed=1000000000
        f.raw.playerFightHistoryProof.recent[1].serverNow=990
        f.raw.playerFightHistoryProof.recent[1].initial.targetDaily.serverNow=990
        f.raw.playerFightHistoryProof.highValue=lua_table(f.h.lua,high)
        view,why=f.read();self.assertIsNotNone(view,why)
        self.assertTrue(view.highValueKnown);self.assertTrue(view.targets[1].highValue)
        self.assertEqual((len(view.targets[1].history),view.targets[1].history[1].cash,view.targets[1].attacksToday),(1,1000000000,1))
        self.assertEqual(view.targets[1].cooldownUntil,1021)
    def test_bad_targeted_history_refuses_high_selection_without_losing_ordinary_view(self):
        f=view_fixture.PlayerTargetViewTests();f.setUp()
        for marker,at in ((0,900),(1,1001)):
            f.raw.playerFightHistoryProof.highValue=lua_table(f.h.lua,{'known':True,'count':1,'lastRequestId':marker,
                'targets':{'2':{'userId':2,'history':[{'requestId':1,'at':at,'cash':1000000000,'won':True}]}}})
            view,why=f.read();self.assertIsNotNone(view,why);self.assertFalse(view.highValueKnown)
            self.assertIsNone(view.targets[1].highValue)
    def test_targeted_proof_only_requested_rows_is_detached_and_default_stays_small(self):
        m=memory_fixture.HighValueMemoryTests();m.setUp();m.record(1,1000000000)
        self.assertIsNone(m.owner.Proof(m.owner,m.f.after).highValue)
        m.f.after.hitListProof=lua_table(m.h.lua,{'rows':[{'userId':42}]})
        proof=m.owner.Proof(m.owner,m.f.after,True)
        self.assertTrue(proof.highValue.known);self.assertEqual(proof.highValue.targets['42'].history[1].cash,1000000000)
        proof.highValue.targets['42'].history[1].cash=0
        self.assertEqual(m.owner.Proof(m.owner,m.f.after,True).highValue.targets['42'].history[1].cash,1000000000)
        m.f.after.hitListProof.rows[1].userId=43
        self.assertEqual(sum(1 for _ in m.owner.Proof(m.owner,m.f.after,True).highValue.targets.keys()),0)
    def test_full_memory_projection_fits_pending_recovery_without_mutating_live_proof(self):
        m=memory_fixture.HighValueMemoryTests();m.setUp();m.test_full_target_history_envelope_fits_actual_redundant_store()
        raw=m.f.before;raw.native.serverNow=m.f.now+4097
        raw.hitListProof.rows=lua_table(m.h.lua,[{'userId':i,'name':'Target_'+str(i),'level':128,'stamina':1,'shielded':False} for i in range(101,229)])
        raw.playerFightHistoryProof=m.owner.Proof(m.owner,raw,True)
        m.f.p.intent.highValueOnly=True;m.f.p.intent.target=228
        pending=m.h.load('src/storage/PendingAction.luau')
        encoded,why=pending.Capture(m.f.p,raw,m.f.baseline)
        self.assertIsNotNone(encoded,why)
        saved=pending.Decode(encoded).before.playerFightHistoryProof.highValue
        self.assertEqual(sum(1 for _ in saved.targets.keys()),1)
        self.assertEqual(saved.targets['228'].userId,228);self.assertIsNone(saved.targets['228'].history)
        self.assertEqual(len(raw.playerFightHistoryProof.highValue.targets['228'].history),32)
        self.assertEqual(sum(1 for _ in raw.playerFightHistoryProof.highValue.targets.keys()),128)
        repeated=pending.WithReply(encoded,m.f.p,lua_table(m.h.lua,{'ok':False}))[0]
        self.assertIsNotNone(repeated);self.assertEqual(pending.Decode(repeated).before.playerFightHistoryProof.highValue.targets['228'].userId,228)
        m.f.p.feature='jobs';m.f.p.intent.highValueOnly=None
        ordinary=pending.Capture(m.f.p,raw,m.f.baseline)[0]
        self.assertIsNotNone(ordinary);self.assertIsNone(pending.Decode(ordinary).before.playerFightHistoryProof.highValue)
    def test_combat_ui_displays_known_and_unknown_memory_without_extra_custom_controls(self):
        import test_ui_prototype as ui_fixture
        f=ui_fixture.PrototypeTests();f.setUp();app,ember=f.app()
        try:
            row=app.ui.features.combat;self.assertIsNotNone(row.memoryStatus)
            self.assertEqual(len(row.feature.custom),18)
            app.model.automationRuntime=f.table({'availableFeatures':{'combat':True},'combatMemory':{'known':True,'count':2}})
            self.assertTrue(app.ui.Render(app.ui,app.model)[0]);self.assertIn('2 retained',row.memoryStatus.Get(row.memoryStatus))
            app.model.automationRuntime.combatMemory=f.table({'known':False,'reason':'Older history is truncated'})
            self.assertTrue(app.ui.Render(app.ui,app.model)[0]);self.assertIn('Unknown',row.memoryStatus.Get(row.memoryStatus))
            self.assertIn('truncated',row.memoryStatus.Get(row.memoryStatus))
        finally:app.Destroy(app)
    def test_legacy_parallel_preference_remains_inert(self):
        import test_legacy_profile_preview as legacy_fixture
        f=legacy_fixture.LegacyProfilePreviewTests();f.setUp()
        try:
            for key,value,word in [('combatHighEnabled',True,'parallel')]:
                accepted,why=f.preview({'version':17,key:value});self.assertTrue(accepted,why)
                self.assertTrue(f.app.staged['values']['combat.memory.preferHighValue'])
                self.assertEqual(f.app.model['values']['combat.custom.targetSource'],'Saved and new')
                self.assertFalse(f.app.model['values']['combat.enabled'])
        finally:f.tearDown()
