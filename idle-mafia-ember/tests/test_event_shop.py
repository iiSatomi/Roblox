"""Reviewed EventShop rows: earned-medal acquisition only, no reward consumption."""
import unittest
import test_automation_runtime as runtime_fixture

from engine_harness import Harness, ROOT, lua_table


ROWS = [
    {"key": "crate_event", "kind": "crate", "item": "crate_event", "price": 15},
    {"key": "crate_surpriseparty", "kind": "crate", "item": "crate_surpriseparty", "price": 500},
    {"key": "gold", "kind": "item", "item": "gold_bar", "count": 1, "price": 3},
    {"key": "consumables", "kind": "crate", "item": "crate_consumables_bound", "price": 6},
    {"key": "insurance", "kind": "item", "item": "upgrade_insurance", "count": 1, "price": 15},
    {"key": "skillreset", "kind": "item", "item": "vc_skillreset", "count": 1, "price": 20},
]


class EventShopTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.load_components()

    def load_components(self):
        for name in ("NativeEventShopSource", "EventShopBuyer"):
            self.assertTrue((ROOT / f"src/tabs/events/{name}.luau").is_file(), name)
        self.source_module = self.h.load("src/tabs/events/NativeEventShopSource.luau")
        self.module = self.h.load("src/tabs/events/EventShopBuyer.luau")
        self.definition = lua_table(self.h.lua, {"MEDAL": "event_medal", "MAX_ITEM_COUNT": 99, "ROWS": ROWS})
        self.attributes = lua_table(self.h.lua, {"GlobalEventShop": True,
            "GlobalEventShopEnd": 2000, "MWPaidRandomRestricted": True})
        self.h.lua.globals().eventShopAttributes = self.attributes
        callback = self.h.lua.eval("function() return eventShopAttributes end")
        self.source, reason = self.source_module.new(self.definition, callback, "a" * 64, "release-a")
        self.assertIsNone(reason)
        self.buyer = self.module.new(self.source)

    def raw(self, revision=1, medals=100, paid=0, item="crate_event", loose=0, bound=0,
            attempted=0, spent=0):
        raw = self.h.snapshot(revision=revision, native={"fullSync": True,
            "serverNow": 1000 + revision, "paidMedals": paid,
            "inventory": {item: loose}, "inventoryBound": {"event_medal": medals, item: bound}})
        raw.eventShopUsageProof = lua_table(self.h.lua, {**self.h.session,
            "revision": revision, "capturedAt": raw.capturedAt, "attempted": attempted, "spent": spent})
        enriched, reason = self.source.Enrich(self.source, raw)
        self.assertIsNone(reason)
        return enriched

    def settings(self, **changes):
        values = {"enabled": True, "offerKey": "crate_event", "medalReserve": 5,
                  "maxSpend": 15, "maxAttempts": 1}
        values.update(changes)
        return lua_table(self.h.lua, values)

    def proposal(self, raw=None, settings=None):
        raw = raw if raw is not None else self.raw()
        view, reason = self.buyer.read(raw, raw)
        self.assertIsNone(reason)
        proposal, reason = self.buyer.propose(view, settings if settings is not None else self.settings())
        self.assertIsNone(reason)
        return proposal

    def test_current_row_exact_call_and_earned_medal_resource_exposure(self):
        raw = self.raw()
        proposal = self.proposal(raw)
        call, reason = self.module.describe(proposal)
        self.assertIsNone(reason)
        self.assertEqual((call.remote, call.arity, call.args[1], call.args[2], call.args[3]),
                         ("EventShopAction", 3, "buy", "crate_event", 1))
        self.assertEqual(dict(proposal.resources.items()), {"event_medal": 15})
        self.assertIsNotNone(self.buyer.capture(proposal, raw)[0])
        self.assertEqual(len(self.h.transport.sent), 0)

    def test_quote_window_origin_reserve_spend_and_attempt_limits_are_rechecked(self):
        for settings in (self.settings(enabled=False), self.settings(offerKey="Select an offer"),
                self.settings(maxSpend=0), self.settings(maxAttempts=0),
                self.settings(medalReserve=86), self.settings(maxSpend=14)):
            raw = self.raw()
            self.assertIsNone(self.buyer.propose(self.buyer.read(raw, raw)[0], settings)[0])
        for raw in (self.raw(paid=1), self.raw(paid=100), self.raw(attempted=1), self.raw(spent=1)):
            self.assertIsNone(self.buyer.propose(self.buyer.read(raw, raw)[0], self.settings())[0])
        for opened, end in ((False, 2000), (True, 1000)):
            self.attributes.GlobalEventShop, self.attributes.GlobalEventShopEnd = opened, end
            raw = self.raw()
            self.assertIsNone(self.buyer.propose(self.buyer.read(raw, raw)[0], self.settings())[0])

    def test_exact_medal_debit_and_item_acquisition_accept_either_observed_bucket(self):
        for destination in ("loose", "bound"):
            before = self.raw()
            proposal = self.proposal(before)
            baseline = self.buyer.capture(proposal, before)[0]
            after = self.raw(revision=2, medals=85, attempted=1, spent=15,
                             **{destination: 1})
            self.assertEqual(self.buyer.evaluate(proposal, before, after,
                lua_table(self.h.lua, {"ok": True}), baseline), "confirmed", destination)

    def test_gold_insurance_and_skillreset_rows_acquire_items_without_using_effect(self):
        for row in ROWS[2:]:
            before = self.raw(item=row["item"])
            settings = self.settings(offerKey=row["key"], maxSpend=row["price"])
            proposal = self.proposal(before, settings)
            baseline = self.buyer.capture(proposal, before)[0]
            after = self.raw(revision=2, medals=100-row["price"], item=row["item"], bound=1)
            self.assertEqual(self.buyer.evaluate(proposal, before, after,
                lua_table(self.h.lua, {"ok": True}), baseline), "confirmed")
            call = self.module.describe(proposal)[0]
            self.assertEqual(call.args[1], "buy")

    def test_reply_only_wrong_debit_extra_item_loss_and_bound_transfer_do_not_confirm(self):
        before = self.raw(loose=2, bound=1)
        proposal = self.proposal(before)
        baseline = self.buyer.capture(proposal, before)[0]
        for after in (self.raw(revision=2, loose=2, bound=1),
                self.raw(revision=2, medals=84, loose=3, bound=1),
                self.raw(revision=2, medals=85, loose=2, bound=1),
                self.raw(revision=2, medals=85, loose=1, bound=3),
                self.raw(revision=2, medals=85, loose=3, bound=1, paid=1)):
            self.assertEqual(self.buyer.evaluate(proposal, before, after,
                lua_table(self.h.lua, {"ok": True}), baseline), "pending")
        after = self.raw(revision=2, medals=85, loose=3, bound=1)
        after.native.inventory.other = 1
        self.assertEqual(self.buyer.evaluate(proposal, before, after,
            lua_table(self.h.lua, {"ok": True}), baseline), "pending")

    def test_ordinary_reply_scope_and_newer_full_sync_are_mandatory(self):
        before = self.raw()
        proposal = self.proposal(before)
        baseline = self.buyer.capture(proposal, before)[0]
        after = self.raw(revision=2, medals=85, bound=1)
        for reply in (None, {"ok": False}, {"ok": True, "pending": True},
                      {"ok": True, "code": "rate_limited"}):
            self.assertEqual(self.buyer.evaluate(proposal, before, after,
                lua_table(self.h.lua, reply), baseline), "pending")
        for key, value in (("session", "restart"), ("account", "other"),
                           ("release", "new"), ("revision", 1)):
            old = after[key]
            after[key] = value
            self.assertEqual(self.buyer.evaluate(proposal, before, after,
                lua_table(self.h.lua, {"ok": True}), baseline), "pending")
            after[key] = old
        after.native.fullSync = False
        self.assertEqual(self.buyer.evaluate(proposal, before, after,
            lua_table(self.h.lua, {"ok": True}), baseline), "pending")

    def test_stale_or_missing_usage_source_and_capture_custody_are_fail_closed(self):
        for change in ("usage", "usage-header", "usage-type", "source", "paid", "stock", "window"):
            before = self.raw()
            proposal = self.proposal(before)
            if change == "usage": before.eventShopUsageProof = None
            elif change == "usage-header": before.eventShopUsageProof.revision = 99
            elif change == "usage-type": before.eventShopUsageProof.spent = "0"
            elif change == "source": before.eventShopProof.sourceKey = "b" * 64
            elif change == "paid": before.native.paidMedals = 1
            elif change == "stock": before.native.inventory.crate_event = 1
            else: before.eventShopProof.endsAt = 900
            self.assertIsNone(self.buyer.capture(proposal, before)[0], change)

    def test_source_copy_generation_callback_errors_and_unsupported_effects(self):
        first = self.raw()
        second = self.raw(revision=2)
        self.assertIsNone(self.source.Read(self.source, first, first)[0])
        self.definition.ROWS[1].price = 1
        self.assertIsNone(self.source.Read(self.source, second, second)[0])
        self.definition.ROWS[1].price = 15
        second.eventShopProof.offers.crate_event.price = 1
        self.assertIsNone(self.source.Read(self.source, second, second)[0])
        broken = self.h.lua.eval("function() error('attributes unavailable') end")
        source = self.source_module.new(self.definition, broken, "a" * 64, "release-a")[0]
        self.assertIsNone(source.Enrich(source, self.h.snapshot(native={"fullSync": True, "serverNow": 1000}))[0])
        self.definition.ROWS[1].kind = "activate_effect"
        source = self.source_module.new(self.definition,
            self.h.lua.eval("function() return eventShopAttributes end"), "a" * 64, "release-a")[0]
        buyer = self.module.new(source)
        raw = source.Enrich(source, self.h.snapshot(native={"fullSync": True, "serverNow": 1000,
            "inventory": {}, "inventoryBound": {"event_medal": 100}}))[0]
        raw.eventShopUsageProof = lua_table(self.h.lua, {**self.h.session,
            "revision": raw.revision, "capturedAt": raw.capturedAt, "attempted": 0, "spent": 0})
        proposal, reason = buyer.propose(buyer.read(raw, raw)[0], self.settings())
        self.assertIsNone(proposal)
        self.assertIn("supported", reason)

    def test_source_bounds_release_full_sync_callback_mutation_and_close(self):
        callback = self.h.lua.eval("function() return eventShopAttributes end")
        for rows in ([ROWS[0], ROWS[0]], [dict(ROWS[0], price=float("inf"))],
                     [dict(ROWS[0], count=100)], ROWS * 11):
            definition = lua_table(self.h.lua, {"MEDAL": "event_medal", "MAX_ITEM_COUNT": 99, "ROWS": rows})
            self.assertIsNone(self.source_module.new(definition, callback, "a" * 64, "release-a")[0])
        for revision, release, full in ((1, "wrong", True), (1, "release-a", False), (-1, "release-a", True)):
            raw = self.h.snapshot(revision=revision, native={"fullSync": full, "serverNow": 1000})
            raw.release = release
            self.assertIsNone(self.source.Enrich(self.source, raw)[0])
        raw = self.raw()
        copied = self.source.Read(self.source, raw, raw)[0]
        copied.offers.crate_event.price = 1
        self.assertEqual(self.source.Read(self.source, raw, raw)[0].offers.crate_event.price, 15)
        context = self.h.snapshot(revision=2)
        self.assertIsNone(self.source.Read(self.source, raw, context)[0])
        self.source.Close(self.source)
        self.assertIsNone(self.source.Read(self.source, raw, raw)[0])
        self.assertIsNone(self.source.Enrich(self.source, raw)[0])
        self.h.lua.globals().mutatedShopRaw = self.h.snapshot(native={"fullSync": True, "serverNow": 1000})
        mutator = self.h.lua.eval("function() mutatedShopRaw.revision=99; return eventShopAttributes end")
        source = self.source_module.new(self.definition, mutator, "a" * 64, "release-a")[0]
        self.assertIsNone(source.Enrich(source, self.h.lua.globals().mutatedShopRaw)[0])

    def test_window_expiry_after_send_can_confirm_and_describe_rejects_unknown_intent(self):
        before = self.raw()
        proposal = self.proposal(before)
        baseline = self.buyer.capture(proposal, before)[0]
        self.attributes.GlobalEventShop = False
        after = self.raw(revision=2, medals=85, bound=1)
        self.assertEqual(self.buyer.evaluate(proposal, before, after,
            lua_table(self.h.lua, {"ok": True}), baseline), "confirmed")
        proposal.intent.useReward = True
        self.assertIsNone(self.module.describe(proposal)[0])
        self.assertEqual(self.buyer.evaluate(proposal, before, after,
            lua_table(self.h.lua, {"ok": True}), baseline), "pending")

    def test_zero_end_and_absent_paid_marker_follow_native_source(self):
        self.attributes.GlobalEventShopEnd = 0
        self.attributes.MWPaidRandomRestricted = None
        raw = self.raw(paid=None)
        view = self.buyer.read(raw, raw)[0]
        self.assertTrue(view.restricted)
        self.assertEqual(view.paidMedals, 0)
        self.assertIsNotNone(self.buyer.propose(view, self.settings())[0])

    def test_old_profiles_default_new_choices_and_malformed_inputs_fail_closed(self):
        model = self.h.load("src/storage/Settings.luau").new(self.h.load("src/ui/Catalog.luau"))
        model.Set(model, "eventShop.custom.maxSpend", 100)
        prepared, reason = model.Validate(model, lua_table(self.h.lua, {"schema": 1,
            "values": {"eventShop.enabled": False}}), True)
        self.assertIsNone(reason)
        self.assertEqual(prepared["eventShop.custom.maxSpend"], 0)
        self.assertEqual(prepared["eventShop.custom.maxAttempts"], 0)
        self.assertEqual(prepared["eventShop.custom.offerKey"], "Select an offer")
        for key, bad in (("maxSpend", "15"), ("maxSpend", float("inf")),
                         ("medalReserve", False), ("maxAttempts", -1)):
            raw = self.raw()
            self.assertIsNone(self.buyer.propose(self.buyer.read(raw, raw)[0], self.settings(**{key: bad}))[0])
        raw = self.raw()
        raw.native.inventoryBound = lua_table(self.h.lua, {"event_medal": 100,
            **{f"item_{i}": 1 for i in range(1000)}})
        self.assertIsNone(self.buyer.read(raw, raw)[0])
        raw = self.raw()
        proposal = self.proposal(raw)
        baseline = self.buyer.capture(proposal, raw)[0]
        after = self.raw(revision=2, medals=85, bound=1)
        baseline.revision = "broken"
        self.assertEqual(self.buyer.evaluate(proposal, raw, after,
            lua_table(self.h.lua, {"ok": True}), baseline), "pending")

    def test_malformed_inventory_marker_and_attributes_never_supply_a_quote(self):
        for field, value in (("paidMedals", False), ("paidMedals", -1),
                              ("paidMedals", float("nan"))):
            raw = self.raw()
            raw.native[field] = value
            self.assertIsNone(self.buyer.read(raw, raw)[0])
        raw = self.raw()
        raw.native.inventoryBound.event_medal = "100"
        self.assertIsNone(self.buyer.read(raw, raw)[0])
        for value in (None, "true"):
            self.attributes.GlobalEventShop = value
            raw = self.h.snapshot(native={"fullSync": True, "serverNow": 1000})
            self.assertIsNone(self.source.Enrich(self.source, raw)[0])

    def app_runtime(self, reuse=False):
        if not reuse:
            base = runtime_fixture.AutomationRuntimeTests();base.setUp()
            base.runtime.Close(base.runtime);self.runtime_base=base
        base=self.runtime_base
        self.h = base.h
        base.storage.Write=self.h.lua.eval("function(self,key,value) self.data[key]=value return true end")
        self.load_components()
        tab_module = self.h.load("src/tabs/events/Module.luau")
        deps = {"EventShopBuyer": self.module, "NativeEventShopSource": self.source_module,
            "eventShopSource": self.source, "fingerprint": "a" * 64, "release": "release-a",
            "EventShopBlocked": self.h.load("src/tabs/events/EventShopBlocked.luau")}
        for name, folder in (("FreeBriefcasesState", "game"), ("FreeBriefcases", "features"),
                              ("FreeBriefcasesEvidence", "features")):
            deps[name] = self.h.load(f"src/{folder}/{name}.luau")
        tab = tab_module.new(lua_table(self.h.lua, deps))
        executor = self.h.lua.execute("""return {calls={},
            Schedule=function(self, cb) self.callback=cb; return true end,
            Invoke=function(self, remote, method, ...)
                self.calls[#self.calls+1]={remote=remote,args=table.pack(...)}; return self.reply or {ok=true}
            end}""")
        native = self.h.load("src/transport/NativeCallPlan.luau")
        plan = native.withEvents(native, self.module)
        adapter = self.h.load("src/transport/NativeDispatchAdapter.luau").new(plan, executor)
        runtime = self.h.load("src/engine/AutomationRuntime.luau").new(lua_table(self.h.lua, {
            "clock": self.h.clock, "transport": adapter, "storage": base.storage,
            "identity": self.h.session, "modules": base.runtime.modules, "features": tab.Descriptors(tab), "tabInstances":[tab],
            "featurePages":{"briefcases":"events","eventShop":"events"},
            "snapshotAssembler":self.h.load("src/tabs/TabSnapshotAssembler.luau").new(lua_table(self.h.lua,[tab]))}))
        self.app_ember = self.h.load("tests/ember_double.lua")()
        app = self.h.load("src/App.luau").start(lua_table(self.h.lua, {
            "Ember": self.app_ember, "Catalog": self.h.load("src/ui/Catalog.luau"),
            "Settings": self.h.load("src/storage/Settings.luau"), "EmberAdapter": self.h.load("src/ui/EmberAdapter.luau"),
            "EventsTab": tab_module, "SettingsTab": self.h.load("src/tabs/settings/Module.luau"),
            "automationRuntimeInstance": runtime}))
        self.assertFalse(app.model["values"]["eventShop.enabled"])
        self.assertEqual(app.model["values"]["eventShop.custom.maxSpend"], 0)
        self.assertEqual(app.model["values"]["eventShop.custom.maxAttempts"], 0)
        self.assertEqual(app.model["values"]["eventShop.custom.offerKey"], "Select an offer")
        self.assertEqual(app.model["values"]["eventShop.custom.medalReserve"], 0)
        handle = app.ui.handles["eventShop.custom.offerKey"]
        self.assertEqual(list(handle.options.Options.values()), ["Select an offer"] + [row["key"] for row in ROWS])
        self.assertTrue(app.ui.numeric["eventShop.custom.maxSpend"])
        self.assertIsNone(app.ui.features.eventShop.blockedReason)
        for key, bad in (("offerKey", "unknown"), ("maxSpend", -1),
                         ("maxAttempts", 0.5), ("medalReserve", float("nan"))):
            self.assertFalse(app.Set(app, "eventShop.custom." + key, bad)[0])
        for key, value in (("eventShop.enabled", True), ("eventShop.custom.offerKey", "crate_event"),
                           ("eventShop.custom.maxSpend", 15), ("eventShop.custom.maxAttempts", 1)):
            self.assertTrue(app.Set(app, key, value)[0])
        app.Resume(app)
        return app, runtime, executor

    def test_app_broker_native_adapter_exact_medal_purchase(self):
        app, runtime, executor = self.app_runtime()
        app.Step(app, self.raw())
        executor.callback()
        self.assertEqual(len(executor.calls), 1)
        self.assertEqual((executor.calls[1].remote, executor.calls[1].args.n,
            executor.calls[1].args[2], executor.calls[1].args[3]), ("EventShopAction", 3, "crate_event", 1))
        self.h.at(1)
        app.Step(app, self.raw(revision=2, medals=85, bound=1, attempted=1, spent=15))
        self.assertEqual(runtime.Status(runtime).outcomes.eventShop, "confirmed")
        app.Destroy(app)

    def test_queued_purchase_rechecks_native_shop_attributes_before_emission(self):
        for field, changed in (('GlobalEventShop', False), ('GlobalEventShopEnd', 999),
                               ('MWPaidRandomRestricted', False), ('serverNow', 2000),
                               ('serverNow', float('nan'))):
            app, runtime, executor = self.app_runtime()
            try:
                before = self.raw()
                app.Step(app, before)
                self.attributes[field] = changed
                executor.callback()
                self.assertEqual(len(executor.calls), 0, field)
                self.assertEqual(len(runtime.checkpoint.Records(runtime.checkpoint)), 0)
                self.assertEqual(runtime.checkpoint.EventShopUsage(runtime.checkpoint, before)[0].spent, 0)
            finally:
                app.Destroy(app)

    def test_uncertain_attempt_is_not_renewed_or_confirmed_by_late_callback(self):
        app, runtime, executor = self.app_runtime()
        self.h.at(46)
        delayed = self.raw(revision=2, attempted=1, spent=15)
        self.h.at(0)
        self.h.lua.globals().eventLateApp = app
        self.h.lua.globals().eventLateRaw = delayed
        executor.Invoke = self.h.lua.eval("""function(self, remote, method, ...)
            self.calls[#self.calls+1]={remote=remote,args=table.pack(...)}
            testNow=46; eventLateApp:Step(eventLateRaw); return {ok=true}
        end""")
        app.Step(app, self.raw())
        executor.callback()
        self.assertNotEqual(runtime.Status(runtime).outcomes.eventShop, "confirmed")
        self.h.at(47)
        app.Step(app, self.raw(revision=3, medals=85, bound=1, attempted=1, spent=15))
        self.assertEqual(len(executor.calls), 1)
        self.assertNotEqual(runtime.Status(runtime).outcomes.eventShop, "confirmed")
        app.Destroy(app)

    def test_runtime_usage_survives_reload_and_caller_zero_totals_do_not_renew_allowance(self):
        app, runtime, executor = self.app_runtime()
        try:
            app.Step(app, self.raw())
            executor.callback()
            self.h.at(1)
            app.Step(app, self.raw(revision=2, medals=85, bound=1))
            self.assertEqual(runtime.Status(runtime).outcomes.eventShop, "confirmed")
            self.h.at(2)
            app.Step(app, self.raw(revision=3, medals=85, bound=1, attempted=0, spent=0))
            self.assertEqual(len(executor.calls), 1)
            self.assertIn("cap", runtime.Status(runtime).reasons.eventShop)
            m = runtime.modules
            restored = m.Checkpoint.new(runtime.checkpoint.storage, m.FamilyContributionUsage,
                m.ResourceReservations, m.PendingAction, m.EventShopUsage)
            self.assertIsNone(restored.Load(restored, "user-a", self.h.session["place"], "release-a")[1])
            proof = restored.EventShopUsage(restored, self.raw(revision=3, medals=85, bound=1))[0]
            self.assertEqual((proof.attempted, proof.spent), (1, 15))
        finally:
            app.Destroy(app)

    def test_disabling_queued_purchase_refunds_only_known_unsent_charge(self):
        app, runtime, executor = self.app_runtime()
        try:
            before = self.raw()
            app.Step(app, before)
            self.assertEqual(runtime.checkpoint.EventShopUsage(runtime.checkpoint, before)[0].spent, 15)
            app.Set(app, "eventShop.enabled", False)
            executor.callback()
            self.assertEqual(len(executor.calls), 0)
            self.assertEqual(runtime.checkpoint.EventShopUsage(runtime.checkpoint, before)[0].spent, 0)
            self.assertEqual(len(runtime.checkpoint.Records(runtime.checkpoint)), 0)
        finally:
            app.Destroy(app)

    def test_settings_review_confirm_resets_local_allowance_and_allows_an_explicit_new_run(self):
        app, runtime, executor = self.app_runtime()
        try:
            app.Step(app, self.raw())
            executor.callback()
            self.h.at(1)
            after = self.raw(revision=2, medals=85, bound=1)
            app.Step(app, after)
            app.Pause(app)
            buttons = {handle.options.Text: handle for handle in app.ui.window.handles.values() if handle.kind == "Button"}
            self.assertEqual(runtime.checkpoint.Allowance(runtime.checkpoint, "eventShop")[0].spent, 15)
            buttons["Confirm allowance reset"].Click(buttons["Confirm allowance reset"])
            self.h.lua.globals().testNow = 1
            # Ember callbacks are deliberately deferred by the local UI double.
            self.app_ember.Flush()
            self.assertEqual(runtime.checkpoint.Allowance(runtime.checkpoint, "eventShop")[0].spent, 15)
            buttons["Review allowance"].Click(buttons["Review allowance"])
            self.app_ember.Flush()
            self.assertIn("15", app.ui.settings.allowanceStatus.Get(app.ui.settings.allowanceStatus))
            buttons["Confirm allowance reset"].Click(buttons["Confirm allowance reset"])
            self.app_ember.Flush()
            self.assertEqual(runtime.checkpoint.Allowance(runtime.checkpoint, "eventShop")[0].spent, 0)
            self.assertTrue(app.model.paused)
            self.assertEqual(app.model["values"]["eventShop.custom.maxSpend"], 15)
            self.assertEqual(len(executor.calls), 1)
            app.Resume(app)
            self.h.at(2)
            app.Step(app, self.raw(revision=3, medals=85, bound=1))
            executor.callback()
            self.assertEqual(len(executor.calls), 2)
        finally:
            app.Destroy(app)

    def test_resume_is_refused_while_a_reviewed_reset_is_saving(self):
        app, runtime, executor = self.app_runtime()
        try:
            app.Step(app, self.raw())
            executor.callback()
            self.h.at(1)
            app.Step(app, self.raw(revision=2, medals=85, bound=1))
            app.Pause(app)
            self.assertIsNotNone(app.PreviewAllowance(app, "eventShop")[0])
            runtime.checkpoint.storage.Write = self.h.lua.eval("""function(self,key,value)
                coroutine.yield('reset_wait');self.data[key]=value;return true end""")
            self.h.lua.globals().resetSavingApp = app
            self.h.lua.execute("resetSaving=coroutine.create(function() return resetSavingApp:ConfirmAllowance('eventShop') end);assert(select(2,coroutine.resume(resetSaving))=='reset_wait')")
            self.assertTrue(runtime.AllowanceResetBusy(runtime))
            self.assertFalse(app.Resume(app)[0])
            self.assertTrue(app.model.paused)
            self.h.lua.execute("assert(coroutine.resume(resetSaving))")
            self.assertFalse(runtime.AllowanceResetBusy(runtime))
            self.assertEqual(runtime.checkpoint.Allowance(runtime.checkpoint, "eventShop")[0].spent, 0)
            self.assertEqual(len(executor.calls), 1)
        finally:
            app.Destroy(app)

    def test_rate_limited_receipt_keeps_usage_and_prevents_allowance_reset(self):
        app,runtime,executor=self.app_runtime()
        try:
            executor.Invoke=self.h.lua.eval("function(self,remote,method,...) self.calls[#self.calls+1]={remote=remote,args=table.pack(...)} return {ok=false,code='rate_limited',retryIn=10} end")
            app.Step(app,self.raw());executor.callback();self.h.at(1)
            app.Step(app,self.raw(revision=2))
            self.assertIsNone(runtime.Status(runtime).outcomes.eventShop)
            app.Pause(app)
            self.assertIsNone(app.PreviewAllowance(app,"eventShop")[0])
            self.assertFalse(app.ConfirmAllowance(app,"eventShop")[0])
            self.h.at(45);app.Step(app,self.raw(revision=3))
            self.assertEqual(runtime.Status(runtime).outcomes.eventShop,"skipped_unconfirmed")
            self.assertEqual(runtime.checkpoint.Allowance(runtime.checkpoint,"eventShop")[0].spent,15)
            self.assertEqual(len(executor.calls),1)
        finally:app.Destroy(app)


if __name__ == "__main__":
    unittest.main()
