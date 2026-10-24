"""Account-scoped profiles stay inactive until explicit App apply."""
import unittest

from engine_harness import Harness, lua_table


class ProfileStoreTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.storage = self.h.lua.execute("""
            return { data = {}, fail = false,
                Read = function(self, key)
                    if self.fail then error('unavailable') end
                    return self.data[key]
                end,
                Write = function(self, key, value)
                    if self.fail then error('unavailable') end
                    self.data[key] = value
                end }
        """)
        self.model = self.h.load("src/storage/Settings.luau").new(
            self.h.load("src/ui/Catalog.luau"))
        self.module = self.h.load("src/storage/ProfileStore.luau")
        self.store = self.module.new(self.storage, self.model,
                                     "user-a", "place-a")

    def profile(self, enabled=True):
        return lua_table(self.h.lua, {"schema": 1,
            "values": {"jobs.enabled": enabled,
                       "jobs.policy": "Balanced"}})

    def test_save_load_copy_and_no_activation(self):
        self.assertEqual(self.store.Save(self.store, "main",
            self.profile())[0], True)
        loaded, reason = self.store.Load(self.store, "main")
        self.assertIsNone(reason)
        self.assertTrue(loaded["values"]["jobs.enabled"])
        self.assertTrue(self.model["paused"])
        self.assertFalse(self.model["values"]["jobs.enabled"])
        loaded["values"]["jobs.enabled"] = False
        self.assertTrue(self.store.Load(self.store,
            "main")[0]["values"]["jobs.enabled"])
        self.assertEqual(self.store.List(self.store)[0][1], "main")

    def test_scope_and_invalid_schema_fail_closed(self):
        self.assertEqual(self.store.Save(self.store, "main",
            self.profile())[0], True)
        other = self.module.new(self.storage, self.model,
                                "user-b", "place-a")
        self.assertIsNone(other.Load(other, "main")[0])
        other = self.module.new(self.storage, self.model,
                                "user-a", "place-b")
        self.assertIsNone(other.Load(other, "main")[0])
        invalid = lua_table(self.h.lua, {"schema": 1,
            "values": {"unknown.enabled": True}})
        self.assertEqual(self.store.Save(self.store, "bad",
            invalid)[0], False)
        self.assertEqual(self.store.Save(self.store, "../bad",
            self.profile())[0], False)

    def test_failed_io_and_corruption_do_not_change_model(self):
        self.storage["fail"] = True
        self.assertEqual(self.store.Save(self.store, "main",
            self.profile())[0], False)
        self.storage["fail"] = False
        self.assertEqual(self.store.Save(self.store, "main",
            self.profile())[0], True)
        key = self.store.ScopeKey(self.store)
        self.storage["data"][key]["account"] = "other"
        self.assertIsNone(self.store.Load(self.store, "main")[0])
        self.assertFalse(self.model["values"]["jobs.enabled"])

    def test_profile_capacity(self):
        for index in range(16):
            self.assertEqual(self.store.Save(self.store,
                f"profile_{index}", self.profile())[0], True)
        self.assertEqual(self.store.Save(self.store,
            "overflow", self.profile())[0], False)
        self.assertEqual(len(self.store.List(self.store)[0]), 16)

    def test_autoload_is_explicit_and_account_scoped(self):
        self.assertIsNone(self.store.GetAutoload(self.store)[0])
        self.assertFalse(self.store.SetAutoload(self.store, "missing")[0])
        self.assertTrue(self.store.Save(self.store, "main", self.profile())[0])
        self.assertTrue(self.store.SetAutoload(self.store, "main")[0])
        self.assertEqual(self.store.GetAutoload(self.store)[0], "main")
        other = self.module.new(self.storage, self.model,
                                "user-b", "place-a")
        self.assertIsNone(other.GetAutoload(other)[0])
        self.assertTrue(self.store.SetAutoload(self.store, None)[0])
        self.assertIsNone(self.store.GetAutoload(self.store)[0])

    def test_functional_app_starts_unpaused_and_autoloads_only_selected_profile(self):
        runtime = self.h.lua.execute("""
            local runtime = { features = { jobs = true }, resumed = false }
            function runtime:Status()
                return { state = 'paused', availableFeatures = {} }
            end
            function runtime:Step() return true end
            function runtime:Pause() self.resumed = false end
            function runtime:Resume() self.resumed = true end
            function runtime:Stop() end
            function runtime:Close() end
            return runtime
        """)
        deps = lua_table(self.h.lua, {
            "Ember": self.h.load("tests/ember_double.lua")(),
            "Catalog": self.h.load("src/ui/Catalog.luau"),
            "Settings": self.h.load("src/storage/Settings.luau"),
            "EmberAdapter": self.h.load("src/ui/EmberAdapter.luau"),
            "ProfilesTab": self.h.load("src/tabs/profiles/Module.luau"),
            "ProfileStore": self.module,
            "ProfileStorage": self.storage,
            "identity": self.h.session,
            "automationRuntimeInstance": runtime,
            "allowedFeatures": {"jobs": True, "bosses": True},
        })
        app_module = self.h.load("src/App.luau")
        app = app_module.start(deps)
        self.assertFalse(app.model.paused)
        self.assertTrue(runtime.resumed)
        self.assertFalse(app.model["values"]["jobs.enabled"])
        self.assertFalse(app.Set(app, "shop.enabled", True)[0])
        self.assertFalse(app.model["values"]["shop.enabled"])
        self.assertTrue(app.Set(app, "jobs.enabled", True)[0])
        self.assertTrue(app.SaveProfile(app, "main")[0])
        self.assertEqual(app.ui.profileStatus.Get(app.ui.profileStatus), "None")
        self.assertTrue(app.SetAutoload(app, "main")[0])
        self.assertEqual(app.ui.profileStatus.Get(app.ui.profileStatus), "None")
        app.Destroy(app)

        runtime.resumed = False
        deps.Ember = self.h.load("tests/ember_double.lua")()
        loaded = app_module.start(deps)
        self.assertFalse(loaded.model.paused)
        self.assertTrue(loaded.model["values"]["jobs.enabled"])
        self.assertTrue(runtime.resumed)
        self.assertTrue(loaded.SetAutoload(loaded, None)[0])
        loaded.Destroy(loaded)

        deps.Ember = self.h.load("tests/ember_double.lua")()
        fresh = app_module.start(deps)
        self.assertFalse(fresh.model.paused)
        self.assertFalse(fresh.model["values"]["jobs.enabled"])
        fresh.Destroy(fresh)

        scoped = self.module.new(self.storage, self.model,
            self.h.session["account"], self.h.session["place"])
        unsafe = lua_table(self.h.lua, {
            "schema": 1, "values": {"shop.enabled": True}})
        self.assertTrue(scoped.Save(scoped, "unsafe", unsafe)[0])
        self.assertTrue(scoped.SetAutoload(scoped, "unsafe")[0])
        deps.Ember = self.h.load("tests/ember_double.lua")()
        blocked = app_module.start(deps)
        self.assertFalse(blocked.model["values"]["shop.enabled"])
        self.assertFalse(blocked.model["values"]["jobs.enabled"])
        self.assertIn("exceeds this runtime preview",
                      blocked.ui.activity.Get(blocked.ui.activity))
        self.assertEqual(blocked.ui.profileStatus.Get(blocked.ui.profileStatus),
                         "None")
        blocked.Destroy(blocked)

    def test_app_preview_requires_separate_paused_apply(self):
        ember = self.h.load("tests/ember_double.lua")()
        deps = lua_table(self.h.lua, {
            "Ember": ember,
            "Catalog": self.h.load("src/ui/Catalog.luau"),
            "Settings": self.h.load("src/storage/Settings.luau"),
            "EmberAdapter": self.h.load("src/ui/EmberAdapter.luau"),
            "ProfilesTab": self.h.load("src/tabs/profiles/Module.luau"),
            "ProfileStore": self.module,
            "ProfileStorage": self.storage,
            "identity": self.h.session,
        })
        app = self.h.load("src/App.luau").start(deps)
        try:
            self.assertEqual(app.ui.profiles.storageStatus.Get(
                app.ui.profiles.storageStatus), "No saved profiles")
            self.assertEqual(app.ui.profiles.autoloadStatus.Get(
                app.ui.profiles.autoloadStatus), "Off")
            self.assertTrue(app.Set(app, "jobs.enabled", True)[0])
            self.assertIsNotNone(app["ui"]["profileName"])
            buttons = {handle["options"]["Text"]: handle
                       for handle in app["ui"]["window"]["handles"].values()
                       if handle["kind"] == "Button"}
            buttons["Save choices locally"].Click(
                buttons["Save choices locally"])
            ember.Flush()
            self.assertEqual(app.ui.profiles.storageStatus.Get(
                app.ui.profiles.storageStatus), "1 saved: main")
            self.assertEqual(app.ui.profiles.savedSelection.options.Options[2],
                             "main")
            app.ui.profileName.Set(app.ui.profileName, "alternate", True)
            buttons["Save choices locally"].Click(
                buttons["Save choices locally"])
            ember.Flush()
            self.assertEqual(app.ui.profiles.savedSelection.options.Options[3],
                             "main")
            app.ui.profiles.savedSelection.Set(
                app.ui.profiles.savedSelection, "main", False)
            ember.Flush()
            self.assertEqual(app.ui.profileName.Get(app.ui.profileName), "main")
            buttons["Autoload this saved profile"].Click(
                buttons["Autoload this saved profile"])
            ember.Flush()
            self.assertEqual(app.profileStore.GetAutoload(
                app.profileStore)[0], "main")
            self.assertEqual(app.ui.profiles.autoloadStatus.Get(
                app.ui.profiles.autoloadStatus), "main")
            buttons["Disable autoload"].Click(buttons["Disable autoload"])
            ember.Flush()
            self.assertIsNone(app.profileStore.GetAutoload(
                app.profileStore)[0])
            self.assertEqual(app.ui.profiles.autoloadStatus.Get(
                app.ui.profiles.autoloadStatus), "Off")
            self.assertTrue(app.Set(app, "jobs.enabled", False)[0])
            buttons["Preview saved profile"].Click(
                buttons["Preview saved profile"])
            ember.Flush()
            self.assertTrue(app["staged"]["values"]["jobs.enabled"])
            self.assertFalse(app["model"]["values"]["jobs.enabled"])
            buttons["Apply staged choices"].Click(
                buttons["Apply staged choices"])
            ember.Flush()
            self.assertTrue(app["model"]["values"]["jobs.enabled"])
            self.assertTrue(app["model"]["paused"])
            self.assertEqual(len(self.h.transport["sent"]), 0)
        finally:
            app.Destroy(app)


if __name__ == "__main__":
    unittest.main()
