"""Actual shared dispatch binds the leased outgoing call before staged observations."""
import unittest
import test_fight_receipts as fixture
from engine_harness import lua_table

class FightReceiptDispatchTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.FightReceiptTests();self.f.setUp();self.h=self.f.h
        self.f.lane.Release(self.f.lane,self.f.token,"fixture")
        self.h.lua.globals().fightReply=lua_table(self.h.lua,self.f.initial)
        self.executor=self.h.lua.execute("""return {queued={},calls=0,
            Schedule=function(self,fn) self.queued[#self.queued+1]=fn;return true end,
            Invoke=function() error('unowned') end,
            InvokeOwned=function(self,token,remote,method,target)
                self.calls=self.calls+1;assert(remote=='Attack' and target==42)
                if self.emit then self.emit() end
                if self.interrupted then error('interrupted') end
                return fightReply
            end}""")
        self.plan=self.h.lua.execute("""return {describe=function(p) return {
            remote='Attack',method='InvokeServer',arity=1,args={p.intent.target}} end}""")
        self.module=self.h.load("src/transport/NativeDispatchAdapter.luau")
        self.transport=self.module.new(self.plan,self.executor,self.f.lane,self.h.clock,self.f.owner)
        self.h.lua.globals().fightAllowed=True
        self.h.lua.globals().receiptReturned=0
    def send(self):
        return self.transport.Send(self.transport,self.f.proposal,self.h.lua.eval("function() receiptReturned=receiptReturned+1 end"),self.h.lua.eval("function() return fightAllowed end"))
    def drain(self):
        self.executor.queued[1]()
    def test_initial_reply_and_final_notification_reach_same_owned_transport_proof(self):
        self.assertTrue(self.send());self.drain()
        self.assertEqual(self.f.read().attempts[1].receipt.cashStage,1)
        self.f.emit(self.f.frames[-1]);self.assertEqual(self.f.read().attempts[1].status,"settled")
        self.assertEqual(self.executor.calls,1);self.assertEqual(self.h.lua.globals().receiptReturned,1)
        self.transport.ReleaseResolved(self.transport,self.f.proposal,"confirmed")
        self.assertEqual(len(self.f.read().attempts),0)
    def test_buffered_pre_return_packet_is_matched_only_after_owned_initial_reply(self):
        self.executor.emit=lambda:self.f.emit(self.f.frames[-1])
        self.send();self.drain();self.assertEqual(self.f.read().attempts[1].status,"settled")
    def test_queued_disable_never_subscribes_or_invokes(self):
        self.send();self.h.lua.globals().fightAllowed=False;self.drain()
        self.assertEqual(self.executor.calls,0);self.assertIsNone(self.f.source.callback)
    def test_source_change_between_queue_and_send_refuses_the_physical_call(self):
        self.send();self.f.source.Current=self.h.lua.eval("function() return false end");self.drain()
        self.assertEqual(self.executor.calls,0)
    def test_missing_receipt_owner_refuses_validation(self):
        transport=self.module.new(self.plan,self.executor,self.f.lane,self.h.clock)
        self.assertFalse(transport.Validate(transport,self.f.proposal)[0])
    def test_expired_send_keeps_reply_unconfirmed_and_cannot_promote_after_45(self):
        self.executor.emit=lambda:self.h.at(45)
        self.send();self.drain();self.assertEqual(self.h.lua.globals().receiptReturned,0)
        self.assertEqual(len(self.f.read().attempts),0)
    def test_interruption_never_fabricates_initial_reply_or_replays(self):
        self.executor.interrupted=True;self.send();self.drain()
        self.assertEqual(self.executor.calls,1);self.assertEqual(len(self.f.read().attempts),0)
        self.assertTrue(self.transport.ReleaseExpired(self.transport,self.f.proposal))
        self.assertEqual(self.executor.calls,1)

    def test_failed_receipt_observer_cannot_discard_the_actual_initial_reply(self):
        self.f.owner.Bind=self.h.lua.eval("function() error('observer failed') end")
        self.send();self.drain()
        self.assertEqual(self.executor.calls,1);self.assertEqual(self.h.lua.globals().receiptReturned,1)

    def test_native_preflight_warning_prevents_subscription_and_physical_attack(self):
        self.f.source.CanAttack=self.h.lua.eval("function() return false,'Native warning' end")
        self.send();self.drain()
        self.assertEqual(self.executor.calls,0);self.assertIsNone(self.f.source.callback)
