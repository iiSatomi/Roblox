"""Name/UserId source binding, stable member identity and durable Recall fences."""
import unittest
from engine_harness import lua_table
from recall_source_fixture import make_recall_client

class RecallOwnedTransactionsTests(unittest.TestCase):
    def setUp(self):
        self.h,self.f=make_recall_client();self.leases=self.h.load('src/tabs/territory/NativeRecallLease.luau')
        self.lease,why=self.leases.bind(lua_table(self.h.lua,{'game':self.f.game,'env':self.f.env,'registry':self.f.registry,
            'requireModule':self.f.requireModule,'clock':self.h.clock,'account':'user-a'}));self.assertIsNotNone(self.lease,why)
        self.module=self.h.load('src/tabs/territory/RecallTransactions.luau')
        self.storage=self.h.lua.execute('''return {strictRecovery=true,data={},Read=function(self,k) return self.data[k] end,
            Write=function(self,k,v) if self.yieldWrite then coroutine.yield('recall-save') end self.data[k]=v;return not self.fail end}''')
        self.scope=lua_table(self.h.lua,{**self.h.session,'userId':42})
        self.terms=lua_table(self.h.lua,{'release':'release-a','recallCooldownSeconds':600})
        self.tx=None
    def new(self):
        owner,why=self.module.new(self.storage,self.scope,self.terms,self.lease)
        self.assertIsNotNone(owner,why);self.tx=owner;return owner
    def raw(self,revision=1,home=False):
        member={'name':'Guard','rarity':4,'train':2,'healId':'guard','injuredUntil':0,'recalledUntil':0}
        if not home:member.update(duty='d1',dutyToken='deployment-a',dutyAt=900)
        return self.h.snapshot(revision=revision,native={'fullSync':True,'serverNow':1000+revision-1,'userId':42,
            'family':{'id':'own-family'},'crew':[{'name':'Player'},member,{'name':'Medic','rarity':3,'train':1,'healId':'medic'}]})
    def proposal(self):
        if not self.tx:self.new()
        quote,why=self.lease.Quote(self.lease,self.tx.LastRequestId(self.tx));self.assertIsNotNone(quote,why)
        p=self.h.proposal('station','recall:guard');p.resources=self.h.lua.table();p.intent=self.h.lua.table(kind='territoryRecall',memberKey='id:guard',maxAttempts=2,attemptedBefore=0)
        for key,value in self.f.target.items():p.intent[key]=value
        for key,value in quote.items():p.intent[key]=value
        return p
    def prepare(self):
        p=self.proposal();ok,why=self.tx.Prepare(self.tx,p,self.raw(),0);self.assertTrue(ok,why);return p
    def send(self):
        p=self.prepare();self.assertTrue(self.tx.MarkSending(self.tx,self.raw(),0)[0]);return p
    def reply(self):return lua_table(self.h.lua,{'ok':True,'settled':[self.f.target]})
    def test_bound_name_and_numeric_native_user_are_distinct_and_both_required(self):
        self.new();p=self.prepare();self.assertEqual((self.tx.Active(self.tx).account,self.tx.Active(self.tx).userId),('user-a',42))
        self.assertIsNone(self.module.new(self.storage,self.scope,self.terms)[0])
        self.scope.userId=43;self.assertIsNone(self.module.new(self.storage,self.scope,self.terms,self.lease)[0])
        self.assertEqual(p.account,'user-a')
    def test_wrong_snapshot_user_or_epoch_and_changed_healid_refuse_prepare_or_send(self):
        p=self.proposal();raw=self.raw();raw.native.userId=43
        self.assertFalse(self.tx.Prepare(self.tx,p,raw,0)[0])
        p.intent.nativeEpoch='other';self.assertFalse(self.tx.Prepare(self.tx,p,self.raw(),0)[0])
        self.setUp();p=self.prepare();raw=self.raw();raw.native.crew[2].healId='replacement'
        self.assertFalse(self.tx.MarkSending(self.tx,raw,0)[0])
    def test_exact_settlement_needs_same_stable_member_return_and_preserves_attempts(self):
        p=self.send();self.assertTrue(self.tx.AcceptReply(self.tx,p.intent.requestId,self.reply())[0])
        after=self.raw(2,True);after.native.crew[2].healId='replacement'
        self.assertNotEqual(self.tx.Reconcile(self.tx,after)[0],'observed')
        after.native.crew[2].healId='guard';self.assertEqual(self.tx.Reconcile(self.tx,after)[0],'observed')
        self.assertTrue(self.tx.ClearObserved(self.tx)[0]);self.assertEqual(self.tx.Usage(self.tx).attempted,1)
    def test_stale_owner_cannot_replace_newer_prepared_record(self):
        old=self.new();p=self.proposal();new=self.new()
        self.assertTrue(new.Prepare(new,p,self.raw(),0)[0])
        self.assertFalse(old.Prepare(old,p,self.raw(),0)[0]);self.assertIsNotNone(new.Active(new))
    def test_ambiguous_write_fault_holds_durable_record_on_reload(self):
        p=self.proposal();self.storage.fail=True
        self.assertFalse(self.tx.Prepare(self.tx,p,self.raw(),0)[0]);self.assertIsNotNone(self.tx.fault)
        self.storage.fail=False;new=self.new();self.assertEqual(new.Active(new).stage,'prepared')
        self.assertEqual(new.Usage(new).attempted,1)
    def test_known_unsent_cleanup_refunds_attempt_but_sent_unknown_keeps_it(self):
        self.prepare();self.assertTrue(self.tx.DiscardPrepared(self.tx)[0]);self.assertEqual(self.tx.Usage(self.tx).attempted,0)
        self.setUp();self.send();self.assertFalse(self.tx.DiscardPrepared(self.tx)[0]);self.assertEqual(self.tx.Usage(self.tx).attempted,1)
    def test_yielding_write_prevents_new_owner_and_close_does_not_rearm_emission(self):
        p=self.proposal();self.storage.yieldWrite=True;self.h.lua.globals().recallTx=self.tx;self.h.lua.globals().recallP=p;self.h.lua.globals().recallRaw=self.raw()
        self.assertEqual(self.h.lua.execute('recallSave=coroutine.create(function() return recallTx:Prepare(recallP,recallRaw,0) end);local ok,v=coroutine.resume(recallSave);assert(ok);return v'),'recall-save')
        self.assertIsNone(self.module.new(self.storage,self.scope,self.terms,self.lease)[0]);self.tx.Close(self.tx)
        self.h.lua.execute('assert(coroutine.resume(recallSave))');self.storage.yieldWrite=False
        new=self.new();self.assertIsNotNone(new.Active(new));self.assertIsNone(new.SubmitCall(new,self.raw(),0)[0])

    def test_capture_uses_exact_wire_target_and_out_of_roster_slot_refuses_cleanly(self):
        p=self.proposal();baseline=self.tx.Capture(self.tx,p,self.raw())
        self.assertIsNotNone(baseline);self.assertEqual(baseline.members['2'].healId,'guard')
        p.intent.memberIndex=4
        self.assertIsNone(self.tx.Capture(self.tx,p,self.raw()))
        self.assertFalse(self.tx.Prepare(self.tx,p,self.raw(),0)[0])

    def test_exact_reply_and_newer_stable_member_effect_confirm_execution_only(self):
        p=self.proposal();baseline=self.tx.Capture(self.tx,p,self.raw())
        self.assertIsNotNone(self.tx.Evaluate,'Recall outcome evaluator is missing')
        self.assertEqual(self.tx.Evaluate(self.tx,p,self.raw(),self.raw(2,True),self.reply(),baseline),'confirmed')
        self.assertEqual(self.tx.Evaluate(self.tx,p,self.raw(),self.raw(2,True),lua_table(self.h.lua,{'ok':True,'pending':True}),baseline),'pending')
        wrong=self.reply();wrong.settled[1].deploymentId='other'
        self.assertEqual(self.tx.Evaluate(self.tx,p,self.raw(),self.raw(2,True),wrong,baseline),'pending')
    def test_explicit_rejection_needs_unchanged_member_and_manual_unknown_stays_pending(self):
        p=self.send();reply=lua_table(self.h.lua,{'ok':False,'code':'deployment_changed'})
        self.assertTrue(self.tx.AcceptReply(self.tx,p.intent.requestId,reply)[0])
        self.assertEqual(self.tx.Reconcile(self.tx,self.raw(2))[0],'rejected')
        self.assertTrue(self.tx.ClearObserved(self.tx)[0]);self.assertEqual(self.tx.Usage(self.tx).attempted,1)
        self.setUp();p=self.proposal();baseline=self.tx.Capture(self.tx,p,self.raw())
        self.assertIsNotNone(self.tx.Evaluate,'Recall outcome evaluator is missing')
        for code in ('presence','busy','unknown_request','rate_limited'):
            self.assertEqual(self.tx.Evaluate(self.tx,p,self.raw(),self.raw(2),lua_table(self.h.lua,{'ok':False,'code':code}),baseline),'pending')

    def test_reloaded_transaction_module_cannot_overtake_a_yielding_old_write(self):
        p=self.proposal();self.storage.yieldWrite=True
        self.h.lua.globals().recallTx=self.tx;self.h.lua.globals().recallP=p;self.h.lua.globals().recallRaw=self.raw()
        self.assertEqual(self.h.lua.execute('recallSave=coroutine.create(function()return recallTx:Prepare(recallP,recallRaw,0)end);local ok,v=coroutine.resume(recallSave);assert(ok);return v'),'recall-save')
        reloaded=self.h.load('src/tabs/territory/RecallTransactions.luau')
        newer=reloaded.new(self.storage,self.scope,self.terms,self.lease)
        self.assertIsNone(newer[0],'Reloaded module bypassed the in-progress durable write fence')
        self.tx.Close(self.tx);self.h.lua.execute('assert(coroutine.resume(recallSave))');self.storage.yieldWrite=False
        new,why=reloaded.new(self.storage,self.scope,self.terms,self.lease);self.assertIsNotNone(new,why)
        self.assertEqual(new.Active(new).stage,'prepared');self.assertEqual(new.Usage(new).attempted,1)

    def test_duplicate_stable_member_ids_refuse_even_with_different_names(self):
        p=self.proposal();raw=self.raw();raw.native.crew[3].healId='guard'
        self.assertIsNone(self.tx.Capture(self.tx,p,raw))
        self.assertFalse(self.tx.Prepare(self.tx,p,raw,0)[0])

    def test_duplicate_names_and_rarities_with_distinct_ids_keep_exact_recall_identity(self):
        p=self.proposal();raw=self.raw();raw.native.crew[3].name='Guard';raw.native.crew[3].rarity=4
        self.f.ctx.State.data=raw.native
        self.assertEqual(len(self.f.api.targets('d1',2)),1,'Captured native Recall supports this exact deployment')
        self.assertIsNotNone(self.tx.ReadState(self.tx,raw));self.assertIsNotNone(self.tx.Capture(self.tx,p,raw))
        self.assertTrue(self.tx.Prepare(self.tx,p,raw,0)[0]);self.assertTrue(self.tx.MarkSending(self.tx,raw,0)[0])
        newer=self.new();self.assertTrue(newer.AcceptReply(newer,p.intent.requestId,self.reply())[0])
        after=self.raw(2,True);after.native.crew[3].name='Guard';after.native.crew[3].rarity=4
        self.assertEqual(newer.Reconcile(newer,after)[0],'observed')

    def test_native_absent_ids_on_unrelated_members_do_not_block_exact_keyed_target(self):
        p=self.proposal();raw=self.raw();raw.native.crew[3].healId=None;self.f.ctx.State.data=raw.native
        self.assertEqual(len(self.f.api.targets('d1',2)),1)
        baseline=self.tx.Capture(self.tx,p,raw);self.assertIsNotNone(baseline)
        self.assertIs(baseline.members['3'].healId,False)
        self.assertTrue(self.tx.Prepare(self.tx,p,raw,0)[0]);self.assertTrue(self.tx.MarkSending(self.tx,raw,0)[0])
        self.assertTrue(self.tx.AcceptReply(self.tx,p.intent.requestId,self.reply())[0])
        after=self.raw(2,True);after.native.crew[3].healId=None
        self.assertEqual(self.tx.Reconcile(self.tx,after)[0],'observed')
    def test_native_absent_selected_id_uses_exact_slot_and_full_saved_roster_on_restart(self):
        p=self.proposal();p.intent.memberKey='slot:2';raw=self.raw();raw.native.crew[2].healId=None;raw.native.crew[3].healId=None
        self.f.ctx.State.data=raw.native;self.assertEqual(len(self.f.api.targets('d1',2)),1)
        baseline=self.tx.Capture(self.tx,p,raw);self.assertIsNotNone(baseline);self.assertIs(baseline.members['2'].healId,False)
        self.assertTrue(self.tx.Prepare(self.tx,p,raw,0)[0]);self.assertTrue(self.tx.MarkSending(self.tx,raw,0)[0])
        newer=self.new();self.assertEqual(newer.Active(newer).memberKey,'slot:2');self.assertTrue(newer.AcceptReply(newer,p.intent.requestId,self.reply())[0])
        after=self.raw(2,True);after.native.crew[2].healId=None;after.native.crew[3].healId=None
        changed=self.raw(2,True);changed.native.crew[2].healId=None;changed.native.crew[3].healId=None;changed.native.crew[3].train=2
        self.assertNotEqual(newer.Reconcile(newer,changed)[0],'observed')
        self.assertEqual(newer.Reconcile(newer,after)[0],'observed')
    def test_absent_key_never_matches_present_id_or_wrong_slot(self):
        p=self.proposal();raw=self.raw();p.intent.memberKey='slot:2'
        self.assertIsNone(self.tx.Capture(self.tx,p,raw))
        raw.native.crew[2].healId=None;p.intent.memberKey='slot:3';self.assertIsNone(self.tx.Capture(self.tx,p,raw))
        p.intent.memberKey='id:guard';self.assertIsNone(self.tx.Capture(self.tx,p,raw))

    def test_absent_id_never_weakens_present_id_or_exact_settlement_proof(self):
        p=self.proposal();p.intent.memberKey='slot:2';raw=self.raw();raw.native.crew[2].healId=None
        self.assertTrue(self.tx.Prepare(self.tx,p,raw,0)[0]);self.assertTrue(self.tx.MarkSending(self.tx,raw,0)[0])
        bad=lua_table(self.h.lua,{'ok':True,'settled':[{**dict(self.f.target.items()),'memberIndex':3}]})
        self.assertFalse(self.tx.AcceptReply(self.tx,p.intent.requestId,bad)[0])
        self.assertTrue(self.tx.AcceptReply(self.tx,p.intent.requestId,self.reply())[0])
        after=self.raw(2,True);self.assertNotEqual(self.tx.Reconcile(self.tx,after)[0],'observed')
        after.native.crew[2].healId=None;after.native.crew[3].healId=None
        self.assertNotEqual(self.tx.Reconcile(self.tx,after)[0],'observed')
    def test_present_malformed_ids_are_not_treated_as_native_absence(self):
        p=self.proposal()
        for value in (False,0,'','bad\nkey'):
            with self.subTest(value=value):
                raw=self.raw();raw.native.crew[3].healId=value
                self.assertIsNone(self.tx.Capture(self.tx,p,raw))
