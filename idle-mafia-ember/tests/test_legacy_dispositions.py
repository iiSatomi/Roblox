"""Every schema-17 control has a reviewed mapping or visible deliberate exclusion."""
import json
import unittest
from pathlib import Path

import test_profile_management as profiles
from test_redundant_store import plain


EXCLUDED_KEYS = set("""
perAction sessionBudget propertyReplace propertyReplaceMultiplier propertyReplacePaybackHours
combatNativeRefresh prestigeMaxPerLoad interval timeout readTimeout combatConfirmGrace
antiAfk botCheckCapture acrylic transparent theme collectionObjective crewGearStrategy
briefcaseUseKeys briefcaseKeyLimit crateLuckOnly consumableUseTradable
shopGold shopGoldMax shopGoldReserve
marketResearchMode marketSellMaxListingsPerLoad marketRentMaxPerLoad marketAutoCheck
eventScheduling xpTargetLevel heistPoll favorUsageDay favorUsageCount
sabotageEnabled sabotageDailyCap sabotageFavorReserve sabotageEnergyReserve
sabotageUsageDay sabotageUsageCount sabotageAttemptDay sabotageAttemptCount
playtimeEnergy playtimeEnergyBelow contractFocus autoContracts contractExcluded trophyFocus
combatWarPriority combatTakedownPriority combatScout combatExploreUnknown combatProfileRefresh
combatScoutRefresh combatMinPowerRatio combatTargetRefresh crewRollUseBank replaceCrew
crewRollWorstFirst replaceWeakCrew crewRollMinQuality crewRollMinAttackQuality
crewRollMinDefenseQuality crewRollQualityScope crewRollLuckOnly skipConfirmation
familyCashMaxPerLoad familyGoldMaxPerLoad familyStaminaMaxPerLoad familyHospitalOnly
familyStaminaOnlyStationed familyBossHealthFloor familyBossStaminaReserve familyBossStrategy
residencyMinImprovement residencyDistricts stationSignificantHpPercent stationMove
stationTrainRotation stationMoveMinDeficit stationCombatRecovery stationRecoveryHealth
stationMinSourceDefenders stationMoveCooldownMinutes
""".split())


BANK_TARGETS = {
    "heistsUseBank": "withdraw.custom.allowHeists",
    "operationsUseBank": "withdraw.custom.allowOperations",
    "propertiesUseBank": "withdraw.custom.allowProperties",
    "safehouseUseBank": "withdraw.custom.allowSafehouse",
}


