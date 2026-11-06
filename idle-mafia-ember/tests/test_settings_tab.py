"""Session-only appearance callbacks respect current values and closed UI."""
import unittest

from engine_harness import Harness, lua_table


class SettingsTabTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.ember = self.h.load("tests/ember_double.lua")()
        self.window = self.ember.new(lua_table(self.h.lua, {"Name": "SettingsAudit"}))
        self.section = self.window.Section(self.window, "Settings", "settings")
        self.h.lua.globals().settingsAuditAlive = True
        self.alive = self.h.lua.eval("function() return settingsAuditAlive end")
        self.origin = self.h.lua.eval("""function(origin)
            return not origin or not (origin.initial or origin.restored or origin.reapplied or origin.reverted)
        end""")
        self.tab = self.h.load("src/tabs/settings/Module.luau").new(self.section,
            self.ember, self.origin, self.alive,
            lua_table(self.h.lua, {"runtimeConnected": False}), self.window)
        self.buttons = {handle.options.Text: handle for handle in self.window.handles.values()
                        if handle.kind == "Button"}

    def test_superseded_async_theme_callbacks_cannot_apply_an_old_selection(self):
        self.tab.theme.Set(self.tab.theme, "Dark")
        self.tab.theme.Set(self.tab.theme, "Slate")
        self.ember.Flush(True)
        self.assertEqual(self.ember.theme, "Slate")
        self.assertEqual(self.tab.themeStatus.Get(self.tab.themeStatus), "Slate")
        self.assertEqual(self.tab.theme.Get(self.tab.theme), "Slate")

    def test_refused_or_throwing_native_theme_does_not_claim_success(self):
        for callback in ("function() return false, 'theme refused' end",
                         "function() error('theme unavailable') end"):
            self.ember.SetTheme = self.h.lua.eval(callback)
            self.tab.theme.Set(self.tab.theme, "Dark")
            self.ember.Flush()
            self.assertEqual(self.tab.themeStatus.Get(self.tab.themeStatus), "Midnight")
            self.assertEqual(self.tab.theme.Get(self.tab.theme), "Midnight")
            self.assertIsNotNone(self.tab.lastError)
            self.assertIn("Unchanged", self.tab.themeUpdate.value)

    def test_reset_wins_over_queued_selection_and_window_controls_stop_after_close(self):
        self.tab.theme.Set(self.tab.theme, "Dark")
        self.buttons["Reset theme"].Click(self.buttons["Reset theme"])
        self.ember.Flush(True)
        self.assertEqual(self.ember.theme, "Midnight")
        self.assertEqual(self.tab.theme.Get(self.tab.theme), "Midnight")
        self.assertFalse(self.tab.theme.options.Save)
        self.assertFalse(self.tab.theme.options.FireOnStart)
        self.tab.theme.Set(self.tab.theme, "Slate")
        self.buttons["Center window"].Click(self.buttons["Center window"])
        self.buttons["Reset theme"].Click(self.buttons["Reset theme"])
        self.h.lua.globals().settingsAuditAlive = False
        self.ember.Flush()
        self.assertEqual(self.ember.theme, "Midnight")
        self.assertIsNone(self.window.centered)
        self.assertEqual(len(self.h.transport.sent), 0)


if __name__ == "__main__":
    unittest.main()
