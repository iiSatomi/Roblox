"""Scout replies require exact owned target/quote and replicated resource evidence."""
import unittest
from engine_harness import Harness,lua_table

class PlayerScoutEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.h=getattr(self,'provided_h',None) or Harness()
        self.e=self.h.load('src/tabs/combat/PlayerScoutEvidence.luau')
        self.p=self.h.proposal('combat','combat:scout:42');self.p.requestId=1
        self.p.resources=lua_table(self.h.lua,{'stamina':5})
        self.p.intent=lua_table(self.h.lua,{'kind':'playerScout','target':42,'targetName':'Target','targetLevel':128,
            'familyId':'other','expectedStaminaCost':1,'maxStaminaExposure':5,'sourceKey':'a'*64,'serverNow':1000.25,
            'attemptedBefore':0,'spentBefore':0,'maxAttackSpend':5,'maxScoutSpend':5,'allowScout':True})
        self.before=self.h.snapshot(native={'fullSync':True,'serverNow':1000.25,'pools':{'stamina':20,'health':100}})
        self.before.hitListProof=lua_table(self.h.lua,{'account':'user-a','capturedAt':0,'sourceKey':'a'*64,
            'rows':[{'userId':42,'name':'Target','level':128,'familyId':'other','stamina':2,'shielded':False}],
            'profiles':{'42':{'userId':42,'name':'Target','level':128,'familyId':'other','scoutCost':1,
                'observedAt':0,'observedServerNow':1000.25,'statsHidden':True,'friend':False,'friendshipStatus':'reported'}}})
        self.before.playerFightUsageProof=lua_table(self.h.lua,{'account':'user-a','capturedAt':0,
            'usage':self.h.load('src/tabs/combat/PlayerFightUsage.luau').copy(None)})
        self.reply=lua_table(self.h.lua,{'ok':True,'atk':300,'def':100,'crew':4})
        self.after=self.h.snapshot(revision=2,native={'fullSync':True,'serverNow':1001.25,'pools':{'stamina':19,'health':100}})
        self.baseline=self.e.capture(self.p,self.before)[0]
    def data(self):
        return lua_table(self.h.lua,{'proposal':self.p,'before':self.before,'baseline':self.baseline,'reply':self.reply})
    def evaluate(self): return self.e.evaluate(self.p,self.before,self.after,self.reply,self.baseline)
    def test_exact_success_requires_replicated_cost_and_returns_only_target_bound_stats(self):
        self.assertIsNotNone(self.baseline);self.assertEqual(self.evaluate(),'confirmed')
        row=self.e.outcome(self.data(),self.after)
        self.assertEqual((row.target,row.level,row.defense,row.at),(42,128,100,1000.25))
        row.defense=999;self.assertEqual(self.e.outcome(self.data(),self.after).defense,100)
    def test_reply_alone_or_matching_balance_alone_never_confirms(self):
        self.after.native.pools.stamina=20;self.assertEqual(self.evaluate(),'pending')
        self.after.native.pools.stamina=19;self.reply=None;self.assertEqual(self.evaluate(),'pending')
    def test_reply_fields_target_or_resource_conflict_remains_uncertain(self):
        for key,value in [('def',float('nan')),('crew',-1),('ok',False),('pending',True),('target',43),('staminaCost',2),('fightId','unrelated')]:
            with self.subTest(key=key):
                self.setUp();self.reply[key]=value;self.assertEqual(self.evaluate(),'pending')
    def test_capture_requires_optin_own_scout_allowance_profile_quote_and_current_identity(self):
        for key,value in [('allowScout',False),('expectedStaminaCost',2),('target',43),('sourceKey','b'*64),('spentBefore',1)]:
            self.setUp();self.p.intent[key]=value;self.assertIsNone(self.e.capture(self.p,self.before)[0])
        self.setUp();self.before.hitListProof.profiles['42'].friend=True
        self.assertIsNone(self.e.capture(self.p,self.before)[0])
    def test_rejection_requires_exact_no_effect_and_preserves_manual_uncertainty(self):
        self.after.native.pools.stamina=20;self.reply=lua_table(self.h.lua,{'ok':False,'code':'target_unavailable'})
        self.assertEqual(self.evaluate(),'rejected')
        for code in ('presence','rate_limited','busy'):
            self.reply.code=code;self.assertEqual(self.evaluate(),'pending')
    def test_fresh_session_saved_exact_reply_recovers_without_replaying_or_inventing_stats(self):
        self.after.session='fresh-session'
        self.assertEqual(self.e.recoverSaved(self.data(),self.after),'confirmed')
        self.after.native.pools.stamina=18;self.assertIsNone(self.e.recoverSaved(self.data(),self.after))
    def test_changed_saved_baseline_scope_or_quote_never_recovers(self):
        data=self.data();data.baseline.target=43;self.assertIsNone(self.e.recoverSaved(data,self.after))
        self.setUp();self.after.account='other';self.assertIsNone(self.e.recoverSaved(self.data(),self.after))
        self.setUp();self.after.native.serverNow=999;self.assertIsNone(self.e.recoverSaved(self.data(),self.after))
    def test_live_broker_header_only_baseline_works_but_numbered_saved_outcome_is_required(self):
        header=lua_table(self.h.lua,{**self.h.session,'revision':1,'capturedAt':0})
        self.assertEqual(self.e.evaluate(self.p,header,self.after,self.reply,self.baseline),'confirmed')
        self.p.requestId=None;self.assertIsNone(self.e.outcome(self.data(),self.after))
