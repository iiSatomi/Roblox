"""Residence previews use locked rent and state the previous-lease effect."""
import unittest
import test_automation_runtime as runtime_fixture
from engine_harness import Harness, lua_table


class ResidencyPreviewTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.module = self.h.load("src/tabs/territory/Residency.luau")

    def raw(self, **changes):
        view = {"districtId": "d1", "owned": True, "status": "none", "admission": "open",
            "kind": "landlord", "rent": 4, "share": 0.075, "count": 4,
            "capacity": 500, "minLevel": 20,
            "header": {**self.h.session, "revision": 1,
                       "capturedAt": self.h.lua.globals().testNow}}
        view.update(changes)
        derived = {"territoryBonuses": {"landlord": 0}}
        if view.get("elsewhere"):
            derived = {"territoryBonuses": {"landlord": .01}, "residency": {
                "d":"previous", "rent":4, "active":True, "kind":"landlord", "share":.01}}
        return self.h.snapshot(native={"fullSync": True, "level": 50, "serverNow": 1001,
            "derived": derived}, residencyView=view)

    def settings(self, **changes):
        result = {"districtId": "d1", "maxRentPct": 5, "minSharePct": 1,
            "selectedKind": "landlord", "allowReplace": False, "allowRequests": False}
        result.update(changes)
        return lua_table(self.h.lua, result)

    def test_open_candidate_has_percentage_rent_and_no_dispatch(self):
        raw = self.raw()
        preview, reason = self.module.preview(raw, raw, self.settings())
        self.assertIsNone(reason)
        self.assertTrue(preview.eligible)
        self.assertTrue(preview.readOnly)
        self.assertEqual(preview.rentPct, 4)
        self.assertEqual(preview.sharePct, 7.5)
        self.assertEqual(preview.rentBasis, "property income")
        self.assertFalse(preview.rollbackAvailable)
        self.assertIsNone(preview.intent)

    def test_existing_resident_uses_locked_rate_not_new_offer(self):
        raw = self.raw(status="resident", myRent=2, rent=9)
        preview, reason = self.module.preview(raw, raw, self.settings())
        self.assertIsNone(reason)
        self.assertEqual(preview.rentPct, 2)
        self.assertFalse(preview.eligible)
        self.assertEqual(preview.reason, "Already resident")

    def test_move_effect_and_requests_need_their_own_choices(self):
        raw = self.raw(elsewhere="Old district")
        preview = self.module.preview(raw, raw, self.settings())[0]
        self.assertFalse(preview.eligible)
        self.assertTrue(preview.previousLeaseEnds)
        preview = self.module.preview(raw, raw, self.settings(allowReplace=True))[0]
        self.assertTrue(preview.eligible)
        raw = self.raw(admission="request")
        self.assertFalse(self.module.preview(raw, raw, self.settings())[0].eligible)
        preview = self.module.preview(raw, raw, self.settings(allowRequests=True))[0]
        self.assertTrue(preview.requiresApproval)
        self.assertTrue(preview.eligible)

    def test_full_locked_stale_or_low_effect_candidates_cannot_qualify(self):
        for change in ({"count": 500}, {"admission": "closed"}, {"rent": 6},
                       {"share": 0.001}, {"minLevel": 100}):
            raw = self.raw(**change)
            self.assertFalse(self.module.preview(raw, raw, self.settings())[0].eligible)
        raw = self.raw()
        raw.residencyView.header.revision = 0
        self.assertIsNone(self.module.preview(raw, raw, self.settings())[0])

    def test_goal_filters_do_not_compare_unrelated_bonus_units(self):
        raw = self.raw()
        self.assertIsNotNone(self.module.preview(raw, raw, self.settings(policy="Income bonus"))[0])
        self.assertIsNone(self.module.preview(raw, raw, self.settings(policy="Combat bonus"))[0])
        self.assertIsNone(self.module.preview(raw, raw, self.settings(policy="Unknown"))[0])

    def test_false_rent_is_not_silently_replaced_with_free(self):
        query = self.h.load("src/tabs/territory/ResidencyQuery.luau").new()
        request = query.Prepare(query, "d1", self.raw())[0]
        self.assertIsNone(query.Accept(query, request, lua_table(self.h.lua, {
            "ok": True, "districtId": "d1", "admission": "open", "kind": "landlord", "rent": False}))[0])

    def test_request_requires_owned_attempts_and_exact_new_lease(self):
        raw = self.raw()
        raw.native.derived = lua_table(self.h.lua, {"territoryBonuses":{"landlord":0}})
        raw.residencyUsageProof = lua_table(self.h.lua, {**self.h.session,
            "revision": 1, "capturedAt": 0, "attempted": 0})
        settings = self.settings(enabled=True, maxAttempts=1)
        view, reason = self.module.read(raw, raw)
        self.assertIsNone(reason)
        proposal, reason = self.module.propose(view, settings)
        self.assertIsNone(reason)
        baseline, reason = self.module.capture(proposal, raw)
        self.assertIsNone(reason)
        after = self.raw(status="resident", myRent=4)
        after.revision = after.residencyView.header.revision = 2
        after.native.derived = lua_table(self.h.lua, {"residency": {"d": "d1", "rent": 4, "active": True, "kind":"landlord", "share":.075}})
        reply = lua_table(self.h.lua, {"ok": True})
        self.assertEqual(self.module.evaluate(proposal, raw, after, reply, baseline), "confirmed")
        after.residencyView.myRent = 6
        self.assertEqual(self.module.evaluate(proposal, raw, after, reply, baseline), "pending")
        raw.residencyUsageProof = None
        view = self.module.read(raw, raw)[0]
        self.assertIsNone(self.module.propose(view, settings)[0])

    def test_owner_pending_reply_does_not_confirm_or_repeat_request(self):
        raw = self.raw(admission="request")
        raw.native.derived = lua_table(self.h.lua, {"territoryBonuses":{"landlord":0}})
        raw.residencyUsageProof = lua_table(self.h.lua, {**self.h.session,
            "revision": 1, "capturedAt": 0, "attempted": 0})
        settings = self.settings(enabled=True, maxAttempts=1, allowRequests=True)
        proposal = self.module.propose(self.module.read(raw, raw)[0], settings)[0]
        baseline = self.module.capture(proposal, raw)[0]
        after = self.raw(status="pending", myRent=4, admission="request")
        after.revision = after.residencyView.header.revision = 2
        after.native.derived = lua_table(self.h.lua, {})
        self.assertEqual(self.module.evaluate(proposal, raw, after,
            lua_table(self.h.lua, {"ok": True, "pending": True}), baseline), "pending")
        after.residencyUsageProof = raw.residencyUsageProof
        after.residencyUsageProof.revision = 2
        self.assertIsNone(self.module.propose(self.module.read(after, after)[0], settings)[0])
        after.native.derived.residency = lua_table(self.h.lua, {"d": "d1", "rent": 4, "active": True, "kind":"landlord", "share":.075})
        after.residencyView.status = "resident"
        self.assertEqual(self.module.evaluate(proposal, raw, after,
            lua_table(self.h.lua, {"ok": True, "pending": True}), baseline), "confirmed")

    def test_request_call_preserves_nil_argument_and_independent_attachment(self):
        raw = self.raw()
        raw.native.derived = lua_table(self.h.lua, {"territoryBonuses":{"landlord":0}})
        raw.residencyUsageProof = lua_table(self.h.lua, {**self.h.session,
            "revision": 1, "capturedAt": 0, "attempted": 0})
        proposal = self.module.propose(self.module.read(raw, raw)[0],
            self.settings(enabled=True, maxAttempts=1))[0]
        call, reason = self.h.load("src/tabs/territory/TerritoryCallPlan.luau").describe(proposal)
        self.assertIsNone(reason)
        self.assertEqual((call.remote, call.arity, call.args[1], call.args[2]),
                         ("ResidencyAction", 3, "request", "d1"))
        attached, reason = self.h.load("src/tabs/territory/ReadAttachment.luau").attachResidency(
            raw, raw.residencyView)
        self.assertIsNone(reason)
        self.assertEqual(attached.residencyView.districtId, "d1")

    def test_app_broker_native_adapter_confirms_exact_residence_admission(self):
        base = runtime_fixture.AutomationRuntimeTests()
        base.setUp()
        self.h = base.h
        base.runtime.Close(base.runtime)
        self.module = self.h.load("src/tabs/territory/Residency.luau")
        entry = self.h.load("src/tabs/territory/Module.luau")
        deps = {name: self.h.load(path) for name, path in {
            "TerritoryMapQuery": "src/tabs/territory/TerritoryMapQuery.luau",
            "ResidencyQuery": "src/tabs/territory/ResidencyQuery.luau",
            "TerritoryState": "src/tabs/territory/TerritoryState.luau",
            "ReadAttachment": "src/tabs/territory/ReadAttachment.luau",
            "TerritoryBlocked": "src/tabs/territory/TerritoryBlocked.luau"}.items()}
        deps["Residency"] = self.module
        tab = entry.new(lua_table(self.h.lua, deps))
        executor = self.h.lua.execute("""return {calls={},
            Schedule=function(self, callback) callback(); return true end,
            Invoke=function(self, remote, method, ...)
                self.calls[#self.calls+1]={remote=remote,args=table.pack(...)}; return {ok=true}
            end}""")
        native = self.h.load("src/transport/NativeCallPlan.luau")
        plan = native.withTerritory(native, self.h.load("src/tabs/territory/TerritoryCallPlan.luau"))
        adapter = self.h.load("src/transport/NativeDispatchAdapter.luau").new(plan, executor)
        runtime = self.h.load("src/engine/AutomationRuntime.luau").new(lua_table(self.h.lua, {
            "clock": self.h.clock, "transport": adapter, "storage": base.storage,
            "identity": self.h.session, "modules": base.runtime.modules,
            "features": tab.Descriptors(tab), "tabInstances": [tab],
            "featurePages": {"territoryWatch":"territory","station":"territory","residency":"territory"},
            "snapshotAssembler": self.h.load("src/tabs/TabSnapshotAssembler.luau").new(lua_table(self.h.lua,[tab]))}))
        app = self.h.load("src/App.luau").start(lua_table(self.h.lua, {
            "Ember": self.h.load("tests/ember_double.lua")(),
            "Catalog": self.h.load("src/ui/Catalog.luau"),
            "Settings": self.h.load("src/storage/Settings.luau"),
            "EmberAdapter": self.h.load("src/ui/EmberAdapter.luau"),
            "TerritoryTab": entry, "automationRuntimeInstance": runtime}))
        for key, value in (("residency.enabled", True), ("residency.custom.districtId", "d1"),
                ("residency.custom.maxRentPct", 5), ("residency.custom.minSharePct", 1),
                ("residency.custom.maxAttempts", 1)):
            self.assertTrue(app.Set(app, key, value)[0])
        raw = self.raw()
        raw.native.derived = lua_table(self.h.lua, {"territoryBonuses":{"landlord":0}})
        raw.residencyUsageProof = lua_table(self.h.lua, {**self.h.session,
            "revision": 1, "capturedAt": 0, "attempted": 0})
        self.assertTrue(app.Resume(app)[0])
        self.assertTrue(app.Step(app, raw)[0])
        self.assertEqual(len(executor.calls), 1)
        self.assertEqual((executor.calls[1].remote, executor.calls[1].args.n), ("ResidencyAction", 3))
        self.assertEqual(executor.calls[1].args[1], "request")
        self.h.at(1)
        after = self.raw(status="resident", myRent=4)
        after.revision = after.residencyView.header.revision = 2
        after.native.derived = lua_table(self.h.lua, {"residency": {"d": "d1", "rent": 4, "active": True, "kind":"landlord", "share":.075}})
        self.assertTrue(app.Step(app, after)[0])
        self.assertEqual(runtime.Status(runtime).outcomes.residency, "confirmed")
        self.assertEqual(len(executor.calls), 1)
        app.Destroy(app)
        raw = self.raw(myRent=False)
        self.assertIsNone(self.module.preview(raw, raw, self.settings())[0])


if __name__ == "__main__": unittest.main()
