"""Native Prestige reads remain bound to the verified client and controller state."""
import unittest

from engine_harness import Harness


class NativePrestigeControllerTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.client = self.h.load("tests/fixtures/prestige-client.lua")
        self.bindings = self.h.load("src/transport/NativeClientBindings.luau")

    def bind(self):
        found, reason = self.bindings.read(
            self.client.game, self.client.requireModule, self.client.readUpvalues)
        self.assertIsNone(reason)
        return found.currentPrestigeController

    def test_current_verified_client_reads_rank_and_clear_controllers(self):
        controller = self.bind()
        self.assertIsNotNone(controller)
        self.assertTrue(controller.Current())
        view = controller.Read()
        self.assertEqual((view.rank, view.level, view.xp), (0, 200, 25))
        self.assertTrue(view.ready)
        self.assertTrue(view.controllersClear)
        self.assertFalse(view.busy)
        self.assertFalse(view.confirmationPending)
        self.assertFalse(view.modalOpen)

    def test_ui_parent_is_the_current_players_normal_player_gui(self):
        found, reason = self.bindings.read(
            self.client.game, self.client.requireModule, self.client.readUpvalues)
        self.assertIsNone(reason)
        self.assertIsNotNone(found.uiParent)
        self.assertTrue(found.uiParent.IsA(found.uiParent, "PlayerGui"))
        self.assertEqual(found.uiParent.Parent.UserId, 123)

    def test_unverified_place_version_has_no_reset_controller(self):
        for version in (648, 653, 656):
            with self.subTest(version=version):
                self.client.game.PlaceVersion = version
                self.assertIsNone(self.bind())

    def test_reviewed_654_client_preserves_same_controller_contract(self):
        self.client.game.PlaceVersion = 654
        controller = self.bind()
        self.assertIsNotNone(controller)
        self.assertTrue(controller.Read().controllersClear)

    def test_busy_confirmation_and_visible_modal_block_clear_proof(self):
        for state in ("busy", "confirmation", "modal", "root"):
            with self.subTest(state=state):
                self.setUp()
                if state == "busy":
                    self.client.init[5] = True
                elif state == "confirmation":
                    self.client.confirmation[3] = self.h.lua.eval("function() end")
                elif state == "modal":
                    self.client.modal.Visible = True
                else:
                    self.client.root.Visible = True
                controller = self.bind()
                self.assertIsNotNone(controller)
                self.assertTrue(controller.Current())
                view = controller.Read()
                self.assertIsNotNone(view)
                self.assertFalse(view.controllersClear)

    def test_changed_native_source_retires_controller_permanently(self):
        controller = self.bind()
        self.assertIsNotNone(controller)
        self.assertTrue(controller.Current())
        self.client.shown[3] = self.h.lua.eval("function() end")
        self.assertFalse(controller.Current())
        self.client.shown[3] = self.client.init[8]
        self.assertFalse(controller.Current())
        self.assertIsNone(controller.Read())

    def test_changed_wrapper_or_account_cannot_produce_a_reset_proof(self):
        for field in ("wrapper", "account", "context", "version"):
            with self.subTest(field=field):
                self.setUp()
                controller = self.bind()
                self.assertIsNotNone(controller)
                self.assertTrue(controller.Current())
                if field == "wrapper":
                    self.client.linked.InvokeServer = self.h.lua.eval("function() end")
                elif field == "account":
                    self.client.data.userId = 456
                elif field == "context":
                    self.client.ctx.State = self.h.lua.table()
                else:
                    self.client.game.PlaceVersion = 656
                self.assertIsNone(controller.Read())

    def test_closed_controller_cannot_read_or_reactivate(self):
        controller = self.bind()
        self.assertIsNotNone(controller)
        controller.Close()
        self.assertFalse(controller.Current())
        self.assertIsNone(controller.Read())


if __name__ == "__main__":
    unittest.main()
