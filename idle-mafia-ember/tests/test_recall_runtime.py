"""Selected own Recall uses the shared broker and durable single-send custody."""
import unittest

from engine_harness import lua_table
import test_conditional_feature_contracts as conditional


class RecallRuntimeTests(unittest.TestCase):
    def setUp(self):
        fixture = conditional.ConditionalContracts()
        fixture.setUp()
        self.h = fixture.h
        self.station = self.h.load("src/tabs/territory/Stationing.luau")
        self.config = self.table({"TERRITORY": {"garrisonCap": 200, "recallCooldownSeconds": 60}})
        station_owner = self.station.new(self.config,
            self.table({"DISTRICTS_BY_ID": {"d1": {"city": "city-a"}}}), conditional.KEY, self.h.session["release"])
        self.before = fixture.station_raw(station_owner)
        self.before.native.crew[2].duty = "d1"
        self.before.native.crew[2].dutyToken = "deployment-a"
        self.before.native.crew[2].dutyAt = 90
        self.before.territoryDistrict.district.garrisonCount = 2
        self.controller = self.h.lua.execute("""local owner = {value = {
            userId=123, lastRequestId=0, epochFloor=101000, controllersClear=true, busy=false}}
            owner.Read=function() return owner.value end
            owner.Current=function() return owner.value ~= nil end
            return owner""")
        self.store = self.h.lua.execute("""return {strictRecovery=true, data={},
            Read=function(self,k) return self.data[k] end,
            Write=function(self,k,v) self.data[k]=v;return true end}""")
        self.deps = self.table({"identity": self.h.session, "storage": self.store,
            "release": self.h.session["release"], "config": self.config,
            "nativeUserId": 123,
            "fingerprint": conditional.KEY,
            "gameData": {"DISTRICTS_BY_ID": {"d1": {"city": "city-a"}}},
            "nativeRecallController": self.controller, "Stationing": self.station,
            "RecallTransactions": self.h.load("src/tabs/territory/RecallTransactions.luau")})
        self.module = self.h.load("src/tabs/territory/RecallRuntime.luau")
        self.runtime, reason = self.module.new(self.deps)
        self.assertIsNone(reason)
        self.feature = self.runtime.Feature(self.runtime, self.table({"id": "station",
            "reader": self.station, "planner": self.station, "evidence": self.station}))
        self.settings = self.table({"enabled": True, "mode": "Recall", "districtId": "d1",
            "memberSlot": 2, "minGarrison": 1, "maxAttempts": 1})

    def table(self, value):
        return lua_table(self.h.lua, value)

    def proposal(self):
        self.runtime.Enrich(self.runtime, self.before)
        view, reason = self.feature.reader.read(self.before, self.before)
        self.assertIsNone(reason)
        proposal, reason = self.feature.planner.propose(view, self.settings)
        self.assertIsNone(reason)
        return proposal

    def test_recall_selected_stable_identity_and_independent_attempt_and_defense_limits(self):
        proposal = self.proposal()
        self.assertEqual((proposal.intent.kind, proposal.intent.requestId, proposal.intent.memberKey),
                         ("territoryRecall", 101000, "id:crew-a"))
        for change, value in (("maxAttempts", 0), ("minGarrison", 2)):
            with self.subTest(change=change):
                old = self.settings[change]
                self.settings[change] = value
                view, _ = self.feature.reader.read(self.before, self.before)
                self.assertIsNone(self.feature.planner.propose(view, self.settings)[0])
                self.settings[change] = old
        self.before.stationReservationProof.members["id:crew-a"] = True
        view, _ = self.feature.reader.read(self.before, self.before)
        self.assertIsNone(self.feature.planner.propose(view, self.settings)[0])

        self.before.stationReservationProof.members["id:crew-a"] = None
        self.before.native.crew[2].training = self.table({"endsAt": 200})
        view, _ = self.feature.reader.read(self.before, self.before)
        self.assertIsNone(self.feature.planner.propose(view, self.settings)[0])

    def test_bootstrap_named_account_keeps_verified_numeric_player_identity_separate(self):
        for target in (self.deps.identity, self.before, self.before.territoryMap.header,
                       self.before.territoryDistrict.header, self.before.stationReservationProof):
            target.account = "PlayerName"
        runtime, reason = self.module.new(self.deps)
        self.assertIsNone(reason)
        self.runtime = runtime
        self.feature = runtime.Feature(runtime, self.table({"id": "station",
            "reader": self.station, "planner": self.station, "evidence": self.station}))
        proposal = self.proposal()
        self.assertEqual((proposal.account, proposal.intent.userId), ("PlayerName", 123))
        baseline, _ = self.feature.evidence.capture(proposal, self.before)
        self.assertTrue(self.feature.lifecycle.prepare(proposal, self.before, baseline, 1)[0])

    def test_pending_reply_then_exact_status_and_newer_sync_confirms_and_recovers_receipt(self):
        proposal = self.proposal()
        baseline, reason = self.feature.evidence.capture(proposal, self.before)
        self.assertIsNone(reason)
        lifecycle = self.feature.lifecycle
        self.assertTrue(lifecycle.prepare(proposal, self.before, baseline, 1)[0])
        self.assertTrue(self.feature.canDispatch(proposal))
        call, reason = lifecycle.authorize(proposal, baseline, 1)
        self.assertIsNone(reason)
        self.assertEqual((call.remote, call.arity, call.args[1]), ("TerritoryAction", 3, "recallcrew"))
        self.assertIsNone(lifecycle.authorize(proposal, baseline, 1)[0])
        self.assertTrue(lifecycle.returned(proposal, self.table({"ok": True, "pending": True}))[0])
        status = self.runtime.ReadSources(self.runtime)[1]
        request, reason = status.prepare(self.before)
        self.assertIsNone(reason)
        self.assertEqual((request.kind, request.remote, request.args[1]),
                         ("statusOnly", "TerritoryStatus", "recallstatus"))
        active = self.runtime.owner.Active(self.runtime.owner)
        staged = status.accept(self.before, request, self.table({"ok": True, "settled": [active.target]}))
        self.assertTrue(status.commit(staged))
        after = self.h.lua.eval("function(raw) local out={} for k,v in pairs(raw) do out[k]=v end return out end")(self.before)
        after.revision = 2
        after.native = self.table({"fullSync": True, "serverNow": 102, "family": {"id": "fam-a"},
            "crew": [{}, {"name": "A", "rarity": 1, "healId": "crew-a"},
                     {"name": "B", "rarity": 1, "healId": "crew-b"}]})
        self.assertEqual(self.feature.evidence.evaluate(proposal, self.before, after,
            self.table({"ok": True, "pending": True}), baseline), "confirmed")
        self.assertTrue(lifecycle.resolve(proposal, "confirmed", after)[0])
        restored, reason = self.module.new(self.deps)
        self.assertIsNone(reason)
        feature = restored.Feature(restored, self.table({"id": "station", "reader": self.station,
            "planner": self.station, "evidence": self.station}))
        saved = self.table({"proposal": proposal, "before": self.before, "baseline": baseline})
        self.assertEqual(feature.recoverSaved(saved, after), "confirmed")

    def test_unknown_request_never_resubmits_and_keeps_member_reservation(self):
        proposal = self.proposal()
        baseline, _ = self.feature.evidence.capture(proposal, self.before)
        self.feature.lifecycle.prepare(proposal, self.before, baseline, 1)
        self.feature.lifecycle.authorize(proposal, baseline, 1)
        self.feature.lifecycle.returned(proposal, self.table({"ok": False, "code": "unknown_request"}))
        self.assertIsNone(self.feature.lifecycle.authorize(proposal, baseline, 1)[0])
        claim = self.runtime.ReservationSources(self.runtime)[1].read(self.before)
        self.assertTrue(claim.claims.members["id:crew-a"])
        self.assertTrue(claim.claims.members["slot:2"])
        self.assertEqual(claim.actionKey, proposal.actionKey)

    def test_final_guard_uses_trusted_broker_ownership_when_tab_snapshot_precedes_usage_proof(self):
        proposal = self.proposal()
        baseline, _ = self.feature.evidence.capture(proposal, self.before)
        self.feature.lifecycle.prepare(proposal, self.before, baseline, 1)
        latest = self.h.lua.eval("function(raw) local out={} for k,v in pairs(raw) do out[k]=v end return out end")(self.before)
        latest.stationReservationProof = None
        self.runtime.Enrich(self.runtime, latest)
        self.assertTrue(self.feature.canDispatch(proposal))

    def test_unavailable_native_controller_preserves_durable_reservation_and_blocks_new_recall(self):
        proposal = self.proposal()
        baseline, _ = self.feature.evidence.capture(proposal, self.before)
        self.feature.lifecycle.prepare(proposal, self.before, baseline, 1)
        self.feature.lifecycle.authorize(proposal, baseline, 1)
        self.deps.nativeRecallController = None
        restored, reason = self.module.new(self.deps)
        self.assertIsNone(reason)
        self.assertTrue(restored.ReservationSources(restored)[1].read(self.before).claims.members["id:crew-a"])
        self.assertIsNone(restored.ReadSources(restored)[1].prepare(self.before)[0])

    def test_unselected_legacy_deployed_member_is_preserved_by_native_deployment_identity(self):
        other = self.before.native.crew[3]
        other.healId, other.duty, other.dutyToken, other.dutyAt = None, "d2", "legacy-b", 80
        proposal = self.proposal()
        self.assertEqual(proposal.intent.memberKey, "id:crew-a")
        baseline, reason = self.feature.evidence.capture(proposal, self.before)
        self.assertIsNone(reason)
        self.assertEqual(baseline.baseline.members["3"].key, "deployment:legacy-b")

    def test_native_call_plan_and_checkpoint_consume_and_preserve_recall_attempt(self):
        proposal = self.proposal()
        baseline, _ = self.feature.evidence.capture(proposal, self.before)
        plan = self.h.load("src/tabs/territory/TerritoryCallPlan.luau").withRecall(self.deps.RecallTransactions)
        call, reason = plan.describe(proposal)
        self.assertIsNone(reason)
        self.assertEqual((call.remote, call.arity, call.args[3][1].deploymentId),
                         ("TerritoryAction", 3, "deployment-a"))
        fixture = conditional.ConditionalContracts()
        fixture.h = self.h
        checkpoint, store = fixture.checkpoint()
        self.assertTrue(checkpoint.Save(checkpoint, proposal, self.before, baseline)[0])
        self.assertEqual(checkpoint.StationUsage(checkpoint, self.before), 1)
        self.assertTrue(checkpoint.RecordReply(checkpoint, proposal.actionKey,
            self.table({"ok": True, "pending": True}))[0])
        self.assertFalse(checkpoint.Resolve(checkpoint, proposal.actionKey, "schedule_failed")[0])
        restored, _ = fixture.checkpoint(store)
        self.assertEqual(restored.StationUsage(restored, self.before), 1)

    def test_real_territory_module_broker_sender_and_checkpoint_confirm_once(self):
        for name in ("TerritoryMapQuery", "ResidencyQuery", "TerritoryState", "ReadAttachment", "TerritoryBlocked", "TerritoryCallPlan", "RecallRuntime"):
            self.deps[name] = self.h.load("src/tabs/territory/" + name + ".luau")
        tab = self.h.load("src/tabs/territory/Module.luau").new(self.deps)
        descriptor = tab.Descriptors(tab)[2]
        modules = {name: self.h.load("src/engine/" + name + ".luau")
                   for name in ("Contracts", "Broker", "Journal", "Scheduler", "Session", "ResourceReservations")}
        modules.update({name: self.h.load("src/storage/" + name + ".luau")
                        for name in ("Checkpoint", "PendingAction")})
        modules["Context"] = self.h.load("src/game/Context.luau")
        sender_plan = self.deps.TerritoryCallPlan.withRecall(self.deps.RecallTransactions)
        executor = self.h.lua.execute("""return {queued={},calls={},
            Schedule=function(self,fn) self.queued[#self.queued+1]=fn;return true end,
            Invoke=function(self,remote,method,...)
                self.calls[#self.calls+1]={remote=remote,args={...}}
                return {ok=true,pending=true}
            end}""")
        sender = self.h.load("src/transport/NativeDispatchAdapter.luau").new(sender_plan, executor)
        automation = self.h.load("src/engine/AutomationRuntime.luau").new(self.table({
            "modules": modules, "identity": self.h.session, "clock": self.h.clock,
            "storage": self.store, "transport": sender, "features": [descriptor],
            "snapshotAssembler": tab, "tabInstances": [tab], "featurePages": {"station": "territory"},
            "reservationSources": tab.ReservationSources(tab)}))
        self.h.at(1)
        automation.Resume(automation)
        automation.Step(automation, self.before, self.table({"station": self.settings}))
        self.assertEqual(len(executor.queued), 1, dict(automation.Status(automation).reasons))
        executor.queued[1]()
        self.assertEqual(len(executor.calls), 1, [dict(row) for row in automation.journal.Events(automation.journal).values()])
        self.assertEqual((len(executor.calls), executor.calls[1].args[1]), (1, "recallcrew"))
        self.assertEqual(automation.checkpoint.StationUsage(automation.checkpoint, self.before), 1)
        active = tab.recall.owner.Active(tab.recall.owner)
        status = tab.recall.ReadSources(tab.recall)[1]
        request, _ = status.prepare(self.before)
        self.assertTrue(status.commit(status.accept(self.before, request,
            self.table({"ok": True, "settled": [active.target]}))))
        after = self.h.lua.eval("function(raw) local out={} for k,v in pairs(raw) do out[k]=v end return out end")(self.before)
        after.revision, after.capturedAt = 2, 2
        after.native = self.table({"fullSync": True, "serverNow": 102, "family": {"id": "fam-a"},
            "crew": [{}, {"name": "A", "rarity": 1, "healId": "crew-a"},
                     {"name": "B", "rarity": 1, "healId": "crew-b"}]})
        self.h.at(2)
        automation.Step(automation, after, self.table({"station": self.settings}))
        final = automation.Status(automation)
        self.assertEqual(final.outcomes.station, "confirmed")
        self.assertFalse(final.storageFault)
        self.assertEqual(len(automation.checkpoint.Records(automation.checkpoint)), 0)
        self.assertEqual(len(executor.calls), 1)


if __name__ == "__main__":
    unittest.main()
