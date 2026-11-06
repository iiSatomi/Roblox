"""Attack and Scout allowances persist independently with their pending custody."""
import unittest
from engine_harness import Harness,lua_table

class PlayerFightUsageTests(unittest.TestCase):
    def setUp(self):
        self.h=Harness();self.pending=self.h.load('src/storage/PendingAction.luau')
        self.usage=self.h.load('src/tabs/combat/PlayerFightUsage.luau')
        self.module=self.h.load('src/storage/Checkpoint.luau')
        self.storage=self.h.lua.execute("""return {strictRecovery=true,data={},Read=function(self,k) return self.data[k] end,
            Write=function(self,k,v) if self.fail then return false end;self.data[k]=v;return true end}""")
        self.cp=self.new()
    def new(self):
        cp=self.module.new(self.storage,None,None,self.pending,None,None,None,self.usage)
        self.assertIsNone(cp.Load(cp,'user-a',self.h.session['place'],'release-a')[1]);return cp
    def proposal(self,key='fight',kind='playerAttack',attempted=0,spent=0,cost=1,feature='combat',attack_cap=2,scout_cap=1):
        p=self.h.proposal(feature,key);p.resources=lua_table(self.h.lua,{'stamina':cost})
        p.intent=lua_table(self.h.lua,{'kind':kind,'target':42,'expectedStaminaCost':cost,'attemptedBefore':attempted,
            'spentBefore':spent,'maxAttackSpend':attack_cap,'maxScoutSpend':scout_cap})
        return p
    def save(self,p=None,cp=None):
        cp=cp or self.cp
        return cp.Save(cp,p or self.proposal(),self.h.snapshot(native={'fullSync':True}),self.h.lua.table())
    def read(self,cp=None):
        cp=cp or self.cp;return cp.PlayerFightUsage(cp,self.h.snapshot())[0].usage.lanes
    def test_attack_and_scout_caps_are_independent_and_persist_after_reload(self):
        self.assertTrue(self.save()[0]);self.cp.Resolve(self.cp,'fight','confirmed')
        self.assertTrue(self.save(self.proposal('scout','playerScout'))[0]);self.cp.Resolve(self.cp,'scout','confirmed')
        cp=self.new();lanes=self.read(cp)
        self.assertEqual((lanes.combat.attack.spent,lanes.combat.scout.spent),(1,1))
        self.assertFalse(self.save(self.proposal('over-scout','playerScout',1,1),cp)[0])
        self.assertTrue(self.save(self.proposal('attack-2',attempted=1,spent=1),cp)[0]);cp.Resolve(cp,'attack-2','confirmed')
        self.assertFalse(self.save(self.proposal('over-attack',attempted=2,spent=2),cp)[0])
    def test_confirmed_rejected_and_unconfirmed_attempts_keep_allowance(self):
        self.save();self.cp.Resolve(self.cp,'fight','rejected')
        self.assertEqual(self.read().combat.attack.spent,1)
        self.assertTrue(self.save(self.proposal('pending',attempted=1,spent=1))[0])
        self.assertEqual(self.read(self.new()).combat.attack.spent,2)
        self.assertFalse(self.save(self.proposal('bypass'))[0])
    def test_only_exact_unsent_cleanup_refunds_its_mode(self):
        self.save();self.assertTrue(self.cp.Resolve(self.cp,'fight','schedule_failed')[0])
        self.assertEqual(self.read().combat.attack.spent,0)
        self.save(self.proposal('scout','playerScout'));self.cp.Resolve(self.cp,'scout','confirmed')
        self.assertEqual((self.read().combat.attack.spent,self.read().combat.scout.spent),(0,1))
    def test_war_and_mugging_allowances_never_borrow_from_each_other(self):
        self.save();self.cp.Resolve(self.cp,'fight','confirmed')
        self.save(self.proposal('war',feature='warCombat'));self.cp.Resolve(self.cp,'war','confirmed')
        self.assertEqual((self.read().combat.attack.spent,self.read().warCombat.attack.spent),(1,1))
    def test_failed_atomic_save_does_not_consume_allowance_or_custody(self):
        self.storage.fail=True;self.assertFalse(self.save()[0]);self.storage.fail=False
        self.assertEqual(len(self.cp.Records(self.cp)),0)
        self.assertIsNotNone(self.cp.fault)
        self.assertEqual(self.read(self.new()).combat.attack.spent,0)
    def test_saved_charge_without_sufficient_usage_fails_closed(self):
        self.save();key=self.cp.ScopeKey(self.cp)
        self.storage.data[key].playerFightUsage.lanes.combat.attack.spent=0
        cp=self.module.new(self.storage,None,None,self.pending,None,None,None,self.usage)
        self.assertIsNone(cp.Load(cp,'user-a',self.h.session['place'],'release-a')[0])
    def test_missing_usage_owner_cannot_drop_saved_allowance(self):
        self.save();cp=self.module.new(self.storage,None,None,self.pending)
        self.assertIsNone(cp.Load(cp,'user-a',self.h.session['place'],'release-a')[0])
    def test_allowance_reset_requires_exact_both_mode_snapshot_and_no_pending(self):
        self.save();before=self.cp.Allowance(self.cp,'combat')[0]
        self.assertFalse(self.cp.ResetAllowance(self.cp,before)[0])
        self.cp.Resolve(self.cp,'fight','confirmed');before=self.cp.Allowance(self.cp,'combat')[0]
        before.scoutSpent=1;self.assertFalse(self.cp.ResetAllowance(self.cp,before)[0])
        exact=self.cp.Allowance(self.cp,'combat')[0];self.assertTrue(self.cp.ResetAllowance(self.cp,exact)[0])
        self.assertEqual(self.read(self.new()).combat.attack.spent,0)
    def test_caller_counters_wrong_cost_and_default_zero_cannot_bypass_caps(self):
        for p in (self.proposal(attempted=1),self.proposal(spent=1),self.proposal(attack_cap=0),self.proposal(cost=6)):
            self.assertFalse(self.save(p)[0])
        p=self.proposal();p.resources.stamina=2;self.assertFalse(self.save(p)[0])
    def test_unrelated_save_resolve_preserves_both_allowances(self):
        self.save();self.cp.Resolve(self.cp,'fight','confirmed')
        p=self.h.proposal('jobs','job');self.assertTrue(self.save(p)[0]);self.cp.Resolve(self.cp,'job','confirmed')
        self.assertEqual(self.read(self.new()).combat.attack.spent,1)

    def test_a_reply_prevents_unsent_refund_and_allowance_remains_charged(self):
        self.save();self.assertTrue(self.cp.RecordReply(self.cp,'fight',lua_table(self.h.lua,{'ok':False}))[0])
        self.assertFalse(self.cp.Resolve(self.cp,'fight','schedule_failed')[0])
        self.assertEqual(self.read().combat.attack.spent,1)
    def test_one_mode_reset_does_not_clear_the_other_feature(self):
        self.save();self.cp.Resolve(self.cp,'fight','confirmed')
        self.save(self.proposal('war',feature='warCombat'));self.cp.Resolve(self.cp,'war','confirmed')
        preview=self.cp.Allowance(self.cp,'combat')[0];self.cp.ResetAllowance(self.cp,preview)
        lanes=self.read(self.new());self.assertEqual((lanes.combat.attack.spent,lanes.warCombat.attack.spent),(0,1))
    def test_scope_mismatch_never_exports_usage(self):
        raw=self.h.snapshot();raw.account='other'
        self.assertIsNone(self.cp.PlayerFightUsage(self.cp,raw)[0])
    def test_ambiguous_write_reloads_both_charge_and_custody(self):
        self.storage.Write=self.h.lua.eval("function(self,k,v) self.data[k]=v;return false end")
        self.assertFalse(self.save()[0]);self.assertIsNotNone(self.cp.fault)
        cp=self.new();self.assertEqual(len(cp.Records(cp)),1)
        self.assertEqual(self.read(cp).combat.attack.spent,1)

    def test_recovery_intent_cannot_change_charged_mode_or_counter(self):
        for field,value in [('mode','scout'),('attemptedBefore',1),('spentBefore',1)]:
            with self.subTest(field=field):
                self.setUp();self.save(self.proposal('scout','playerScout'));self.cp.Resolve(self.cp,'scout','confirmed')
                self.save();key=self.cp.ScopeKey(self.cp)
                self.storage.data[key].records[1].fightCharge[field]=value
                cp=self.module.new(self.storage,None,None,self.pending,None,None,None,self.usage)
                self.assertIsNone(cp.Load(cp,'user-a',self.h.session['place'],'release-a')[0])

    def test_runtime_erases_caller_usage_when_owner_is_missing(self):
        import test_automation_runtime as fixture
        base=fixture.AutomationRuntimeTests();base.setUp()
        raw=base.raw();raw.playerFightUsageProof=lua_table(base.h.lua,{'forged':True})
        base.runtime.Step(base.runtime,raw,lua_table(base.h.lua,{}))
        self.assertIsNone(base.runtime.allowanceSnapshot.playerFightUsageProof)
        base.runtime.Close(base.runtime)

    def test_numbered_pending_fight_cannot_lose_both_charge_and_usage(self):
        for feature in ('combat','warCombat'):
            with self.subTest(feature=feature):
                self.setUp();self.save(self.proposal(feature=feature));key=self.cp.ScopeKey(self.cp)
                self.storage.data[key].records[1].fightCharge=None
                self.storage.data[key].playerFightUsage=None
                cp=self.module.new(self.storage,None,None,self.pending,None,None,None,self.usage)
                self.assertIsNone(cp.Load(cp,'user-a',self.h.session['place'],'release-a')[0])

    def test_unnumbered_legacy_fight_keeps_custody_without_inventing_recovery(self):
        key=self.cp.ScopeKey(self.cp)
        self.storage.data[key]=lua_table(self.h.lua,{'version':1,'records':[{'account':'user-a',
            'place':self.h.session['place'],'release':'release-a','feature':'combat','actionKey':'legacy','resources':{'stamina':1}}]})
        cp=self.new();self.assertEqual(len(cp.Records(cp)),1);self.assertIsNone(cp.Recovery(cp,'legacy')[0])

    def test_legacy_fight_usage_is_unknown_and_cannot_admit_new_same_feature_charge(self):
        self.test_unnumbered_legacy_fight_keeps_custody_without_inventing_recovery()
        cp=self.new();proof=cp.PlayerFightUsage(cp,self.h.snapshot())[0]
        self.assertIsNone(proof.usage.lanes.combat)
        self.assertIsNone(cp.Allowance(cp,'combat')[0])
        self.assertFalse(self.save(self.proposal('new-combat'),cp)[0])
        self.assertTrue(self.save(self.proposal('war',feature='warCombat'),cp)[0])
        self.assertEqual(len(cp.Records(cp)),2)

    def bounded(self,key='bounded'):
        p=self.proposal(key,attack_cap=5);p.resources.stamina=5;p.intent.maxStaminaExposure=5;return p
    def test_configured_max_exposure_is_charged_independently_from_lower_quoted_cost(self):
        self.assertTrue(self.save(self.bounded())[0]);cp=self.new()
        self.assertEqual(self.read(cp).combat.attack.spent,5)
        charge=cp.Records(cp)[1].fightCharge;self.assertEqual((charge.cost,charge.quoteCost),(5,1))
        cp.Resolve(cp,'bounded','confirmed');self.assertEqual(self.read(cp).combat.attack.spent,5)
    def test_small_quoted_cost_cannot_bypass_max_exposure_cap_or_resource_reserve(self):
        p=self.bounded();p.intent.maxAttackSpend=4;self.assertFalse(self.save(p)[0])
        p=self.bounded();p.resources.stamina=1;self.assertFalse(self.save(p)[0])
        p=self.bounded();p.intent.expectedStaminaCost=6;self.assertFalse(self.save(p)[0])
    def test_only_known_unsent_bounded_attempt_refunds_full_exposure(self):
        self.save(self.bounded());self.assertTrue(self.cp.Resolve(self.cp,'bounded','schedule_failed')[0])
        self.assertEqual(self.read().combat.attack.spent,0)
        self.save(self.bounded());self.cp.RecordReply(self.cp,'bounded',lua_table(self.h.lua,{'ok':False}))
        self.assertFalse(self.cp.Resolve(self.cp,'bounded','schedule_failed')[0]);self.assertEqual(self.read().combat.attack.spent,5)
    def test_saved_bounded_quote_cannot_be_erased_or_changed_into_a_legacy_charge(self):
        for value in (None,2):
            self.setUp();self.save(self.bounded());key=self.cp.ScopeKey(self.cp)
            self.storage.data[key].records[1].fightCharge.quoteCost=value
            cp=self.module.new(self.storage,None,None,self.pending,None,None,None,self.usage)
            self.assertIsNone(cp.Load(cp,'user-a',self.h.session['place'],'release-a')[0])
