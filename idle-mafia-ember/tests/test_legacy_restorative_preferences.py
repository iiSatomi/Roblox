"""Legacy restorative choices preserve shared-policy and zero-disable intent."""
import json
import unittest
from engine_harness import lua_table
from test_redundant_store import plain
import test_profile_management as profiles
import test_automation_runtime as runtime_fixture
import test_inventory_restoratives as restoratives


MODE_KEYS = ("consumableHealthMode", "consumableEnergyMode", "consumableStaminaMode")


class LegacyRestorativePreferencesTests(unittest.TestCase):
    def setUp(self):
        self.f = profiles.ProfileManagementTests()
        self.f.setUp()
        self.app, self.h = self.f.app, self.f.h

    def tearDown(self):
        self.f.tearDown()

    def preview(self, **choices):
        return self.app.PreviewImport(self.app, json.dumps({"version": 17, **choices}))

    def test_matching_size_preferences_map_without_item_permission_or_activation(self):
        for policy in ("Small first", "Large first"):
            accepted, reason = self.preview(**dict.fromkeys(MODE_KEYS, policy))
            self.assertTrue(accepted, reason)
            self.assertEqual(self.app.staged["values"]["restoratives.policy"], policy)
            self.assertFalse(self.app.staged["values"]["restoratives.enabled"])
            self.assertEqual(self.app.staged["values"]["restoratives.custom.custody"], "Bound only")
            self.assertTrue(self.app.model.paused)
            self.assertEqual(len(self.f.base.storage.data), 0)

    def test_mixed_and_omitted_pool_preferences_map_exact_policies(self):
        for choices in ({"consumableHealthMode": "Small first"},
                        dict(zip(MODE_KEYS, ("Small first", "Large first", "Small first")))):
            accepted, reason = self.preview(**choices)
            self.assertTrue(accepted, reason)
            for pool, key in zip(("health", "energy", "stamina"), MODE_KEYS):
                expected = choices.get(key, "Balanced")
                if expected == "Balanced": expected = "Balanced recovery"
                self.assertEqual(self.app.staged["values"][f"restoratives.custom.{pool}Policy"], expected)
            self.assertFalse(self.app.staged["values"]["restoratives.enabled"])
            self.assertEqual(self.app.staged["values"]["restoratives.custom.custody"], "Bound only")
            self.assertEqual(plain(self.app.importReview.original), {"version": 17, **choices})

    def test_unknown_size_labels_and_types_refuse_without_staging(self):
        for invalid in ("Largest", "", False, 1, {}):
            choices = dict.fromkeys(MODE_KEYS, "Small first")
            choices[MODE_KEYS[1]] = invalid
            accepted, reason = self.preview(**choices)
            self.assertFalse(accepted)
            self.assertIn(MODE_KEYS[1], reason)
            self.assertIsNone(self.app.staged)

    def test_legacy_zero_pool_disable_maps_to_off_without_permission(self):
        for pool in ("health", "energy", "stamina"):
            key = "consumable" + pool.title() + "Below"
            accepted, reason = self.preview(**{key: 0}, **dict.fromkeys(MODE_KEYS, "Large first"))
            self.assertTrue(accepted, reason)
            self.assertEqual(self.app.staged["values"][f"restoratives.custom.{pool}Policy"], "Off")
            self.assertEqual(self.app.staged["values"][f"restoratives.custom.{pool}Below"], 0)
            self.assertFalse(self.app.staged["values"]["restoratives.enabled"])
            self.assertEqual(self.app.staged["values"]["restoratives.custom.custody"], "Bound only")
            self.assertEqual(self.app.importReview.original[key], 0)

    def test_explicit_nonzero_thresholds_preserve_exact_integers_including_old_defaults(self):
        for threshold in (1, 25, 100):
            choices = {"consumable" + pool.title() + "Below": threshold for pool in ("health", "energy", "stamina")}
            accepted, reason = self.preview(**choices)
            self.assertTrue(accepted, reason)
            for pool in ("health", "energy", "stamina"):
                self.assertEqual(self.app.staged["values"][f"restoratives.custom.{pool}Below"], threshold)

    def test_fractional_pool_thresholds_preserve_exact_values(self):
        for threshold in (0.001, 25.5, 99.999):
            for pool in ("health", "energy", "stamina"):
                key = "consumable" + pool.title() + "Below"
                accepted, reason = self.preview(**{key: threshold})
                self.assertTrue(accepted, reason)
                self.assertEqual(self.app.staged["values"][f"restoratives.custom.{pool}Below"], threshold)
                self.assertEqual(self.app.importReview.original[key], threshold)

    def test_invalid_pool_thresholds_refuse_without_staging(self):
        for value in (-0.001, 100.001, float("nan"), float("inf"), -float("inf"), True, "25.5"):
            accepted, reason = self.preview(consumableHealthBelow=value)
            self.assertFalse(accepted)
            self.assertIsNone(self.app.staged)

    def test_tradable_item_permission_is_not_inferred_from_matching_policy(self):
        choices = dict.fromkeys(MODE_KEYS, "Large first")
        accepted, reason = self.preview(**choices, consumableUseTradable=True)
        self.assertFalse(accepted)
        self.assertIn("consumableUseTradable", reason)
        self.assertIsNone(self.app.staged)
        self.assertFalse(self.app.model["values"]["restoratives.enabled"])

    def runtime_app(self):
        f = runtime_fixture.AutomationRuntimeTests()
        f.setUp()
        feature = f.h.load("src/tabs/inventory/Restoratives.luau")
        spec = lua_table(f.h.lua, {"id": "restoratives", "reader": feature, "planner": feature, "evidence": feature})
        f.runtime.features.restoratives = spec
        f.h.lua.eval("function(rows, row) rows[#rows+1]=row end")(f.runtime.order, spec)
        executor = f.install_native_adapter()
        plan = f.h.load("src/transport/NativeCallPlan.luau")
        plan = plan.withInventory(plan.withCrew(f.h.load("src/tabs/crew/CrewCallPlan.luau")),
                                  f.h.load("src/tabs/inventory/InventoryCallPlan.luau"))
        f.runtime.session.broker.transport = f.h.load("src/transport/NativeDispatchAdapter.luau").new(plan, executor)
        app = f.start_test_app()
        self.addCleanup(app.Destroy, app)
        self.assertTrue(app.ApplyProfile(app, lua_table(f.h.lua, plain(self.app.staged)))[0])
        self.assertTrue(app.model.paused)
        self.assertEqual(len(executor.calls), 0)
        before = f.raw()
        before.restorativeCatalog = lua_table(f.h.lua, {"release": "release-a", "catalogKey": "a"*64,
            "cooldown": 3, "items": [{"id": item, "pool": pool, "percent": percent}
                                    for item, pool, percent in restoratives.ITEMS]})
        before.native.serverNow = 2000000
        before.native.consumableUseSequence = 4
        before.native.consumableReadyAt = 1999999
        before.native.pools = lua_table(f.h.lua, {"health": 30, "energy": 100, "stamina": 100})
        before.native.stats = lua_table(f.h.lua, {"maxHealth": 100, "maxStamina": 100})
        before.native.derived.effMaxEnergy = 100
        before.native.inventoryBound = lua_table(f.h.lua, {item: 1 for item, _, _ in restoratives.ITEMS})
        self.assertTrue(app.Set(app, "restoratives.enabled", True)[0])
        return f, app, executor, before

    def test_imported_size_preference_reaches_actual_app_native_dispatch(self):
        for policy, expected in (("Small first", "con_bandages"), ("Large first", "con_medkit_large")):
            with self.subTest(policy=policy):
                accepted, reason = self.preview(**dict.fromkeys(MODE_KEYS, policy))
                self.assertTrue(accepted, reason)
                f, app, executor, before = self.runtime_app()
                app.Resume(app)
                app.Step(app, before)
                executor.Drain(executor)
                self.assertEqual(len(executor.calls), 1)
                self.assertEqual(executor.calls[1].remote, "UseConsumable")
                self.assertEqual(executor.calls[1].args[1], expected)
                self.assertTrue(executor.calls[1].args[2])
                self.assertEqual(executor.calls[1].args[3], 4)

    def test_imported_mixed_policies_select_each_pool_through_native_dispatch(self):
        choices = dict(zip(MODE_KEYS, ("Small first", "Large first", "Balanced")))
        choices.update({"consumable" + pool.title() + "Below": 50 for pool in ("health", "energy", "stamina")})
        self.assertTrue(self.preview(**choices)[0])
        for pool, expected in (("health", "con_bandages"), ("energy", "con_energy_pack"), ("stamina", "con_sandwich")):
            f, app, executor, before = self.runtime_app()
            before.native.pools = lua_table(f.h.lua, {"health": 100, "energy": 100, "stamina": 100})
            before.native.pools[pool] = 30
            app.Resume(app)
            app.Step(app, before)
            executor.Drain(executor)
            self.assertEqual(len(executor.calls), 1)
            self.assertEqual(executor.calls[1].args[1], expected)

    def test_imported_zero_disables_empty_pool_and_next_pool_can_dispatch(self):
        self.assertTrue(self.preview(consumableHealthBelow=0, consumableEnergyMode="Small first")[0])
        f, app, executor, before = self.runtime_app()
        before.native.pools.health = 0
        app.Resume(app)
        app.Step(app, before)
        executor.Drain(executor)
        self.assertEqual(len(executor.calls), 0)
        before.native.pools.energy = 0
        before.revision = 2
        app.Step(app, before)
        executor.Drain(executor)
        self.assertEqual(len(executor.calls), 1)
        self.assertEqual(executor.calls[1].args[1], "con_energy_small")

    def test_imported_fractional_threshold_dispatches_without_rounding_at_exact_boundary(self):
        for pool in ("health", "energy", "stamina"):
            for current, expected in ((25.499, 1), (25.5, 1), (25.501, 0)):
                with self.subTest(pool=pool, current=current):
                    self.assertTrue(self.preview(**{"consumable" + pool.title() + "Below": 25.5})[0])
                    f, app, executor, before = self.runtime_app()
                    before.native.pools = lua_table(f.h.lua, {"health": 100, "energy": 100, "stamina": 100})
                    before.native.pools[pool] = current
                    app.Resume(app)
                    app.Step(app, before)
                    executor.Drain(executor)
                    self.assertEqual(len(executor.calls), expected)

    def test_threshold_controls_reject_nonfinite_and_out_of_range_without_rounding(self):
        self.assertTrue(self.preview()[0])
        f, app, executor, before = self.runtime_app()
        for pool in ("health", "energy", "stamina"):
            key = f"restoratives.custom.{pool}Below"
            for invalid in (-0.001, 100.001, float("nan"), float("inf"), -float("inf"), True, "25.5"):
                self.assertFalse(app.Set(app, key, invalid)[0])
            for valid in (0, 0.001, 25.5, 99.999, 100):
                self.assertTrue(app.Set(app, key, valid)[0])
                self.assertEqual(app.model["values"][key], valid)
        self.assertFalse(app.Set(app, "restoratives.custom.minUsefulPercent", 0.5)[0])

    def test_balanced_fractional_waste_and_ties_reach_actual_native_dispatch(self):
        for current, expected in ((50.001, "con_bandages"), (50.00000001, "con_bandages"), (50, "con_medkit_small")):
            for policy in ("Shared policy", "Balanced recovery"):
                with self.subTest(current=current, policy=policy):
                    self.assertTrue(self.preview(consumableHealthBelow=75)[0])
                    f, app, executor, before = self.runtime_app()
                    self.assertTrue(app.Set(app, "restoratives.custom.healthPolicy", policy)[0])
                    before.native.pools.health = current
                    app.Resume(app)
                    app.Step(app, before)
                    executor.Drain(executor)
                    self.assertEqual(len(executor.calls), 1)
                    self.assertEqual(executor.calls[1].args[1], expected)
                    self.assertTrue(executor.calls[1].args[2])

    def test_queued_pool_shared_threshold_custody_disable_and_unload_changes_refuse(self):
        changes = (("restoratives.custom.healthPolicy", "Off"),
                   ("restoratives.custom.healthPolicy", "Small first"),
                   ("restoratives.custom.energyPolicy", "Off"),
                   ("restoratives.policy", "Large first"),
                   ("restoratives.custom.healthBelow", 1),
                   ("restoratives.custom.custody", "Bound or tradable"),
                   ("restoratives.enabled", False), (None, None))
        for key, value in changes:
            with self.subTest(key=key, value=value):
                self.assertTrue(self.preview()[0])
                f, app, executor, before = self.runtime_app()
                app.Resume(app)
                app.Step(app, before)
                self.assertEqual(len(executor.queued), 1)
                if key: self.assertTrue(app.Set(app, key, value)[0])
                else: app.Destroy(app)
                executor.Drain(executor)
                self.assertEqual(len(executor.calls), 0)

    def test_pool_controls_validate_and_round_trip_old_profiles_keep_shared_fallback(self):
        self.assertTrue(self.preview()[0])
        f, app, executor, before = self.runtime_app()
        for pool in ("health", "energy", "stamina"):
            key = f"restoratives.custom.{pool}Policy"
            self.assertEqual(app.model["values"][key], "Shared policy")
            for invalid in ("Largest", "", True, 1):
                self.assertFalse(app.Set(app, key, invalid)[0])
            for policy in ("Shared policy", "Off", "Balanced recovery", "Small first", "Large first"):
                self.assertTrue(app.Set(app, key, policy)[0])
        profile = app.model.Snapshot(app.model)
        self.assertTrue(app.ApplyProfile(app, profile)[0])
        self.assertEqual(app.model["values"]["restoratives.custom.staminaPolicy"], "Large first")
        self.assertTrue(app.Set(app, "restoratives.custom.healthBelow", 25.5)[0])
        old = lua_table(f.h.lua, {"schema": 1, "values": {"restoratives.enabled": True,
            "restoratives.policy": "Large first"}})
        self.assertTrue(app.ApplyProfile(app, old)[0])
        self.assertEqual(app.model["values"]["restoratives.custom.healthPolicy"], "Shared policy")
        app.Resume(app)
        app.Step(app, before)
        executor.Drain(executor)
        self.assertEqual(len(executor.calls), 1)
        self.assertEqual(executor.calls[1].args[1], "con_medkit_large")


if __name__ == "__main__":
    unittest.main()
