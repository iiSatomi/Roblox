"""Verified native wrapper ownership, combat guards and own-player display facts."""
import unittest

from engine_harness import Harness


class NativeCombatPlayerBindingsTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        base = self.h.load("tests/fixtures/prestige-client.lua")
        self.client = self.h.load("tests/fixtures/combat-client.lua")(base)
        self.bindings = self.h.load("src/transport/NativeClientBindings.luau")

    def bind(self):
        return self.bindings.read(self.client.game, self.client.requireModule,
                                  self.client.readUpvalues)[0]

    def test_verified_client_requires_native_wrapper_module(self):
        self.client.client.children.RemoteLink = None
        self.assertIsNone(self.bind())

    def test_reviewed_654_client_requires_wrapper_and_supports_current_facts(self):
        self.client.game.PlaceVersion = 654
        found = self.bind()
        view = found.currentFightNotifications.CombatFrame(
            found.currentFightNotifications, self.client.data, self.h.lua.table())
        self.assertIsNotNone(view)
        self.assertTrue(found.currentPlayerInfo.Current())
        self.client.client.children.RemoteLink = None
        self.assertIsNone(self.bind())

    def test_current_combat_frame_uses_native_estimate_and_target_guards(self):
        source = self.bind().currentFightNotifications
        targets = self.h.lua.eval("{{userId = 456, familyId = 0}}")
        view = source.CombatFrame(source, self.client.data, targets)
        self.assertIsNotNone(view)
        self.assertAlmostEqual(view.attack, 72.6)
        self.assertEqual((view.health, view.stamina, view.maxStaminaCost), (100, 20, 5))
        self.assertFalse(view.busy)
        self.assertFalse(view.shielded)
        self.assertEqual(view.targets["456"].remainingDaily, 5)
        self.assertFalse(view.targets["456"].manualWarning)

    def test_attack_preflight_allows_guarded_request_and_blocks_busy_or_low_resources(self):
        source = self.bind().currentFightNotifications
        self.assertTrue(source.CanAttack(source, self.client.proposal, 456)[0])
        self.client.busy[1] = True
        self.assertFalse(source.CanAttack(source, self.client.proposal, 456)[0])
        self.client.busy[1] = False
        self.client.data.pools.stamina = 4
        self.assertFalse(source.CanAttack(source, self.client.proposal, 456)[0])

    def test_scout_preflight_keeps_followup_attack_reserve_and_native_busy_guard(self):
        source = self.bind().currentFightNotifications
        intent = self.client.proposal.intent
        intent.kind, intent.allowScout = "playerScout", True
        intent.attackExposure = 5
        self.client.proposal.resources.stamina = 5
        self.assertTrue(source.CanScout(source, self.client.proposal, 456)[0])
        self.client.data.pools.stamina = 9
        self.assertFalse(source.CanScout(source, self.client.proposal, 456)[0])
        self.client.data.pools.stamina = 20
        self.client.profileUpvalues[3] = True
        self.assertFalse(source.CanScout(source, self.client.proposal, 456)[0])

    def test_player_display_reads_verified_multiplier_and_copied_property_rows(self):
        source = self.bind().currentPlayerInfo
        self.assertTrue(source.Current())
        view = source.Read(source, self.client.data)
        self.assertIsNotNone(view)
        self.assertEqual((view.userId, view.name, view.displayName), (123, "user-a", "User A"))
        self.assertEqual(view.propertyMultiplier, 0.9)
        self.assertEqual(view.properties[1].incomePerHour, 100)
        view.properties[1].name = "Changed copy"
        self.assertEqual(self.client.gameData.PROPERTIES[1].name, "Property A")

    def test_replaced_wrapper_or_context_fails_preflight(self):
        source = self.bind().currentFightNotifications
        self.client.wrapped.Attack.InvokeServer = self.h.lua.eval("function() end")
        self.assertFalse(source.CanAttack(source, self.client.proposal, 456)[0])

    def test_unverified_version_cannot_supply_combat_or_player_facts(self):
        found = self.bind()
        self.client.game.PlaceVersion = 656
        combat, player = found.currentFightNotifications, found.currentPlayerInfo
        self.assertIsNone(combat.CombatFrame(combat, self.client.data, self.h.lua.table()))
        self.assertFalse(combat.CanAttack(combat, self.client.proposal, 456)[0])
        self.assertFalse(player.Current())
        self.assertIsNone(player.Read(player, self.client.data))


if __name__ == "__main__":
    unittest.main()
