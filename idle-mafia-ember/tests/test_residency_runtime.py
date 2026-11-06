"""Actual App and native adapter, reusing the existing Territory fixture."""
import unittest
import test_territory_stationing as fixture
from engine_harness import lua_table

class ResidencyRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.TerritoryStationingTests();self.f.setUp();self.h=self.f.h
        self.module=self.h.load("src/tabs/territory/Residency.luau")
        self.app,self.runtime,self.executor=self.f.start_app(with_residency=True)
    def tearDown(self): self.app.Destroy(self.app)
    def raw(self, revision=1, lease=None, **quote):
        if lease is not None:
            lease = dict(lease)
            lease.setdefault("kind", "landlord")
            lease.setdefault("share", .025 if lease.get("d") == "d1" else .01)
        raw=self.h.snapshot(revision=revision,native={"fullSync":True,"serverNow":1000+revision,
            "level":50,"family":{"id":"fam-a"},"crew":[{"name":"YOU"}],
            "derived":{"residency":lease,"territoryBonuses":{"landlord":lease["share"]}} if lease else {"territoryBonuses":{"landlord":0}}})
        q=self.h.load("src/tabs/territory/ResidencyQuery.luau").new()
        request=q.Prepare(q,"d1",raw)[0]
        response={"ok":True,"owned":True,"districtId":"d1","kind":"landlord","admission":"open",
            "rent":1,"share":.025,"count":4,"capacity":500,"minLevel":20}
        response.update(quote)
        accepted,reason=q.Accept(q,request,lua_table(self.h.lua,response))
        self.assertIsNone(reason)
        raw.residencyView=accepted
        return raw
    def select(self, **settings):
        values={"residency.enabled":True,"residency.custom.districtId":"d1",
            "residency.custom.maxRentPct":5,"residency.custom.minSharePct":1,
            "residency.custom.maxAttempts":1}
        values.update(settings)
        for key,value in values.items(): self.assertTrue(self.app.Set(self.app,key,value)[0])
        self.app.Resume(self.app)
    def begin(self, **quote):
        self.select();raw=self.raw(**quote);self.app.Step(self.app,raw)
        self.assertIsNotNone(self.executor.callback)
        return raw
    def test_owned_usage_and_exact_new_native_lease_confirms(self):
        self.assertIsNone(self.app.ui.features.residency.blockedReason)
        self.begin();self.executor.callback();self.h.at(1)
        after=self.raw(2,{"d":"d1","rent":1,"active":True},status="resident",myRent=1)
        self.app.Step(self.app,after)
        self.assertEqual(self.runtime.Status(self.runtime).outcomes.residency,"confirmed")
        self.assertEqual(self.runtime.checkpoint.residencyAttempts,1)
        self.assertEqual((self.executor.calls[1].remote,self.executor.calls[1].args.n),("ResidencyAction",3))
    def test_unowned_or_unknown_district_never_requests_admission(self):
        self.select();self.app.Step(self.app,self.raw(owned=False))
        self.assertIsNone(self.executor.callback)
    def test_native_explicit_none_status_reaches_normal_admission_and_settles(self):
        before=self.begin(status="none")
        self.assertEqual(before.residencyView.status,"none")
        self.executor.callback();self.h.at(1)
        self.app.Step(self.app,self.raw(2,{"d":"d1","rent":1,"active":True},status="resident",myRent=1))
        self.assertEqual(self.runtime.Status(self.runtime).outcomes.residency,"confirmed")
        self.assertEqual(len(self.executor.calls),1)

    def test_native_none_status_still_obeys_zero_rent_limit(self):
        self.select(**{"residency.custom.maxRentPct":0})
        self.app.Step(self.app,self.raw(status="none",rent=1))
        self.assertIsNone(self.executor.callback)
    def test_pending_negative_same_revision_does_not_reject(self):
        raw=self.begin();self.executor.reply=lua_table(self.h.lua,{"ok":False,"pending":True})
        self.executor.callback();self.app.Step(self.app,raw)
        self.assertIsNone(self.runtime.Status(self.runtime).outcomes.residency)
    def test_native_lease_rent_must_match_the_original_quote(self):
        self.begin();self.executor.callback();self.h.at(1)
        self.app.Step(self.app,self.raw(2,{"d":"d1","rent":3,"active":True},status="resident",myRent=1))
        self.assertIsNone(self.runtime.Status(self.runtime).outcomes.residency)
    def test_landlord_rent_equal_or_above_resident_gain_is_not_an_upgrade(self):
        self.select();self.app.Step(self.app,self.raw(rent=4))
        self.assertIsNone(self.executor.callback)

    def restart(self):
        self.app.Destroy(self.app)
        self.app,self.runtime,self.executor=self.f.start_app(with_residency=True)
    def test_saved_exact_lease_recovers_with_settings_off_without_replay(self):
        self.begin();self.executor.callback();self.restart();self.h.at(1)
        self.app.Step(self.app,self.raw(2,{"d":"d1","rent":1,"active":True},status="resident",myRent=1))
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.residency,"confirmed")
        self.assertEqual(len(self.executor.calls),0)
        self.assertEqual(self.runtime.checkpoint.residencyAttempts,1)
    def test_saved_explicit_rejection_keeps_counted_attempt(self):
        self.begin();self.executor.reply=lua_table(self.h.lua,{"ok":False});self.executor.callback()
        self.restart();self.h.at(1);self.app.Step(self.app,self.raw(2))
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.residency,"rejected")
        self.assertEqual(self.runtime.checkpoint.residencyAttempts,1)
        self.assertEqual(len(self.executor.calls),0)
    def test_saved_pending_negative_or_partial_lease_remains_held(self):
        self.begin();self.executor.reply=lua_table(self.h.lua,{"ok":False,"pending":True});self.executor.callback()
        self.restart();self.h.at(1);self.app.Step(self.app,self.raw(2))
        self.assertIsNone(self.runtime.Status(self.runtime).recoveries.residency)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),1)
    def test_owner_approval_pending_retains_previous_lease_until_exact_acceptance(self):
        self.select(**{"residency.custom.allowRequests":True,"residency.custom.allowReplace":True})
        raw=self.raw(lease={"d":"old","rent":1,"active":True},admission="request",elsewhere="Old district")
        self.app.Step(self.app,raw);self.executor.reply=lua_table(self.h.lua,{"ok":True,"pending":True});self.executor.callback()
        self.h.at(1);self.app.Step(self.app,self.raw(2,{"d":"old","rent":1,"active":True},status="pending",myRent=1,admission="request"))
        self.assertIsNone(self.runtime.Status(self.runtime).outcomes.residency)
        self.h.at(2);self.app.Step(self.app,self.raw(3,{"d":"d1","rent":1,"active":True},status="resident",myRent=1))
        self.assertEqual(self.runtime.Status(self.runtime).outcomes.residency,"confirmed")
        self.assertEqual(len(self.executor.calls),1)
    def test_request_and_replacement_require_separate_opt_ins(self):
        self.select();self.app.Step(self.app,self.raw(admission="request"))
        self.assertIsNone(self.executor.callback)
        self.app.Step(self.app,self.raw(lease={"d":"old","rent":1,"active":True},elsewhere="Old district"))
        self.assertIsNone(self.executor.callback)
    def test_selected_old_lease_cost_must_be_known_before_replacement(self):
        self.select(**{"residency.custom.allowReplace":True})
        self.app.Step(self.app,self.raw(lease={"d":"old"},elsewhere="Old district"))
        self.assertIsNone(self.executor.callback)
    def test_queued_quote_or_old_lease_change_prevents_move(self):
        raw=self.begin();raw.residencyView.rent=2;self.executor.callback()
        self.assertEqual(len(self.executor.calls),0)
        self.assertEqual(self.runtime.checkpoint.residencyAttempts,0)
    def test_queued_new_native_lease_prevents_replacing_an_unselected_lease(self):
        raw=self.begin();raw.native.derived.residency=lua_table(self.h.lua,{"d":"unexpected","rent":1,"active":True})
        self.executor.callback();self.assertEqual(len(self.executor.calls),0)
        self.assertEqual(self.runtime.checkpoint.residencyAttempts,0)
    def test_disable_before_invoke_is_unsent_and_refunded(self):
        self.begin();self.app.Set(self.app,"residency.enabled",False);self.executor.callback()
        self.assertEqual(len(self.executor.calls),0)
        self.assertEqual(self.runtime.checkpoint.residencyAttempts,0)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),0)
    def test_unload_before_invoke_has_durable_exact_unsent_recovery(self):
        self.begin();old=self.executor;self.app.Destroy(self.app);old.callback();self.restart()
        self.h.at(1);self.app.Step(self.app,self.raw(2))
        self.assertEqual(self.runtime.Status(self.runtime).recoveries.residency,"known_unsent")
        self.assertEqual(self.runtime.checkpoint.residencyAttempts,0)
        self.assertEqual(len(old.calls),0)
    def test_disable_after_send_still_observes_exact_outcome(self):
        self.begin();self.executor.callback();self.app.Set(self.app,"residency.enabled",False)
        self.h.at(1);self.app.Step(self.app,self.raw(2,{"d":"d1","rent":1,"active":True},status="resident",myRent=1))
        self.assertEqual(self.runtime.Status(self.runtime).outcomes.residency,"confirmed")
        self.assertEqual(len(self.executor.calls),1)
    def test_timeout_does_not_count_as_admission_and_retains_usage(self):
        self.begin();self.executor.reply=lua_table(self.h.lua,{"ok":True,"pending":True});self.executor.callback()
        self.h.at(45);self.app.Step(self.app,self.raw(2,status="pending",myRent=1))
        self.assertEqual(self.runtime.Status(self.runtime).outcomes.residency,"skipped_unconfirmed")
        self.assertEqual(self.runtime.checkpoint.residencyAttempts,1)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),1)
    def test_zero_cap_and_forged_unowned_usage_do_not_send(self):
        self.select(**{"residency.custom.maxAttempts":0});raw=self.raw()
        raw.residencyUsageProof=lua_table(self.h.lua,{**self.h.session,"revision":1,"capturedAt":0,"attempted":0})
        self.app.Step(self.app,raw);self.assertIsNone(self.executor.callback)
    def test_rejected_retry_has_new_identity_and_stops_at_persistent_cap(self):
        self.select(**{"residency.custom.maxAttempts":2});self.app.Step(self.app,self.raw())
        first=self.runtime.session.broker.active.proposal.actionKey
        self.executor.reply=lua_table(self.h.lua,{"ok":False});self.executor.callback()
        self.h.at(1);self.app.Step(self.app,self.raw(2))
        self.assertEqual(self.runtime.Status(self.runtime).outcomes.residency,"rejected")
        active=self.runtime.session.broker.active
        self.assertIsNotNone(active)
        self.assertNotEqual(first,active.proposal.actionKey)
        self.executor.callback();self.h.at(2);self.app.Step(self.app,self.raw(3))
        self.h.at(3);self.app.Step(self.app,self.raw(4))
        self.assertEqual(len(self.executor.calls),2)
        self.assertEqual(self.runtime.checkpoint.residencyAttempts,2)
    def test_allowance_reset_is_paused_reviewed_and_independent_of_station(self):
        self.begin();self.executor.callback();self.h.at(1)
        self.app.Step(self.app,self.raw(2,{"d":"d1","rent":1,"active":True},status="resident",myRent=1))
        self.assertIsNone(self.app.PreviewAllowance(self.app,"residency")[0]);self.app.Pause(self.app)
        preview,reason=self.app.PreviewAllowance(self.app,"residency")
        self.assertIsNone(reason);self.assertEqual(preview.attempted,1)
        self.assertTrue(self.app.ConfirmAllowance(self.app,"residency")[0])
        self.assertEqual(self.runtime.checkpoint.residencyAttempts,0)
        self.assertEqual(self.runtime.checkpoint.stationAttempts,0)
    def test_backward_clock_or_wrong_district_or_paused_bonus_never_confirms(self):
        self.begin();self.executor.callback();self.h.at(1)
        for lease in ({"d":"wrong","rent":1,"active":True},{"d":"d1","rent":1,"active":False}):
            self.app.Step(self.app,self.raw(2,lease,status="resident",myRent=1))
            self.assertIsNone(self.runtime.Status(self.runtime).outcomes.residency)
        after=self.raw(3,{"d":"d1","rent":1,"active":True},status="resident",myRent=1)
        after.native.serverNow=999;self.app.Step(self.app,after)
        self.assertIsNone(self.runtime.Status(self.runtime).outcomes.residency)
    def test_corrupt_saved_residency_attempt_count_blocks_load(self):
        self.begin();key=self.runtime.checkpoint.ScopeKey(self.runtime.checkpoint)
        self.app.Destroy(self.app);self.f.storage.data[key].residencyAttempts=False;self.restart()
        self.assertIsNotNone(self.runtime.session.storageFault)

if __name__=="__main__": unittest.main()
