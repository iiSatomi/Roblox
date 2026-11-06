"""Terminal-only sequence continuation; no mutation replay."""
import unittest
from engine_harness import Harness,lua_table

class HeistProtocolTests(unittest.TestCase):
    def setUp(self):
        self.h=Harness();h=self.h
        self.port=h.lua.execute("return {counter=4,running=false,valid=true,Current=function(s) return s.valid end,Read=function(s) return {counter=s.counter,pending=s.pending,running=s.running} end,Write=function(s,k,v) s[k]=v end}")
        scope=lua_table(h.lua,{'account':'user-a','place':h.session['place'],'jobId':'job-a','sourceKey':'a'*64})
        self.lease=h.load('src/tabs/heists/NativeHeistLease.luau').new(self.port,h.clock,scope,lua_table(h.lua,{'id':'epoch-a','counterSeen':4}))[0]
        self.cp=h.lua.execute("return {rows={},data={},Records=function(s) return s.rows end,Recovery=function(s,k) return s.data[k] end,RecordReply=function(s,k,r) s.saved=(s.saved or 0)+1;s.data[k].reply=r;return true end,KnownUnsent=function() return false end}")
        self.protocol=h.load('src/tabs/heists/HeistProtocol.luau').new(lua_table(h.lua,{'lease':self.lease,'clock':h.clock,'identity':h.session}))
        self.protocol.BindCheckpoint(self.protocol,self.cp)
        self.p=lua_table(h.lua,{**h.session,'revision':1,'feature':'heists','actionKey':'heists:one','resources':{},'intent':{'kind':'heistStart','heistId':'h_a','sequence':5,'nativeJob':'job-a','nativeEpoch':'epoch-a','nativeSourceKey':'a'*64,'needsSequence':True}})
        self.spec=self.protocol.Wrap(self.protocol,lua_table(h.lua,{'id':'heists','reader':{'read':h.lua.eval('function(raw) return {} end')},'planner':{'propose':h.lua.eval('function() return nil end')},'evidence':{'capture':h.lua.eval('function() return {} end'),'evaluate':h.lua.eval('function() return "pending" end')}}))
        self.before=h.snapshot()
    def begin(self):
        self.assertTrue(self.spec.lifecycle.prepare(self.p,self.before,self.h.lua.table(),0)[0])
    def test_pending_no_pending_then_terminal_delivers_only_once(self):
        self.begin();out=self.h.lua.table();self.h.lua.globals().protocolReplies=out
        callback=self.h.lua.eval('function(r) protocolReplies[#protocolReplies+1]=r end')
        self.protocol.Returned(self.protocol,self.p,lua_table(self.h.lua,{'pending':True}),callback)
        self.assertEqual(len(out),0)
        call,_=self.protocol.StatusCall(self.protocol);self.assertEqual(call.args[1],'status');self.assertEqual(call.args[3],5)
        self.protocol.AcceptStatus(self.protocol,call,lua_table(self.h.lua,{'ok':False,'code':'no_pending'}));self.assertEqual(len(out),0)
        self.protocol.AcceptStatus(self.protocol,call,lua_table(self.h.lua,{'ok':True,'runId':'run-a'}));self.assertEqual(len(out),1)
        self.protocol.AcceptStatus(self.protocol,call,lua_table(self.h.lua,{'ok':False}));self.assertEqual(len(out),1)
        self.assertEqual(self.port.counter,5)
    def test_one_shared_checkpoint_blocks_all_four_features(self):
        self.cp.rows[1]=lua_table(self.h.lua,{'feature':'favors','actionKey':'old'})
        result=self.spec.lifecycle.prepare(self.p,self.before,self.h.lua.table(),0)
        self.assertFalse(result[0]);self.assertEqual(result[2],'controller_wait');self.assertEqual(self.port.counter,4)
    def test_native_race_is_expected_contention_and_does_not_overwrite(self):
        self.port.counter=5
        result=self.spec.lifecycle.prepare(self.p,self.before,self.h.lua.table(),0)
        self.assertFalse(result[0]);self.assertEqual(result[2],'controller_wait');self.assertIsNone(self.port.pending)
    def test_release_after_expiry_preserves_sequence_and_fences_late_reply(self):
        self.begin();self.h.at(45);self.protocol.Release(self.protocol,self.p)
        self.h.lua.globals().late=0
        self.protocol.Returned(self.protocol,self.p,lua_table(self.h.lua,{'ok':True}),self.h.lua.eval('function() late=late+1 end'))
        self.assertIsNone(self.port.pending);self.assertEqual(self.port.counter,5);self.assertEqual(self.h.lua.globals().late,0)
    def test_saved_status_recovery_requires_original_native_epoch(self):
        self.cp.rows[1]=lua_table(self.h.lua,{'feature':'heists','actionKey':'heists:one'})
        self.cp.data['heists:one']=lua_table(self.h.lua,{'proposal':self.p,'before':self.before,'baseline':{}})
        call,why=self.protocol.StatusCall(self.protocol);self.assertIsNotNone(call,why)
        self.protocol.AcceptStatus(self.protocol,call,lua_table(self.h.lua,{'ok':True,'runId':'run-a'}));self.assertEqual(self.cp.saved,1)
        self.cp.data['heists:one'].reply=None;self.p.intent.nativeEpoch='other'
        self.assertIsNone(self.protocol.StatusCall(self.protocol)[0]);self.assertEqual(self.cp.saved,1)
    def test_numeric_row_identity_and_nil_collect_middle_argument(self):
        self.p.feature='favors';self.p.intent.kind='favorHelp';self.p.intent.rowId=42
        self.begin();call=self.spec.lifecycle.authorize(self.p,self.before,0);self.assertEqual(call.args[2],42)
        self.protocol.Release(self.protocol,self.p)
        self.p.feature='heistCollect';self.p.intent.kind='heistCollect';self.p.intent.sequence=6
        self.begin();call=self.spec.lifecycle.authorize(self.p,self.before,0);self.assertIsNone(call.args[2]);self.assertEqual(call.arity,3)
    def test_source_owned_proof_removes_forged_injected_quote(self):
        raw=self.h.snapshot(native={'fullSync':True},heistProtocolProof={'quote':{'sequence':999}})
        enriched=self.protocol.Enrich(self.protocol,raw)
        self.assertEqual(enriched.heistProtocolProof.quote.sequence,5)
        self.assertEqual(enriched.heistProtocolProof.controllerCounter,4)
        self.assertEqual(enriched.heistProtocolProof.revision,raw.revision)
    def test_close_releases_exact_native_token(self):
        self.begin();self.protocol.Close(self.protocol);self.assertIsNone(self.port.pending);self.assertFalse(self.port.running)
        self.assertIsNone(self.protocol.StatusCall(self.protocol)[0])

    def test_same_vm_hard_stop_expires_old_exact_token_even_with_unresolved_checkpoint(self):
        self.begin();self.cp.rows[1]=lua_table(self.h.lua,{'feature':'heists','actionKey':'heists:one'})
        self.cp.data['heists:one']=lua_table(self.h.lua,{'proposal':self.p,'before':self.before,'baseline':{}})
        fresh=self.h.load('src/tabs/heists/NativeHeistLease.luau').new(self.port,self.h.clock,self.lease.scope,self.lease.epoch)[0]
        owner=self.h.load('src/tabs/heists/HeistProtocol.luau').new(lua_table(self.h.lua,{'lease':fresh,'clock':self.h.clock,'identity':self.h.session}));owner.BindCheckpoint(owner,self.cp)
        self.h.at(46);owner.Enrich(owner,self.h.snapshot(native={'fullSync':True}))
        self.assertIsNone(self.port.pending);self.assertFalse(self.port.running);self.assertEqual(self.port.counter,5)
        self.assertEqual(len(self.cp.rows),1);self.assertIsNone(self.lease.epoch.live)
