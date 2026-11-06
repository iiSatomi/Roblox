"""A strict checkpoint needs literal durable success before it can admit sends."""
import unittest

from engine_harness import lua_table
import test_pending_action as snapshots


class CheckpointStrictWriteTests(unittest.TestCase):
    def setUp(self):
        fixture=snapshots.PendingActionSnapshotTests()
        fixture.setUp()
        self.h=fixture.h
        self.proposal,self.before,self.baseline=fixture.action(inventory_size=1)
        self.pending=fixture.pending
        self.module=self.h.load('src/storage/Checkpoint.luau')
        self.store=self.h.lua.execute('''return {data={},strictRecovery=true,mode='true',
            hash=function() return string.rep('a',64) end,
            Read=function(self,key) return self.data[key] end,
            Write=function(self,key,value)
                if self.mode=='throw' then error('refused') end
                if self.mode=='nil' then return nil end
                if self.mode=='false' then return false end
                self.data[key]=value
                if self.mode=='write_throw' then error('after write') end
                if self.mode=='write_nil' then return nil end
                return true
            end}''')
        self.cp=self.new_owner()

    def new_owner(self):
        owner=self.module.new(self.store,None,None,self.pending)
        _,reason=owner.Load(owner,self.h.session['account'],self.h.session['place'],self.h.session['release'])
        self.assertIsNone(reason)
        return owner

    def test_nontrue_main_save_faults_without_advancing_local_records_or_authorizing_send(self):
        for mode in ('nil','false','throw','write_nil','write_throw'):
            with self.subTest(mode=mode):
                self.setUp();self.store.mode=mode
                saved,reason=self.cp.Save(self.cp,self.proposal,self.before,self.baseline)
                self.assertFalse(saved)
                self.assertIsNotNone(reason)
                self.assertIsNotNone(self.cp.fault)
                self.assertEqual(len(self.cp.Records(self.cp)),0)
                self.assertEqual(self.cp.requestHighwater,0)
                self.assertEqual(self.proposal.checkpointRequestId,1)
                restored=self.new_owner()
                committed=mode.startswith('write_')
                self.assertEqual(len(restored.Records(restored)),1 if committed else 0)
                self.assertEqual(restored.requestHighwater,1 if committed else 0)
                if committed:
                    data=restored.Recovery(restored,self.proposal.actionKey)[0]
                    self.assertIsNone(data.reply)
                    self.assertFalse(restored.KnownUnsent(restored,restored.Records(restored)[1]))
                else:
                    self.assertFalse(self.cp.RecordUnsent(self.cp,self.proposal,self.before,self.baseline)[0])

    def test_real_broker_does_not_enter_transport_after_nil_checkpoint_write(self):
        self.h.broker.policy.captureBefore=self.h.load('src/features/JobsEvidence.luau').capture
        session=self.h.load('src/engine/Session.luau').new(
            self.h.broker,self.cp,lua_table(self.h.lua,self.h.session))
        self.store.mode='nil'
        self.assertEqual(session.Offer(session,self.proposal,self.before)[0],'admitted')
        self.assertEqual(session.Tick(session,self.before),'checkpoint_failed')
        self.assertEqual(len(self.h.transport.sent),0)
        self.assertTrue(session.Status(session).storageFault)

    def test_stale_owner_cannot_write_or_claim_another_owner_numbered_unsent_fact(self):
        stale=self.new_owner()
        self.assertTrue(self.cp.Save(self.cp,self.proposal,self.before,self.baseline)[0])
        losing=self.pending.Decode(self.cp.Records(self.cp,True)[1].recovery).proposal
        losing.actionKey='jobs:different'
        saved,reason=stale.Save(stale,losing,self.before,self.baseline)
        self.assertFalse(saved)
        self.assertIsNotNone(reason)
        self.assertIsNone(losing.checkpointRequestId)
        self.assertFalse(stale.RecordUnsent(stale,losing,self.before,self.baseline)[0])
        restored=self.new_owner()
        self.assertEqual(restored.Records(restored)[1].actionKey,self.proposal.actionKey)

    def test_reply_and_clear_writes_require_true_and_keep_prior_state_on_failure(self):
        for mode in ('nil','false','throw','write_nil','write_throw'):
            for operation in ('reply','clear'):
                with self.subTest(mode=mode,operation=operation):
                    self.setUp()
                    self.assertTrue(self.cp.Save(self.cp,self.proposal,self.before,self.baseline)[0])
                    self.store.mode=mode
                    if operation=='reply':
                        result=self.cp.RecordReply(self.cp,self.proposal.actionKey,lua_table(self.h.lua,{'ok':True}))
                    else: result=self.cp.Resolve(self.cp,self.proposal.actionKey,'confirmed')
                    self.assertFalse(result[0])
                    self.assertIsNotNone(self.cp.fault)
                    self.assertEqual(len(self.cp.Records(self.cp)),1)
                    self.assertIsNone(self.pending.Decode(self.cp.Records(self.cp,True)[1].recovery).reply)
                    restored=self.new_owner()
                    if operation=='clear' and mode.startswith('write_'):
                        self.assertEqual(len(restored.Records(restored)),0)
                    else:
                        self.assertEqual(len(restored.Records(restored)),1)
                        data=restored.Recovery(restored,self.proposal.actionKey)[0]
                        self.assertEqual(data.reply is not None,operation=='reply' and mode.startswith('write_'))


if __name__=='__main__': unittest.main()
