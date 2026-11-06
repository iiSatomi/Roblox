"""Actual player proposal admission reuses owned view, policy and durable lane counters."""
import unittest
import test_player_target_view as view_fixture
import test_combat_target_selection as policy_fixture
from engine_harness import lua_table

class PlayerFightPlannerTests(unittest.TestCase):
    def setUp(self):
        self.f=view_fixture.PlayerTargetViewTests();self.f.setUp();self.h=self.f.h
        self.view=self.f.read()[0]
        s=policy_fixture.CombatTargetSelectionTests();s.h=self.h;self.settings=s.settings()
        self.planner=self.h.load('src/tabs/combat/PlayerFightPlanner.luau').new(self.h.load('src/tabs/combat/TargetSelection.luau'))
        self.held=lua_table(self.h.lua,{'stamina':0,'uncertainStamina':0})
    def propose(self):return self.planner.propose(self.view,self.settings,self.held)
    def test_public_stats_propose_exact_attack_quote_maximum_exposure_and_independent_counters(self):
        p,why=self.propose();self.assertIsNotNone(p,why)
        self.assertEqual((p.feature,p.intent.kind,p.intent.target,p.intent.expectedStaminaCost,p.resources.stamina),('combat','playerAttack',2,2,5))
        self.assertEqual((p.intent.attemptedBefore,p.intent.spentBefore,p.intent.sourceKey),(0,0,'a'*64))
        self.assertEqual(p.revision,self.view.revision);self.assertEqual(p.intent.defense,100)
    def test_hidden_target_proposes_scout_only_with_its_optin_cap_and_followup_attack_reserve(self):
        self.view.targets[1].stats=None;self.assertIsNone(self.propose()[0])
        self.settings.allowScout=True;self.settings.maxScoutSpend=5
        p,why=self.propose();self.assertIsNotNone(p,why)
        self.assertEqual((p.intent.kind,p.intent.expectedStaminaCost,p.resources.stamina,p.intent.attackExposure),('playerScout',1,5,5))
        self.view.scoutSpent=5;self.assertIsNone(self.propose()[0])
        self.view.scoutSpent=0;self.view.stamina=10;self.assertIsNone(self.propose()[0])
    def test_reservations_and_existing_attempts_cannot_borrow_attack_or_scout_allowances(self):
        self.settings.maxAttackSpend=5;self.view.attackSpent=5;self.assertIsNone(self.propose()[0])
        self.view.attackSpent=0;self.held.uncertainStamina=15;self.assertIsNone(self.propose()[0])
        self.held.uncertainStamina=2;p=self.propose()[0];self.assertEqual(p.intent.uncertainStamina,2)
    def test_missing_explicit_holds_usage_or_unknown_view_never_proposes(self):
        self.held.uncertainStamina=None;self.assertIsNone(self.propose()[0])
        self.setUp();self.view.attackAttempted=None;self.assertIsNone(self.propose()[0])
        self.setUp();self.view.status='unknown';self.assertIsNone(self.propose()[0])
