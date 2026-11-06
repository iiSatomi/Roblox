"""Actual existing Event Shop App fixture, durable outcomes and custody."""
import unittest,hashlib
import test_event_shop as fixture
from engine_harness import lua_table
class EventShopRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.EventShopTests();self.f.setUp()
        self.app,self.runtime,self.executor=self.f.app_runtime();self.h=self.f.h
        self.h.lua.globals().eventRecoveryHash=lambda value:hashlib.sha256(value.encode()).hexdigest()
        self.f.runtime_base.storage.hash=self.h.lua.eval("function(value) return eventRecoveryHash(value) end")
    def tearDown(self):self.app.Destroy(self.app)
    def begin(self,reply=None):
        raw=self.f.raw();self.app.Step(self.app,raw)
        if reply:self.executor.reply=lua_table(self.h.lua,reply)
        self.executor.callback();return raw
    def restart(self):
        self.app.Destroy(self.app)
        self.app,self.runtime,self.executor=self.f.app_runtime(reuse=True)
        self.app.Set(self.app,"eventShop.enabled",False);self.app.Pause(self.app)
    def test_saved_exact_debit_and_award_recovers_without_replay(self):
        self.begin();self.restart();self.h.at(1)
        self.app.Step(self.app,self.f.raw(revision=2,medals=85,bound=1))
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.eventShop,"confirmed")
        self.assertEqual(len(self.executor.calls),0)
        self.assertEqual(self.runtime.checkpoint.EventShopUsage(self.runtime.checkpoint,self.f.raw(revision=2))[0].spent,15)
    def test_pending_negative_does_not_release_unchanged_inventory(self):
        self.begin({"ok":False,"pending":True});self.h.at(1)
        self.app.Step(self.app,self.f.raw(revision=2))
        self.assertIsNone(self.runtime.Status(self.runtime).outcomes.eventShop)
    def test_unconfirmed_purchase_keeps_award_inventory_in_custody(self):
        self.begin({"ok":True,"pending":True});self.h.at(45)
        raw=self.f.raw(revision=2);self.app.Step(self.app,raw)
        self.assertEqual(self.runtime.Status(self.runtime).outcomes.eventShop,"skipped_unconfirmed")
        self.assertTrue(self.runtime.reservationOwner.Held(self.runtime.reservationOwner,raw)[0].allItems)
    def test_saved_partial_award_or_debit_stays_uncertain(self):
        self.begin();self.restart();self.h.at(1)
        self.app.Step(self.app,self.f.raw(revision=2,medals=85))
        self.assertIsNone(self.runtime.Status(self.runtime).recoveries.eventShop)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),1)
    def test_saved_rejection_keeps_both_attempt_and_medal_charge(self):
        self.begin({"ok":False});self.restart();self.h.at(1)
        self.app.Step(self.app,self.f.raw(revision=2))
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.eventShop,"rejected")
        usage=self.runtime.checkpoint.Allowance(self.runtime.checkpoint,"eventShop")[0]
        self.assertEqual((usage.attempted,usage.spent),(1,15))
        self.assertEqual(len(self.executor.calls),0)
    def test_cross_session_revision_reset_requires_newer_native_clock(self):
        self.begin();self.app.Destroy(self.app);self.h.session["session"]="next-run"
        self.app,self.runtime,self.executor=self.f.app_runtime(reuse=True)
        self.app.Set(self.app,"eventShop.enabled",False);self.app.Pause(self.app);self.h.at(1)
        after=self.f.raw(revision=0,medals=85,bound=1);after.native.serverNow=1002
        self.app.Step(self.app,after)
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.eventShop,"confirmed")
        self.assertEqual(len(self.executor.calls),0)
    def test_saved_window_expired_or_attributes_missing_can_observe_exact_effect(self):
        self.begin();self.restart();self.h.at(1)
        self.f.attributes.GlobalEventShop=False
        after=self.f.raw(revision=2,medals=85,bound=1)
        self.f.attributes.GlobalEventShop=None
        self.app.Step(self.app,after)
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.eventShop,"confirmed")
        self.assertEqual(len(self.executor.calls),0)
    def test_saved_extra_award_or_origin_transfer_stays_held(self):
        self.begin();self.restart();self.h.at(1)
        self.app.Step(self.app,self.f.raw(revision=2,medals=85,bound=2))
        self.assertIsNone(self.runtime.Status(self.runtime).recoveries.eventShop)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),1)
    def test_saved_pending_or_presence_receipt_never_becomes_success(self):
        self.begin({"ok":True,"code":"presence"});self.restart();self.h.at(1)
        self.app.Step(self.app,self.f.raw(revision=2,medals=85,bound=1))
        self.assertIsNone(self.runtime.Status(self.runtime).recoveries.eventShop)
        self.assertEqual(len(self.executor.calls),0)
    def test_unknown_native_return_does_not_replay(self):
        raw=self.f.raw();self.app.Step(self.app,raw)
        old=self.executor;old.Invoke=self.h.lua.eval("function() error('connection lost') end")
        old.callback();self.restart();self.h.at(1)
        self.app.Step(self.app,self.f.raw(revision=2,medals=85,bound=1))
        self.assertIsNone(self.runtime.Status(self.runtime).recoveries.eventShop)
        self.assertEqual(len(self.executor.calls),0)
    def test_unload_before_invoke_has_exact_durable_unsent_refund(self):
        raw=self.f.raw();self.app.Step(self.app,raw);old=self.executor
        self.app.Destroy(self.app);old.callback();self.restart();self.h.at(1)
        self.app.Step(self.app,self.f.raw(revision=2))
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.eventShop,"known_unsent")
        usage=self.runtime.checkpoint.Allowance(self.runtime.checkpoint,"eventShop")[0]
        self.assertEqual((usage.attempted,usage.spent),(0,0))
        self.assertEqual(len(old.calls),0)
    def test_live_or_saved_mixed_paid_medals_never_authorize_or_confirm(self):
        self.app.Step(self.app,self.f.raw(paid=1));self.assertIsNone(self.executor.callback)
        self.begin();self.restart();self.h.at(1)
        self.app.Step(self.app,self.f.raw(revision=2,medals=85,bound=1,paid=1))
        self.assertIsNone(self.runtime.Status(self.runtime).recoveries.eventShop)
    def test_disagreeing_saved_baseline_or_new_offer_catalog_is_refused(self):
        self.begin();record=self.runtime.checkpoint.Records(self.runtime.checkpoint)[1]
        data=self.runtime.checkpoint.Recovery(self.runtime.checkpoint,record.actionKey)[0]
        data.baseline.inventoryBound.event_medal=999
        after=self.f.raw(revision=2,medals=85,bound=1)
        self.assertIsNone(self.f.buyer.recoverSaved(data,after))
if __name__=="__main__":unittest.main()
