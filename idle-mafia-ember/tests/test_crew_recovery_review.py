"""Explicit local Crew cleanup never invokes or replays a game action."""
import unittest
from engine_harness import ROOT, lua_table
import test_crew_runtime as runtime_fixture


class CrewRecoveryReviewTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue((ROOT/'src/tabs/crew/CrewRecoveryReview.luau').is_file())
        self.f = runtime_fixture.CrewRuntimeTests()
        self.f.setUp()
        self.h = self.f.h
        self.h.lua.globals().reviewRuntime = self.f.runtime
        self.module = self.h.load('src/tabs/crew/CrewRecoveryReview.luau')

    def tearDown(self):
        if hasattr(self,'f'):
            self.f.tearDown()

    def review(self):
        self.h.lua.globals().reviewRuntime = self.f.runtime
        return self.module.new(lua_table(self.h.lua, {'owner': self.f.owner,'helper': self.f.f.source,
            'environment': {'session': self.f.runtime.session,'checkpoint': self.f.runtime.checkpoint,
                'identity': self.h.session,'clock': self.h.clock,
                'currentSnapshot': self.h.lua.eval('function() return reviewRuntime.allowanceSnapshot end'),
                'requested': self.h.lua.eval('function() return reviewRuntime.requested end'),
                'busy': self.h.lua.eval('function() return false end')}}))

    def prepare_reloaded(self, hire=False):
        self.f.choose()
        self.f.step()
        if hire:
            self.f.drain()
            self.f.step(revision=2,stage='empty')
        self.f.restart()
        self.f.app.Pause(self.f.app)
        self.f.step(revision=3,stage='empty' if hire else 'member')

    def test_review_confirm_releases_unsent_dismissal_and_reserved_attempt(self):
        self.prepare_reloaded()
        review = self.review()
        preview, reason = review.Preview(review)
        self.assertIsNone(reason)
        self.assertEqual(preview.kind,'discardDismiss')
        self.assertEqual(preview.slot,2)
        self.assertTrue(review.Confirm(review,preview.ticket)[0])
        self.assertIsNone(self.f.owner.Active(self.f.owner))
        self.assertEqual(self.f.owner.Usage(self.f.owner).attempted,0)
        self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)),0)
        self.assertEqual(len(self.f.executor.calls),0)
        self.assertFalse(review.Confirm(review,preview.ticket)[0])

    def test_unsent_hire_review_restores_funding_and_retains_cycle_count(self):
        self.prepare_reloaded(hire=True)
        review = self.review()
        preview = review.Preview(review)[0]
        self.assertEqual(preview.kind,'restoreHire')
        self.assertTrue(review.Confirm(review,preview.ticket)[0])
        self.assertEqual(self.f.owner.Active(self.f.owner).stage,'observedEmpty')
        self.assertEqual((self.f.owner.Usage(self.f.owner).attempted,self.f.owner.Usage(self.f.owner).spent),(1,0))
        self.assertEqual(len(self.f.executor.calls),1)
        self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)),0)

    def test_review_cannot_discard_an_unknown_sent_outcome(self):
        self.f.choose()
        self.f.step()
        self.f.executor.Invoke = self.h.lua.eval('function() return nil end')
        self.f.drain()
        self.f.app.Pause(self.f.app)
        self.h.at(46)
        self.f.app.Step(self.f.app,self.f.f.raw(revision=2))
        review = self.review()
        self.assertIsNone(review.Preview(review)[0])
        self.assertEqual(self.f.owner.Active(self.f.owner).stage,'sentDismiss')
        self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)),1)

    def test_proven_rejected_hire_release_retains_conservative_counted_use(self):
        self.f.choose()
        self.f.step()
        self.f.drain()
        self.f.step(revision=2,stage='empty')
        self.f.executor.reply = lua_table(self.h.lua,{'ok':False,'code':'refused'})
        self.f.drain()
        self.f.step(revision=3,stage='empty')
        self.f.app.Pause(self.f.app)
        review = self.review()
        preview = review.Preview(review)[0]
        self.assertEqual(preview.kind,'releaseRejectedHire')
        self.assertTrue(review.Confirm(review,preview.ticket)[0])
        self.assertIsNone(self.f.owner.Active(self.f.owner))
        self.assertEqual((self.f.owner.Usage(self.f.owner).attempted,self.f.owner.Usage(self.f.owner).spent),(1,10000))
        self.assertEqual(len(self.f.executor.calls),2)

    def test_actual_app_buttons_require_user_review_and_ignore_restore_callbacks(self):
        self.prepare_reloaded()
        row = self.f.app.ui.features.crewRoll
        generation = self.f.owner.generation
        for marker in ('initial','restored','reapplied','reverted'):
            origin = lua_table(self.h.lua,{marker:True})
            row.recoveryReview.options.Callback(None,None,origin)
            row.recoveryConfirm.options.Callback(None,None,origin)
        self.assertEqual(self.f.owner.generation,generation)
        row.recoveryConfirm.Click(row.recoveryConfirm)
        self.f.ember.Flush()
        self.assertIsNotNone(self.f.owner.Active(self.f.owner))
        row.recoveryReview.Click(row.recoveryReview)
        self.f.ember.Flush()
        self.assertIn('Slot 2',row.recoveryStatus.value)
        row.recoveryConfirm.Click(row.recoveryConfirm)
        self.f.ember.Flush()
        self.assertIsNone(self.f.owner.Active(self.f.owner))
        self.assertTrue(self.f.app.model.paused)
        self.assertEqual(len(self.f.executor.calls),0)
        self.assertIn('remains paused',row.recoveryStatus.value)

    def test_expired_changed_scope_and_generation_tickets_cannot_clear_records(self):
        self.prepare_reloaded()
        review = self.review()
        preview = review.Preview(review)[0]
        self.h.at(34)
        self.assertFalse(review.Confirm(review,preview.ticket)[0])
        preview = review.Preview(review)[0]
        self.assertTrue(self.f.owner.save(self.f.owner,self.f.owner.Active(self.f.owner))[0])
        self.assertFalse(review.Confirm(review,preview.ticket)[0])
        preview = review.Preview(review)[0]
        self.f.runtime.allowanceSnapshot.account = 'other'
        self.assertFalse(review.Confirm(review,preview.ticket)[0])
        self.assertIsNotNone(self.f.owner.Active(self.f.owner))
        self.assertEqual(len(self.f.executor.calls),0)

    def test_actual_app_resume_waits_for_recovery_write(self):
        self.prepare_reloaded()
        preview, reason = self.f.app.PreviewFeatureRecovery(self.f.app,'crewRoll')
        self.assertIsNone(reason)
        self.h.lua.globals().crewReviewApp = self.f.app
        self.f.storage.Write = self.h.lua.eval("""function(self,key,value)
            if value.resolution and not self.yielded then self.yielded=true; coroutine.yield('recovery save') end
            self.data[key]=value; return true end """)
        self.h.lua.execute("crewReview=coroutine.create(function() return crewReviewApp:ConfirmFeatureRecovery('crewRoll') end)")
        self.assertTrue(self.h.lua.eval('coroutine.resume(crewReview)')[0])
        self.assertTrue(self.f.runtime.FeatureRecoveryBusy(self.f.runtime))
        self.assertFalse(self.f.app.Resume(self.f.app)[0])
        self.assertTrue(self.f.app.model.paused)
        self.assertTrue(self.h.lua.eval('coroutine.resume(crewReview)')[0])
        self.assertFalse(self.f.runtime.FeatureRecoveryBusy(self.f.runtime))
        self.assertIsNone(self.f.owner.Active(self.f.owner))
        self.assertEqual(len(self.f.executor.calls),0)

    def test_unload_during_review_save_uses_receipt_to_finish_on_reload(self):
        self.prepare_reloaded()
        self.f.app.PreviewFeatureRecovery(self.f.app,'crewRoll')
        self.h.lua.globals().crewReviewApp = self.f.app
        self.f.storage.Write = self.h.lua.eval("""function(self,key,value)
            self.data[key]=value
            if value.resolution then crewReviewApp:Destroy() end
            return true end """)
        self.assertFalse(self.f.app.ConfirmFeatureRecovery(self.f.app,'crewRoll')[0])
        self.f.storage.Write = self.h.lua.eval('function(self,key,value) self.data[key]=value return true end')
        self.f.restart()
        self.f.step(revision=4)
        self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)),0)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).recoveries.crewRoll,'known_unsent')
        self.assertEqual(len(self.f.executor.calls),0)

    def test_pending_negative_reply_is_not_a_proven_rejection(self):
        self.f.choose()
        self.f.step()
        self.f.drain()
        self.f.step(revision=2,stage='empty')
        self.f.executor.reply = lua_table(self.h.lua,{'ok':False,'pending':True})
        self.f.drain()
        self.f.step(revision=3,stage='empty')
        self.assertNotEqual(self.f.runtime.Status(self.f.runtime).outcomes.crewRoll,'rejected')
        self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)),1)
