"""Family relations protect before ranking and before the real App dispatch."""
import unittest
import test_combat_target_selection as selection
import test_player_combat_planner_app as app_fixture

class AlliancePolicyTests(unittest.TestCase):
    def setUp(self):
        self.f=selection.CombatTargetSelectionTests();self.f.setUp();self.v=self.f.view()
        self.s=self.f.settings(relationAllies='',relationEnemies='',enemyMode='Off')
    def choose(self):return self.f.choose(self.v,self.s)[0]
    def test_ally_wins_enemy_overlap_and_blocks_scout(self):
        self.s.relationAllies='11';self.s.relationEnemies='11';self.s.enemyMode='Prefer enemies'
        self.assertIsNone(self.choose())
        self.v.targets[1].stats=None;self.s.allowScout=True;self.s.maxScoutSpend=5
        self.assertIsNone(self.choose())
    def test_enemies_only_empty_list_and_unknown_membership_refuse(self):
        self.s.enemyMode='Enemies only';self.assertIsNone(self.choose())
        self.s.relationEnemies='11';self.assertIsNotNone(self.choose())
        self.v.targets[1].familyId=None;self.assertIsNone(self.choose())
        self.v.targets[1].familyId=0;self.assertIsNone(self.choose())
    def test_enemy_preference_after_safety_before_high_value_with_fallback(self):
        other=self.f.view().targets[1];other.userId=3;other.familyId=12;other.history[1].cash=100000
        other.highValue=True;self.v.targets[2]=other;self.v.highValueKnown=True
        self.s.preferHighValue=True;self.s.enemyMode='Prefer enemies';self.s.relationEnemies='11'
        self.assertEqual(self.choose().userId,2)
        self.v.targets[1].shieldUntil=2000;self.assertEqual(self.choose().userId,3)
        self.s.enemyMode='Enemies only';self.assertIsNone(self.choose())
    def test_strings_are_stable_ids_and_malformed_policy_holds(self):
        self.v.ownFamilyId='own';self.v.war.active=False;self.v.targets[1].familyId='family-a'
        self.s.relationAllies='family-a';self.assertIsNone(self.choose())
        for bad in ('a,,b','bad id','0',','.join('f'+str(i) for i in range(65))):
            self.s.relationAllies=bad;self.assertIsNone(self.choose())

class AllianceAppTests(unittest.TestCase):
    def setUp(self):
        self.b=app_fixture.PlayerCombatPlannerAppTests();self.b.setUp();self.f=self.b.f;self.app=self.b.app
        self.b.seed(False,target_family='family-a')
    def set(self,k,v):self.assertTrue(self.app.Set(self.app,'alliance.'+k,v)[0])
    def test_ally_prevents_proposal_without_spend(self):
        self.set('allies','family-a');self.app.Set(self.app,'combat.enabled',True);self.app.Resume(self.app);self.f.step()
        self.assertEqual(len(self.f.executor.queued),0)
    def test_adding_ally_after_queue_blocks_send_without_another_step(self):
        self.f.begin();self.set('allies','family-a');self.f.executor.queued[1]()
        self.assertEqual(self.f.executor.calls,0)
        self.assertEqual(self.f.runtime.checkpoint.Allowance(self.f.runtime.checkpoint,'combat')[0].attackSpent,0)
    def test_enemy_mode_change_after_queue_blocks_send(self):
        self.f.begin();self.set('mode','Enemies only');self.f.executor.queued[1]();self.assertEqual(self.f.executor.calls,0)
    def test_stop_preserves_protection_and_profile_roundtrip(self):
        self.set('allies','family-a');self.set('enemies','family-b');profile=self.app.model.Snapshot(self.app.model)
        self.app.Stop(self.app);self.assertEqual(self.app.model['values']['alliance.allies'],'family-a')
        self.assertTrue(self.app.ApplyProfile(self.app,profile)[0]);self.assertEqual(self.app.model['values']['alliance.enemies'],'family-b')
    def test_adding_ally_during_final_yielding_preflight_cannot_send(self):
        self.f.begin();self.f.source.yieldFrame=True;h=self.b.h
        h.lua.globals().allianceGuardCallback=self.f.executor.queued[1]
        self.assertEqual(h.lua.execute('allianceGuardThread=coroutine.create(allianceGuardCallback);local ok,v=coroutine.resume(allianceGuardThread);assert(ok);return v'),'daily-native-frame')
        self.assertEqual(h.lua.execute('local ok,v=coroutine.resume(allianceGuardThread);assert(ok);return v'),'daily-native-frame')
        self.set('allies','family-a')
        h.lua.execute('assert(coroutine.resume(allianceGuardThread))')
        self.assertEqual(self.f.executor.calls,0)
        self.assertEqual(self.f.runtime.checkpoint.Allowance(self.f.runtime.checkpoint,'combat')[0].attackSpent,0)
    def test_membership_change_after_queue_blocks_send(self):
        self.set('allies','ally-family');self.f.begin()
        self.f.tab.playerProfiles.cache['42'].familyId='ally-family'
        self.f.executor.queued[1]();self.assertEqual(self.f.executor.calls,0)
    def test_ally_change_after_send_preserves_uncertain_custody_and_charge(self):
        self.f.begin();self.f.send();self.set('allies','family-a');self.app.Stop(self.app)
        self.assertEqual(self.f.executor.calls,1)
        self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)),1)
        self.assertEqual(self.f.runtime.checkpoint.Allowance(self.f.runtime.checkpoint,'combat')[0].attackSpent,5)
    def test_invalid_lists_and_modes_reject_without_erasing_protection(self):
        self.set('allies','family-a')
        for key,value in [('allies','bad,,id'),('allies','0'),('enemies',','.join('f'+str(i) for i in range(65))),('mode','All')]:
            self.assertFalse(self.app.Set(self.app,'alliance.'+key,value)[0])
            self.assertEqual(self.app.model['values']['alliance.allies'],'family-a')
    def tearDown(self):self.b.tearDown()

class AllianceSabotageTests(unittest.TestCase):
    def test_missing_native_owner_family_cannot_bypass_relations(self):
        from engine_harness import Harness,lua_table
        h=Harness();m=h.load('src/features/Sabotage.luau')
        result=m.propose(lua_table(h.lua,{}),lua_table(h.lua,{'enabled':True,'relationAllies':'family-a'}),lua_table(h.lua,{}))
        self.assertIsNone(result[0]);self.assertIn('Family membership',result[1])
