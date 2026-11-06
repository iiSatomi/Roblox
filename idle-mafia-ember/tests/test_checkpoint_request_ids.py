"""Each write-ahead attempt has a durable identity, distinct from native sequence."""
import unittest
import hashlib
from engine_harness import Harness, lua_table


class CheckpointRequestIdsTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.pending = self.h.load('src/storage/PendingAction.luau')
        self.module = self.h.load('src/storage/Checkpoint.luau')
        self.storage = self.h.lua.execute('''return {strictRecovery=true,data={},
            Read=function(self,key) return self.data[key] end,
            Write=function(self,key,value) self.data[key]=value; return true end}''')
        self.cp = self.new()
        self.h.lua.globals().requestHash = lambda value: hashlib.sha256(value.encode()).hexdigest()
        self.storage.hash = self.h.lua.eval('function(value) return requestHash(value) end')

    def new(self):
        cp = self.module.new(self.storage,None,None,self.pending)
        self.assertIsNone(cp.Load(cp,'user-a',self.h.session['place'],'release-a')[1])
        return cp

    def save(self, cp=None, proposal=None):
        cp = cp or self.cp
        proposal = proposal or self.h.proposal()
        result = cp.Save(cp,proposal,
            self.h.snapshot(native={'fullSync':True}),lua_table(self.h.lua,{'before':1}))
        return (*result,proposal.checkpointRequestId)

    def test_reusing_same_action_key_after_unsent_cleanup_gets_a_new_id_even_after_reload(self):
        self.assertEqual(self.save(),(True,None,1))
        record = self.cp.Records(self.cp)[1]
        self.assertEqual(record.requestId,1)
        self.assertEqual(self.cp.Recovery(self.cp,record.actionKey)[0].proposal.requestId,1)
        self.assertTrue(self.cp.Resolve(self.cp,record.actionKey,'schedule_failed')[0])
        cp = self.new()
        self.assertEqual(cp.requestHighwater,1)
        self.assertEqual(self.save(cp),(True,None,2))

    def test_caller_cannot_choose_identity_and_reply_resolve_commits_preserve_highwater(self):
        proposal = self.h.proposal()
        proposal.requestId = 999
        self.assertEqual(self.save(proposal=proposal),(True,None,1))
        self.assertTrue(self.cp.RecordReply(self.cp,proposal.actionKey,lua_table(self.h.lua,{'ok':True}))[0])
        self.assertEqual(self.cp.Records(self.cp)[1].requestId,1)
        self.assertTrue(self.cp.Resolve(self.cp,proposal.actionKey,'confirmed')[0])
        self.assertEqual(self.new().requestHighwater,1)

    def test_legacy_record_loads_without_identity_and_next_save_is_numbered(self):
        self.assertTrue(self.save()[0])
        key = self.cp.ScopeKey(self.cp)
        stored = self.storage.data[key]
        data = self.pending.Decode(stored.records[1].recovery,stored.records[1])
        data.proposal.requestId = None
        stored.records[1].recovery = self.pending.Capture(data.proposal,data.before,data.baseline)[0]
        stored.records[1].requestId = None
        stored.requestHighwater = None
        cp = self.new()
        self.assertIsNone(cp.Records(cp)[1].requestId)
        self.assertEqual(self.save(cp,self.h.proposal('operations','other')),(True,None,1))

    def test_bad_highwater_or_mismatched_pending_id_refuses_load(self):
        self.assertTrue(self.save()[0])
        key = self.cp.ScopeKey(self.cp)
        stored = self.storage.data[key]
        for value in (-1,0,1.5,9007199254740992,True):
            stored.requestHighwater = value
            cp = self.module.new(self.storage,None,None,self.pending)
            self.assertIsNone(cp.Load(cp,'user-a',self.h.session['place'],'release-a')[0])
        stored.requestHighwater = 2
        stored.records[1].requestId = 2
        cp = self.module.new(self.storage,None,None,self.pending)
        self.assertIsNone(cp.Load(cp,'user-a',self.h.session['place'],'release-a')[0])

    def test_ambiguous_write_returns_attempt_id_but_exhaustion_never_writes(self):
        self.storage.Write = self.h.lua.eval('''function(self,key,value)
            self.data[key]=value; return false end''')
        ok,reason,attempt = self.save()
        self.assertFalse(ok)
        self.assertEqual(attempt,1)
        self.assertIn('write',reason)
        self.storage.Write = self.h.lua.eval('function(self,key,value) error("must not write") end')
        self.storage.data[self.cp.ScopeKey(self.cp)].requestHighwater = 9007199254740991
        cp = self.new()
        self.assertTrue(cp.Resolve is not None)
        result = self.save(cp,self.h.proposal('operations','other'))
        self.assertFalse(result[0])
        self.assertIn('exhausted',result[1])

    def test_append_only_unsent_fact_matches_only_exact_numbered_baseline(self):
        proposal = self.h.proposal()
        before = self.h.snapshot(native={'fullSync':True})
        baseline = lua_table(self.h.lua,{'before':1})
        self.assertTrue(self.cp.Save(self.cp,proposal,before,baseline)[0])
        record = self.cp.Records(self.cp)[1]
        stored = self.storage.data[self.cp.ScopeKey(self.cp)]
        self.assertTrue(self.cp.RecordUnsent(self.cp,proposal,before,baseline)[0])
        self.assertTrue(self.cp.KnownUnsent(self.cp,record))
        self.assertTrue(self.h.lua.eval('function(a,b) return a==b end')(
            stored,self.storage.data[self.cp.ScopeKey(self.cp)]))
        self.assertTrue(self.cp.Resolve(self.cp,proposal.actionKey,'schedule_failed')[0])
        self.assertTrue(self.cp.Save(self.cp,proposal,before,baseline)[0])
        self.assertFalse(self.cp.KnownUnsent(self.cp,self.cp.Records(self.cp)[1]))

    def test_unsent_fact_cannot_clear_returned_or_changed_baseline(self):
        proposal = self.h.proposal()
        before = self.h.snapshot(native={'fullSync':True})
        baseline = lua_table(self.h.lua,{'before':1})
        self.assertTrue(self.cp.Save(self.cp,proposal,before,baseline)[0])
        self.assertTrue(self.cp.RecordUnsent(self.cp,proposal,before,baseline)[0])
        self.assertTrue(self.cp.RecordReply(self.cp,proposal.actionKey,lua_table(self.h.lua,{'ok':True}))[0])
        self.assertFalse(self.cp.KnownUnsent(self.cp,self.cp.Records(self.cp)[1]))
        baseline.before = 2
        self.assertFalse(self.cp.RecordUnsent(self.cp,proposal,before,baseline)[0])

    def test_unsent_fact_requires_storage_hash_and_trusted_attempt_id(self):
        proposal = self.h.proposal()
        before = self.h.snapshot(native={'fullSync':True})
        baseline = lua_table(self.h.lua,{'before':1})
        self.assertFalse(self.cp.RecordUnsent(self.cp,proposal,before,baseline)[0])
        self.assertTrue(self.cp.Save(self.cp,proposal,before,baseline)[0])
        self.storage.hash = None
        self.assertFalse(self.cp.RecordUnsent(self.cp,proposal,before,baseline)[0])

    def test_failed_main_write_cannot_leave_a_fact_aliasing_same_number_retry(self):
        proposal = self.h.proposal()
        before = self.h.snapshot(native={'fullSync':True})
        baseline = lua_table(self.h.lua,{'before':1})
        self.storage.Write = self.h.lua.eval('''function(self,key,value)
            if key:find(':checkpoint:',1,true) then return false end
            self.data[key]=value; return true end''')
        self.assertFalse(self.cp.Save(self.cp,proposal,before,baseline)[0])
        self.assertEqual(proposal.checkpointRequestId,1)
        self.assertFalse(self.cp.RecordUnsent(self.cp,proposal,before,baseline)[0])
        self.storage.Write = self.h.lua.eval('function(self,key,value) self.data[key]=value; return true end')
        cp = self.new()
        self.assertTrue(cp.Save(cp,proposal,before,baseline)[0])
        self.assertEqual(proposal.checkpointRequestId,1)
        self.assertFalse(cp.KnownUnsent(cp,cp.Records(cp)[1]))


    def test_stale_loaded_checkpoint_cannot_overwrite_or_receipt_a_newer_attempt(self):
        stale = self.new()
        proposal = self.h.proposal()
        before = self.h.snapshot(native={'fullSync':True})
        baseline = lua_table(self.h.lua,{'before':1})
        self.assertTrue(self.cp.Save(self.cp,proposal,before,baseline)[0])
        retry = self.h.proposal()
        self.assertFalse(stale.Save(stale,retry,before,baseline)[0])
        self.assertIsNone(retry.checkpointRequestId)
        self.assertFalse(stale.RecordUnsent(stale,retry,before,baseline)[0])
        fresh = self.new()
        self.assertFalse(fresh.KnownUnsent(fresh,fresh.Records(fresh)[1]))


if __name__ == '__main__': unittest.main()
