"""Read-only arbitration binds current native recall state without starting it."""
import unittest

from engine_harness import Harness


class NativeRecallControllerTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        base = self.h.load("tests/fixtures/prestige-client.lua")
        self.client = self.h.lua.eval("""function(f)
            f.game.PlaceVersion = 654
            local mw = f.remotes.Parent
            local clock = {now = function() return 100 end}
            mw:Add(f.node('ServerClock', 'ModuleScript')).Value = clock
            for _, name in ipairs({'TerritoryAction', 'TerritoryStatus'}) do
                local raw = f.remotes:Add(f.node(name, 'RemoteFunction'))
                f.wrapped[name] = {Name = name, Instance = raw,
                    InvokeServer = function() error('Read-only binding invoked a remote') end}
            end
            local function init() end
            local function start() error('Read-only binding started native retry loop') end
            local function busy() return f.recallBusy[1] ~= nil end
            local function changed() end
            local function finish() end
            local api = {init = init, start = start, busy = busy}
            f.client:Add(f.node('CrewRecall', 'ModuleScript')).Value = api
            f.recallInit = {[1] = f.ctx, [3] = finish}
            f.recallStart = {[2] = 100000, [3] = clock, [4] = changed, [5] = finish, [6] = f.ctx}
            f.recallBusy = {}
            f.upvalues[init], f.upvalues[start], f.upvalues[busy] = f.recallInit, f.recallStart, f.recallBusy
            f.recallApi = api
            return f
        end""")(base)

    def bind(self):
        return self.h.load("src/tabs/territory/NativeRecallController.luau").bind(
            self.client.game, self.client.requireModule, self.client.readUpvalues)

    def test_reads_current_native_request_floor_and_busy_without_mutation(self):
        controller = self.bind()
        self.assertIsNotNone(controller)
        view = controller.Read()
        self.assertEqual((view.lastRequestId, view.epochFloor), (100000, 100000))
        self.assertTrue(view.controllersClear)
        self.assertEqual(view.userId, 123)
        pending = self.h.lua.table(id=100001)
        self.client.recallInit[2] = pending
        self.client.recallStart[1] = pending
        self.client.recallBusy[1] = pending
        self.assertTrue(controller.Busy())
        self.assertFalse(controller.Read().controllersClear)

    def test_current_client_bindings_expose_reviewed_recall_controller(self):
        bindings, reason = self.h.load("src/transport/NativeClientBindings.luau").read(
            self.client.game, self.client.requireModule, self.client.readUpvalues, None,
            self.h.load("src/tabs/territory/NativeRecallController.luau"))
        self.assertIsNone(reason)
        self.assertIsNotNone(bindings.currentRecallController)
        self.assertTrue(bindings.currentRecallController.Current())

    def test_changed_native_source_or_counter_regression_retires_binding(self):
        for change in ("source", "counter", "version", "userId"):
            with self.subTest(change=change):
                self.setUp()
                controller = self.bind()
                self.assertTrue(controller.Current())
                if change == "source":
                    self.client.recallStart[6] = self.h.lua.table()
                elif change == "counter":
                    self.client.recallStart[2] = 99999
                elif change == "version":
                    self.client.game.PlaceVersion = 655
                else:
                    self.client.ctx.player.UserId = 124
                self.assertFalse(controller.Current())
                self.assertTrue(controller.Busy())
                self.assertIsNone(controller.Read())


if __name__ == "__main__":
    unittest.main()
