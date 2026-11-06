"""Fresh owned info, persistent limits and App-selected ordinary contributions."""
import unittest

import test_family_contribution_pipeline as fixture
from engine_harness import lua_table


class FamilyContributionReadPipelineTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture.FamilyContributionPipelineTests()
        self.fixture.setUp()
        self.h = self.fixture.h
        self.app, self.reader = None, None

    def start(self, feature="familyCash", kind="cash", amount=100):
        if self.app:
            self.app.Destroy(self.app)
            self.reader.Close(self.reader)
        self.tab = self.fixture.tab()
        self.lane = self.h.load("src/engine/RequestLane.luau").new(self.h.clock)
        self.reader = self.h.load("src/transport/NativeSnapshotReader.luau").new(
            lua_table(self.h.lua, self.h.session), self.h.clock, "a" * 64)
        self.h.lua.globals().familyInfoReply = lua_table(self.h.lua, {"ok": True, "family": self.fixture.family()})
        self.h.lua.globals().familyReceipt = lua_table(self.h.lua, {
            "ok": True, "family": self.fixture.family(kind, amount)})
        self.executor = self.h.lua.execute("""return {queued={},calls={},
            Schedule=function(self,fn) if self.decline then return false end; self.queued[#self.queued+1]=fn; return true end,
            Invoke=function() error('Unowned invocation') end,
            InvokeOwned=function(self,token,remote,method,...)
                local args=table.pack(...)
                assert(remote=='FamilyAction')
                self.calls[#self.calls+1]={remote=remote,args=args}
                if args[1]=='info' then return familyInfoReply end
                assert(args[1]=='donate' or args[1]=='donategold' or args[1]=='contribute')
                familyInfoReply=familyReceipt
                return familyReceipt
            end}""")
        native = self.h.load("src/transport/NativeCallPlan.luau")
        self.transport = self.h.load("src/transport/NativeDispatchAdapter.luau").new(
            native.withFamily(native, self.fixture.calls), self.executor, self.lane, self.h.clock)
        self.h.lua.globals().currentFamilyReader, self.h.lua.globals().familyTransport = self.reader, self.transport
        sources = self.tab.ReadSources(self.tab, self.reader)
        reads = self.h.load("src/transport/ReadCoordinator.luau").new(lua_table(self.h.lua, {
            "clock": self.h.clock, "lane": self.lane, "executor": self.executor, "sources": sources,
            "budget": self.h.load("src/engine/ReadBudget.luau").new(self.h.clock,
                lua_table(self.h.lua, [{"id": "familyInfo", "interval": 5}]), 5, 60),
            "currentSnapshot": self.h.lua.eval("function() return currentFamilyReader:Capture() end"),
            "borrowLease": self.h.lua.eval("function(feature) return familyTransport:ReadLease(feature) end")}))
        self.runtime = self.h.load("src/engine/AutomationRuntime.luau").new(lua_table(self.h.lua, {
            "clock": self.h.clock, "transport": self.transport, "storage": self.fixture.storage,
            "identity": self.h.session, "modules": self.fixture.runtime_modules, "features": self.tab.Descriptors(self.tab),
            "snapshotAssembler": self.h.load("src/tabs/TabSnapshotAssembler.luau").new(lua_table(self.h.lua, [self.tab])),
            "featurePages": {"familyCash": "family", "familyGold": "family", "familyStamina": "family"},
            "tabInstances": [self.tab], "readCoordinator": reads, "readSources": sources,
            "reservationSources": getattr(self,"additional_reservation_sources",[])}))
        self.app = self.h.load("src/App.luau").start(lua_table(self.h.lua, {
            "Ember": self.h.load("tests/ember_double.lua")(), "Catalog": self.h.load("src/ui/Catalog.luau"),
            "Settings": self.h.load("src/storage/Settings.luau"),
            "EmberAdapter": self.h.load("src/ui/EmberAdapter.luau"),
            "FamilyTab": self.h.load("src/tabs/family/Module.luau"), "automationRuntimeInstance": self.runtime}))
        self.reader.ObserveSync(self.reader, self.fixture.raw().native)
        for key, value in ((feature + ".enabled", True), (feature + ".custom.amount", amount),
                (feature + ".custom.runBudget", amount), (feature + ".custom.maxAttempts", 1)):
            self.assertTrue(self.app.Set(self.app, key, value)[0])
        self.app.Resume(self.app)

    def step(self, forged_usage=False):
        raw = self.reader.Capture(self.reader)[0]
        if forged_usage:
            raw.familyUsageProof = lua_table(self.h.lua, {**self.h.session,
                "revision": raw.revision, "capturedAt": raw.capturedAt, "usage": {
                    feature: {"attempted": 0, "spent": 0} for feature in ("familyCash", "familyGold", "familyStamina")}})
        return self.app.Step(self.app, raw)

    def test_three_independent_features_read_send_and_confirm_exact_debit(self):
        for feature, kind, resource, amount, command in (
                ("familyCash", "cash", "cash", 100, "donate"),
                ("familyGold", "gold_bar", "gold_bar", 1, "donategold"),
                ("familyStamina", "stamina", "stamina", 5, "contribute")):
            with self.subTest(feature=feature):
                self.start(feature, kind, amount)
                self.assertIsNone(self.app.ui.features[feature].blockedReason)
                self.step()
                self.executor.queued[1]()
                self.h.at(self.h.lua.globals().testNow + 0.25)
                self.step()
                self.executor.queued[2]()
                call = self.executor.calls[2]
                self.assertEqual((call.args[1], call.args.n), (command, 4))
                self.h.at(self.h.lua.globals().testNow + 0.75)
                self.reader.ObserveSync(self.reader, self.fixture.raw(2, resource, amount).native)
                self.step()
                self.assertEqual(self.runtime.Status(self.runtime).outcomes[feature], "confirmed")
                proof = self.runtime.checkpoint.FamilyContributionUsage(self.runtime.checkpoint,
                    self.reader.Capture(self.reader)[0])[0]
                self.assertEqual((proof.usage[feature].attempted, proof.usage[feature].spent), (1, amount))

    def test_named_account_uses_native_actor_through_actual_app_and_independent_caps(self):
        self.h.session["account"] = "PlayerName"
        self.test_three_independent_features_read_send_and_confirm_exact_debit()
        self.assertEqual(self.runtime.Status(self.runtime).outcomes.familyStamina, "confirmed")

    def test_native_58_member_family_reaches_all_three_independent_senders(self):
        original=self.fixture.family
        def large_family(*args,**kwargs):
            family=original(*args,**kwargs)
            family.update(level=137,capSlots=10,memberCap=60)
            family['members'].extend({'userId':actor} for actor in range(44,100))
            return family
        self.fixture.family=large_family
        self.test_named_account_uses_native_actor_through_actual_app_and_independent_caps()

    def test_named_account_rejects_foreign_or_missing_native_actor(self):
        self.h.session["account"] = "PlayerName"
        self.start()
        self.step(); self.executor.queued[1]()
        self.h.at(.25); self.step()
        self.assertEqual(len(self.executor.queued), 2)
        captured = self.reader.Capture(self.reader)[0]
        captured.native.userId = 43
        self.assertFalse(self.fixture.evidence.canDispatch(
            self.runtime.Status(self.runtime).active.proposal, captured))
        for actor in (None, 0, False, "42"):
            raw = self.fixture.raw(userId=actor)
            self.assertIsNone(self.fixture.state.Stage(self.fixture.state, raw,
                lua_table(self.h.lua, {"ok": True, "family": self.fixture.family()}))[0])

    def test_reload_and_forged_usage_cannot_reset_confirmed_cash_budget(self):
        self.start()
        self.step()
        self.executor.queued[1]()
        self.h.at(0.25)
        self.step()
        self.executor.queued[2]()
        self.h.at(1)
        self.reader.ObserveSync(self.reader, self.fixture.raw(2, "cash", 100).native)
        self.step()
        self.start()
        self.step()
        self.executor.queued[1]()
        self.h.at(1.25)
        self.step(forged_usage=True)
        self.assertEqual(len(self.executor.calls), 1)
        self.assertEqual(self.executor.calls[1].args[1], "info")
        self.assertIn("cap", self.runtime.Status(self.runtime).reasons.familyCash)

    def test_definite_schedule_refusal_restores_unsent_usage_and_unload_fences_reads(self):
        self.start()
        self.step()
        self.executor.queued[1]()
        self.executor.decline = True
        self.h.at(0.25)
        self.step()
        proof = self.runtime.checkpoint.FamilyContributionUsage(self.runtime.checkpoint,
            self.reader.Capture(self.reader)[0])[0]
        self.assertEqual(proof.usage.familyCash.spent, 0)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)), 0)
        self.assertEqual(len(self.executor.calls), 1)

    def test_unconfirmed_deadline_and_reload_keep_exposure_and_budget(self):
        self.start()
        self.step()
        self.executor.queued[1]()
        self.h.at(0.25)
        self.step()
        self.executor.queued[2]()
        self.h.at(45.25)
        self.reader.ObserveSync(self.reader, self.fixture.raw(2).native)
        self.step()
        self.assertEqual(self.runtime.Status(self.runtime).outcomes.familyCash, "skipped_unconfirmed")
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)), 1)
        self.assertEqual(self.runtime.checkpoint.FamilyContributionUsage(self.runtime.checkpoint,
            self.reader.Capture(self.reader)[0])[0].usage.familyCash.spent, 100)
        self.start()
        self.step()
        self.executor.queued[1]()
        self.h.at(45.5)
        self.step(forged_usage=True)
        self.assertEqual(len(self.executor.calls), 1)
        self.assertEqual(self.runtime.Status(self.runtime).uncertainCount, 1)

    def test_unload_cancels_queued_info_before_any_native_invocation(self):
        self.start()
        self.step()
        self.app.Destroy(self.app)
        self.executor.queued[1]()
        self.assertEqual(len(self.executor.calls), 0)

    def test_disable_or_changed_amount_cancels_queued_contribution_and_restores_budget(self):
        for key, value in (("familyCash.enabled", False), ("familyCash.custom.amount", 200)):
            with self.subTest(key=key):
                self.fixture.storage.data = self.h.lua.table()
                self.start()
                self.step()
                self.executor.queued[1]()
                self.h.at(self.h.lua.globals().testNow + 0.25)
                self.step()
                self.app.Set(self.app, key, value)
                self.executor.queued[2]()
                self.assertEqual(len(self.executor.calls), 1)
                self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)), 0)
                proof = self.runtime.checkpoint.FamilyContributionUsage(self.runtime.checkpoint,
                    self.reader.Capture(self.reader)[0])[0]
                self.assertEqual(proof.usage.familyCash.spent, 0)

    def test_unrelated_feature_change_does_not_cancel_the_queued_contribution(self):
        self.start()
        self.step()
        self.executor.queued[1]()
        self.h.at(0.25)
        self.step()
        self.assertTrue(self.app.Set(self.app, "jobs.enabled", True)[0])
        self.executor.queued[2]()
        self.assertEqual(len(self.executor.calls), 2)

    def test_duplicate_dispatch_callback_cannot_invoke_or_refund_a_sent_action_twice(self):
        self.start()
        self.step()
        self.executor.queued[1]()
        self.h.at(0.25)
        self.step()
        self.executor.queued[2]()
        self.executor.queued[2]()
        self.assertEqual(len(self.executor.calls), 2)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)), 1)
        self.assertEqual(self.runtime.checkpoint.FamilyContributionUsage(self.runtime.checkpoint,
            self.reader.Capture(self.reader)[0])[0].usage.familyCash.spent, 100)

    def tearDown(self):
        if self.app: self.app.Destroy(self.app)
        if self.reader: self.reader.Close(self.reader)


if __name__ == "__main__":
    unittest.main()
