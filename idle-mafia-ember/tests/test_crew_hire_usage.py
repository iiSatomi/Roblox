"""Independent hire exposure persists atomically with the generic pending record."""
import unittest
from engine_harness import Harness,lua_table
class CrewHireUsageTests(unittest.TestCase):
    def setUp(self):
        self.h=Harness();self.usage=self.h.load('src/tabs/crew/CrewHireUsage.luau')
        self.pending=self.h.load('src/storage/PendingAction.luau');self.module=self.h.load('src/storage/Checkpoint.luau')
        self.storage=self.h.lua.execute('return {strictRecovery=true,data={},Read=function(self,k) return self.data[k] end,Write=function(self,k,v) self.data[k]=v return true end}')
        self.cp=self.new()
    def new(self):
        cp=self.module.new(self.storage,None,None,self.pending,None,None,self.usage)
        self.assertIsNone(cp.Load(cp,'user-a',self.h.session['place'],'release-a')[1]);return cp
    def proposal(self,key='hire',attempted=0,spent=0):
        p=self.h.proposal('crewHire',key);p.resources=lua_table(self.h.lua,{'cash':100})
        p.intent=lua_table(self.h.lua,{'kind':'crewHire','cost':100,'attemptedBefore':attempted,'spentBefore':spent,'maxAttempts':2,'maxSpend':200})
        return p
    def save(self,cp=None,p=None):
        cp=cp or self.cp
        return cp.Save(cp,p or self.proposal(),self.h.snapshot(native={'fullSync':True,'cash':500}),self.h.lua.table())
    def test_confirmed_or_rejected_attempts_keep_durable_exposure_and_stale_zero_is_refused(self):
        self.assertTrue(self.save()[0]);self.assertTrue(self.cp.Resolve(self.cp,'hire','confirmed')[0])
        cp=self.new();self.assertEqual(cp.CrewHireUsage(cp,self.h.snapshot())[0].spent,100)
        self.assertFalse(self.save(cp,self.proposal('stale'))[0])
        self.assertTrue(self.save(cp,self.proposal('next',1,100))[0]);self.cp=cp
        self.assertTrue(cp.Resolve(cp,'next','rejected')[0]);self.assertFalse(self.save(cp,self.proposal('over',2,200))[0])
    def test_only_definitely_unsent_refunds_charge_once(self):
        self.assertTrue(self.save()[0]);self.assertTrue(self.cp.Resolve(self.cp,'hire','schedule_failed')[0])
        self.assertEqual(self.cp.CrewHireUsage(self.cp,self.h.snapshot())[0].spent,0)
        self.assertFalse(self.cp.Resolve(self.cp,'hire','schedule_failed')[0])
    def test_pending_prevents_reset_and_completed_allowance_requires_exact_review(self):
        self.assertTrue(self.save()[0]);preview=self.cp.Allowance(self.cp,'crewHire')[0]
        self.assertFalse(self.cp.ResetAllowance(self.cp,preview)[0])
        self.cp.Resolve(self.cp,'hire','confirmed');preview=self.cp.Allowance(self.cp,'crewHire')[0]
        self.assertTrue(self.cp.ResetAllowance(self.cp,preview)[0]);self.assertEqual(self.cp.CrewHireUsage(self.cp,self.h.snapshot())[0].spent,0)
    def test_failed_main_write_cannot_charge_memory_or_restart(self):
        self.storage.Write=self.h.lua.eval('function() return false end')
        self.assertFalse(self.save()[0]);self.assertIsNone(self.storage.data[self.cp.key])
        self.storage.Write=self.h.lua.eval('function(self,k,v) self.data[k]=v return true end')
        cp=self.new();self.assertEqual(cp.CrewHireUsage(cp,self.h.snapshot())[0].spent,0)
