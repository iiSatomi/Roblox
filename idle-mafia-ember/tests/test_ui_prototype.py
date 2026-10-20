"""Behavioral tests of fresh Lua-compatible Luau, not live UI verification."""
import json
import importlib.util
from pathlib import Path
import unittest

from lupa import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]


class PrototypeTests(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)

    def module(self, name):
        return self.lua.execute((ROOT / name).read_text(encoding="utf-8"))

    def table(self, value):
        if isinstance(value, dict):
            return self.lua.table_from({k: self.table(v) for k, v in value.items()})
        if isinstance(value, list):
            return self.lua.table_from([self.table(v) for v in value])
        return value

    def model(self):
        catalog = self.table(json.loads((ROOT / "preview/catalog.json").read_text(encoding="utf-8")))
        return self.module("src/storage/Settings.luau").new(catalog)

    def app(self, **options):
        ember = self.module("tests/ember_double.lua")()
        for key, value in options.items():
            ember[key] = value
        dependencies = self.table({})
        dependencies.Ember = ember
        dependencies.Catalog = self.module("src/ui/Catalog.luau")
        dependencies.Settings = self.module("src/storage/Settings.luau")
        dependencies.EmberAdapter = self.module("src/ui/EmberAdapter.luau")
        return self.module("src/App.luau").start(dependencies), ember

    def profile(self, **values):
        return self.table({"schema": 1, "values": values})

    def test_defaults_are_false_and_paused(self):
        model = self.model()
        self.assertTrue(model.paused)
        for key, value in model["values"].items():
            if key.endswith(".enabled"):
                self.assertIs(value, False)

    def test_false_hydration_and_snapshot_are_independent(self):
        model = self.model()
        self.assertTrue(model.Set(model, "jobs.enabled", True)[0])
        prepared, error = model.Validate(model, self.profile(**{"jobs.enabled": False}))
        self.assertIsNone(error)
        model.Commit(model, prepared)
        self.assertIs(model["values"]["jobs.enabled"], False)
        snapshot = model.Snapshot(model)
        snapshot["values"]["jobs.enabled"] = True
        self.assertIs(model["values"]["jobs.enabled"], False)

    def test_profile_rejection_is_atomic(self):
        model = self.model()
        for values in ({"jobs.enabled": True, "unknown": True},
                       {"jobs.enabled": "false"},
                       {"jobs.policy": "Impossible"},
                       {"combat.custom.healthFloor": 101},
                       {"combat.custom.minimumPayout": float("nan")}):
            prepared, error = model.Validate(model, self.profile(**values))
            self.assertIsNone(prepared)
            self.assertTrue(error)
            self.assertIs(model["values"]["jobs.enabled"], False)
        prepared, error = model.Validate(model, self.table({"schema": 2, "values": {}}))
        self.assertIsNone(prepared)
        self.assertTrue(error)

    def test_gear_exclusion_and_conflicting_import(self):
        model = self.model()
        model.Set(model, "crew.enabled", True)
        model.Set(model, "crewGear.enabled", True)
        self.assertIs(model["values"]["crew.enabled"], False)
        prepared, error = model.Validate(model, self.profile(**{
            "jobs.enabled": True, "crew.enabled": True, "crewGear.enabled": True}))
        self.assertIsNone(prepared)
        self.assertIn("Conflicting", error)
        self.assertIs(model["values"]["jobs.enabled"], False)

    def test_stop_latch_and_import_cannot_resume(self):
        model = self.model()
        model.Set(model, "jobs.enabled", True)
        model.Stop(model)
        model.Set(model, "jobs.enabled", True)
        self.assertTrue(model.stopped)
        model.Resume(model)
        self.assertFalse(model.stopped)
        prepared, _ = model.Validate(model, self.profile(**{"jobs.enabled": False}))
        model.Commit(model, prepared)
        self.assertTrue(model.paused)

    def test_catalog_renders_all_tabs_and_every_feature_once(self):
        app, ember = self.app()
        self.assertEqual(len(app.ui.window.sections), 25)
        self.assertEqual(len(list(app.ui.features.items())), 55)
        self.assertIs(ember.configured.Storage, False)
        self.assertIs(ember.configured.Effects.RespectReducedMotion, True)
        self.assertEqual(app.ui.window.options.Keybind, "F8")
        self.assertFalse(app.ui.window.options.SaveLayout)

    def test_import_updates_false_silently_and_does_not_release_pause(self):
        app, ember = self.app()
        app.Set(app, "jobs.enabled", True)
        ok, error = app.ApplyProfile(app, self.profile(**{"jobs.enabled": False}))
        self.assertTrue(ok, error)
        self.assertIs(app.ui.handles["jobs.enabled"].Get(app.ui.handles["jobs.enabled"]), False)
        self.assertEqual(len(ember.queue), 0)
        self.assertTrue(app.model.paused)

    def test_refused_import_rolls_back_ui_and_model(self):
        app, _ = self.app()
        app.ui.handles["jobs.policy"].reject = "XP"
        ok, error = app.ApplyProfile(app, self.profile(**{"jobs.enabled": True, "jobs.policy": "XP"}))
        self.assertFalse(ok)
        self.assertIn("refused", error)
        self.assertIs(app.model["values"]["jobs.enabled"], False)
        self.assertIs(app.ui.handles["jobs.enabled"].Get(app.ui.handles["jobs.enabled"]), False)

    def test_queued_toggle_cannot_revive_after_stop_or_unload(self):
        app, ember = self.app()
        handle = app.ui.handles["jobs.enabled"]
        handle.Set(handle, True)
        app.Stop(app)
        ember.Flush(True)
        self.assertIs(app.model["values"]["jobs.enabled"], False)
        self.assertTrue(app.model.stopped)
        handle.Set(handle, True)
        app.Destroy(app)
        ember.Flush()
        self.assertFalse(app.alive)
        self.assertIs(app.model["values"]["jobs.enabled"], False)

    def test_delayed_callbacks_use_current_values(self):
        app, ember = self.app()
        handle = app.ui.handles["jobs.enabled"]
        handle.Set(handle, True)
        handle.Set(handle, False)
        ember.Flush(True)
        self.assertIs(app.model["values"]["jobs.enabled"], False)

    def test_custom_input_validation_and_visibility(self):
        app, ember = self.app()
        app.Set(app, "combat.policy", "Custom")
        self.assertTrue(app.ui.features.combat.custom.visible)
        handle = app.ui.handles["combat.custom.healthFloor"]
        handle.Set(handle, "101")
        ember.Flush()
        self.assertEqual(app.model["values"]["combat.custom.healthFloor"], 50)
        self.assertEqual(handle.Get(handle), "50")
        handle.Set(handle, "65")
        ember.Flush()
        self.assertEqual(app.model["values"]["combat.custom.healthFloor"], 65)
        app.Set(app, "combat.policy", "Cautious")
        self.assertFalse(app.ui.features.combat.custom.visible)

    def test_recreate_and_constructor_failure_clean_up(self):
        app, ember = self.app()
        deps = self.table({"Ember": ember,
                           "Catalog": self.module("src/ui/Catalog.luau"),
                           "Settings": self.module("src/storage/Settings.luau"),
                           "EmberAdapter": self.module("src/ui/EmberAdapter.luau")})
        second = self.module("src/App.luau").start(deps)
        self.assertFalse(app.alive)
        self.assertTrue(second.alive)
        ember.failLabel = "Allow Do Jobs"
        with self.assertRaisesRegex(Exception, "construction failed"):
            self.module("src/App.luau").start(deps)
        self.assertFalse(second.alive)
        self.assertTrue(ember.windows[3].destroyed)

    def test_missing_input_is_rejected_without_losing_the_previous_value(self):
        app, ember = self.app()
        handle = app.ui.handles["combat.custom.healthFloor"]
        handle.Set(handle, "not a number")
        ember.Flush()
        self.assertIn("Invalid", app.ui.lastError)
        self.assertEqual(app.model["values"]["combat.custom.healthFloor"], 50)
        self.assertEqual(handle.Get(handle), "50")
        ok, reason = app.Set(app, "jobs.enabled", None)
        self.assertFalse(ok)
        self.assertTrue(reason)

    def test_status_failure_does_not_commit_profile(self):
        app, _ = self.app()
        app.ui.sessionStatus.throwNext = True
        ok, reason = app.ApplyProfile(app, self.profile(**{"jobs.enabled": True}))
        self.assertFalse(ok)
        self.assertTrue(reason)
        self.assertIs(app.model["values"]["jobs.enabled"], False)
        self.assertIs(app.ui.handles["jobs.enabled"].Get(app.ui.handles["jobs.enabled"]), False)
        self.assertTrue(app.model.paused)

    def test_initial_activity_render_failure_destroys_window(self):
        app, ember = self.app()
        deps = self.table({"Ember": ember,
                           "Catalog": self.module("src/ui/Catalog.luau"),
                           "Settings": self.module("src/storage/Settings.luau"),
                           "EmberAdapter": self.module("src/ui/EmberAdapter.luau")})
        ember.throwSetLabel = "Latest local command"
        with self.assertRaisesRegex(Exception, "setter failed"):
            self.module("src/App.luau").start(deps)
        self.assertTrue(ember.windows[2].destroyed)

    def test_failed_rollback_freezes_editing(self):
        app, _ = self.app()
        app.ui.handles["jobs.enabled"].reject = False
        app.ui.handles["jobs.policy"].reject = "XP"
        ok, reason = app.ApplyProfile(app, self.profile(**{"jobs.enabled": True, "jobs.policy": "XP"}))
        self.assertFalse(ok)
        self.assertIn("rollback failed", reason)
        self.assertTrue(app.ui.degraded)
        self.assertTrue(app.ui.handles["jobs.enabled"].disabled)
        self.assertIs(app.model["values"]["jobs.enabled"], False)
        self.assertTrue(app.model.paused)

    def test_startup_callbacks_do_not_hydrate_or_resume(self):
        app, ember = self.app(forceInitial=True)
        ember.Flush(True)
        self.assertTrue(app.alive)
        self.assertTrue(app.model.paused)
        self.assertIs(app.model["values"]["jobs.enabled"], False)
        self.assertIsNone(app.staged)

    def test_closed_session_commands_cannot_change_the_model(self):
        app, _ = self.app()
        app.Destroy(app)
        for name in ("Resume", "Pause", "Stop"):
            ok, reason = app[name](app)
            self.assertFalse(ok)
            self.assertIn("closed", reason)
            self.assertTrue(app.model.paused)
            self.assertTrue(app.model.stopped)


class BuilderTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location("ui_builder", ROOT / "tools/build_ui_prototype.py")
        self.builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.builder)

    def test_generated_catalog_is_current(self):
        self.assertEqual((ROOT / "src/ui/Catalog.luau").read_text(encoding="utf-8"),
                         self.builder.catalog_source())

    def test_unreviewed_ember_bytes_are_refused(self):
        with self.assertRaisesRegex(ValueError, "fingerprint"):
            self.builder.prototype_source(b"return {} -- changed dependency")


if __name__ == "__main__":
    unittest.main()
