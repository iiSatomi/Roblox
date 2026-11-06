"""Only observed full Sync can carry full-Sync state into the app."""
import unittest

from engine_harness import Harness, lua_table


class RuntimeDriverTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.reader = self.h.load("src/transport/NativeSnapshotReader.luau").new(
            lua_table(self.h.lua, self.h.session), self.h.clock)
        self.app = self.h.lua.execute("""return {seen = {}, alive = true,
            Step = function(self, raw)
                self.seen[#self.seen + 1] = raw
                return true
            end,
            Destroy = function(self) self.alive = false end,
        }""")
        self.driver = self.h.load("src/transport/RuntimeDriver.luau").new(
            self.app, self.reader)

    def test_sync_changed_and_tick_preserve_source_kind(self):
        self.assertFalse(self.driver.Tick(self.driver)[0])
        self.assertFalse(self.driver.ObserveChanged(
            self.driver, lua_table(self.h.lua, {"cash": 1}))[0])
        self.assertTrue(self.driver.ObserveSync(
            self.driver, lua_table(self.h.lua, {"cash": 10})))
        self.assertTrue(self.app.seen[1]["fullSync"])
        self.assertTrue(self.driver.ObserveChanged(
            self.driver, lua_table(self.h.lua, {"cash": 11})))
        self.assertFalse(self.app.seen[2]["fullSync"])
        self.assertTrue(self.driver.Tick(self.driver))
        self.assertEqual(len(self.app.seen), 3)

    def test_bad_payload_and_close_cannot_step(self):
        self.assertFalse(self.driver.ObserveSync(self.driver,
            self.h.lua.eval("function() end"))[0])
        self.assertEqual(len(self.app.seen), 0)
        self.assertTrue(self.driver.Close(self.driver))
        self.assertFalse(self.app.alive)
        self.assertFalse(self.driver.ObserveSync(self.driver,
            lua_table(self.h.lua, {"cash": 1}))[0])
        self.assertEqual(len(self.app.seen), 0)

    def test_ui_unload_closes_driver_before_later_ticks(self):
        self.assertTrue(self.driver.ObserveSync(
            self.driver, lua_table(self.h.lua, {"cash": 10})))
        self.app.alive = False
        self.assertFalse(self.driver.Tick(self.driver)[0])
        self.assertFalse(self.driver.alive)
        self.assertEqual(len(self.app.seen), 1)


if __name__ == "__main__":
    unittest.main()
