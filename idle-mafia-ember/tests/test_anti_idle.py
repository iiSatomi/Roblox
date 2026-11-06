"""Standalone autoexec lifecycle/input contract, with no real input or transport."""
import unittest

from lupa import LuaRuntime

from engine_harness import ROOT


SCRIPT = ROOT.parent / "autoexec/IdleMafiaAntiIdle.luau"


class AntiIdleTests(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.lua.execute("""
            now, calls, warnings, timers, environment = 0, {}, {}, {}, {}
            os.clock = function() return now end
            warn = function(message) warnings[#warnings + 1] = message end
            print = function() end
            getgenv = function() return environment end
            Vector2 = {new = function(x, y) return {X = x, Y = y} end}
            workspace = {CurrentCamera = {CFrame = 'camera-a'}}
            idle = {listeners = {}}
            function idle:Connect(callback)
                local connection = {Connected = true, callback = callback}
                function connection:Disconnect() self.Connected = false end
                self.listeners[#self.listeners + 1] = connection
                return connection
            end
            function fireIdle()
                for _, connection in ipairs(idle.listeners) do
                    if connection.Connected then connection.callback(120) end
                end
            end
            virtualUser = {}
            function virtualUser:CaptureController()
                if failInput then error('input unavailable') end
                calls[#calls + 1] = {kind = 'capture'}
            end
            function virtualUser:ClickButton2(position, camera)
                calls[#calls + 1] = {kind = 'click', position = position, camera = camera}
            end
            players = {LocalPlayer = {Idled = idle}}
            game = {GameId = 10643795368, PlaceId = 73897506680154}
            function game:GetService(name)
                if name == 'Players' then return players end
                if name == 'VirtualUser' then return virtualUser end
                error('Unexpected service: ' .. name)
            end
            task = {}
            function task.delay(seconds, callback)
                local timer = {at = now + seconds, callback = callback}
                timers[#timers + 1] = timer
                return timer
            end
            function task.cancel(timer) timer.cancelled = true end
            function task.wait(seconds)
                now = now + seconds
                if playerReadyAt and now >= playerReadyAt then
                    players.LocalPlayer = {Idled = idle}
                end
                if gameReadyAt and now >= gameReadyAt then
                    game.GameId, game.PlaceId = 10643795368, 73897506680154
                end
            end
            function advance(seconds)
                now = now + seconds
                local pending = timers
                timers = {}
                for _, timer in ipairs(pending) do
                    if not timer.cancelled and timer.at <= now then timer.callback()
                    elseif not timer.cancelled then timers[#timers + 1] = timer end
                end
            end
        """)

    def start(self):
        self.assertTrue(SCRIPT.is_file(), "Standalone anti-idle autoexec is missing")
        return self.lua.execute(SCRIPT.read_text(encoding="utf-8"))

    def status(self, handle):
        return handle.Status(handle)

    def test_scopes_before_any_input_or_timer(self):
        for field in ("GameId", "PlaceId"):
            self.lua.globals().game[field] = 1
            handle = self.start()
            self.assertFalse(self.status(handle).running)
            self.assertEqual(len(self.lua.globals().calls), 0)
            self.assertEqual(len(self.lua.globals().timers), 0)
            self.lua.globals().game.GameId = 10643795368
            self.lua.globals().game.PlaceId = 73897506680154

    def test_periodic_input_uses_current_camera_and_status_is_detached(self):
        handle = self.start()
        self.assertEqual(self.status(handle).successes, 1)
        self.lua.execute("workspace.CurrentCamera.CFrame = 'camera-b'; advance(60)")
        self.assertEqual(self.status(handle).successes, 2)
        self.assertEqual(self.lua.globals().calls[4].camera, "camera-b")
        self.assertEqual(self.lua.globals().calls[4].position.X, 0)
        snapshot = self.status(handle)
        snapshot.running = False
        self.assertTrue(self.status(handle).running)

    def test_duplicate_run_stops_old_owner_and_late_callbacks_are_inert(self):
        first = self.start()
        late = self.lua.globals().timers[1].callback
        second = self.start()
        self.assertFalse(self.status(first).running)
        self.assertTrue(self.status(second).running)
        self.assertFalse(self.lua.globals().idle.listeners[1].Connected)
        late()
        self.assertEqual(len(self.lua.globals().calls), 4)
        self.lua.execute("advance(60)")
        self.assertEqual(len(self.lua.globals().calls), 6)

    def test_idled_fallback_is_spaced_and_stop_disconnects_everything(self):
        handle = self.start()
        self.lua.execute("advance(5); fireIdle(); fireIdle()")
        self.assertEqual(self.status(handle).successes, 2)
        self.assertTrue(handle.Stop(handle))
        self.assertFalse(handle.Stop(handle))
        self.lua.execute("advance(120); fireIdle()")
        self.assertEqual(len(self.lua.globals().calls), 4)
        self.assertFalse(self.status(handle).running)

    def test_repeated_input_failure_stops_after_three_attempts(self):
        self.lua.globals().failInput = True
        handle = self.start()
        self.lua.execute("advance(60); advance(60); advance(600); fireIdle()")
        status = self.status(handle)
        self.assertFalse(status.running)
        self.assertEqual(status.attempts, 3)
        self.assertEqual(status.consecutiveFailures, 3)
        self.assertIn("input unavailable", status.lastError)
        self.assertGreater(len(self.lua.globals().warnings), 0)
        self.assertFalse(self.lua.globals().idle.listeners[1].Connected)

    def test_transient_missing_camera_recovers_and_scope_change_stops(self):
        self.lua.execute("workspace.CurrentCamera = nil")
        handle = self.start()
        self.lua.execute("workspace.CurrentCamera = {CFrame = 'new'}; advance(60)")
        self.assertEqual(self.status(handle).successes, 1)
        self.assertEqual(self.status(handle).consecutiveFailures, 0)
        self.lua.execute("game.GameId = 1; advance(60)")
        self.assertFalse(self.status(handle).running)
        self.assertEqual(self.status(handle).attempts, 2)

    def test_early_autoexec_waits_for_game_and_local_player_readiness(self):
        self.lua.execute("game.GameId = 0; game.PlaceId = 0; gameReadyAt = 1; players.LocalPlayer = nil; playerReadyAt = 2")
        handle = self.start()
        self.assertTrue(self.status(handle).running)
        self.assertEqual(self.status(handle).successes, 1)
        self.assertEqual(self.lua.globals().now, 2)

    def test_missing_player_or_unknown_game_times_out_without_input(self):
        for missing in ("player", "game"):
            self.setUp()
            if missing == "player":
                self.lua.execute("players.LocalPlayer = nil")
            else:
                self.lua.execute("game.GameId = 0; game.PlaceId = 0")
            handle = self.start()
            self.assertFalse(self.status(handle).running)
            self.assertEqual(len(self.lua.globals().calls), 0)
            self.assertEqual(self.lua.globals().now, 30)

    def test_duplicate_refuses_previous_owner_that_claims_to_remain_running(self):
        self.lua.execute("""environment.__IdleMafiaAntiIdle = {
            Stop = function() return false end,
            Status = function() return {running = true} end}
        """)
        handle = self.start()
        self.assertFalse(self.status(handle).running)
        self.assertEqual(len(self.lua.globals().calls), 0)
        self.assertIn("Previous", self.status(handle).lastError)


if __name__ == "__main__":
    unittest.main()