class LegacyDispositionTests(unittest.TestCase):
    def setUp(self):
        self.f = profiles.ProfileManagementTests()
        self.f.setUp()
        self.app = self.f.app
        self.defaults = plain(self.f.h.load("src/storage/LegacySettings.luau").defaults())
        self.inventory = json.loads((Path(__file__).parents[1] /
            "docs/legacy-settings-inventory.json").read_text(encoding="utf-8"))

    def tearDown(self):
        self.f.tearDown()

    def changed(self, key):
        labels = {"theme": "Dark", "collectionObjective": "Attack",
                  "crewGearStrategy": "Build complete sets", "shopKind": "Weapons",
                  "shopRule": "Buy cash items under price", "marketResearchMode": "Fast Turnover",
                  "crewRollQualityScope": "Selected rarity and higher (preserve rarity)",
                  "familyBossStrategy": "Rank focus"}
        special = {"prestigeMaxPerLoad": 2, "xpTargetLevel": 100,
                   "shopOverrideRarities": {"Mythic": True},
                   "contractExcluded": {"heiststarts": True},
                   "residencyDistricts": {"district_a": True}}
        if key in labels:
            return labels[key]
        if key in special:
            return special[key]
        value = self.defaults[key]
        return not value if isinstance(value, bool) else value + 1

    def preview(self, choices):
        return self.app.PreviewImport(self.app, json.dumps({"version": 17, **choices}))

    def test_every_excluded_nondefault_retains_intent_and_a_specific_reason(self):
        self.assertEqual(len(EXCLUDED_KEYS), 84)
        generic = []
        for key in sorted(EXCLUDED_KEYS):
            value = self.changed(key)
            accepted, reason = self.preview({key: value})
            with self.subTest(key=key):
                self.assertFalse(accepted)
                self.assertIn(key, reason)
                self.assertIsNone(self.app.staged)
                self.assertEqual(plain(self.app.importReview.original[key]), value)
                detail = self.app.importReview.unresolvedReasons[key]
                if not detail or detail.startswith("No reviewed equivalent"):
                    generic.append(key)
                self.assertEqual(len(self.f.base.storage.data), 0)
                self.assertTrue(self.app.model.paused)
        self.assertEqual(generic, [], "Known exclusions need a precise reason instead of a fallback")

    def test_inventory_accounts_for_all_231_controls_and_matches_exclusion_reviews(self):
        rows = self.inventory["settings"]
        self.assertEqual(len(rows), 231)
        self.assertEqual({row["legacy_key"] for row in rows}, set(self.defaults))
        excluded = {row["legacy_key"] for row in rows
                    if row["migration"]["status"] == "deliberately-excluded-nondefault"}
        self.assertEqual(excluded, EXCLUDED_KEYS)
        for row in rows:
            key, migration = row["legacy_key"], row["migration"]
            with self.subTest(key=key):
                self.assertNotEqual(migration["status"], "review-required-for-nondefault")
                if key in excluded:
                    self.assertFalse(self.preview({key: self.changed(key)})[0])
                    self.assertEqual(migration["reason"], self.app.importReview.unresolvedReasons[key])
                    self.assertTrue(migration["exclusion_kind"])
                elif key != "version":
                    self.assertTrue(migration.get("target") or migration.get("targets")
                                    or migration.get("condition") or migration.get("note"))
        evidence = self.inventory["migration_evidence"]
        self.assertEqual(evidence["reviewed_control_dispositions"], 231)
        self.assertEqual(evidence["supported_preference_keys"], 146)
        self.assertEqual(evidence["deliberately_excluded_keys"], 84)
        self.assertFalse(evidence["historical_runtime_ledger_migration"])
        self.assertFalse(evidence["automatic_activation"])

    def test_saved_bank_flags_map_exact_scopes_with_missing_legacy_flags_false(self):
        for key, target in BANK_TARGETS.items():
            for choice in (False, True):
                with self.subTest(key=key, choice=choice):
                    self.assertNotIn(key, self.defaults)
                    accepted, reason = self.preview({key: choice, "marketFlipMinMargin": 25})
                    self.assertTrue(accepted, reason)
                    review = json.loads(self.app.ui.profiles.importReviewText.value)
                    self.assertEqual(review["original"][key], choice)
                    self.assertNotIn(key, review["defaultExclusions"])
                    for destination in BANK_TARGETS.values():
                        expected = choice if destination == target else False
                        self.assertEqual(review["mapped"][destination], expected)
                        self.assertEqual(self.app.staged["values"][destination], expected)
                    self.assertNotIn("withdraw.enabled", review["mapped"])
                    self.assertFalse(self.app.staged["values"]["withdraw.enabled"])
                    self.assertFalse(any(v for k, v in self.app.staged["values"].items()
                                         if k.endswith(".enabled")))
                    self.assertEqual(len(self.f.base.storage.data), 0)
                    self.assertTrue(self.app.ApplyProfile(self.app, self.app.staged)[0])
                    self.assertFalse(self.app.model["values"]["withdraw.enabled"])
                    self.assertTrue(self.app.model.paused)

    def test_all_four_bank_flags_apply_without_enabling_withdrawal_or_rewriting_history(self):
        self.assertTrue(self.app.Set(self.app, "withdraw.enabled", True)[0])
        before = plain(self.app.model.Snapshot(self.app.model))
        self.f.base.storage.data["historical-custody"] = "preserve-exactly"
        accepted, reason = self.preview(dict.fromkeys(BANK_TARGETS, True))
        self.assertTrue(accepted, reason)
        self.assertEqual(plain(self.app.model.Snapshot(self.app.model)), before)
        self.assertTrue(all(self.app.staged["values"][target] for target in BANK_TARGETS.values()))
        self.assertFalse(self.app.staged["values"]["withdraw.enabled"])
        self.assertTrue(self.app.ApplyProfile(self.app, self.app.staged)[0])
        self.assertFalse(self.app.model["values"]["withdraw.enabled"])
        self.assertTrue(all(self.app.model["values"][target] for target in BANK_TARGETS.values()))
        self.assertTrue(self.app.model.paused)
        self.assertEqual(plain(self.f.base.storage.data), {"historical-custody": "preserve-exactly"})

    def test_empty_saved_shop_selection_is_visible_without_importing_an_offer(self):
        accepted, reason = self.preview({"shopSelected": {}})
        self.assertTrue(accepted, reason)
        review = json.loads(self.app.ui.profiles.importReviewText.value)
        self.assertEqual(review["original"]["shopSelected"], {})
        self.assertIn("shopSelected", review["currentDefaults"])
        self.assertIn("empty", review["defaultExclusions"]["shopSelected"].lower())
        self.assertNotIn("shop.custom.itemId", review["mapped"])
        self.assertEqual(self.app.staged["values"]["shop.custom.itemId"],
                         self.app.model.defaults["shop.custom.itemId"])
        self.assertFalse(self.app.staged["values"]["shop.enabled"])
        self.assertEqual(len(self.f.base.storage.data), 0)

    def test_actual_saved_extensions_import_all_cash_mode_without_activation(self):
        choices = {**dict.fromkeys(BANK_TARGETS, True), "shopBuyAll": True,
                   "shopSelected": {}, "marketFlipMinMargin": 25}
        before = plain(self.app.model.Snapshot(self.app.model))
        self.f.base.storage.data["historical-custody"] = "preserve-exactly"
        accepted, reason = self.preview(choices)
        self.assertTrue(accepted, reason)
        review = json.loads(self.app.ui.profiles.importReviewText.value)
        self.assertEqual(set(review["unresolved"]), set())
        self.assertEqual(review["original"], {"version": 17, **choices})
        self.assertEqual(review["mapped"]["shop.custom.selection"], "All cash items")
        self.assertEqual(review["mapped"]["shop.custom.selectedIds"], "")
        self.assertEqual(review["mapped"]["marketFlip.custom.minMargin"], 25)
        self.assertTrue(all(review["mapped"][target] for target in BANK_TARGETS.values()))
        self.assertFalse(any(k.endswith(".enabled") for k in review["mapped"]))
        self.assertEqual(plain(self.app.model.Snapshot(self.app.model)), before)
        self.assertEqual(plain(self.f.base.storage.data), {"historical-custody": "preserve-exactly"})
        self.assertIsNotNone(self.app.staged)
        self.assertFalse(self.app.staged["values"]["shop.enabled"])
        self.assertFalse(self.app.staged["values"]["withdraw.enabled"])

    def test_shop_modes_and_nonempty_selections_do_not_become_a_default_cash_offer(self):
        choices = [{"shopBuyAll": buy_all, "shopSelected": selected}
                   for buy_all in (False, True)
                   for selected in ({}, {"w_pipe": True}, {"w_pipe": True, "w_other": True})]
        for values in choices:
            with self.subTest(values=values):
                accepted, reason = self.preview(values)
                self.assertTrue(accepted, reason)
                self.assertIsNotNone(self.app.staged)
                self.assertEqual(plain(self.app.importReview.original), {"version": 17, **values})
                self.assertIsNone(self.app.importReview.mapped["shop.custom.itemId"])
                self.assertEqual(self.app.importReview.mapped["shop.custom.selection"],
                                 "All cash items" if values["shopBuyAll"] else "Selected cash items")
                self.assertEqual(self.app.importReview.mapped["shop.custom.selectedIds"],
                                 ",".join(sorted(values["shopSelected"])))
                self.assertFalse(self.app.staged["values"]["shop.enabled"])
        accepted, reason = self.preview({"shopSelected": {"w_pipe": True}})
        self.assertFalse(accepted)
        self.assertIn("shopSelected", reason)
        self.assertIsNone(self.app.staged)
        accepted, reason = self.preview({"shopSelected": {"w_pipe": False}})
        self.assertTrue(accepted, reason)
        self.assertEqual(self.app.importReview.mapped["shop.custom.selection"], "Category rules")
        self.assertEqual(self.app.importReview.mapped["shop.custom.selectedIds"], "")

    def test_saved_extension_wrong_types_and_unrelated_custody_still_block(self):
        for key in BANK_TARGETS:
            for value in (0, 1, "false", {}):
                with self.subTest(key=key, value=value):
                    accepted, reason = self.preview({key: value})
                    self.assertFalse(accepted)
                    self.assertIn(key, reason)
                    self.assertIsNone(self.app.staged)
                    self.assertFalse(any(self.app.importReview.mapped[target] is not None
                                         for target in BANK_TARGETS.values()))
        inactive = {**dict.fromkeys(BANK_TARGETS, False), "shopSelected": {}}
        for key, value in (("favorUsageCount", 3), ("skipConfirmation", True),
                           ("unknownSetting", False), ("shopSelected", False), ("shopBuyAll", 0)):
            with self.subTest(key=key):
                accepted, reason = self.preview({**inactive, key: value})
                self.assertFalse(accepted)
                self.assertIn(key, reason)
                self.assertIsNone(self.app.staged)
                self.assertEqual(plain(self.app.importReview.original[key]), value)
        self.assertEqual(len(self.defaults), 231)
        metadata = self.inventory["additional_saved_fields"]
        self.assertEqual(set(metadata["keys"]), set(inactive) | {"shopBuyAll"})
        self.assertFalse(metadata["accepted_as_baseline_defaults"])

    def test_missing_current_funding_scope_refuses_the_whole_legacy_group(self):
        missing = BANK_TARGETS["heistsUseBank"]
        original = self.app.model.specs[missing]
        self.app.model.specs[missing] = None
        try:
            accepted, reason = self.preview({"operationsUseBank": True})
            self.assertFalse(accepted)
            self.assertIn("operationsUseBank", reason)
            self.assertIsNone(self.app.staged)
            self.assertFalse(any(self.app.importReview.mapped[target] is not None
                                 for target in BANK_TARGETS.values()))
        finally:
            self.app.model.specs[missing] = original

    def test_omitted_funding_extensions_keep_current_defaults_and_never_import_enable(self):
        accepted, reason = self.preview({"bankCashToKeep": 700})
        self.assertTrue(accepted, reason)
        self.assertFalse(any(self.app.importReview.mapped[target] is not None
                             for target in BANK_TARGETS.values()))
        settings = {"version": 17, **dict.fromkeys(BANK_TARGETS, True)}
        accepted, reason = self.app.PreviewImport(self.app, json.dumps({
            "settings": settings, "enabled": {"withdraw": True}}))
        self.assertFalse(accepted)
        self.assertIn("enabled.withdraw", reason)
        self.assertIsNone(self.app.staged)
        self.assertFalse(self.app.model["values"]["withdraw.enabled"])

    def test_all_exclusions_remain_copyable_together_without_partial_application(self):
        choices = {key: self.changed(key) for key in EXCLUDED_KEYS}
        choices["marketFlipMinMargin"] = 25
        before = plain(self.app.model.Snapshot(self.app.model))
        accepted, reason = self.preview(choices)
        self.assertFalse(accepted)
        review = json.loads(self.app.ui.profiles.importReviewText.value)
        self.assertEqual(set(review["unresolved"]), EXCLUDED_KEYS)
        self.assertEqual(review["original"], {"version": 17, **choices})
        self.assertEqual(review["mapped"]["marketFlip.custom.minMargin"], 25)
        self.assertEqual(set(review["unresolvedReasons"]), EXCLUDED_KEYS)
        self.assertLess(len(self.app.ui.profiles.importReviewText.value.encode("utf-8")), 65536)
        self.assertEqual(plain(self.app.model.Snapshot(self.app.model)), before)
        self.assertIsNone(self.app.staged)
        self.assertEqual(len(self.f.base.storage.data), 0)


if __name__ == "__main__":
    unittest.main()
