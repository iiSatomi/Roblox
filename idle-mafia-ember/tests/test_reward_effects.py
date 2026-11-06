"""Saved reward definitions need exact marker plus observable configured effect."""
from datetime import datetime, timezone
import unittest

import test_rewards_tab as rewards_fixture
from engine_harness import Harness, lua_table


NOW = int(datetime(2026, 10, 21, 12, tzinfo=timezone.utc).timestamp())
DAY = 2026294


class RewardEffectsTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.config = lua_table(self.h.lua, {"LADDER": rewards_fixture.RUNGS,
            "LADDER_TIERS": [1, 10, 30, 102], "GROUP": {"id": 674050067, "incomeBonus": 0.1},
            "LADDER_MYSTERY": {"pool": [{"item": "crate_loot", "weight": 1, "maxLevel": 29},
                {"item": "crate_rare", "weight": 1, "minLevel": 30}],
                "robux": {"crates": [{"item": "crate_premium", "weight": 1}]}},
            "MONTHLY_CALENDAR": {"enabled": True, "default": {"kind": "gold", "amount": 1}, "days": {}}})
        self.source = self.h.load("src/tabs/rewards/NativeRewardsCatalog.luau").new(self.config, "a" * 64, "release-a")
        self.module = self.h.load("src/tabs/rewards/RewardEffects.luau")
        self.playtime = self.module.new(self.source, self.h.load("src/features/PlaytimeEvidence.luau"), "playtime")
        self.monthly = self.module.new(self.source, self.h.load("src/features/MonthlyRewardsEvidence.luau"), "monthlyRewards")

    def raw(self, revision=1, index=None, weekend=False, level=1):
        raw = self.h.snapshot(revision=revision, native={"fullSync": True, "serverNow": NOW + revision,
            "level": level, "maxLevel": level, "cash": 1000, "inventory": {}, "inventoryBound": {},
            "pools": {"energy": 20, "stamina": 20}, "stats": {"maxStamina": 60},
            "derived": {"effMaxEnergy": 40}, "playtime": {"todaySeconds": 20000,
                "laddersClaimed": {str(index): 1} if index else {}}},
            weekendBuff={"active": weekend, "day": DAY})
        return self.source.Enrich(self.source, raw)[0]

    def proposal(self, before, index, lane="playtime"):
        proposal = self.h.proposal(lane, f"{lane}:test:{index}", revision=before.revision)
        proposal.resources = lua_table(self.h.lua, {})
        proposal.intent = lua_table(self.h.lua, {"kind": "playtimeClaim", "index": index, "day": DAY,
                "catalogKey": "a" * 64} if lane == "playtime" else {
                "kind": "monthlyClaim", "month": "2026-10", "today": DAY, "nextDay": index})
        return proposal

    def outcome(self, index, before, after, reply=None, lane="playtime"):
        evidence = self.playtime if lane == "playtime" else self.monthly
        proposal = self.proposal(before, index, lane)
        baseline, reason = evidence.capture(proposal, before)
        self.assertIsNone(reason)
        return evidence.evaluate(proposal, before, after,
            lua_table(self.h.lua, reply or {"ok": True}), baseline)

    def test_item_award_needs_count_and_exact_claim_tier(self):
        before, after = self.raw(), self.raw(2, 3)
        self.assertEqual(self.outcome(3, before, after), "pending")
        after.native.inventoryBound.crate_loot = 1
        self.assertEqual(self.outcome(3, before, after), "confirmed")
        after.native.playtime.laddersClaimed["3"] = 4
        self.assertEqual(self.outcome(3, before, after), "pending")

    def test_explicit_bound_award_cannot_be_satisfied_by_loose_item(self):
        before, after = self.raw(), self.raw(2, 7)
        after.native.inventory.crate_consumables_bound = 1
        self.assertEqual(self.outcome(7, before, after), "pending")
        after.native.inventory.crate_consumables_bound = 0
        after.native.inventoryBound.crate_consumables_bound = 1
        self.assertEqual(self.outcome(7, before, after), "confirmed")

    def test_weekend_gold_uses_source_quantity_and_no_invented_origin(self):
        before, after = self.raw(weekend=True), self.raw(2, 5, weekend=True)
        after.native.inventory.gold_bar, after.native.inventoryBound.gold_bar = 2, 1
        self.assertEqual(self.outcome(5, before, after), "confirmed")
        after.native.inventoryBound.gold_bar = 0
        self.assertEqual(self.outcome(5, before, after), "pending")

    def test_refill_requires_current_capacity_and_configured_pool(self):
        before, after = self.raw(), self.raw(2, 2)
        self.assertEqual(self.outcome(2, before, after), "pending")
        after.native.pools.energy = 40
        self.assertEqual(self.outcome(2, before, after), "confirmed")
        after.native.derived.effMaxEnergy = 50
        after.native.pools.energy = 50
        self.assertEqual(self.outcome(2, before, after), "pending")

    def test_fresh_xp_boost_uses_exact_grant_window_and_active_claim_is_available(self):
        before, after = self.raw(), self.raw(2, 5)
        after.native.xpBoostEnd = NOW + 1802
        self.assertEqual(self.outcome(5, before, after), "confirmed")
        after.native.xpBoostEnd = NOW + 3600
        self.assertEqual(self.outcome(5, before, after), "pending")
        before.native.xpBoostEnd = NOW + 60
        self.assertTrue(self.playtime.Supports(self.playtime, before, 5)[0])

    def test_mystery_reply_must_name_an_eligible_source_item_and_real_acquisition(self):
        before, after = self.raw(), self.raw(2, 6)
        after.native.inventory.crate_loot = 1
        self.assertEqual(self.outcome(6, before, after), "pending")
        self.assertEqual(self.outcome(6, before, after, {"ok": True, "mystery": "crate_loot"}), "confirmed")
        self.assertEqual(self.outcome(6, before, after, {"ok": True, "mystery": "crate_rare"}), "pending")

    def test_flat_cash_has_exact_effect_and_income_claim_has_no_invented_amount(self):
        before, after = self.raw(), self.raw(2, 1)
        after.native.cash = 11000
        self.assertEqual(self.outcome(1, before, after), "confirmed")
        income = self.raw(level=30)
        self.assertTrue(self.playtime.Supports(self.playtime, income, 1)[0])
        spec = self.source.RewardSpec(self.source, income, "playtime", 1)[0]
        self.assertEqual(spec.kind, "incomeCash")
        self.assertIsNone(spec.amount)

    def test_exact_large_wallet_addition_confirms_and_one_cash_mismatch_stays_pending(self):
        before, after = self.raw(), self.raw(2, 1)
        before.native.cash = 2**40 - 0.1
        after.native.cash = before.native.cash + 10000
        self.assertNotEqual(after.native.cash - before.native.cash, 10000)
        self.assertEqual(self.outcome(1, before, after), "confirmed")
        after.native.cash += 1
        self.assertEqual(self.outcome(1, before, after), "pending")

    def test_large_wallet_saved_reward_uses_exact_addition_after_reload(self):
        before, after = self.raw(), self.raw(2, 1)
        before.native.cash = 2**40 - 0.1
        after.native.cash = before.native.cash + 10000
        proposal = self.proposal(before, 1)
        baseline = self.playtime.capture(proposal, before)[0]
        after.session, after.revision = "reloaded", 0
        data = lua_table(self.h.lua, {"proposal": proposal, "before": before,
            "baseline": baseline, "reply": {"ok": True}})
        self.assertEqual(self.playtime.recoverSaved(data, after), "confirmed")
        after.native.cash += 1
        self.assertIsNone(self.playtime.recoverSaved(data, after))

    def test_actual_app_accepts_exact_cash_update_across_float_precision_boundary(self):
        import test_group_income_effect as app_fixture
        base = app_fixture.GroupIncomeEffectTests()
        base.setUp()
        h = base.h
        spec = next(row for row in base.tab.Descriptors(base.tab).values() if row.id == "playtime")
        executor = h.lua.execute("""return {calls={},Schedule=function(s,fn)fn();return true end,
            Invoke=function(s,remote,method,...)s.calls[#s.calls+1]={remote=remote};return {ok=true}end}""")
        adapter = h.load("src/transport/NativeDispatchAdapter.luau").new(
            h.load("src/transport/NativeCallPlan.luau"), executor)
        runtime = h.load("src/engine/AutomationRuntime.luau").new(lua_table(h.lua, {
            "clock": h.clock, "transport": adapter, "storage": base.base.storage,
            "identity": h.session, "modules": base.base.runtime.modules, "features": [spec]}))
        app = h.load("src/App.luau").start(lua_table(h.lua, {
            "Ember": h.load("tests/ember_double.lua")(), "Catalog": h.load("src/ui/Catalog.luau"),
            "Settings": h.load("src/storage/Settings.luau"),
            "EmberAdapter": h.load("src/ui/EmberAdapter.luau"), "automationRuntimeInstance": runtime}))
        def raw(revision, claimed=False):
            value = base.raw(revision)
            value.native.level, value.native.maxLevel = 1, 1
            value.native.playtime.laddersClaimed = lua_table(h.lua, {"1": 1} if claimed else {})
            value.native.cash = (2**40 - 0.1) + (10000 if claimed else 0)
            return value
        try:
            self.assertTrue(app.Set(app, "playtime.enabled", True)[0])
            app.Resume(app)
            app.Step(app, raw(1))
            self.assertEqual(len(executor.calls), 1)
            self.assertEqual(executor.calls[1].remote, "ClaimLadder")
            self.assertTrue(app.Set(app, "playtime.enabled", False)[0])
            h.at(1)
            app.Step(app, raw(2, True))
            self.assertEqual(runtime.Status(runtime).outcomes.playtime, "confirmed")
            self.assertEqual(len(runtime.checkpoint.Records(runtime.checkpoint)), 0)
            self.assertEqual(len(executor.calls), 1)
        finally:
            app.Destroy(app)

    def test_monthly_native_default_and_pending_reply(self):
        before, after = self.raw(), self.raw(2)
        after.native.monthly = lua_table(self.h.lua, {"month": "2026-10", "claimed": 1, "lastDay": DAY})
        after.native.inventoryBound.gold_bar = 1
        self.assertEqual(self.outcome(1, before, after, lane="monthlyRewards"), "confirmed")
        for reply in ({"ok": True, "pending": True}, {"ok": True, "code": "rate_limited"}):
            self.assertEqual(self.outcome(1, before, after, reply, "monthlyRewards"), "pending")

    def test_source_copy_and_newer_spec_must_match_capture(self):
        before, after = self.raw(), self.raw(2, 3)
        self.config.LADDER[3].crate = "crate_other"
        after.native.inventory.crate_loot = 1
        self.assertEqual(self.outcome(3, before, after), "confirmed")
        after.native.maxLevel = 30
        self.assertEqual(self.outcome(3, before, after), "pending")

    def test_negative_reply_cannot_clear_changed_effect_and_positive_pending_is_held(self):
        before, after = self.raw(), self.raw(2)
        for reply in ({"ok": True, "pending": True}, {"ok": True, "code": "rate_limited"}):
            after.native.playtime.laddersClaimed["3"] = 1
            after.native.inventory.crate_loot = 1
            self.assertEqual(self.outcome(3, before, after, reply), "pending")
        after.native.playtime.laddersClaimed["3"] = None
        self.assertEqual(self.outcome(3, before, after, {"ok": False}), "pending")
        after.native.inventory.crate_loot = 0
        self.assertEqual(self.outcome(3, before, after, {"ok": False}), "rejected")

    def test_saved_cross_session_revision_restart_keeps_exact_effect_proof(self):
        before,after=self.raw(),self.raw(2,3)
        proposal=self.proposal(before,3)
        baseline=self.playtime.capture(proposal,before)[0]
        after.native.inventoryBound.crate_loot=1
        after.session="reloaded";after.revision=0
        data=lua_table(self.h.lua,{"proposal":proposal,"before":before,"baseline":baseline,"reply":{"ok":True}})
        self.assertEqual(self.playtime.recoverSaved(data,after),"confirmed")
    def test_saved_monthly_negative_with_another_claim_marker_stays_uncertain(self):
        before=self.raw();proposal=self.proposal(before,1,"monthlyRewards")
        baseline=self.monthly.capture(proposal,before)[0]
        after=self.raw(2);after.native.monthly=lua_table(self.h.lua,{"month":"2026-10","claimed":2,"lastDay":DAY})
        data=lua_table(self.h.lua,{"proposal":proposal,"before":before,"baseline":baseline,"reply":{"ok":False}})
        self.assertIsNone(self.monthly.recoverSaved(data,after))


if __name__ == "__main__":
    unittest.main()
