"""Exact staged Combat results; aggregate balances never establish an outcome."""
import copy
import unittest
from engine_harness import Harness,lua_table
from test_fight_receipts import LIVE

class PlayerFightEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.h=getattr(self,'provided_h',None) or Harness();self.receipts=self.h.load('src/tabs/combat/FightReceipts.luau')
        self.e=self.h.load('src/tabs/combat/PlayerFightEvidence.luau').new(self.receipts)
        self.initial=copy.deepcopy(LIVE['second']['initial']);self.final=copy.deepcopy(LIVE['second']['final'])
        self.now=self.initial['targetDaily']['serverNow'];self.day=self.initial['targetDaily']['day']
        self.p=self.h.proposal('combat','combat:42');self.p.requestId=1;self.p.resources=lua_table(self.h.lua,{'stamina':1})
        self.p.intent=lua_table(self.h.lua,{'kind':'playerAttack','target':42,'targetName':'Target B','targetLevel':128,
            'expectedStaminaCost':1,'sourceKey':'a'*64,'serverNow':self.now,'attemptedBefore':0,'spentBefore':0,
            'maxAttackSpend':2,'maxScoutSpend':0})
        self.before=self.h.snapshot(native={'fullSync':True,'serverNow':self.now,'pools':{'stamina':20,'health':100},
            'attackDaily':{'day':self.day,'counts':{}}})
        self.before.hitListProof=lua_table(self.h.lua,{'account':'user-a','capturedAt':0,
            'rows':[{'userId':42,'name':'Target B','level':128,'stamina':1,'shielded':False}]})
        self.before.playerFightProof=lua_table(self.h.lua,{**self.h.session,'revision':1,'capturedAt':0,'sourceKey':'a'*64,'attempts':[]})
        usage=self.h.load('src/tabs/combat/PlayerFightUsage.luau').copy(None)
        self.before.playerFightUsageProof=lua_table(self.h.lua,{'account':'user-a','capturedAt':0,'usage':usage})
        self.baseline=self.e.capture(self.p,self.before)[0]
        self.after=self.h.snapshot(revision=2,native={'fullSync':True,'serverNow':self.now+1,
            'pools':{'stamina':19,'health':100},'attackDaily':{'day':self.day,'counts':{'42':1}}})
        self.after.playerFightProof=lua_table(self.h.lua,{**self.h.session,'revision':2,'capturedAt':0,'sourceKey':'a'*64,
            'attempts':[{'actionKey':'combat:42','feature':'combat','target':42,'status':'settled',
                'initial':self.initial,'receipt':self.final}]})
    def evaluate(self):
        return self.e.evaluate(self.p,self.before,self.after,lua_table(self.h.lua,self.initial),self.baseline)
    def data(self):
        return lua_table(self.h.lua,{'proposal':self.p,'before':self.before,'baseline':self.baseline,'reply':self.initial})
    def test_exact_native_stages_confirm_even_if_other_income_changes_balances(self):
        self.assertIsNotNone(self.baseline);self.after.native.cash=99999999
        self.assertEqual(self.evaluate(),'confirmed')
        row=self.e.outcome(self.data(),self.after)
        self.assertEqual((row.target,row.receipt.cashConfirmed,row.staminaCost),(42,36274716,1))
    def test_no_receipt_or_ambiguous_receipt_never_uses_aggregate_balances(self):
        for status in ('pending','ambiguous'):
            self.after.playerFightProof.attempts[1].status=status;self.assertEqual(self.evaluate(),'pending')
        self.after.playerFightProof=None;self.assertEqual(self.evaluate(),'pending')
    def test_changed_scope_target_cost_fight_or_initial_cannot_confirm(self):
        for field,value in [('target',43),('feature','warCombat'),('actionKey','other')]:
            with self.subTest(field=field):
                self.setUp();self.after.playerFightProof.attempts[1][field]=value;self.assertEqual(self.evaluate(),'pending')
        for field,value in [('fightId','other'),('staminaCost',2),('targetName','Other'),('won',False)]:
            with self.subTest(field=field):
                self.setUp();self.after.playerFightProof.attempts[1].receipt[field]=value
                self.assertEqual(self.evaluate(),'pending')
    def test_terminal_loss_is_confirmed_execution_and_zero_cash_history(self):
        self.initial['won']=False;self.final.update(won=False,cashConfirmed=0,stolen=0)
        attempt=self.after.playerFightProof.attempts[1];attempt.initial=lua_table(self.h.lua,self.initial)
        attempt.receipt=lua_table(self.h.lua,self.final)
        self.assertEqual(self.evaluate(),'confirmed');self.assertFalse(self.e.outcome(self.data(),self.after).receipt.won)
    def test_explicit_negative_requires_unchanged_resources_and_no_fight_id(self):
        self.after.native.pools.stamina=20;self.after.native.attackDaily.counts['42']=None
        reply=lua_table(self.h.lua,{'ok':False,'code':'target_hospitalized'})
        self.assertEqual(self.e.evaluate(self.p,self.before,self.after,reply,self.baseline),'rejected')
        self.after.native.pools.stamina=19
        self.assertEqual(self.e.evaluate(self.p,self.before,self.after,reply,self.baseline),'pending')
    def test_manual_challenge_rate_limit_and_pending_are_never_rejections(self):
        self.after.native.pools.stamina=20;self.after.native.attackDaily.counts['42']=None
        for reply in ({'ok':False,'code':'presence'},{'ok':False,'code':'rate_limited'},
                {'ok':False,'pending':True},{'ok':False,'fightId':'unknown'}):
            self.assertEqual(self.e.evaluate(self.p,self.before,self.after,lua_table(self.h.lua,reply),self.baseline),'pending')
    def test_saved_baseline_tamper_and_cross_session_without_ledger_stay_held(self):
        data=self.data();data.baseline.staminaCost=2;self.assertIsNone(self.e.recoverSaved(data,self.after))
        self.setUp();self.after.session='new-session';self.after.playerFightProof=None
        self.assertIsNone(self.e.recoverSaved(self.data(),self.after))
    def test_daily_only_capture_refuses_prior_count_and_malformed_option(self):
        self.p.intent.dailyOnly=True;self.before.native.attackDaily.counts['42']=1
        self.assertIsNone(self.e.capture(self.p,self.before)[0])
        self.p.intent.dailyOnly='true';self.assertIsNone(self.e.capture(self.p,self.before)[0])
    def test_selection_baseline_requires_exact_quote_source_and_own_usage(self):
        for field,value in [('target',43),('expectedStaminaCost',2),('sourceKey','b'*64),('spentBefore',1)]:
            self.setUp();self.p.intent[field]=value;self.assertIsNone(self.e.capture(self.p,self.before)[0])
    def test_settled_receipt_cannot_be_replaced_by_matching_fight_id_only(self):
        self.after.playerFightProof.attempts[1].initial.cashEstimate=0
        self.assertEqual(self.evaluate(),'pending')

    def test_fractional_native_pools_are_retained_without_rounding(self):
        self.before.native.pools.stamina=20.5;self.before.native.pools.health=100.25
        baseline,why=self.e.capture(self.p,self.before)
        self.assertIsNotNone(baseline,why)
        self.assertEqual((baseline.staminaBefore,baseline.healthBefore),(20.5,100.25))

    def test_bounded_reservation_does_not_change_exact_native_cost_baseline_or_outcome(self):
        self.p.resources.stamina=5;self.p.intent.maxStaminaExposure=5
        self.baseline,why=self.e.capture(self.p,self.before);self.assertIsNotNone(self.baseline,why)
        self.assertEqual((self.baseline.staminaCost,self.baseline.staminaExposure),(1,5))
        self.assertEqual(self.evaluate(),'confirmed')

    def test_fractional_replicated_server_time_keeps_exact_owned_outcome(self):
        self.before.native.serverNow+=.25;self.p.intent.serverNow=self.before.native.serverNow
        self.baseline,why=self.e.capture(self.p,self.before);self.assertIsNotNone(self.baseline,why)
        self.assertEqual(self.evaluate(),'confirmed')
