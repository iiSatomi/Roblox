"""Behavioral tests of fresh Lua-compatible Luau, not live UI verification."""
import json
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from lupa import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]


class PrototypeTests(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)

    def module(self, name):
        return self.lua.execute((ROOT / name).read_text(encoding="utf-8"))

    def table(self, value):
        if isinstance(value, dict):
            return self.lua.table_from({k: self.table(v) for k, v in value.items()})
        if isinstance(value, list):
            return self.lua.table_from([self.table(v) for v in value])
        return value

    def model(self):
        catalog = self.table(json.loads((ROOT / "preview/catalog.json").read_text(encoding="utf-8")))
        return self.module("src/storage/Settings.luau").new(catalog)

    def app(self, **options):
        ember = self.module("tests/ember_double.lua")()
        for key, value in options.items():
            ember[key] = value
        dependencies = self.table({})
        dependencies.Ember = ember
        dependencies.Catalog = self.module("src/ui/Catalog.luau")
        dependencies.Settings = self.module("src/storage/Settings.luau")
        dependencies.EmberAdapter = self.module("src/ui/EmberAdapter.luau")
        dependencies.OverviewTab = self.module("src/tabs/overview/Module.luau")
        dependencies.HeistsTab = self.module("src/tabs/heists/Module.luau")
        dependencies.JobsTab = self.module("src/tabs/jobs/Module.luau")
        dependencies.OperationsTab = self.module("src/tabs/operations/Module.luau")
        dependencies.FavorsTab = self.module("src/tabs/favors/Module.luau")
        dependencies.CombatTab = self.module("src/tabs/combat/Module.luau")
        dependencies.CrewTab = self.module("src/tabs/crew/Module.luau")
        dependencies.InventoryTab = self.module(
            "src/tabs/inventory/Module.luau")
        dependencies.CollectionTab = self.module(
            "src/tabs/collection/Module.luau")
        dependencies.MoneyTab = self.module("src/tabs/money/Module.luau")
        dependencies.PropertyTab = self.module(
            "src/tabs/property/Module.luau")
        dependencies.SafehouseTab = self.module(
            "src/tabs/safehouse/Module.luau")
        dependencies.PrestigeTab = self.module(
            "src/tabs/prestige/Module.luau")
        dependencies.ShopTab = self.module(
            "src/tabs/shop/Module.luau")
        dependencies.BlackMarketTab = self.module(
            "src/tabs/blackMarket/Module.luau")
        dependencies.FamilyTab = self.module(
            "src/tabs/family/Module.luau")
        dependencies.TerritoryTab = self.module(
            "src/tabs/territory/Module.luau")
        dependencies.ContractsTab = self.module(
            "src/tabs/contracts/Module.luau")
        dependencies.TrophiesTab = self.module(
            "src/tabs/trophies/Module.luau")
        dependencies.SkillsTab = self.module(
            "src/tabs/skills/Module.luau")
        dependencies.RewardsTab = self.module(
            "src/tabs/rewards/Module.luau")
        dependencies.EventsTab = self.module(
            "src/tabs/events/Module.luau")
        dependencies.ProfilesTab = self.module(
            "src/tabs/profiles/Module.luau")
        dependencies.SettingsTab = self.module(
            "src/tabs/settings/Module.luau")
        dependencies.ActivityTab = self.module(
            "src/tabs/activity/Module.luau")
        return self.module("src/App.luau").start(dependencies), ember

    def profile(self, **values):
        return self.table({"schema": 1, "values": values})

    def test_defaults_are_false_and_paused(self):
        model = self.model()
        self.assertTrue(model.paused)
        for key, value in model["values"].items():
            if key.endswith(".enabled"):
                self.assertIs(value, False)

    def test_false_hydration_and_snapshot_are_independent(self):
        model = self.model()
        self.assertTrue(model.Set(model, "jobs.enabled", True)[0])
        prepared, error = model.Validate(model, self.profile(**{"jobs.enabled": False}))
        self.assertIsNone(error)
        model.Commit(model, prepared)
        self.assertIs(model["values"]["jobs.enabled"], False)
        snapshot = model.Snapshot(model)
        snapshot["values"]["jobs.enabled"] = True
        self.assertIs(model["values"]["jobs.enabled"], False)

    def test_profile_rejection_is_atomic(self):
        model = self.model()
        for values in ({"jobs.enabled": True, "unknown": True},
                       {"jobs.enabled": "false"},
                       {"jobs.policy": "Impossible"},
                       {"combat.custom.healthFloor": 101},
                       {"combat.custom.minimumPayout": float("nan")}):
            prepared, error = model.Validate(model, self.profile(**values))
            self.assertIsNone(prepared)
            self.assertTrue(error)
            self.assertIs(model["values"]["jobs.enabled"], False)
        prepared, error = model.Validate(model, self.table({"schema": 2, "values": {}}))
        self.assertIsNone(prepared)
        self.assertTrue(error)

    def test_gear_exclusion_and_conflicting_import(self):
        model = self.model()
        model.Set(model, "crew.enabled", True)
        model.Set(model, "crewGear.enabled", True)
        self.assertIs(model["values"]["crew.enabled"], False)
        prepared, error = model.Validate(model, self.profile(**{
            "jobs.enabled": True, "crew.enabled": True, "crewGear.enabled": True}))
        self.assertIsNone(prepared)
        self.assertIn("Conflicting", error)
        self.assertIs(model["values"]["jobs.enabled"], False)

    def test_stop_latch_and_import_cannot_resume(self):
        model = self.model()
        model.Set(model, "jobs.enabled", True)
        model.Stop(model)
        model.Set(model, "jobs.enabled", True)
        self.assertTrue(model.stopped)
        model.Resume(model)
        self.assertFalse(model.stopped)
        prepared, _ = model.Validate(model, self.profile(**{"jobs.enabled": False}))
        model.Commit(model, prepared)
        self.assertTrue(model.paused)

    def test_catalog_renders_all_tabs_and_every_feature_once(self):
        app, ember = self.app()
        self.assertEqual(len(app.ui.window.sections), 25)
        self.assertEqual(len(list(app.ui.features.items())), 55)
        self.assertIs(ember.configured.Storage, False)
        self.assertIs(ember.configured.Effects.RespectReducedMotion, True)
        self.assertEqual(app.ui.window.options.Keybind, "F8")
        self.assertFalse(app.ui.window.options.SaveLayout)

    def test_overview_owns_session_and_request_health(self):
        app, _ = self.app()
        self.assertIsNotNone(app.ui.overview)
        self.assertIn("Paused", app.ui.overview.sessionStatus.Get(
            app.ui.overview.sessionStatus))
        self.assertIn("Unavailable", app.ui.overview.requestStatus.Get(
            app.ui.overview.requestStatus))
        app.Resume(app)
        self.assertIn("Resumed", app.ui.overview.sessionStatus.Get(
            app.ui.overview.sessionStatus))
        app.Stop(app)
        self.assertIn("Stopped", app.ui.overview.sessionStatus.Get(
            app.ui.overview.sessionStatus))

    def test_overview_buttons_drive_session_and_unload(self):
        app, ember = self.app()
        buttons = {handle.options.Text: handle
                   for handle in app.ui.window.handles.values()
                   if handle.kind == "Button"}
        for name in ("Resume", "Pause", "Emergency Stop", "Unload"):
            self.assertIn(name, buttons)
        buttons["Resume"].Click(buttons["Resume"])
        ember.Flush()
        self.assertFalse(app.model.paused)
        buttons["Pause"].Click(buttons["Pause"])
        ember.Flush()
        self.assertTrue(app.model.paused)
        buttons["Emergency Stop"].Click(buttons["Emergency Stop"])
        ember.Flush()
        self.assertTrue(app.model.stopped)
        buttons["Unload"].Click(buttons["Unload"])
        ember.Flush()
        self.assertFalse(app.alive)

    def test_overview_request_health_reports_active_and_uncertain(self):
        app, _ = self.app()
        overview = app.ui.overview
        overview.Render(overview, self.table({"paused": False,
            "stopped": False, "automationRuntime": {
                "active": {"phase": "sent"}, "uncertainCount": 0}}))
        self.assertIn("Awaiting exact state", overview.requestStatus.Get(
            overview.requestStatus))
        overview.Render(overview, self.table({"paused": False,
            "stopped": False, "automationRuntime": {
                "uncertainCount": 1}}))
        self.assertIn("duplicate risk", overview.requestStatus.Get(
            overview.requestStatus))

    def test_heists_controls_are_tab_owned_and_show_protocol_blockers(self):
        app, _ = self.app()
        for feature in ("heists", "heistCollect", "sabotage"):
            row = app.ui.features[feature]
            self.assertTrue(row["tabOwned"])
            self.assertIn("Blocked", row["status"].Get(row["status"]))
        self.assertTrue(app.ui.features["jobs"]["tabOwned"])

    def test_jobs_selected_policy_has_catalog_selection_and_no_unsupported_custom(self):
        app, ember = self.app()
        row = app.ui.features["jobs"]
        self.assertFalse(row["custom"].visible)
        policies = [app.ui.handles["jobs.policy"].options.Options[i]
                    for i in range(1, len(app.ui.handles["jobs.policy"].options.Options) + 1)]
        self.assertNotIn("Custom", policies)
        selected = app.ui.handles["jobs.custom.selectedJobId"]
        self.assertIn("j_watch", [selected.options.Options[i]
                                  for i in range(1, len(selected.options.Options) + 1)])
        self.assertFalse(app.Set(app, "jobs.policy", "Custom")[0])
        self.assertTrue(app.Set(app, "jobs.policy", "Selected job")[0])
        self.assertTrue(row["custom"].visible)
        self.assertTrue(app.Set(app, "jobs.custom.selectedJobId", "j_watch")[0])
        self.assertFalse(app.Set(app, "jobs.custom.selectedJobId", "fake-id")[0])
        search = next(handle for handle in app.ui.window.handles.values()
                      if handle.kind == "Input" and handle.options.Text == "Find Job")
        search.Set(search, "newsstand")
        ember.Flush()
        narrowed = [selected.options.Options[i]
                    for i in range(1, len(selected.options.Options) + 1)]
        self.assertIn("j_watch", narrowed)  # Keep the selected value valid.
        self.assertIn("j_shake", narrowed)
        self.assertLess(len(narrowed), 10)
        search.Set(search, "boost")
        app.Destroy(app)
        ember.Flush()
        self.assertEqual([selected.options.Options[i]
                          for i in range(1, len(selected.options.Options) + 1)], narrowed)

    def test_jobs_selection_reaches_shared_runtime_settings(self):
        runtime = self.lua.execute("""
            local runtime = { features = { jobs = true } }
            function runtime:Status() return { state = "paused", availableFeatures = {} } end
            function runtime:Step(_, settings) self.received = settings end
            function runtime:Pause() end
            function runtime:Resume() end
            function runtime:Stop() end
            function runtime:Close() end
            return runtime
        """)
        deps = self.table({})
        deps.Ember = self.module("tests/ember_double.lua")()
        deps.Catalog = self.module("src/ui/Catalog.luau")
        deps.Settings = self.module("src/storage/Settings.luau")
        deps.EmberAdapter = self.module("src/ui/EmberAdapter.luau")
        deps.JobsTab = self.module("src/tabs/jobs/Module.luau")
        deps.AutomationRuntime = runtime
        app = self.module("src/App.luau").start(deps)
        self.assertIn("Runtime connected", app.ui.window.options.StatusBar.Text)
        app.Set(app, "jobs.policy", "Selected job")
        app.Set(app, "jobs.custom.selectedJobId", "j_tag")
        app.Set(app, "jobs.enabled", True)
        app.Resume(app)
        app.Step(app, self.table({}))
        self.assertEqual(runtime.received.jobs.selectedJobId, "j_tag")
        app.Destroy(app)

    def test_loaded_runtime_module_does_not_activate_itself(self):
        deps = self.table({})
        deps.Ember = self.module("tests/ember_double.lua")()
        deps.Catalog = self.module("src/ui/Catalog.luau")
        deps.Settings = self.module("src/storage/Settings.luau")
        deps.EmberAdapter = self.module("src/ui/EmberAdapter.luau")
        deps.AutomationRuntime = self.module(
            "src/engine/AutomationRuntime.luau")
        deps.ProfileStore = self.module(
            "src/storage/ProfileStore.luau")
        app = self.module("src/App.luau").start(deps)
        self.assertIsNone(app.automationRuntime)
        self.assertIsNone(app.profileStore)
        self.assertIn("UI only", app.ui.sessionStatus.Get(app.ui.sessionStatus))
        self.assertIn("UI prototype only", app.ui.window.options.StatusBar.Text)
        app.Destroy(app)

    def test_explicit_runtime_activation_fails_before_ui_if_assembly_is_incomplete(self):
        ember = self.module("tests/ember_double.lua")()
        deps = self.table({"Ember": ember, "activateAutomation": True})
        deps.Catalog = self.module("src/ui/Catalog.luau")
        deps.Settings = self.module("src/storage/Settings.luau")
        deps.EmberAdapter = self.module("src/ui/EmberAdapter.luau")
        deps.AutomationRuntime = self.module(
            "src/engine/AutomationRuntime.luau")
        deps.RuntimeAssembly = self.module(
            "src/engine/RuntimeAssembly.luau")
        with self.assertRaisesRegex(Exception, "Missing runtime composition modules"):
            self.module("src/App.luau").start(deps)
        self.assertEqual(len(ember.windows), 0)

    def test_storage_requires_explicit_activation_and_complete_adapter(self):
        ember = self.module("tests/ember_double.lua")()
        deps = self.table({"Ember": ember, "activateStorage": True,
                           "identity": {"account": "self", "place": "idle-mafia"}})
        deps.Catalog = self.module("src/ui/Catalog.luau")
        deps.Settings = self.module("src/storage/Settings.luau")
        deps.EmberAdapter = self.module("src/ui/EmberAdapter.luau")
        deps.ProfileStore = self.module("src/storage/ProfileStore.luau")
        with self.assertRaisesRegex(Exception, "Invalid storage activation"):
            self.module("src/App.luau").start(deps)
        self.assertEqual(len(ember.windows), 0)
        deps.StorageAssembly = self.lua.execute("""return {
            new = function()
                return { ProfileStorage = {
                    Read = function() return nil end,
                    Write = function() return true end,
                }, storage = { strictRecovery = true } }
            end,
        }""")
        app = self.module("src/App.luau").start(deps)
        self.assertIsNotNone(app.profileStore)
        app.Destroy(app)

    def test_operations_controls_are_separate_tab_owned_and_supported(self):
        app, _ = self.app()
        start = app.ui.features["operations"]
        collect = app.ui.features["collect"]
        self.assertTrue(start["tabOwned"])
        self.assertTrue(collect["tabOwned"])
        options = app.ui.handles["operations.policy"].options.Options
        self.assertEqual([options[i] for i in range(1, len(options) + 1)],
                         ["Best chest", "Highest tier"])
        self.assertFalse(app.Set(app, "operations.policy", "Custom")[0])
        self.assertTrue(app.Set(app, "collect.enabled", True)[0])
        self.assertIs(app.model["values"]["operations.enabled"], False)

    def test_favors_ui_is_tab_owned_and_sequence_blocked(self):
        app, _ = self.app()
        row = app.ui.features["favors"]
        self.assertTrue(row["tabOwned"])
        self.assertIn("sequence", row["status"].Get(row["status"]))
        policies = app.ui.handles["favors.policy"].options.Options
        self.assertEqual([policies[i] for i in range(1, len(policies) + 1)],
                         ["Best reward", "Highest tier"])
        self.assertFalse(app.Set(app, "favors.policy", "Custom")[0])

    def test_crew_tab_owns_all_eight_controls(self):
        app, _ = self.app()
        for feature in ("crew", "crewGear", "crewRoll", "crewSort",
                        "crewHeal", "crewTrain", "crewHire", "crewHealItems"):
            self.assertTrue(app.ui.features[feature]["tabOwned"])
        self.assertIn("crewGear.policy", app.ui.handles)
        self.assertIsNone(app.ui.features["crewGear"]["blockedReason"])
        self.assertIn("crewHeal.custom.staminaReserve", app.ui.handles)
        self.assertIn("crewTrain.custom.targetLevel", app.ui.handles)
        self.assertIn("crewHire.custom.cashReserve", app.ui.handles)
        self.assertIn("crewHire.policy", app.ui.handles)
        self.assertIn("crewHealItems.policy", app.ui.handles)
        self.assertIn("crewHealItems.custom.minRemaining", app.ui.handles)
        self.assertIsNone(app.ui.features["crewHire"]["blockedReason"])
        self.assertIsNone(app.ui.features["crewHealItems"]["blockedReason"])
        for feature in ("crewRoll",):
            row = app.ui.features[feature]
            self.assertIn("Unavailable", row["blockedReason"])
            self.assertIn("Blocked", row["status"].Get(row["status"]))

    def test_inventory_tab_owns_controls_and_restorative_limits(self):
        app, _ = self.app()
        for feature in ("restoratives", "chests", "cosmetics"):
            self.assertTrue(app.ui.features[feature]["tabOwned"])
        self.assertIn("restoratives.custom.healthBelow", app.ui.handles)
        self.assertIn("restoratives.custom.custody", app.ui.handles)
        self.assertIn("chests.custom.maxBatch", app.ui.handles)
        self.assertIsNone(app.ui.features["restoratives"]["blockedReason"])
        self.assertIsNone(app.ui.features["chests"]["blockedReason"])
        self.assertIsNone(app.ui.features["cosmetics"]["blockedReason"])
        self.assertIn("cosmetics.policy", app.ui.handles)

    def test_collection_tab_owns_surplus_and_spare_controls(self):
        app, _ = self.app()
        self.assertTrue(app.ui.features["collectionDonate"]["tabOwned"])
        self.assertIn("collectionDonate.custom.maxBatch", app.ui.handles)
        self.assertIn("collectionDonate.custom.sparesToKeep",
                      app.ui.handles)

    def test_money_tab_owns_both_cash_controls(self):
        app, _ = self.app()
        for feature in ("bank", "withdraw"):
            self.assertTrue(app.ui.features[feature]["tabOwned"])
        self.assertIn("bank.custom.cashToKeep", app.ui.handles)
        self.assertIn("withdraw.custom.maxWithdrawal", app.ui.handles)

    def test_property_tab_owns_build_goal_and_limits(self):
        app, _ = self.app()
        self.assertTrue(app.ui.features["properties"]["tabOwned"])
        self.assertIn("properties.policy", app.ui.handles)
        self.assertIn("properties.custom.cashReserve", app.ui.handles)
        self.assertIn("properties.custom.ownedLimit", app.ui.handles)

    def test_safehouse_tab_owns_tier_and_spending_limits(self):
        app, _ = self.app()
        self.assertTrue(app.ui.features["safehouse"]["tabOwned"])
        self.assertIn("safehouse.custom.maxTier", app.ui.handles)
        self.assertIn("safehouse.custom.maxCost", app.ui.handles)
        self.assertIn("safehouse.custom.cashReserve", app.ui.handles)

    def test_prestige_tab_is_owned_and_blocked(self):
        app, _ = self.app()
        row = app.ui.features["prestige"]
        self.assertTrue(row["tabOwned"])
        self.assertIn("Reset", row["blockedReason"])

    def test_shop_tab_owns_selected_cash_offer_controls(self):
        app, _ = self.app()
        self.assertTrue(app.ui.features["shop"]["tabOwned"])
        self.assertIn("shop.custom.itemId", app.ui.handles)
        self.assertIn("shop.custom.cashReserve", app.ui.handles)
        self.assertFalse(app.model.Set(app.model,
            "shop.custom.itemId", "invalid id")[0])

    def test_black_market_tab_owns_research_payout_and_blocked_trades(self):
        app, _ = self.app()
        for feature in ("marketWatch", "marketManage", "marketSell",
                        "marketFlip", "marketRent"):
            self.assertTrue(app.ui.features[feature]["tabOwned"])
        for feature in ("marketSell", "marketFlip", "marketRent"):
            self.assertIsNotNone(app.ui.features[feature]["blockedReason"])

    def test_family_tab_owns_separate_blocked_spending_controls(self):
        app, _ = self.app()
        for feature in ("familyCash", "familyStamina", "familyGold"):
            self.assertTrue(app.ui.features[feature]["tabOwned"])
            self.assertIn("consent", app.ui.features[feature]["blockedReason"])

    def test_territory_tab_owns_holdings_and_blocked_changes(self):
        app, _ = self.app()
        for feature in ("territoryWatch", "station", "residency"):
            self.assertTrue(app.ui.features[feature]["tabOwned"])
        for feature in ("station", "residency"):
            self.assertIsNotNone(app.ui.features[feature]["blockedReason"])
        self.assertIn("residency.policy", app.ui.handles)

    def test_contracts_tab_owns_claims_and_blocks_goal_borrowing(self):
        app, _ = self.app()
        for feature in ("contracts", "bonuses", "autoContracts"):
            self.assertTrue(app.ui.features[feature]["tabOwned"])
        self.assertIn("borrow", app.ui.features["autoContracts"]
                      ["blockedReason"])

    def test_trophies_tab_owns_claims_and_goal_selection(self):
        app, _ = self.app()
        for feature in ("trophies", "trophyFocus"):
            self.assertTrue(app.ui.features[feature]["tabOwned"])
        self.assertIn("trophyFocus.custom.goalId", app.ui.handles)
        self.assertIsNotNone(app.ui.features["trophyFocus"]
                             ["blockedReason"])

    def test_skills_tab_owns_selected_stat_and_limits(self):
        app, _ = self.app()
        self.assertTrue(app.ui.features["skills"]["tabOwned"])
        for key in ("stat", "maxAllocations", "batchSize"):
            self.assertIn("skills.custom." + key, app.ui.handles)

    def test_rewards_tab_owns_three_claim_controls(self):
        app, _ = self.app()
        for feature in ("playtime", "groupBonus", "monthlyRewards"):
            self.assertTrue(app.ui.features[feature]["tabOwned"])

    def test_events_tab_owns_free_picks_and_blocks_shop(self):
        app, _ = self.app()
        self.assertTrue(app.ui.features["briefcases"]["tabOwned"])
        self.assertTrue(app.ui.features["eventShop"]["tabOwned"])
        self.assertIn("unavailable", app.ui.features["eventShop"]
                      ["blockedReason"])

    def test_profiles_tab_owns_staging_controls(self):
        app, _ = self.app()
        self.assertTrue(app.ui.profiles["tabOwned"])
        self.assertIsNotNone(app.ui.profiles["profileStatus"])
        self.assertEqual(app.ui.profileStatus.Get(app.ui.profileStatus),
                         "None")

    def test_settings_theme_is_tab_owned_and_ignores_startup_or_closed_callbacks(self):
        app, ember = self.app(forceInitial=True)
        self.assertTrue(app.ui.settings["tabOwned"])
        theme = app.ui.settings["theme"]
        self.assertEqual(theme.options.Save, False)
        ember.Flush()
        self.assertIsNone(ember.theme)
        theme.options.Callback("Dark", None, self.table({"initial": True}))
        self.assertIsNone(ember.theme)
        theme.options.Callback("Dark", None, None)
        self.assertEqual(ember.theme, "Dark")
        app.Destroy(app)
        theme.options.Callback("Slate", None, None)
        self.assertEqual(ember.theme, "Dark")

    def test_activity_tab_bounds_local_journal_and_reports_adapter_health(self):
        app, _ = self.app()
        activity = app.ui.activityTab
        self.assertTrue(activity["tabOwned"])
        for number in range(25):
            app.ui.RecordActivity(app.ui, "Local " + str(number))
        snapshot = activity.Snapshot(activity)
        self.assertEqual(len(snapshot["localCommands"]), 20)
        self.assertEqual(snapshot["localCommands"][1], "Local 5")
        self.assertEqual(snapshot["localCommands"][20], "Local 24")
        self.assertEqual(activity.runtimeHealth.Get(activity.runtimeHealth),
                         "Disconnected — UI only")
        activity.Render(activity, self.table({"automationRuntime": {
            "storageFault": True, "uncertainCount": 1}}), None)
        self.assertIn("checkpoint", activity.runtimeHealth.Get(activity.runtimeHealth))
        activity.Render(activity, self.table({"automationRuntime": {
            "storageFault": False, "uncertainCount": 1,
            "recentActions": [{"feature": "jobs", "kind": "skipped_unconfirmed",
                               "duplicateRisk": True}]}}), None)
        self.assertIn("duplicate risk", activity.runtimeHealth.Get(activity.runtimeHealth))
        self.assertIn("jobs — skipped_unconfirmed (duplicate risk)",
                      activity.brokerEvent.Get(activity.brokerEvent))
        self.assertEqual(app.ui.activity.Get(app.ui.activity), "Local 24")

    def test_combat_tab_owns_all_controls_and_blocks_unimplemented_player_fights(self):
        app, _ = self.app()
        for feature in ("combat", "warCombat", "bosses", "bossShop",
                        "familyBossAttacks", "familyBossClaims",
                        "globalBossAttack", "globalBossClaim"):
            self.assertTrue(app.ui.features[feature]["tabOwned"])
        for feature in ("combat", "warCombat"):
            self.assertIn("Unavailable", app.ui.features[feature]["status"].Get(
                app.ui.features[feature]["status"]))
        self.assertIn("bossShop.custom.itemId", app.ui.handles)
        self.assertIn("combat.custom.healthFloor", app.ui.handles)
        app.ui.Render(app.ui, self.table({"values": {
            "combat.enabled": True, "warCombat.enabled": True},
            "paused": False, "stopped": False,
            "automationRuntime": {"availableFeatures": {
                "combat": True, "warCombat": True}}}))
        self.assertIn("Unavailable", app.ui.features["combat"]["status"].Get(
            app.ui.features["combat"]["status"]))

    def test_sidebar_icons_are_distinct_and_from_the_reviewed_catalog(self):
        app, _ = self.app()
        icons = [section.icon for _, section in app.ui.window.sections.items()]
        self.assertEqual(len(icons), len(set(icons)), "Sidebar icons must be distinct")
        self.assertNotIn("house", icons)
        dependency = ROOT / ".private/ember-2026-10-20.lua"
        if dependency.is_file():
            import re
            source = dependency.read_text(encoding="utf-8")
            catalog = source.split("local Icons = {", 1)[1].split("\n}", 1)[0]
            available = set(re.findall(r'\["([\w-]+)"\]\s*=', catalog))
            self.assertTrue(available)
            self.assertTrue(set(icons) <= available, set(icons) - available)

    def test_import_updates_false_silently_and_does_not_release_pause(self):
        app, ember = self.app()
        app.Set(app, "jobs.enabled", True)
        ok, error = app.ApplyProfile(app, self.profile(**{"jobs.enabled": False}))
        self.assertTrue(ok, error)
        self.assertIs(app.ui.handles["jobs.enabled"].Get(app.ui.handles["jobs.enabled"]), False)
        self.assertEqual(len(ember.queue), 0)
        self.assertTrue(app.model.paused)

    def test_refused_import_rolls_back_ui_and_model(self):
        app, _ = self.app()
        app.ui.handles["jobs.policy"].reject = "XP"
        ok, error = app.ApplyProfile(app, self.profile(**{"jobs.enabled": True, "jobs.policy": "XP"}))
        self.assertFalse(ok)
        self.assertIn("refused", error)
        self.assertIs(app.model["values"]["jobs.enabled"], False)
        self.assertIs(app.ui.handles["jobs.enabled"].Get(app.ui.handles["jobs.enabled"]), False)

    def test_queued_toggle_cannot_revive_after_stop_or_unload(self):
        app, ember = self.app()
        handle = app.ui.handles["jobs.enabled"]
        handle.Set(handle, True)
        app.Stop(app)
        ember.Flush(True)
        self.assertIs(app.model["values"]["jobs.enabled"], False)
        self.assertTrue(app.model.stopped)
        handle.Set(handle, True)
        app.Destroy(app)
        ember.Flush()
        self.assertFalse(app.alive)
        self.assertIs(app.model["values"]["jobs.enabled"], False)

    def test_delayed_callbacks_use_current_values(self):
        app, ember = self.app()
        handle = app.ui.handles["jobs.enabled"]
        handle.Set(handle, True)
        handle.Set(handle, False)
        ember.Flush(True)
        self.assertIs(app.model["values"]["jobs.enabled"], False)

    def test_custom_input_validation_and_visibility(self):
        app, ember = self.app()
        app.Set(app, "combat.policy", "Custom")
        self.assertTrue(app.ui.features.combat.custom.visible)
        handle = app.ui.handles["combat.custom.healthFloor"]
        handle.Set(handle, "101")
        ember.Flush()
        self.assertEqual(app.model["values"]["combat.custom.healthFloor"], 50)
        self.assertEqual(handle.Get(handle), "50")
        handle.Set(handle, "65")
        ember.Flush()
        self.assertEqual(app.model["values"]["combat.custom.healthFloor"], 65)
        app.Set(app, "combat.policy", "Cautious")
        self.assertFalse(app.ui.features.combat.custom.visible)

    def test_recreate_and_constructor_failure_clean_up(self):
        app, ember = self.app()
        deps = self.table({"Ember": ember,
                           "Catalog": self.module("src/ui/Catalog.luau"),
                           "Settings": self.module("src/storage/Settings.luau"),
                           "EmberAdapter": self.module("src/ui/EmberAdapter.luau")})
        second = self.module("src/App.luau").start(deps)
        self.assertFalse(app.alive)
        self.assertTrue(second.alive)
        ember.failLabel = "Allow Do Jobs"
        with self.assertRaisesRegex(Exception, "construction failed"):
            self.module("src/App.luau").start(deps)
        self.assertFalse(second.alive)
        self.assertTrue(ember.windows[3].destroyed)

    def test_ui_constructor_failure_closes_attached_runtime(self):
        ember = self.module("tests/ember_double.lua")()
        ember.failLabel = "Allow Do Jobs"
        runtime = self.lua.execute("""return { closed = false,
            Status = function() return { state = 'paused' } end,
            Step = function() end,
            Pause = function() end, Resume = function() end,
            Stop = function() end,
            Close = function(self) self.closed = true end,
        }""")
        deps = self.table({"Ember": ember})
        deps.Catalog = self.module("src/ui/Catalog.luau")
        deps.Settings = self.module("src/storage/Settings.luau")
        deps.EmberAdapter = self.module("src/ui/EmberAdapter.luau")
        deps.automationRuntimeInstance = runtime
        with self.assertRaisesRegex(Exception, "construction failed"):
            self.module("src/App.luau").start(deps)
        self.assertTrue(runtime.closed)
        self.assertTrue(ember.windows[1].destroyed)

    def test_missing_input_is_rejected_without_losing_the_previous_value(self):
        app, ember = self.app()
        handle = app.ui.handles["combat.custom.healthFloor"]
        handle.Set(handle, "not a number")
        ember.Flush()
        self.assertIn("Invalid", app.ui.lastError)
        self.assertEqual(app.model["values"]["combat.custom.healthFloor"], 50)
        self.assertEqual(handle.Get(handle), "50")
        ok, reason = app.Set(app, "jobs.enabled", None)
        self.assertFalse(ok)
        self.assertTrue(reason)

    def test_status_failure_does_not_commit_profile(self):
        app, _ = self.app()
        app.ui.sessionStatus.throwNext = True
        ok, reason = app.ApplyProfile(app, self.profile(**{"jobs.enabled": True}))
        self.assertFalse(ok)
        self.assertTrue(reason)
        self.assertIs(app.model["values"]["jobs.enabled"], False)
        self.assertIs(app.ui.handles["jobs.enabled"].Get(app.ui.handles["jobs.enabled"]), False)
        self.assertTrue(app.model.paused)

    def test_initial_activity_render_failure_destroys_window(self):
        app, ember = self.app()
        deps = self.table({"Ember": ember,
                           "Catalog": self.module("src/ui/Catalog.luau"),
                           "Settings": self.module("src/storage/Settings.luau"),
                           "EmberAdapter": self.module("src/ui/EmberAdapter.luau")})
        ember.throwSetLabel = "Latest local command"
        with self.assertRaisesRegex(Exception, "setter failed"):
            self.module("src/App.luau").start(deps)
        self.assertTrue(ember.windows[2].destroyed)

    def test_failed_rollback_freezes_editing(self):
        app, _ = self.app()
        app.ui.handles["jobs.enabled"].reject = False
        app.ui.handles["jobs.policy"].reject = "XP"
        ok, reason = app.ApplyProfile(app, self.profile(**{"jobs.enabled": True, "jobs.policy": "XP"}))
        self.assertFalse(ok)
        self.assertIn("rollback failed", reason)
        self.assertTrue(app.ui.degraded)
        self.assertTrue(app.ui.handles["jobs.enabled"].disabled)
        self.assertIs(app.model["values"]["jobs.enabled"], False)
        self.assertTrue(app.model.paused)

    def test_startup_callbacks_do_not_hydrate_or_resume(self):
        app, ember = self.app(forceInitial=True)
        ember.Flush(True)
        self.assertTrue(app.alive)
        self.assertTrue(app.model.paused)
        self.assertIs(app.model["values"]["jobs.enabled"], False)
        self.assertIsNone(app.staged)

    def test_closed_session_commands_cannot_change_the_model(self):
        app, _ = self.app()
        app.Destroy(app)
        for name in ("Resume", "Pause", "Stop"):
            ok, reason = app[name](app)
            self.assertFalse(ok)
            self.assertIn("closed", reason)
            self.assertTrue(app.model.paused)
            self.assertTrue(app.model.stopped)


class BuilderTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location("ui_builder", ROOT / "tools/build_ui_prototype.py")
        self.builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.builder)

    def test_generated_catalog_is_current(self):
        self.assertEqual((ROOT / "src/ui/Catalog.luau").read_text(encoding="utf-8"),
                         self.builder.catalog_source())

    def test_unreviewed_ember_bytes_are_refused(self):
        with self.assertRaisesRegex(ValueError, "fingerprint"):
            self.builder.prototype_source(b"return {} -- changed dependency")

    def test_embedded_modules_compile_before_any_module_executes(self):
        runtime = LuaRuntime(unpack_returned_tuples=True)
        runtime.execute("getfenv = function() return _G end; loadstring = load; executed = 0")
        source = self.builder.assemble_modules([
            ("Ember", "executed = executed + 1; return {}"),
            ("App", "this is invalid Lua"),
        ])
        with self.assertRaisesRegex(Exception, "App"):
            runtime.execute(source)
        self.assertEqual(runtime.globals().executed, 0)

    def test_embedded_module_boundaries_and_source_delimiters(self):
        runtime = LuaRuntime(unpack_returned_tuples=True)
        runtime.execute("getfenv = function() return _G end; loadstring = load; executed = 0")
        source = self.builder.assemble_modules([
            ("Ember", "local payload = [==[quotes: ]] ]=] ]===] ' \"]=] \" ]==]; "
                       "executed = executed + 1; return { marker = payload }"),
            ("App", "return { start = function(deps) return deps.Ember.marker end }"),
        ])
        self.assertIn("quotes:", runtime.execute(source))
        self.assertEqual(runtime.globals().executed, 1)

    def test_missing_source_compiler_and_invalid_exports_stop_startup(self):
        source = self.builder.assemble_modules([("Ember", "return nil")])
        runtime = LuaRuntime(unpack_returned_tuples=True)
        runtime.execute("getfenv = function() return _G end")
        with self.assertRaisesRegex(Exception, "loadstring"):
            runtime.execute(source)
        runtime.execute("loadstring = load")
        with self.assertRaisesRegex(Exception, "Ember"):
            runtime.execute(source)

    def test_source_without_final_newline_cannot_overlap_its_closing_delimiter(self):
        runtime = LuaRuntime(unpack_returned_tuples=True)
        runtime.execute("getfenv = function() return _G end; loadstring = load")
        for suffix in ("]", "]]=", "]]]=="):
            source = self.builder.assemble_modules([
                ("Ember", "return { value = 7 } -- suffix " + suffix),
                ("App", "return { start = function(deps) return deps.Ember.value end }"),
            ])
            self.assertEqual(runtime.execute(source), 7)


class LuauAnalysisTests(unittest.TestCase):
    def test_app_and_wrapper_types_check_in_both_solver_generations(self):
        analyzer = (os.environ.get("LUAU_ANALYZE") or shutil.which("luau-analyze")
                    or str(ROOT / ".private/luau-compiler/luau-analyze.exe"))
        if not Path(analyzer).is_file():
            self.skipTest("Set LUAU_ANALYZE to the official Luau analyzer")
        spec = importlib.util.spec_from_file_location("ui_builder", ROOT / "tools/build_ui_prototype.py")
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
        with tempfile.TemporaryDirectory() as directory:
            wrapper = Path(directory) / "wrapper.luau"
            wrapper.write_text(builder.assemble_modules([
                ("App", "return { start = function() return {} end }"),
            ]), encoding="utf-8")
            for solver in ("old", "new"):
                for path in (ROOT / "src/App.luau", wrapper):
                    with self.subTest(solver=solver, path=path.name):
                        result = subprocess.run([analyzer, "--solver=" + solver, str(path)],
                                                capture_output=True, text=True)
                        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
