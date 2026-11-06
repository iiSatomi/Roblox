"""Native act alone allocates Heist sequences; unknown custody cannot dispatch."""
import unittest

from engine_harness import Harness, lua_table


class NativeHeistControllerTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        base = self.h.load("tests/fixtures/prestige-client.lua")
        self.client = self.h.load("tests/fixtures/heist-client.lua")(base)
        self.module = self.h.load("src/tabs/heists/NativeHeistController.luau")
        self.controller = self.module.bind(
            self.client.game, self.client.requireModule, self.client.readUpvalues)

    def test_current_controller_reads_native_counter_without_allocating(self):
        self.assertIsNotNone(self.controller)
        view = self.controller.Read()
        self.assertEqual(view.sequence, 7)
        self.assertTrue(view.controllersClear)
        self.assertFalse(view.working)
        self.assertFalse(view.invocationPending)
        self.assertEqual(len(self.client.heistCalls), 0)

    def test_start_reuses_native_act_and_only_delivers_owned_success(self):
        self.assertIsNotNone(self.controller)
        replies = self.h.lua.table()
        callback = self.h.lua.eval("function(replies) return function(reply) replies[#replies+1] = reply end end")(replies)
        self.assertTrue(self.controller.Start(8, "start", "h_a", callback))
        self.assertEqual(self.client.heistAct[2], 8)
        self.assertEqual(len(self.client.heistCalls), 1)
        self.assertEqual(self.client.heistCalls[1].action, "start")
        self.assertEqual(self.client.heistCalls[1].arg1, "h_a")
        self.assertFalse(self.controller.Read().controllersClear)
        self.client.finishHeist(lua_table(self.h.lua, {"ok": True, "runId": "run-a"}))
        self.assertEqual(replies[1].runId, "run-a")
        self.assertFalse(self.controller.Read().controllersClear)
        self.assertTrue(self.controller.Release(8))
        self.assertTrue(self.controller.Read().controllersClear)

    def test_stale_counter_busy_and_other_native_pending_refuse_without_call(self):
        self.assertIsNotNone(self.controller)
        callback = self.h.lua.eval("function() end")
        self.assertFalse(self.controller.Start(7, "start", "h_a", callback))
        self.client.heistAct[3] = True
        self.assertFalse(self.controller.Start(8, "start", "h_a", callback))
        self.client.heistAct[3] = False
        self.client.heistAct[1] = lua_table(self.h.lua,
            {"sequence": 7, "actionName": "ledger", "startedAt": 0})
        self.assertFalse(self.controller.Start(8, "start", "h_a", callback))
        self.assertEqual(len(self.client.heistCalls), 0)

    def test_terminal_failure_does_not_invent_a_callback_or_free_local_custody(self):
        self.assertIsNotNone(self.controller)
        replies = self.h.lua.table()
        callback = self.h.lua.eval("function(replies) return function(reply) replies[#replies+1] = reply end end")(replies)
        self.assertTrue(self.controller.Start(8, "help", "row-a", callback))
        self.client.finishHeist(lua_table(self.h.lua, {"ok": False, "code": "expired"}))
        self.assertEqual(len(replies), 0)
        self.assertFalse(self.controller.Read().controllersClear)
        self.assertFalse(self.controller.Start(9, "start", "h_a", callback))

    def test_changed_identity_or_version_retires_controller(self):
        self.assertIsNotNone(self.controller)
        self.client.heistInit[38] = self.h.lua.eval("function() end")
        self.assertFalse(self.controller.Current())
        self.assertIsNone(self.controller.Read())
        self.assertFalse(self.controller.Start(8, "start", "h_a", self.h.lua.eval("function() end")))

    def test_unreviewed_version_is_not_bound(self):
        self.client.game.PlaceVersion = 656
        self.assertIsNone(self.module.bind(
            self.client.game, self.client.requireModule, self.client.readUpvalues))

    def test_reviewed_654_uses_its_explicit_act_index(self):
        self.client.game.PlaceVersion = 654
        self.client.heistInit[37] = self.client.heistInit[38]
        self.client.heistInit[38] = False
        controller = self.module.bind(
            self.client.game, self.client.requireModule, self.client.readUpvalues)
        self.assertIsNotNone(controller)
        self.assertEqual(controller.Read().sequence, 7)

    def test_timed_out_pending_keeps_heist_custody_but_allows_status_read_lane(self):
        self.assertTrue(self.controller.Start(8, "help", "row-a", self.h.lua.eval("function() end")))
        self.client.heistAct[3] = False
        self.assertFalse(self.controller.Busy())
        self.assertFalse(self.controller.Read().controllersClear)

    def test_shared_bindings_expose_factory_bound_controller(self):
        bindings = self.h.load("src/transport/NativeClientBindings.luau")
        found = bindings.read(self.client.game, self.client.requireModule,
                              self.client.readUpvalues, self.module)[0]
        self.assertIsNotNone(found.currentHeistController)
        self.assertEqual(found.currentHeistController.Read().sequence, 7)

    def test_native_snapshot_time_is_read_for_dispatch_day_continuity(self):
        self.client.data.serverNow = 1987300
        self.assertEqual(self.controller.Read().serverNow, 1987300)

    def test_completed_native_invocation_record_is_not_still_a_physical_rpc(self):
        self.client.heistInvocation[1] = lua_table(self.h.lua, {"done": True, "ok": True})
        self.assertFalse(self.controller.Busy())
        self.assertFalse(self.controller.Read().controllersClear)


if __name__ == "__main__":
    unittest.main()
