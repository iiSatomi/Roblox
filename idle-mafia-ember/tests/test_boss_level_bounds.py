"""Inclusive city Boss level preferences through real App and saved evidence."""
import unittest
from engine_harness import lua_table
import test_bosses as unit
import test_bosses_runtime as runtime
import test_legacy_remaining_preferences as legacy

class BossLevelBoundsTests(unittest.TestCase):
    def fixture(self):
        f=runtime.BossesRuntimeTests();f.setUp();self.addCleanup(f.tearDown);return f
    def configure(self,f,minimum,maximum):
        self.assertTrue(f.app.Set(f.app,'bosses.custom.limitsEnabled',True)[0])
        self.assertTrue(f.app.Set(f.app,'bosses.custom.minLevel',minimum)[0])
        self.assertTrue(f.app.Set(f.app,'bosses.custom.maxLevel',maximum)[0])
    def test_default_visible_off_and_inclusive_selection(self):
        for minimum,maximum,stage in ((1,10000,2),(10,10,2),(5,5,1),(6,9,None),(11,20,None),(11,5,None)):
            f=self.fixture();self.assertFalse(f.app.model['values']['bosses.enabled'])
            self.assertFalse(f.app.model['values']['bosses.custom.limitsEnabled'])
            self.assertEqual(f.app.model['values']['bosses.custom.minLevel'],1)
            self.assertEqual(f.app.model['values']['bosses.custom.maxLevel'],10000)
            self.assertTrue(f.app.ui.features.bosses.custom.visible)
            self.configure(f,minimum,maximum);f.choose();f.step();f.drain()
            self.assertEqual(len(f.executor.calls),0 if stage is None else 1)
            if stage:self.assertEqual(f.executor.calls[1].args[2],stage)
    def test_default_unrestricted_preserves_native_domain_and_quotes(self):
        for level,calls in ((10001,1),(1000000,1),(1000001,0)):
            f=self.fixture()
            f.h.lua.globals().quotedBossLevel=level
            f.source.get=f.h.lua.eval('function(stage) return {stage=stage,level=quotedBossLevel,hp=stage*100,hitBackMax=stage*10} end')
            f.choose();raw=f.raw();raw.native.level=level
            f.app.Step(f.app,raw);f.drain();self.assertEqual(len(f.executor.calls),calls)
    def test_unrestricted_high_level_saved_effect_keeps_quote_guard(self):
        for changed in (False,True):
            f=self.fixture();f.h.lua.globals().quotedBossLevel=10001
            f.source.get=f.h.lua.eval('function(stage) return {stage=stage,level=quotedBossLevel,hp=stage*100,hitBackMax=stage*10} end')
            f.choose();raw=f.raw();raw.native.level=10002
            f.app.Step(f.app,raw);f.drain();self.assertEqual(len(f.executor.calls),1)
            f.restart();f.h.lua.globals().quotedBossLevel=10002 if changed else 10001
            after=f.raw(0,hp=150,stamina=11,server_now=2000005);after.native.level=10002
            f.app.Step(f.app,after)
            self.assertEqual(f.runtime.Status(f.runtime).recoveries.bosses,None if changed else 'confirmed')
            self.assertEqual(len(f.executor.calls),1)
    def test_bounds_only_filter_when_explicitly_enabled(self):
        for enabled,stage in ((False,2),(True,1)):
            f=self.fixture();self.configure(f,5,5)
            f.app.Set(f.app,'bosses.custom.limitsEnabled',enabled)
            f.choose();f.step();f.drain();self.assertEqual(f.executor.calls[1].args[2],stage)
        f=self.fixture();self.configure(f,11,5)
        f.app.Set(f.app,'bosses.custom.limitsEnabled',False);f.choose();f.step();f.drain()
        self.assertEqual(len(f.executor.calls),1)
        f=self.fixture();self.configure(f,1000000,1000000)
        f.source.get=f.h.lua.eval('function(stage) return {stage=stage,level=1000000,hp=stage*100,hitBackMax=stage*10} end')
        f.choose();raw=f.raw();raw.native.level=1000000
        f.app.Step(f.app,raw);f.drain();self.assertEqual(len(f.executor.calls),1)
    def test_legacy_explicit_defaults_and_omitted_edges_activate_complete_range_inertly(self):
        f=legacy.LegacyRemainingPreferencesTests();f.setUp();self.addCleanup(f.tearDown)
        for settings,minimum,maximum in (({'bossMinLevel':5},5,10000),({'bossMaxLevel':10},1,10),({'bossMinLevel':1,'bossMaxLevel':10000},1,10000),({'bossMinLevel':1},1,10000),({'bossMaxLevel':10000},1,10000)):
            accepted,reason=f.preview(**settings);self.assertTrue(accepted,reason);f.assert_inert()
            values=f.app.staged['values']
            self.assertTrue(values['bosses.custom.limitsEnabled'])
            self.assertEqual(values['bosses.custom.minLevel'],minimum)
            self.assertEqual(values['bosses.custom.maxLevel'],maximum)
        defaults=f.h.load('src/storage/LegacySettings.luau').defaults()
        def plain(value):
            return {key:plain(child) for key,child in value.items()} if hasattr(value,'items') else value
        settings=plain(defaults)
        accepted,reason=f.preview(**{key:value for key,value in settings.items() if key!='version'})
        self.assertTrue(accepted,reason);f.assert_inert()
        self.assertTrue(f.app.staged['values']['bosses.custom.limitsEnabled'])
        self.assertTrue(f.app.ApplyProfile(f.app,f.app.staged)[0])
        self.assertTrue(f.app.model['values']['bosses.custom.limitsEnabled'])
        self.assertFalse(f.app.model['values']['bosses.enabled'])
        accepted,reason=f.preview();self.assertTrue(accepted,reason)
        self.assertFalse(f.app.staged['values']['bosses.custom.limitsEnabled'])
    def test_legacy_inverted_bounds_refuse_import(self):
        f=legacy.LegacyRemainingPreferencesTests();f.setUp();self.addCleanup(f.tearDown)
        accepted,reason=f.preview(bossMinLevel=11,bossMaxLevel=5)
        self.assertFalse(accepted);self.assertIsNone(f.app.staged)
        self.assertIn('bossMinLevel',reason);self.assertIn('bossMaxLevel',reason)
    def test_upper_bound_10000_is_inclusive_and_player_level_still_required(self):
        for player_level,calls in ((10000,1),(9999,0)):
            f=self.fixture();self.configure(f,10000,10000)
            f.source.get=f.h.lua.eval('function(stage) return {stage=stage,level=10000,hp=stage*100,hitBackMax=stage*10} end')
            f.choose();raw=f.raw();raw.native.level=player_level
            f.app.Step(f.app,raw);f.drain();self.assertEqual(len(f.executor.calls),calls)
    def test_truncated_quote_window_does_not_claim_full_legacy_selection(self):
        f=self.fixture();self.configure(f,5,5)
        f.source.get=f.h.lua.eval('function(stage) return {stage=stage,level=stage==1 and 5 or 10,hp=100,hitBackMax=1} end')
        f.choose();raw=f.raw();raw.native.bossStage.best=200
        f.app.Step(f.app,raw);f.drain();self.assertEqual(len(f.executor.calls),0)
    def test_partial_level_intent_is_not_treated_as_legacy(self):
        f=unit.BossesTests();f.setUp();raw=f.raw();p=f.propose(raw)[0]
        for field in ('limitsEnabled','minLevel','maxLevel','selectedLevel'):
            original=p.intent[field];p.intent[field]=None
            self.assertIsNone(f.evidence.capture(p,raw)[0]);p.intent[field]=original
    def test_controls_refuse_invalid_values_without_coercion(self):
        f=self.fixture()
        for field in ('minLevel','maxLevel'):
            for value in (0,1000001,1.5,True,'5',float('nan'),float('inf')):
                self.assertFalse(f.app.Set(f.app,'bosses.custom.'+field,value)[0])
    def test_queued_preferences_disable_unload_fence(self):
        for change in ('limitsEnabled','minLevel','maxLevel','disable','unload'):
            f=self.fixture();self.configure(f,10,10);f.choose();f.step()
            self.assertEqual(len(f.executor.queued),1)
            if change=='unload':f.app.Destroy(f.app)
            elif change=='limitsEnabled':f.app.Set(f.app,'bosses.custom.limitsEnabled',False)
            elif change=='disable':f.app.Set(f.app,'bosses.enabled',False)
            else:f.app.Set(f.app,'bosses.custom.'+change,1 if change=='minLevel' else 20)
            f.drain();self.assertEqual(len(f.executor.calls),0)
            if change!='unload':self.assertEqual(f.runtime.checkpoint.bossUsage.hits,0)
    def test_selected_level_quote_change_inside_range_refuses_emit(self):
        f=self.fixture();f.choose();f.step()
        f.source.get=f.h.lua.eval('function(stage) return {stage=stage,level=stage*5+1,hp=stage*100,hitBackMax=stage*10} end')
        f.drain();self.assertEqual(len(f.executor.calls),0)
        self.assertEqual(f.runtime.checkpoint.bossUsage.hits,0)
    def test_sent_and_saved_confirmation_uses_original_level_preferences(self):
        for restart in (False,True):
            f=self.fixture();self.configure(f,10,10);f.begin()
            if restart:f.restart()
            self.configure(f,1,5)
            f.step(0 if restart else 2,hp=150,stamina=11,server_now=2000005)
            status=f.runtime.Status(f.runtime)
            self.assertEqual((status.recoveries if restart else status.outcomes).bosses,'confirmed')
            self.assertEqual(len(f.executor.calls),1)
    def test_saved_outcome_with_changed_level_quote_stays_pending(self):
        f=self.fixture();f.begin();f.restart()
        f.source.get=f.h.lua.eval('function(stage) return {stage=stage,level=stage*5+1,hp=stage*100,hitBackMax=stage*10} end')
        f.step(0,hp=150,stamina=11,server_now=2000005)
        self.assertIsNone(f.runtime.Status(f.runtime).recoveries.bosses)
        self.assertEqual(len(f.runtime.checkpoint.Records(f.runtime.checkpoint)),1)
    def test_direct_planner_and_evidence_reject_invalid_bounds(self):
        f=unit.BossesTests();f.setUp();raw=f.raw();view=f.view(raw)[0]
        for minimum,maximum in ((0,10),(1,1000001),(1.5,10),(True,10),(11,10)):
            p=f.planner.propose(view,lua_table(f.h.lua,{'enabled':True,'limitsEnabled':True,'minLevel':minimum,'maxLevel':maximum}),f.h.lua.table())[0]
            self.assertIsNone(p)
        p=f.propose(raw)[0];p.intent.limitsEnabled=True
        for field,value in (('minLevel',11),('maxLevel',9),('selectedLevel',11),('minLevel',True),('maxLevel',1000001),('limitsEnabled',1)):
            previous=p.intent[field];p.intent[field]=value
            self.assertIsNone(f.evidence.capture(p,raw)[0]);p.intent[field]=previous
    def test_old_saved_intent_remains_recoverable(self):
        f=unit.BossesTests();f.setUp();before=f.raw();p=f.propose(before)[0]
        p.intent.limitsEnabled=None;p.intent.minLevel=None;p.intent.maxLevel=None;p.intent.selectedLevel=None
        baseline=f.evidence.capture(p,before)[0];self.assertIsNotNone(baseline)
        self.assertIsNone(baseline.selectedLevel)
        after=f.raw(revision=2,hp=150,hits=1,spent=1,last=f.now,stamina=11)
        saved=lua_table(f.h.lua,{'proposal':p,'before':before,'baseline':baseline,'reply':{'ok':True}})
        self.assertEqual(f.evidence.recoverSaved(saved,after),'confirmed')
    def test_legacy_bounds_map_inertly_without_goal_or_cap_aliases(self):
        f=legacy.LegacyRemainingPreferencesTests();f.setUp();self.addCleanup(f.tearDown)
        accepted,reason=f.preview(bossMinLevel=5,bossMaxLevel=10)
        self.assertTrue(accepted,reason);f.assert_inert()
        values=f.app.staged['values']
        self.assertEqual(values['bosses.custom.minLevel'],5);self.assertEqual(values['bosses.custom.maxLevel'],10)
        for field,value in (('bossMaxHits',10),('bossMaxStamina',10)):
            accepted,reason=f.preview(**{field:value});self.assertTrue(accepted,reason);f.assert_inert()
        for field,value in (('bossMinLevel',0),('bossMaxLevel',10001),('bossMinLevel',1.5),('bossMaxLevel',True)):
            accepted,reason=f.preview(**{field:value});self.assertFalse(accepted)

if __name__=='__main__':unittest.main()
