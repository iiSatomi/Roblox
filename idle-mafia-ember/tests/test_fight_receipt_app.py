"""Reuse the actual App fixture: scoped receipts enrich Combat and unload fences feeds."""
import copy
import unittest
import test_family_claim_read_pipeline as fixture
from test_fight_receipts import LIVE
from engine_harness import lua_table

class FightReceiptAppTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.FamilyClaimReadPipelineTests();self.f.setUp();self.h=self.f.h
        self.source=self.h.lua.execute("""return {callback=nil,disconnected=0,
            Subscribe=function(self,cb) self.callback=cb;return {Disconnect=function() self.disconnected=self.disconnected+1 end} end,
            CanAttack=function() return true end,Current=function() return true end}""")
        self.owner=self.h.load("src/tabs/combat/FightReceipts.luau").new(lua_table(self.h.lua,self.h.session),self.h.clock,self.f.lane,self.source,"a"*64)
        self.f.tab.fightReceipts=self.owner
    def begin(self):
        self.token=self.f.lane.TryAcquire(self.f.lane,"mutation","combat:42",45)[0]
        p=lua_table(self.h.lua,{**self.h.session,"feature":"combat","actionKey":"combat:42","resources":{"stamina":1},"intent":{"kind":"playerAttack","target":42}})
        self.assertTrue(self.owner.Begin(self.owner,self.token,p,42)[0])
        self.assertTrue(self.owner.Bind(self.owner,self.token,lua_table(self.h.lua,LIVE["second"]["initial"]))[0])
    def emit(self):
        self.source.callback("fightcash","",lua_table(self.h.lua,LIVE["second"]["final"]))
    def test_all_off_makes_no_read_mutation_or_notification_subscription(self):
        self.f.step();self.assertIsNone(self.source.callback)
        self.assertEqual(len(self.f.executor.calls),0)
        self.assertEqual(len(self.f.runtime.allowanceSnapshot.playerFightProof.attempts),0)
    def test_actual_app_receives_exact_staged_proof_without_enabling_a_fight(self):
        self.begin();self.emit();self.f.step()
        proof=self.f.runtime.allowanceSnapshot.playerFightProof
        self.assertEqual(proof.attempts[1].status,"settled")
        self.assertEqual(proof.attempts[1].receipt.cashConfirmed,36274716)
        self.assertIsNone(self.f.runtime.Status(self.f.runtime).outcomes.combat)
        self.assertEqual(len(self.f.executor.calls),0)
    def test_app_unload_disconnects_and_old_callback_cannot_change_owner(self):
        self.begin();cb=self.source.callback;self.f.app.Destroy(self.f.app)
        cb("fightcash","",lua_table(self.h.lua,LIVE["second"]["final"]))
        self.assertEqual(self.source.disconnected,1)
        self.assertIsNone(self.owner.Read(self.owner,self.f.reader.Capture(self.f.reader)[0]))
    def test_untrusted_caller_receipts_are_erased_at_actual_tab_boundary(self):
        self.f.tab.fightReceipts=None
        raw=self.f.reader.Capture(self.f.reader)[0];raw.playerFightProof=lua_table(self.h.lua,{"status":"settled"})
        self.f.app.Step(self.f.app,raw)
        self.assertIsNone(self.f.runtime.allowanceSnapshot.playerFightProof)
    def test_changed_native_source_drops_proof_in_actual_app(self):
        self.begin();self.emit();self.source.Current=self.h.lua.eval("function() return false end")
        self.f.step();self.assertIsNone(self.f.runtime.allowanceSnapshot.playerFightProof)
    def test_exact_deadline_cannot_leave_old_receipt_in_actual_app(self):
        self.begin();self.emit();self.h.at(45);self.f.reader.ObserveSync(self.f.reader,self.f.native)
        self.f.step();self.assertEqual(len(self.f.runtime.allowanceSnapshot.playerFightProof.attempts),0)
    def tearDown(self):
        self.f.tearDown()
