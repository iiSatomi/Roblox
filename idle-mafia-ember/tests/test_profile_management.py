"""Profile transfer is staged data, never executable code or an activation."""
import json
import unittest

import test_profile_store as profile_fixture
from engine_harness import lua_table
from test_redundant_store import plain


class ProfileManagementTests(unittest.TestCase):
    def setUp(self):
        base = profile_fixture.ProfileStoreTests()
        base.setUp()
        self.h, self.store, self.base = base.h, base.store, base
        self.h.lua.globals().json_encode = lambda value: json.dumps(plain(value))
        self.h.lua.globals().json_decode = lambda value: lua_table(self.h.lua, json.loads(value))
        codec = self.h.lua.eval("""{Encode=function(self,value) return json_encode(value) end,
            Decode=function(self,value) return json_decode(value) end}""")
        self.ember = self.h.load("tests/ember_double.lua")()
        self.app = self.h.load("src/App.luau").start(lua_table(self.h.lua, {
            "Ember": self.ember, "Catalog": self.h.load("src/ui/Catalog.luau"),
            "Settings": self.h.load("src/storage/Settings.luau"),
            "LegacySettings": self.h.load("src/storage/LegacySettings.luau"),
            "EmberAdapter": self.h.load("src/ui/EmberAdapter.luau"),
            "ProfilesTab": self.h.load("src/tabs/profiles/Module.luau"),
            "ProfileStore": base.module, "ProfileStorage": base.storage,
            "identity": self.h.session, "codec": codec}))

    def tearDown(self):
        self.app.Destroy(self.app)

    def test_export_contains_only_preferences_and_import_stays_staged(self):
        self.app.Set(self.app, "jobs.enabled", True)
        exported, reason = self.app.ExportProfile(self.app)
        self.assertIsNone(reason)
        self.assertEqual(set(json.loads(exported)), {"schema", "values"})
        self.app.Set(self.app, "jobs.enabled", False)
        staged, reason = self.app.PreviewImport(self.app, exported)
        self.assertTrue(staged, reason)
        self.assertFalse(self.app.model["values"]["jobs.enabled"])
        self.assertTrue(self.app.staged["values"]["jobs.enabled"])
        self.assertTrue(self.app.ApplyProfile(self.app, self.app.staged)[0])
        self.assertTrue(self.app.model["values"]["jobs.enabled"])
        self.assertTrue(self.app.model.paused)

    def test_invalid_import_does_not_replace_valid_preview_or_touch_storage(self):
        self.assertTrue(self.app.PreviewImport(self.app,
            '{"schema":1,"values":{"jobs.enabled":true}}')[0])
        for text in ('not json', '{"schema":1,"values":{"obsolete.enabled":true}}',
                     '{"schema":1,"values":{},"account":"other"}', 'x' * 65537):
            accepted, reason = self.app.PreviewImport(self.app, text)
            self.assertFalse(accepted)
            self.assertIsNotNone(reason)
            self.assertTrue(self.app.staged["values"]["jobs.enabled"])
        self.assertEqual(len(self.base.storage.data), 0)

    def test_rename_is_atomic_and_requires_autoload_disabled_for_old_name(self):
        self.assertTrue(self.store.Save(self.store, "old", self.base.profile())[0])
        self.assertTrue(self.store.SetAutoload(self.store, "old")[0])
        self.assertFalse(self.store.Rename(self.store, "old", "new")[0])
        self.assertTrue(self.store.SetAutoload(self.store, None)[0])
        self.base.storage.fail = True
        self.assertFalse(self.store.Rename(self.store, "old", "new")[0])
        self.base.storage.fail = False
        self.assertIsNotNone(self.store.Load(self.store, "old")[0])
        original_write = self.base.storage.Write
        self.base.storage.Write = self.h.lua.eval("function() return false end")
        self.assertFalse(self.store.Rename(self.store, "old", "new")[0])
        self.base.storage.Write = original_write
        self.assertIsNotNone(self.store.Load(self.store, "old")[0])
        self.assertIsNone(self.store.Load(self.store, "new")[0])
        self.assertTrue(self.store.Rename(self.store, "old", "new")[0])
        self.assertIsNone(self.store.Load(self.store, "old")[0])
        self.assertTrue(self.store.Load(self.store, "new")[0]["values"]["jobs.enabled"])
        self.assertTrue(self.store.Save(self.store, "other", self.base.profile())[0])
        self.assertFalse(self.store.Rename(self.store, "new", "other")[0])

    def test_ui_transfer_and_current_saved_profile_are_distinct_from_selection(self):
        self.app.Set(self.app, "jobs.enabled", True)
        self.assertTrue(self.app.SaveProfile(self.app, "main")[0])
        self.assertEqual(self.app.ui.profiles.appliedStatus.value, "main")
        self.app.Set(self.app, "jobs.enabled", False)
        self.assertIn("modified", self.app.ui.profiles.appliedStatus.value)
        buttons = {handle.options.Text: handle for handle in self.app.ui.window.handles.values()
                   if handle.kind == "Button"}
        buttons["Export current choices"].Click(buttons["Export current choices"])
        self.ember.Flush()
        self.assertFalse(json.loads(self.app.ui.profiles.transferText.value)["values"]["jobs.enabled"])
        self.app.ui.profiles.transferText.Set(self.app.ui.profiles.transferText,
            '{"schema":1,"values":{"jobs.enabled":true}}', True)
        buttons["Preview imported choices"].Click(buttons["Preview imported choices"])
        self.ember.Flush()
        self.assertFalse(self.app.model["values"]["jobs.enabled"])
        self.assertTrue(self.app.staged["values"]["jobs.enabled"])

    def test_sparse_saved_and_imported_profiles_replace_with_defaults(self):
        self.assertTrue(self.app.profileStore.Save(self.app.profileStore, "legacy",
            lua_table(self.h.lua, {"schema": 1, "values": {"jobs.enabled": False}}))[0])
        self.assertTrue(self.app.Set(self.app, "shop.enabled", True)[0])
        self.assertTrue(self.app.PreviewProfile(self.app, "legacy")[0])
        self.assertTrue(self.app.model["values"]["shop.enabled"])
        self.assertEqual(self.app.staged["values"]["shop.enabled"], False)
        self.assertTrue(self.app.ApplyProfile(self.app, self.app.staged)[0])
        self.assertFalse(self.app.model["values"]["shop.enabled"])
        self.assertEqual(self.app.ui.profiles.appliedStatus.value, "legacy")
        self.assertTrue(self.app.Set(self.app, "shop.enabled", True)[0])
        self.assertTrue(self.app.PreviewImport(self.app,
            '{"schema":1,"values":{"jobs.enabled":true}}')[0])
        self.assertTrue(self.app.model["values"]["shop.enabled"])
        self.assertEqual(self.app.staged["values"]["shop.enabled"], False)

    def test_async_saved_selection_cannot_autoload_an_obsolete_name(self):
        for name in ("alpha", "beta"):
            self.assertTrue(self.app.SaveProfile(self.app, name)[0])
        selection = self.app.ui.profiles.savedSelection
        selection.Set(selection, "alpha")
        selection.Set(selection, "beta")
        self.ember.Flush(True)
        self.assertEqual(selection.value, "beta")
        self.assertEqual(self.app.ui.profiles.profileName.value, "beta")
        buttons = {handle.options.Text: handle for handle in self.app.ui.window.handles.values()
                   if handle.kind == "Button"}
        buttons["Autoload this saved profile"].Click(buttons["Autoload this saved profile"])
        self.ember.Flush()
        self.assertEqual(self.app.profileStore.GetAutoload(self.app.profileStore)[0], "beta")


if __name__ == "__main__":
    unittest.main()
