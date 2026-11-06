"""Remaining source-reviewed preferences use the actual App import/apply path."""
import json
import unittest

import test_profile_management as fixture
from engine_harness import lua_table


class LegacyRemainingPreferencesTests(unittest.TestCase):
    def setUp(self):
        self.f = fixture.ProfileManagementTests()
        self.f.setUp()
        self.app, self.h = self.f.app, self.f.h

    def tearDown(self):
        self.f.tearDown()

    def preview(self, **settings):
        return self.app.PreviewImport(self.app, json.dumps(dict(version=17, **settings)))

    def assert_inert(self):
        values = self.app.staged['values']
        self.assertFalse(any(value for key, value in values.items() if key.endswith('.enabled')))
        for key in ('crewRoll.custom.allowDismiss', 'residency.custom.allowReplace',
                    'residency.custom.allowRequests', 'combat.custom.allowScout',
                    'warCombat.custom.allowScout', 'prestige.custom.allowReset'):
            self.assertFalse(values[key], key)
        for feature in ('crewHire', 'crewRoll'):
            for key in ('maxAttempts', 'maxSpend'):
                self.assertEqual(values[feature + '.custom.' + key], 0)
        self.assertEqual(values['residency.custom.maxAttempts'], 0)
        for key, value in values.items():
            if key.startswith('trophyFocus.custom.borrow'):
                self.assertFalse(value, key)
        self.assertEqual(values['restoratives.custom.custody'], 'Bound only')
        self.assertEqual(len(self.f.base.storage.data), 0)
        self.assertTrue(self.app.model.paused)

    def test_chest_total_allowance_import_is_exact_inert_and_independent_of_batch(self):
        for limit,enabled in ((1,True),(5,True),(1000,False)):
            accepted,reason=self.preview(chestLimit=limit,chestLimitEnabled=enabled)
            self.assertTrue(accepted,reason)
            values=self.app.staged['values']
            self.assertEqual(values['chests.custom.totalLimit'],limit)
            self.assertEqual(values['chests.custom.totalLimitEnabled'],enabled)
            self.assertEqual(values['chests.custom.maxBatch'],1)
            self.assert_inert()
            self.assertTrue(self.app.ApplyProfile(self.app,self.app.staged)[0])
            self.assertFalse(self.app.model['values']['chests.enabled'])
            self.assertTrue(self.app.model.paused)
        for key,bad in (('chestLimit',0),('chestLimit',1001),('chestLimit',1.5),('chestLimit',True),('chestLimitEnabled',1)):
            accepted,reason=self.preview(**{key:bad})
            self.assertFalse(accepted);self.assertIn(key,reason);self.assertIsNone(self.app.staged)

    def test_contract_hire_tier_preserves_native_id_without_purchase_permission(self):
        for label, native in (('Professional', 'professional'), ('Elite', 'elite')):
            with self.subTest(label=label):
                accepted, reason = self.preview(contractHireTier=label)
                self.assertTrue(accepted, reason)
                self.assertEqual(self.app.staged['values']['crewHire.policy'], native)
                self.assertEqual(self.app.model['values']['crewHire.policy'], 'street')
                self.assert_inert()

    def test_crew_rarity_selects_custom_policy_so_threshold_is_not_overridden(self):
        module = self.h.load('src/tabs/crew/Module.luau')
        labels = ('Common', 'Uncommon', 'Rare', 'Epic', 'Legendary', 'Mythic', 'Secret', 'Forbidden')
        for rarity, label in enumerate(labels, 1):
            if label == 'Legendary':
                continue  # Unchanged baseline continues to use visible current defaults.
            with self.subTest(label=label):
                accepted, reason = self.preview(crewRollRarity=label)
                self.assertTrue(accepted, reason)
                values = self.app.staged['values']
                self.assertEqual(values['crewRoll.policy'], 'Custom')
                self.assertEqual(values['crewRoll.custom.targetRarity'], rarity)
                effective = module.ReplacementSettings(lua_table(self.h.lua, {
                    'enabled': False, 'policy': values['crewRoll.policy'],
                    'custom': {'targetRarity': values['crewRoll.custom.targetRarity']}}))
                self.assertEqual(effective.targetRarity, rarity)
                self.assertFalse(effective.enabled)
                self.assert_inert()

    def test_rent_ceiling_keeps_exact_percentage_without_selecting_or_requesting_residence(self):
        for rent in (1, 5, 10):
            with self.subTest(rent=rent):
                accepted, reason = self.preview(residencyMaxRent=rent)
                self.assertTrue(accepted, reason)
                values = self.app.staged['values']
                self.assertEqual(values['residency.custom.maxRentPct'], rent)
                self.assertEqual(values['residency.custom.districtId'], '')
                self.assert_inert()

    def test_selected_trophy_id_is_retained_without_goal_enable_or_borrowing(self):
        for goal in ('level_100', 'future_native_trophy'):
            accepted, reason = self.preview(trophyGoalId=goal)
            self.assertTrue(accepted, reason)
            self.assertEqual(self.app.staged['values']['trophyFocus.custom.goalId'], goal)
            self.assert_inert()

    def test_combined_preferences_apply_while_paused_without_storage_or_activation(self):
        accepted, reason = self.preview(contractHireTier='Elite', crewRollRarity='Secret',
            residencyMaxRent=4, trophyGoalId='level_100')
        self.assertTrue(accepted, reason)
        self.assert_inert()
        self.assertTrue(self.app.ApplyProfile(self.app, self.app.staged)[0])
        self.assertTrue(self.app.model.paused)
        self.assertEqual(self.app.model['values']['crewHire.policy'], 'elite')
        self.assertEqual(self.app.model['values']['crewRoll.custom.targetRarity'], 7)
        self.assertEqual(self.app.model['values']['residency.custom.maxRentPct'], 4)
        self.assertEqual(self.app.model['values']['trophyFocus.custom.goalId'], 'level_100')
        self.assertFalse(any(value for key, value in self.app.model['values'].items() if key.endswith('.enabled')))
        self.assertEqual(len(self.f.base.storage.data), 0)

    def test_unknown_labels_wrong_types_and_unrepresentable_rent_remain_unresolved(self):
        for key, value in (('contractHireTier', 'VIP'), ('contractHireTier', True),
                           ('crewRollRarity', 'Contraband'), ('crewRollRarity', 7),
                           ('residencyMaxRent', 2.5), ('residencyMaxRent', 11),
                           ('residencyMaxRent', -1), ('residencyMaxRent', '5'),
                           ('trophyGoalId', True), ('trophyGoalId', 'x' * 121)):
            with self.subTest(key=key, value=value):
                accepted, reason = self.preview(**{key: value})
                self.assertFalse(accepted)
                self.assertIn(key, reason)
                self.assertIsNone(self.app.staged)

    def test_existing_unsafe_and_runtime_intent_cannot_be_hidden_by_new_mappings(self):
        for key, value in (('replaceCrew', True), ('replaceWeakCrew', True),
                           ('crewRollUseBank', True), ('trophyFocus', True),
                           ('favorUsageCount', 3), ('familyGoldMaxPerLoad', 5),
                           ('prestigeMaxPerLoad', 2), ('combatScout', True)):
            with self.subTest(key=key):
                accepted, reason = self.preview(contractHireTier='Elite', **{key: value})
                self.assertFalse(accepted)
                self.assertIn(key, reason)
                self.assertIsNone(self.app.staged)
                self.assertEqual(self.app.importReview.mapped['crewHire.policy'], 'elite')
                self.assertEqual(self.app.importReview.original[key], value)

    def test_nearest_policy_and_constraint_mismatches_explain_why_they_do_not_map(self):
        for key, value, fragment in (
            ('residencyMinImprovement', 5, 'improvement'),
            ('residencyDistricts', {'d_a': True}, 'allowlist')):
            with self.subTest(key=key):
                accepted, reason = self.preview(**{key: value})
                self.assertFalse(accepted)
                self.assertIn(key, reason)
                self.assertIn(fragment, self.app.importReview.unresolvedReasons[key])
                self.assertIsNone(self.app.staged)


if __name__ == '__main__':
    unittest.main()
