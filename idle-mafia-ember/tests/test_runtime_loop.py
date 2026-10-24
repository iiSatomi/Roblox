"""A quiet client still ticks; closing fences a queued timer."""
import unittest

from engine_harness import Harness


class RuntimeLoopTests(unittest.TestCase):
    def test_quarter_second_pulses_and_close_fence(self):
        h = Harness()
        driver = h.lua.execute("""return {ticks = 0, closed = false,
            Tick = function(self) self.ticks = self.ticks + 1 end,
            Close = function(self) self.closed = true end,
        }""")
        timer = h.lua.execute("""return {pending = {}, intervals = {},
            After = function(self, delay, callback)
                local handle = #self.pending + 1
                self.pending[handle] = callback
                self.intervals[#self.intervals + 1] = delay
                return handle
            end,
            Cancel = function(self, handle)
                self.pending[handle] = nil
            end,
            Fire = function(self, handle)
                local callback = self.pending[handle]
                self.pending[handle] = nil
                if callback then callback() end
            end,
        }""")
        loop = h.load("src/transport/RuntimeLoop.luau").new(driver, timer)
        self.assertTrue(loop.Start(loop))
        self.assertFalse(loop.Start(loop))
        timer.Fire(timer, 1)
        self.assertEqual(driver.ticks, 1)
        self.assertEqual(timer.intervals[1], 0.25)
        queued = loop.handle
        self.assertTrue(loop.Close(loop))
        self.assertTrue(driver.closed)
        timer.Fire(timer, queued)
        self.assertEqual(driver.ticks, 1)

    def test_timer_failure_closes_driver_before_any_tick(self):
        h = Harness()
        driver = h.lua.execute("""return {ticks = 0, closed = false,
            Tick = function(self) self.ticks = self.ticks + 1 end,
            Close = function(self) self.closed = true end,
        }""")
        timer = h.lua.execute("""return {
            After = function() return nil end,
            Cancel = function() end,
        }""")
        loop = h.load("src/transport/RuntimeLoop.luau").new(driver, timer)
        self.assertFalse(loop.Start(loop))
        self.assertTrue(driver.closed)
        self.assertEqual(driver.ticks, 0)

    def test_explicit_timer_refusal_closes_driver(self):
        h = Harness()
        driver = h.lua.execute("""return {closed = false,
            Tick = function() end,
            Close = function(self) self.closed = true end,
        }""")
        timer = h.lua.execute("""return {
            After = function() return false end,
            Cancel = function() end,
        }""")
        loop = h.load("src/transport/RuntimeLoop.luau").new(
            driver, timer)
        self.assertFalse(loop.Start(loop))
        self.assertTrue(driver.closed)

    def test_timer_refusal_after_first_tick_closes_driver(self):
        h = Harness()
        driver = h.lua.execute("""return {ticks = 0, closed = false,
            Tick = function(self) self.ticks = self.ticks + 1 end,
            Close = function(self) self.closed = true end,
        }""")
        timer = h.lua.execute("""return {queued = nil, calls = 0,
            After = function(self, _, callback)
                self.calls = self.calls + 1
                if self.calls > 1 then return false end
                self.queued = callback
                return 1
            end,
            Cancel = function() end,
        }""")
        loop = h.load("src/transport/RuntimeLoop.luau").new(
            driver, timer)
        self.assertTrue(loop.Start(loop))
        timer.queued()
        self.assertEqual(driver.ticks, 1)
        self.assertTrue(driver.closed)
        self.assertFalse(loop.alive)

    def test_driver_closure_stops_rescheduling(self):
        h = Harness()
        driver = h.lua.execute("""return {alive = true, closed = false,
            Tick = function(self) self.alive = false end,
            Close = function(self) self.closed = true end,
        }""")
        timer = h.lua.execute("""return {queued = nil, count = 0,
            After = function(self, _, callback)
                self.count = self.count + 1
                self.queued = callback
                return self.count
            end,
            Cancel = function() end,
        }""")
        loop = h.load("src/transport/RuntimeLoop.luau").new(driver, timer)
        self.assertTrue(loop.Start(loop))
        timer.queued()
        self.assertFalse(loop.alive)
        self.assertTrue(driver.closed)
        self.assertEqual(timer.count, 1)


if __name__ == "__main__":
    unittest.main()
