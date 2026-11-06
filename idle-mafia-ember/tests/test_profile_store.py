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
            self.assertTrue(app.Set(app, "jobs.enabled", True)[0])
            self.assertIsNotNone(app["ui"]["profileName"])
            buttons = {handle["options"]["Text"]: handle
                       for handle in app["ui"]["window"]["handles"].values()
                       if handle["kind"] == "Button"}
            buttons["Save choices locally"].Click(
                buttons["Save choices locally"])
            ember.Flush()
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
