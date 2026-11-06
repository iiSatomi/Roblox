"""Legacy perk choices migrate exactly without importing contribution permission."""
import json
import unittest
from engine_harness import lua_table
from test_redundant_store import plain
import test_profile_management as profiles
import test_family_contribution_read_pipeline as contributions


class LegacyFamilyPreferencesTests(unittest.TestCase):
    def setUp(self):
        self.f = profiles.ProfileManagementTests()
        self.f.setUp()
        self.app = self.f.app

    def tearDown(self):
        self.f.tearDown()

    def preview(self, perks, **choices):
        return self.app.PreviewImport(self.app, json.dumps({"version": 17, "familyPerks": perks, **choices}))

    def test_one_current_perk_maps_without_allowances_or_activation(self):
        choices = {"guardians": True, "enforcers": False}
        accepted, reason = self.preview(choices, familyPerk="runners")
        self.assertTrue(accepted, reason)
        values = self.app.staged["values"]
        self.assertEqual(values["familyStamina.custom.selectedPerk"], "guardians")
        self.assertFalse(values["familyStamina.enabled"])
        self.assertEqual(values["familyStamina.custom.maxAttempts"], 0)
        self.assertEqual(values["familyStamina.custom.runBudget"], 0)
        self.assertEqual(plain(self.app.importReview.original.familyPerks), choices)
        self.assertEqual(len(self.f.base.storage.data), 0)

    def test_multiple_empty_or_malformed_choices_remain_reviewable(self):
        for choices in ({}, {"enforcers": False},
                        {"enforcers": "true"}, {"unknown": True}, {"guardians": True, "unknown": False}, ["guardians"]):
            with self.subTest(choices=choices):
                accepted, reason = self.preview(choices)
                self.assertFalse(accepted)
                self.assertIn("familyPerks", reason)
                self.assertIsNone(self.app.staged)

    def test_explicit_legacy_default_perk_keeps_runners_choice(self):
        accepted, reason = self.preview({"runners": True})
        self.assertTrue(accepted, reason)
        self.assertEqual(self.app.staged["values"]["familyStamina.custom.selectedPerk"], "runners")
        self.assertFalse(self.app.staged["values"]["familyStamina.enabled"])

    def test_multiple_perks_import_exact_ids_without_enabling_or_allowances(self):
        accepted, reason = self.preview({"guardians": True, "enforcers": True, "runners": False})
        self.assertTrue(accepted, reason)
        values = self.app.staged["values"]
        self.assertEqual(values["familyStamina.custom.selectedPerks"], "enforcers,guardians")
        self.assertFalse(values["familyStamina.enabled"])
        self.assertEqual(values["familyStamina.custom.runBudget"], 0)
        self.assertEqual(values["familyStamina.custom.maxAttempts"], 0)

    def test_imported_multi_perks_reach_actual_calls_in_native_order(self):
        import test_family_perk_rotation as rotation
        accepted, reason = self.preview({"guardians": True, "enforcers": True})
        self.assertTrue(accepted, reason)
        f = rotation.FamilyPerkRotationAppTests(); f.setUp()
        try:
            self.assertTrue(f.app.ApplyProfile(f.app, lua_table(f.h.lua, plain(self.app.staged)))[0])
            self.assertTrue(f.app.model.paused)
            self.assertEqual(len(f.executor.calls), 0)
            for key, value in (("enabled", True), ("custom.amount", 5), ("custom.runBudget", 15), ("custom.maxAttempts", 3)):
                self.assertTrue(f.app.Set(f.app, "familyStamina."+key, value)[0])
            f.app.Resume(f.app)
            f.send("guardians"); f.send("enforcers"); f.send("guardians")
        finally:
            f.tearDown()

    def test_current_multi_selection_rejects_unknown_or_duplicate_ids_atomically(self):
        before = plain(self.app.model.Snapshot(self.app.model))
        for value in ("enforcers,unknown", "enforcers,enforcers", "enforcers,", "unknown", True):
            self.assertFalse(self.app.Set(self.app, "familyStamina.custom.selectedPerks", value)[0])
            self.assertEqual(plain(self.app.model.Snapshot(self.app.model)), before)

    def test_nondefault_singular_plural_conflict_still_refuses(self):
        accepted, reason = self.preview({"guardians": True}, familyPerk="enforcers")
        self.assertFalse(accepted)
        self.assertIn("familyPerk", reason)
        self.assertIsNone(self.app.staged)

    def test_unsupported_stamina_amounts_remain_reviewable_without_substitution(self):
        for amount in (0, 2, 3, 4, 1.5, 6, "1", "5", True):
            with self.subTest(amount=amount):
                accepted, reason = self.preview({"guardians": True}, familyStaminaAmount=amount)
                self.assertFalse(accepted)
                self.assertIn("familyStaminaAmount", reason)
                self.assertIsNone(self.app.staged)
                self.assertEqual(self.app.importReview.original.familyStaminaAmount, amount)
                self.assertEqual(self.app.model["values"]["familyStamina.custom.amount"], 1)
                self.assertEqual(len(self.f.base.storage.data), 0)

    def test_current_profile_rejects_unsupported_amount_atomically(self):
        before = plain(self.app.model.Snapshot(self.app.model))
        for amount in (2, 3, 4, 1.5, "5", True):
            with self.subTest(amount=amount):
                profile = {"schema": 1, "values": {"familyStamina.custom.amount": amount,
                    "familyStamina.enabled": True, "familyStamina.custom.runBudget": 5}}
                accepted, reason = self.app.PreviewImport(self.app, json.dumps(profile))
                self.assertFalse(accepted)
                self.assertIn("familyStamina.custom.amount", reason)
                self.assertIsNone(self.app.staged)
                self.assertFalse(self.app.ApplyProfile(self.app, lua_table(self.f.h.lua, profile))[0])
                self.assertEqual(plain(self.app.model.Snapshot(self.app.model)), before)
                self.assertEqual(len(self.f.base.storage.data), 0)

    def test_actual_family_ui_and_set_reject_intermediate_amounts(self):
        f = contributions.FamilyContributionReadPipelineTests()
        f.setUp()
        f.start("familyStamina", "stamina", 5)
        try:
            key = "familyStamina.custom.amount"
            before = plain(f.app.model.Snapshot(f.app.model))
            handle = f.app.ui.handles[key]
            for amount in (2, 3, 4, 1.5):
                with self.subTest(amount=amount):
                    self.assertFalse(f.app.Set(f.app, key, amount)[0])
                    handle.Set(handle, str(amount), True)
                    handle.options.Callback(str(amount))
                    self.assertEqual(handle.value, "5")
                    self.assertIn(key, f.app.ui.lastError)
                    self.assertEqual(plain(f.app.model.Snapshot(f.app.model)), before)
                    self.assertEqual(len(f.executor.calls), 0)
        finally:
            f.tearDown()

    def test_imported_five_stamina_reaches_actual_owned_family_call(self):
        self.assert_imported_family_call(5)

    def test_imported_perk_reaches_actual_owned_family_call(self):
        self.assert_imported_family_call(1)

    def assert_imported_family_call(self, amount):
        accepted, reason = self.preview({"guardians": True}, familyStaminaAmount=amount)
        self.assertTrue(accepted, reason)
        self.assertEqual(self.app.staged["values"]["familyStamina.custom.amount"], amount)
        self.assertFalse(self.app.staged["values"]["familyStamina.enabled"])
        self.assertEqual(self.app.staged["values"]["familyStamina.custom.runBudget"], 0)
        self.assertEqual(self.app.staged["values"]["familyStamina.custom.maxAttempts"], 0)
        f = contributions.FamilyContributionReadPipelineTests()
        f.setUp()
        original_family = f.fixture.family
        def family(resource=None, amount=0, other_donation=0):
            value = original_family(resource, amount, other_donation)
            value["perks"]["guardians"] = 0
            value["perkProgress"]["guardians"] = 20 + (amount if resource == "stamina" else 0)
            return value
        f.fixture.family = family
        f.fixture.config.FAMILY.perkTracks.guardians = lua_table(f.h.lua, {"kind": "stamina"})
        f.start("familyStamina", "stamina", amount)
        try:
            self.assertTrue(f.app.ApplyProfile(f.app, lua_table(f.h.lua, plain(self.app.staged)))[0])
            self.assertTrue(f.app.model.paused)
            self.assertEqual(len(f.executor.calls), 0)
            for key, value in (("enabled", True), ("custom.runBudget", amount), ("custom.maxAttempts", 1)):
                self.assertTrue(f.app.Set(f.app, "familyStamina." + key, value)[0])
            f.app.Resume(f.app)
            f.step()
            f.executor.queued[1]()
            f.h.at(.25)
            f.step()
            f.executor.queued[2]()
            call = f.executor.calls[2]
            self.assertEqual(call.remote, "FamilyAction")
            self.assertEqual(call.args[1], "contribute")
            self.assertEqual(call.args[2], "guardians")
            self.assertEqual(call.args[3], amount)
        finally:
            f.tearDown()


if __name__ == "__main__":
    unittest.main()
