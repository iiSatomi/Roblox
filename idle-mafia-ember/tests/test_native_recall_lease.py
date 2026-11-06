"""Bound Recall counter/opaque pending ownership without invoking native workers."""
import unittest
from pathlib import Path
from engine_harness import Harness,lua_table,ROOT

class NativeRecallLeaseTests(unittest.TestCase):
    def setUp(self):
        self.h=Harness();self.path=ROOT/'src/tabs/territory/NativeRecallLease.luau'
        self.port=self.h.lua.execute('''return {counter=0,valid=true,serverNow=1000,writes=0,workers=0,
            Current=function(self) return self.valid end,Clock=function(self) return self.serverNow end,
            Read=function(self) if self.readFail then error('read failed') end return {counter=self.counter,pending=self.pending} end,
            Write=function(self,k,v) if self.fail==k then error('write failed') end self.writes=self.writes+1;self[k]=v end,
            NativeStart=function(self) if self.pending then return end self.counter=self.counter+1;self.pending={id=self.counter};self.workers=self.workers+1 end,
            NativeUpdate=function(self,id) if self.pending and self.pending.id==id then self.pending=nil end end}''')
        self.scope=lua_table(self.h.lua,{'account':'user-a','userId':42,'place':self.h.session['place'],'jobId':'job-a','sourceKey':'a'*64})
        self.epoch=lua_table(self.h.lua,{'id':'epoch-a','counterKnown':0,'proven':True})
        self.owner=None
    def new(self):
        self.assertTrue(self.path.is_file(),'Native Recall lease is missing')
        self.module=self.h.load('src/tabs/territory/NativeRecallLease.luau')
        self.owner,why=self.module.new(self.port,self.h.clock,self.scope,self.epoch);self.assertIsNotNone(self.owner,why)
        return self.owner
    def proposal(self):
        if not self.owner:self.new()
        quote,why=self.owner.Quote(self.owner,0);self.assertIsNotNone(quote,why)
        p=self.h.proposal('station','recall:one');p.resources=self.h.lua.table()
        p.intent=lua_table(self.h.lua,{'kind':'territoryRecall','userId':42,'districtId':'d1','memberIndex':2,
            'deploymentId':'deployment-a','at':900,'memberName':'Guard','rarity':4,'memberKey':'id:guard'})
        for key,value in quote.items():p.intent[key]=value
        return p
    def test_pristine_quote_and_cas_claim_advance_counter_without_native_worker(self):
        p=self.proposal();self.assertEqual((p.intent.requestId,self.port.writes),(1000000,0))
        self.assertTrue(self.owner.Acquire(self.owner,p,45)[0]);self.assertTrue(self.owner.Owns(self.owner,p))
        self.port.NativeStart(self.port);self.assertEqual((self.port.counter,self.port.workers),(1000000,0))
        self.assertTrue(self.owner.Release(self.owner,p)[0]);self.assertIsNone(self.port.pending);self.assertEqual(self.port.counter,1000000)
    def test_unknown_prior_native_counter_or_changed_counter_refuses_adoption(self):
        self.epoch.proven=False;self.port.counter=12;self.epoch.counterKnown=12;self.new()
        self.assertIsNone(self.owner.Quote(self.owner,0)[0]);self.assertEqual(self.port.writes,0)
        self.setUp();self.new();self.port.counter=1
        self.assertIsNone(self.owner.Quote(self.owner,0)[0]);self.assertTrue(self.epoch.retired)
    def test_foreign_native_winning_quote_race_is_never_overwritten(self):
        p=self.proposal();self.port.NativeStart(self.port);native=self.port.pending
        self.assertFalse(self.owner.Acquire(self.owner,p,45)[0]);self.assertEqual(self.port.writes,0)
        self.assertTrue(self.h.lua.eval('function(a,b) return a==b end')(native,self.port.pending))
    def test_native_update_cannot_clear_opaque_hub_token_with_wire_request_id(self):
        p=self.proposal();self.assertTrue(self.owner.Acquire(self.owner,p,45)[0])
        self.port.NativeUpdate(self.port,p.intent.requestId);self.assertTrue(self.owner.Owns(self.owner,p))
        self.assertEqual(self.h.lua.eval('type')(self.port.pending.id),'table')
    def test_durable_highwater_and_native_server_clock_both_bound_wire_identity(self):
        self.new();quote,why=self.owner.Quote(self.owner,2000000);self.assertIsNotNone(quote,why)
        self.assertEqual(quote.requestId,2000001);self.assertEqual(quote.nativeCounterBefore,0)
        self.assertEqual((quote.nativeJob,quote.nativeEpoch,quote.nativeSourceKey),('job-a','epoch-a','a'*64))
    def test_wrong_name_user_epoch_job_or_source_cannot_claim(self):
        for field,value in (('userId',43),('nativeJob','other'),('nativeEpoch','other'),('nativeSourceKey','b'*64)):
            self.setUp();p=self.proposal();p.intent[field]=value
            self.assertFalse(self.owner.Acquire(self.owner,p,45)[0]);self.assertEqual(self.port.writes,0)
        self.setUp();p=self.proposal();p.account='other';self.assertFalse(self.owner.Acquire(self.owner,p,45)[0])
    def test_expiry_and_current_source_loss_still_allow_only_exact_token_cleanup(self):
        p=self.proposal();self.assertTrue(self.owner.Acquire(self.owner,p,45)[0]);self.h.at(45);self.port.valid=False
        self.assertFalse(self.owner.Owns(self.owner,p));self.assertTrue(self.owner.Release(self.owner,p)[0])
        self.assertIsNone(self.port.pending);self.assertEqual(self.port.counter,1000000)
    def test_newer_foreign_token_and_counter_are_not_cleared_on_close(self):
        p=self.proposal();self.owner.Acquire(self.owner,p,45)
        foreign=self.h.lua.table();self.port.pending=foreign;self.port.counter=1000001
        self.owner.Close(self.owner);self.assertTrue(self.h.lua.eval('function(a,b) return a==b end')(foreign,self.port.pending))
        self.assertEqual(self.port.counter,1000001)
    def test_partial_write_and_cleanup_read_failure_retain_retryable_ownership(self):
        p=self.proposal();self.port.fail='counter';self.assertFalse(self.owner.Acquire(self.owner,p,45)[0]);self.assertIsNone(self.port.pending)
        self.port.fail=None;self.assertTrue(self.owner.Acquire(self.owner,p,45)[0]);self.port.readFail=True
        self.assertFalse(self.owner.Release(self.owner,p)[0]);self.assertIsNotNone(self.epoch.live)
        self.port.readFail=False;self.assertTrue(self.owner.Release(self.owner,p)[0])
    def test_same_epoch_status_hold_does_not_allocate_or_submit_again(self):
        p=self.proposal();self.owner.Acquire(self.owner,p,45);self.owner.Release(self.owner,p)
        self.assertTrue(self.owner.AcquireStatus(self.owner,p,45)[0]);self.assertEqual(self.port.counter,1000000)
        self.port.NativeStart(self.port);self.assertEqual(self.port.workers,0)
        self.owner.Release(self.owner,p);self.assertEqual(self.port.counter,1000000)
