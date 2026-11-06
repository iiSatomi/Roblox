"""One source-owned native Heist counter, no native worker or RPC loop."""
import unittest
from engine_harness import Harness,lua_table

class NativeHeistLeaseTests(unittest.TestCase):
    def setUp(self):
        self.h=Harness();h=self.h
        self.module=h.load('src/tabs/heists/NativeHeistLease.luau')
        self.port=h.lua.execute('''return {counter=4,running=false,valid=true,writes=0,workers=0,
            Current=function(self) return self.valid end,
            Read=function(self) return {counter=self.counter,pending=self.pending,running=self.running,inflight=self.inflight} end,
            Write=function(self,key,value) self.writes=self.writes+1;if self.fail==key then error('write failed') end;self[key]=value end,
            Refresh=function(self) self.refreshes=(self.refreshes or 0)+1 end,
            NativeAct=function(self) if not self.pending then self.counter=self.counter+1;self.pending={sequence=self.counter} end;if self.running then return end;self.running=true;self.workers=self.workers+1 end}''')
        self.epoch=lua_table(h.lua,{'id':'epoch-a','counterSeen':4})
        self.scope=lua_table(h.lua,{'account':'user-a','place':'73897506680154','jobId':'job-a','sourceKey':'a'*64})
        self.owner=self.module.new(self.port,h.clock,self.scope,self.epoch)[0]
        self.p=lua_table(h.lua,{**h.session,'feature':'heists','actionKey':'start:one','intent':{'kind':'heistStart','heistId':'h_a','sequence':5,'nativeJob':'job-a','nativeEpoch':'epoch-a','nativeSourceKey':'a'*64,'needsSequence':True}})
    def test_quote_is_read_only_and_acquire_advances_native_counter_once(self):
        q,why=self.owner.Quote(self.owner);self.assertIsNone(why);self.assertEqual(q.sequence,5);self.assertEqual(self.port.writes,0)
        self.assertTrue(self.owner.Acquire(self.owner,self.p,45)[0]);self.assertEqual(self.port.counter,5)
        self.assertTrue(self.owner.Owns(self.owner,self.p));self.port.NativeAct(self.port)
        self.assertEqual(self.port.counter,5);self.assertEqual(self.port.workers,0)
        self.assertTrue(self.owner.Release(self.owner,self.p)[0]);self.assertIsNone(self.port.pending);self.assertFalse(self.port.running);self.assertEqual(self.port.counter,5)
    def test_native_ui_winning_quote_race_is_untouched(self):
        self.port.NativeAct(self.port);native=self.port.pending
        self.assertFalse(self.owner.Acquire(self.owner,self.p,45)[0]);self.assertEqual(self.port.writes,0)
        self.assertTrue(self.h.lua.eval('function(a,b) return a==b end')(self.port.pending,native))
    def test_unfinished_native_invocation_cannot_be_adopted(self):
        self.port.inflight=self.h.lua.table();self.assertFalse(self.owner.Acquire(self.owner,self.p,45)[0]);self.assertEqual(self.port.writes,0)
    def test_expiry_and_broader_source_change_still_release_only_owned_token(self):
        self.assertTrue(self.owner.Acquire(self.owner,self.p,45)[0]);self.h.at(45);self.port.valid=False
        self.assertFalse(self.owner.Owns(self.owner,self.p));self.assertTrue(self.owner.Release(self.owner,self.p)[0])
        self.assertIsNone(self.port.pending);self.assertFalse(self.port.running);self.assertEqual(self.port.counter,5)
    def test_newer_native_owner_is_never_cleared(self):
        self.assertTrue(self.owner.Acquire(self.owner,self.p,45)[0]);other=self.h.lua.table();self.port.pending=other
        self.owner.Close(self.owner);self.assertTrue(self.h.lua.eval('function(a,b) return a==b end')(self.port.pending,other));self.assertTrue(self.port.running)
    def test_counter_reset_retires_the_old_epoch_without_guessing_highwater(self):
        self.port.counter=3;q,_=self.owner.Quote(self.owner);self.assertIsNone(q);self.assertTrue(self.epoch.retired);self.assertEqual(self.port.counter,3)
    def test_wrong_job_epoch_and_source_never_acquire(self):
        for k,value in [('nativeJob','other'),('nativeEpoch','other'),('nativeSourceKey','b'*64)]:
            old=self.p.intent[k];self.p.intent[k]=value;self.assertFalse(self.owner.Acquire(self.owner,self.p,45)[0]);self.p.intent[k]=old
        self.assertEqual(self.port.writes,0)
    def test_partial_write_failure_cleans_own_flags_without_counter_rollback(self):
        self.port.fail='counter';self.assertFalse(self.owner.Acquire(self.owner,self.p,45)[0]);self.assertIsNone(self.port.pending);self.assertFalse(self.port.running);self.assertEqual(self.port.counter,4)

    def test_cleanup_read_failure_retains_exact_ownership_for_retry(self):
        self.assertTrue(self.owner.Acquire(self.owner,self.p,45)[0]);old=self.port.Read
        self.port.Read=self.h.lua.eval("function() error('detached debug read') end")
        self.assertFalse(self.owner.Release(self.owner,self.p)[0]);self.assertIsNotNone(self.epoch.live)
        self.port.Read=old;self.assertTrue(self.owner.Release(self.owner,self.p)[0]);self.assertIsNone(self.port.pending)
    def test_cleanup_second_write_failure_can_retry_without_losing_its_token_proof(self):
        self.assertTrue(self.owner.Acquire(self.owner,self.p,45)[0]);self.port.fail='running'
        self.assertFalse(self.owner.Release(self.owner,self.p)[0]);self.assertIsNotNone(self.epoch.live)
        self.port.fail=None;self.assertTrue(self.owner.Release(self.owner,self.p)[0]);self.assertFalse(self.port.running);self.assertIsNone(self.epoch.live)
