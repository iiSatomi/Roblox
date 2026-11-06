"""Only observed full Sync can carry full-Sync state into the app."""
import unittest

from engine_harness import Harness, lua_table


class RuntimeDriverTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.reader = self.h.load("src/transport/NativeSnapshotReader.luau").new(
            lua_table(self.h.lua, self.h.session), self.h.clock)
        self.app = self.h.lua.execute("""return {seen = {}, alive = true,
            Step = function(self, raw, observationOnly)
                self.seen[#self.seen + 1] = raw
                self.observedOnly = self.observedOnly or {}
                self.observedOnly[#self.seen] = observationOnly == true
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
        self.assertEqual(len(self.app.seen), 0)
        self.assertTrue(self.driver.Tick(self.driver))
        self.assertTrue(self.app.seen[1]["fullSync"])
        self.assertTrue(self.driver.ObserveChanged(
            self.driver, lua_table(self.h.lua, {"cash": 11})))
        self.assertEqual(len(self.app.seen), 1)
        self.assertTrue(self.driver.Tick(self.driver))
        self.assertFalse(self.app.seen[2]["fullSync"])
        self.assertTrue(self.driver.Tick(self.driver))
        self.assertEqual(len(self.app.seen), 3)


    def test_changed_burst_retains_evidence_without_rendering_native_callbacks(self):
        self.driver.ObserveSync(self.driver, lua_table(self.h.lua, {"cash": 10}))
        for cash in range(11, 31):
            self.assertTrue(self.driver.ObserveChanged(self.driver, lua_table(self.h.lua, {"cash": cash})))
        self.assertEqual(len(self.app.seen), 0)
        self.driver.Tick(self.driver)
        self.assertEqual(len(self.app.seen), 21)
        self.assertEqual(self.app.seen[21].native.cash, 30)
        self.assertFalse(self.app.seen[21].fullSync)
        self.assertTrue(all(self.app.observedOnly[i] for i in range(1,21)))
        self.assertFalse(self.app.observedOnly[21])

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
        self.assertEqual(len(self.app.seen), 0)

    def test_native_callbacks_preserve_terminal_sync_and_latest_change_until_owner_tick(self):
        self.driver.ObserveSync(self.driver, lua_table(self.h.lua, {"cash": 10}))
        self.driver.ObserveChanged(self.driver, lua_table(self.h.lua, {"cash": 11}))
        self.driver.ObserveSync(self.driver, lua_table(self.h.lua, {"cash": 12}))
        self.assertEqual(len(self.app.seen), 0)
        self.assertTrue(self.driver.Tick(self.driver))
        self.assertEqual([self.app.seen[i].revision for i in (1, 2, 3)], [1, 2, 3])
        self.assertEqual([self.app.seen[i].fullSync for i in (1, 2, 3)], [True, False, True])
        self.assertEqual([self.app.observedOnly[i] for i in (1, 2, 3)], [True, True, False])
        self.assertEqual(self.app.seen[3].native.cash, 12)

    def test_event_context_never_enters_ui_and_queue_overflow_stops_on_owner_tick(self):
        self.app.Step = self.h.lua.eval("function() error('UI capability unavailable in event') end")
        for index in range(32):
            self.assertTrue(self.driver.ObserveSync(self.driver, lua_table(self.h.lua, {"cash": index})))
        accepted, reason = self.driver.ObserveSync(self.driver, lua_table(self.h.lua, {"cash": 33}))
        self.assertFalse(accepted)
        self.assertIn("queue", reason)
        self.assertTrue(self.app.alive)
        self.assertFalse(self.driver.Tick(self.driver)[0])
        self.assertFalse(self.app.alive)

    def test_sync_arriving_while_draining_does_not_overwrite_queued_terminal_revision(self):
        self.h.lua.globals().drainingDriver = self.driver
        self.app.Step = self.h.lua.eval("""function(original)
            return function(self, raw, observationOnly)
                local accepted = original(self, raw, observationOnly)
                if raw.revision == 1 then drainingDriver:ObserveSync({cash = 13}) end
                return accepted
            end
        end""")(self.app.Step)
        self.driver.ObserveSync(self.driver, lua_table(self.h.lua, {"cash": 10}))
        self.driver.ObserveSync(self.driver, lua_table(self.h.lua, {"cash": 12}))
        self.assertTrue(self.driver.Tick(self.driver))
        self.assertEqual([row.revision for row in self.app.seen.values()], [1, 2, 3])
        self.assertEqual([self.app.observedOnly[i] for i in (1, 2, 3)], [True, True, False])


if __name__ == "__main__":
    unittest.main()
