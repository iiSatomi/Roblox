"""Group claim activates its source-defined income modifier, not an invented award."""
import unittest

import test_automation_runtime as runtime_fixture
import test_rewards_tab as rewards_fixture
from engine_harness import lua_table


class GroupIncomeEffectTests(unittest.TestCase):
    def setUp(self):
        base = runtime_fixture.AutomationRuntimeTests()
        base.setUp()
        self.h, self.base = base.h, base
        base.runtime.Close(base.runtime)
        self.config = lua_table(self.h.lua, {"LADDER": rewards_fixture.RUNGS,
            "LADDER_TIERS": [1, 10, 30, 102], "GROUP": {"id": 674050067, "incomeBonus": 0.1},
            "MONTHLY_CALENDAR": {"enabled": False}})
        deps = {"NativeRewardsCatalog": self.h.load("src/tabs/rewards/NativeRewardsCatalog.luau"),
            "RewardEffects": self.h.load("src/tabs/rewards/RewardEffects.luau"),
            "rewardsSource": base.rewards_source,
            "config": self.config, "fingerprint": "a" * 64, "release": "release-a"}
        for name, folder in (("PlaytimeState", "game"), ("Playtime", "features"),
                ("PlaytimeEvidence", "features"), ("GroupBonusState", "game"),
                ("GroupBonus", "features"), ("GroupBonusEvidence", "features"),
                ("MonthlyRewardsState", "game"), ("MonthlyRewards", "features"),
                ("MonthlyRewardsEvidence", "features")):
            deps[name] = self.h.load(f"src/{folder}/{name}.luau")
        self.tab = self.h.load("src/tabs/rewards/Module.luau").new(lua_table(self.h.lua, deps))
        self.spec = next(row for row in self.tab.Descriptors(self.tab).values() if row.id == "groupBonus")
        self.reader, self.planner, self.evidence = self.spec.reader, self.spec.planner, self.spec.evidence

    def raw(self, revision=1, claimed=False):
        raw = self.base.raw(revision=revision)
        raw.native.groupBonus = claimed
        raw.groupMembership = lua_table(self.h.lua, {**self.h.session, "groupId": 674050067,
            "isMember": True, "checkedAt": 0})
        return self.tab.Enrich(self.tab, raw)[0]

    def proposed(self):
        raw = self.raw()
        view = self.reader.read(raw, raw)[0]
        proposal = self.planner.propose(view, lua_table(self.h.lua, {"enabled": True}))[0]
        return raw, proposal, self.evidence.capture(proposal, raw)[0]

    def test_source_pins_income_bonus_and_reported_multiplier(self):
        before = self.raw()
        effect, reason = self.tab.GroupEffect(self.tab, before)
        self.assertIsNone(reason)
        self.assertEqual((effect.kind, effect.incomeBonus, effect.multiplier), ("propertyIncome", 0.1, 1))
        self.config.GROUP.incomeBonus = 0.9
        after = self.raw(2, True)
        self.assertEqual(self.tab.GroupEffect(self.tab, after)[0].multiplier, 1.1)
        after.groupConfig.incomeBonus = 0.9
        self.assertIsNone(self.tab.GroupEffect(self.tab, after)[0])

    def test_positive_claim_flag_confirms_effect_without_any_cash_award(self):
        before, proposal, baseline = self.proposed()
        self.assertIsNotNone(baseline)
        after = self.raw(2, True)
        self.assertEqual(after.native.cash, before.native.cash)
        self.assertEqual(self.evidence.evaluate(proposal, before, after,
            lua_table(self.h.lua, {"ok": True}), baseline), "confirmed")
        after.groupConfig.incomeBonus = 0.2
        self.assertEqual(self.evidence.evaluate(proposal, before, after,
            lua_table(self.h.lua, {"ok": True}), baseline), "pending")

    def test_pending_or_rate_limited_claim_cannot_use_a_concurrent_marker(self):
        before, proposal, baseline = self.proposed()
        for reply in ({"ok": True, "pending": True}, {"ok": True, "code": "rate_limited"}):
            self.assertEqual(self.evidence.evaluate(proposal, before, self.raw(2, True),
                lua_table(self.h.lua, reply), baseline), "pending")

    def test_app_native_adapter_confirms_current_income_modifier(self):
        executor = self.h.lua.execute("""return {calls={},
            Schedule=function(self,callback) callback(); return true end,
            Invoke=function(self,remote,method,...)
                self.calls[#self.calls+1]={remote=remote,count=select('#',...)}
                return {ok=true}
            end}""")
        adapter = self.h.load("src/transport/NativeDispatchAdapter.luau").new(
            self.h.load("src/transport/NativeCallPlan.luau"), executor)
        runtime = self.h.load("src/engine/AutomationRuntime.luau").new(lua_table(self.h.lua, {
            "clock": self.h.clock, "transport": adapter, "storage": self.base.storage,
            "identity": self.h.session, "modules": self.base.runtime.modules, "features": [self.spec]}))
        app = self.h.load("src/App.luau").start(lua_table(self.h.lua, {
            "Ember": self.h.load("tests/ember_double.lua")(), "Catalog": self.h.load("src/ui/Catalog.luau"),
            "Settings": self.h.load("src/storage/Settings.luau"),
            "EmberAdapter": self.h.load("src/ui/EmberAdapter.luau"), "automationRuntimeInstance": runtime}))
        try:
            self.assertTrue(app.Set(app, "groupBonus.enabled", True)[0])
            app.Resume(app)
            app.Step(app, self.raw())
            self.assertEqual((executor.calls[1].remote, executor.calls[1].count), ("ClaimGroupBonus", 0))
            self.h.at(1)
            app.Step(app, self.raw(2, True))
            self.assertEqual(runtime.Status(runtime).outcomes.groupBonus, "confirmed")
            self.assertEqual(len(executor.calls), 1)
        finally:
            app.Destroy(app)


if __name__ == "__main__":
    unittest.main()
