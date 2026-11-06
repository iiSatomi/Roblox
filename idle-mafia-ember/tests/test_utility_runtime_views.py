"""Utility tabs expose bounded runtime facts without leaking request identifiers."""
import unittest

from engine_harness import Harness, lua_table


class UtilityRuntimeViewTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.ember = self.h.load("tests/ember_double.lua")()
        self.window = self.ember.new(lua_table(self.h.lua, {"Name": "utilities"}))

    def section(self, name):
        return self.window.Section(self.window, name)

    def test_overview_reports_active_feature_blockers_and_uncertainty_separately(self):
        tab = self.h.load("src/tabs/overview/Module.luau").new(self.section("Overview"),
            lua_table(self.h.lua, {"runtimeConnected": True, "command": self.h.lua.eval("function() end")}),
            self.h.lua.eval("function() return true end"))
        tab.Render(tab, lua_table(self.h.lua, {"values": {"jobs.enabled": True,
            "shop.enabled": True}, "paused": False, "automationRuntime": {
                "active": {"feature": "jobs", "phase": "sent", "actionKey": "secret"},
                "uncertainCount": 2, "uncertainByFeature": {"shop": 2},
                "availableFeatures": {"jobs": True}, "reasons": {"shop": "Quote expired"}}}))
        self.assertIn("jobs", tab.actionStatus.value)
        self.assertIn("sent", tab.actionStatus.value)
        self.assertIn("Quote expired", tab.blockerStatus.value)
        self.assertIn("2", tab.exposureStatus.value)
        self.assertIn("shop", tab.exposureStatus.value)
        self.assertIn("1", tab.availabilityStatus.value)
        self.assertNotIn("secret", tab.actionStatus.value)
        tab.Render(tab, lua_table(self.h.lua, {"values": {}, "paused": True}))
        self.assertIn("Disconnected", tab.actionStatus.value)
        self.assertIn("Unavailable", tab.exposureStatus.value)

    def test_activity_retains_bounded_public_history_and_explains_outcomes(self):
        tab = self.h.load("src/tabs/activity/Module.luau").new(self.section("Activity"))
        rows = [{"kind": "sent", "feature": "jobs", "actionKey": "private",
                 "token": "secret", "reason": "Bearer credential"} for _ in range(25)]
        rows[-1] = {"kind": "skipped_unconfirmed", "feature": "shop", "duplicateRisk": True}
        tab.Render(tab, lua_table(self.h.lua, {"automationRuntime": {"recentActions": rows}}), None)
        snapshot = tab.Snapshot(tab)
        self.assertEqual(len(snapshot.gameplayEvents), 10)
        self.assertIn("unconfirmed", snapshot.gameplayEvents[10])
        self.assertIn("duplicate risk", snapshot.gameplayEvents[10])
        self.assertNotIn("credential", " ".join(snapshot.gameplayEvents.values()))
        self.assertNotIn("secret", " ".join(snapshot.gameplayEvents.values()))
        self.assertIn("shop", tab.history[5].value)
        tab.Render(tab, lua_table(self.h.lua, {"automationRuntime": {"recentActions": [
            {"kind": "confirmed", "feature": "jobs"}]}}), None)
        self.assertEqual(len(tab.Snapshot(tab).gameplayEvents), 1)
        self.assertIn("replicated state", tab.history[1].value)
        self.assertEqual(tab.history[5].value, "—")
        tab.Render(tab, lua_table(self.h.lua, {'automationRuntime': {'recentActions': [
            {'kind': 'reconciled_saved','feature': 'crewRoll'}]}}), None)
        self.assertIn('saved outcome observed',tab.history[1].value)
        self.assertNotIn('confirmed by',tab.history[1].value)


if __name__ == "__main__":
    unittest.main()
