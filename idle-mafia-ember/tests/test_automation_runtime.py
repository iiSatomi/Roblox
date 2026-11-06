"""One offline broker coordinates Jobs and ordinary Operation actions."""
from datetime import datetime, timezone
import unittest

from engine_harness import Harness, lua_table


class AutomationRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.storage = self.h.lua.execute("""
            return { data = {}, strictRecovery = true,
                Read = function(self, key) return self.data[key] end,
                Write = function(self, key, value) self.data[key] = value; return true end }
        """)
        self.rewards_source = self.h.lua.execute("""return {
            release = 'release-a',
            IsWeekend = function() return false end,
            Membership = function() return true, 0 end,
        }""")
        m = lua_table(self.h.lua, {
            "Contracts": self.h.contracts,
            "Broker": self.h.load("src/engine/Broker.luau"),
            "Journal": self.h.load("src/engine/Journal.luau"),
            "Context": self.h.load("src/game/Context.luau"),
            "EconomyContext": self.h.load("src/game/EconomyContext.luau"),
            "BuffContext": self.h.load("src/game/BuffContext.luau"),
            "HeistBoardState": self.h.load("src/game/HeistBoardState.luau"),
            "BossStageState": self.h.load("src/game/BossStageState.luau"),
            "GlobalBossState": self.h.load("src/game/GlobalBossState.luau"),
            "BossShopState": self.h.load("src/game/BossShopState.luau"),
            "FamilyTakedownState": self.h.load(
                "src/game/FamilyTakedownState.luau"),
            "Scheduler": self.h.load("src/engine/Scheduler.luau"),
            "Session": self.h.load("src/engine/Session.luau"),
            "Checkpoint": self.h.load("src/storage/Checkpoint.luau"),
            "ResourceReservations": self.h.load("src/engine/ResourceReservations.luau"),
            "PendingAction": self.h.load("src/storage/PendingAction.luau"),
            "Chests": self.h.load("src/tabs/inventory/Chests.luau"),
            "EventShopUsage": self.h.load("src/tabs/events/EventShopUsage.luau"),
            "CrewHireUsage": self.h.load("src/tabs/crew/CrewHireUsage.luau"),
            "AllowanceReset": self.h.load("src/engine/AllowanceReset.luau"),
            "FundingCoordinator": self.h.load("src/engine/FundingCoordinator.luau"),
            "PurchaseSavings": self.h.load("src/engine/PurchaseSavings.luau"),
            "CollectionProtection": self.h.load(
                "src/engine/CollectionProtection.luau"),
            "RewardsProofProducer": self.h.load(
                "src/engine/RewardsProofProducer.luau"),
            "rewardsSource": self.rewards_source,
            "OperationsState": self.h.load("src/game/OperationsState.luau"),
            "OperationsStart": self.h.load("src/features/OperationsStart.luau"),
            "SafehouseState": self.h.load("src/game/SafehouseState.luau"),
            "SafehouseUpgrades": self.h.load("src/features/SafehouseUpgrades.luau"),
        })
        registry = self.h.load("src/engine/FeatureRegistry.luau")
        exports = {}
        for row in registry.requirements().values():
            exports[row["reader"]] = self.h.load(
                "src/game/" + row["reader"] + ".luau")
            exports[row["planner"]] = self.h.load(
                "src/features/" + row["planner"] + ".luau")
            exports[row["evidence"]] = self.h.load(
                "src/features/" + row["evidence"] + ".luau")
        specs, reason = registry.build(lua_table(self.h.lua, exports),
            self.h.load("src/ui/Catalog.luau"))
        self.assertIsNone(reason)
        self.runtime = self.h.load("src/engine/AutomationRuntime.luau").new(
            lua_table(self.h.lua, {
                "clock": self.h.clock, "transport": self.h.transport,
                "storage": self.storage, "identity": self.h.session,
                "modules": m, "features": specs,
            }))

    def raw(self, revision=1, active=None, completions=0,
            operation_catalog=None):
        return self.h.snapshot(
            revision=revision, native={
                "fullSync": True, "cityId": "city-a",
                "level": 15, "maxLevel": 15,
                "respect": 100, "cash": 1000, "banked": 100,
                "safehouse": 3,
                "pools": {"energy": 5},
                "skillPoints": 4, "allocs": {"energy": 0},
                "groupBonus": False,
                "serverNow": int(datetime(2026, 10, 20, 12,
                           tzinfo=timezone.utc).timestamp()),
                "playtime": {"todaySeconds": 5400,
                             "laddersClaimed": {"1": 4, "2": 4,
                                                "3": 4, "4": 4}},
                "jobs": {"j_watch": {"completions": completions}},
                "derived": {"autoJobs": False, "fourthSlot": False,
                            "noBankFees": False,
                            "trophyReady": ["t_eldersignet"]},
                "inventory": {}, "inventoryBound": {},
                "collection": {}, "collectionBound": {},
                "contracts": {"daily": [
                    {"id": "c_rounds", "done": True, "claimed": False},
                    {"id": "c_cash", "done": False, "claimed": False},
                    {"id": "c_hire", "done": False, "claimed": False},
                    {"id": "c_jobs", "done": False, "claimed": False},
                    {"id": "c_boss", "done": False, "claimed": False}],
                    "weekly": [{"id": "w_" + str(i), "done": False,
                                "claimed": False} for i in range(1, 6)],
                    "bonusClaimed": False, "weeklyBonusClaimed": False},
                "briefcase": {"season": 7, "free": 2,
                              "board": {"n": 3, "cfg": 0,
                                        "opened": {"c1": {"p": "cash2"}}}},
                "operations": {"active": active if active is not None else [
                    {"opId": "op_fence", "remaining": 0, "slot": 1},
                ]}},
            catalogKey="build-1",
            jobCatalog=[{"id": "j_watch", "level": 1, "energy": 1,
                         "cash": 60, "xp": 2}],
            masteryRules=[{"completions": 25, "energyDiscount": 0}],
            skillRules={"energy": {"baseCost": 1, "costEvery": 5},
                        "stamina": {"baseCost": 1, "costEvery": 5},
                        "health": {"baseCost": 1, "costEvery": 5},
                        "attack": {"baseCost": 1, "costEvery": 3},
                        "defense": {"baseCost": 1, "costEvery": 3},
                        "property": {"baseCost": 1, "costMultiplier": 2}},
            groupConfig={"id": 674050067},
            groupMembership={"groupId": 674050067, "isMember": True,
                             "account": "user-a", "checkedAt": 0},
            monthlyConfig={"enabled": False},
            economyProof={"account": "user-a", "capturedAt": 0,
                          "city": "city-a", "revision": 1,
                          "familyId": "", "rulerId": "",
                          "shopPct": 0, "hirePct": 0,
                          "marketPct": 10,
                          "territoryShopDiscount": 0,
                          "globalShopSale": 0},
            bankConfig={"depositFee": 0.1},
            safehouseCatalog=[{"name": "Tier " + str(i), "level": i,
                               "cost": (i - 1) * 1000}
                              for i in range(1, 19)],
            purchaseSavings={"account": "user-a", "capturedAt": 0,
                             "amount": 0},
            contractConfig={"dailyTiers": [1, 1, 2, 2, 3],
                            "weeklyTiers": [4, 4, 4, 4, 4]},
            contractBonusConfig={"daily": {"seals": 2, "energyRefill": True},
                                 "weekly": {"seals": 12,
                                            "crate": "crate_fixervault"}},
            caseEvent={"season": 7, "endAt": int(datetime(2026, 10, 20, 13,
                          tzinfo=timezone.utc).timestamp())},
            briefcaseRules={"cases": 12, "version": 0},
            trophyCatalog=[{"id": "t_eldersignet", "kind": "trophy"},
                           {"id": "t_grudgeledger", "kind": "trophy"}],
            ladderTiers=[1, 10, 30, 102],
            ladderCatalog=[
                {"seconds": 300, "kind": "cash", "flat": 10000},
                {"seconds": 900, "kind": "energy"},
                {"seconds": 1800, "kind": "crate", "crate": "crate_loot"},
                {"seconds": 3600, "kind": "crate", "crate": "crate_rare"},
                {"seconds": 5400, "kind": "xpboost", "minutes": 30,
                 "weekend": {"kind": "gold", "amount": 3}},
                {"seconds": 7200, "kind": "mystery"},
                {"seconds": 10800, "kind": "crate",
                 "crate": "crate_consumables_bound", "bound": True}],
            weekendBuff={"active": False, "day": 2026293},
            operationCatalog=operation_catalog if operation_catalog is not None else [
                {"id": "op_fence", "duration": 600, "cost": 200,
                 "cash": 1500, "xp": 20}],
        )

    def settings(self, jobs=True, operations=True, collect=True):
        return lua_table(self.h.lua, {
            "jobs": {"enabled": jobs, "policy": "Balanced"},
            "operations": {"enabled": operations, "policy": "Highest tier"},
            "collect": {"enabled": collect},
        })

    def install_native_adapter(self):
        executor = self.h.lua.execute("""return {
            queued = {}, calls = {},
            Schedule = function(self, fn)
                self.queued[#self.queued + 1] = fn
            end,
            Invoke = function(self, remote, method, ...)
                self.calls[#self.calls + 1] = { remote = remote,
                    method = method, arity = select('#', ...),
                    args = table.pack(...) }
                return self.reply or { ok = true }
            end,
            Drain = function(self)
                local pending = self.queued
                self.queued = {}
                for _, fn in ipairs(pending) do fn() end
            end,
        }""")
        adapter = self.h.load("src/transport/NativeDispatchAdapter.luau").new(
            self.h.load("src/transport/NativeCallPlan.luau"), executor)
        self.runtime["session"]["broker"]["transport"] = adapter
        return executor

    def start_test_app(self):
        return self.h.load("src/App.luau").start(lua_table(self.h.lua, {
            "Ember": self.h.load("tests/ember_double.lua")(),
            "Catalog": self.h.load("src/ui/Catalog.luau"),
            "Settings": self.h.load("src/storage/Settings.luau"),
            "EmberAdapter": self.h.load("src/ui/EmberAdapter.luau"),
            "AutomationRuntime": self.runtime,
        }))

    def step(self, raw=None, settings=None):
        return self.runtime.Step(self.runtime, raw or self.raw(),
                                 settings or self.settings())

    def test_one_owner_collect_then_start_then_job(self):
        self.step()
        self.assertEqual(len(self.h.transport["sent"]), 0)
        self.runtime.Resume(self.runtime)
        self.step()
        self.assertEqual(self.h.transport["sent"][1]["feature"], "collect")
        self.h.transport["callbacks"][1](lua_table(self.h.lua, {"ok": True}))
        self.step()
        self.assertEqual(len(self.h.transport["sent"]), 1)
        self.h.at(1)
        self.step(self.raw(2, active=[]))
        self.assertEqual(self.h.transport["sent"][2]["feature"], "operations")
        self.assertEqual(self.runtime.Status(self.runtime)["outcomes"]["collect"],
                         "confirmed")
        self.h.transport["callbacks"][2](lua_table(self.h.lua, {"ok": True}))
        self.h.at(2)
        started = self.raw(3, active=[{"opId": "op_fence", "remaining": 600,
                                       "slot": 1}])
        started["native"]["cash"] = 800
        self.step(started,
                  self.settings(operations=False, collect=False))
        self.assertEqual(self.h.transport["sent"][3]["feature"], "jobs")
        self.assertEqual(self.runtime.Status(self.runtime)["outcomes"]["operations"],
                         "confirmed")

    def test_operations_app_native_collect_replan_start_and_exact_cash(self):
        executor = self.h.lua.execute("""return {
            queued = {}, calls = {},
            Schedule = function(self, fn)
                self.queued[#self.queued + 1] = fn
            end,
            Invoke = function(self, remote, method, ...)
                self.calls[#self.calls + 1] = { remote = remote,
                    method = method, arity = select('#', ...),
                    args = table.pack(...) }
                return { ok = true }
            end,
            Drain = function(self)
                local pending = self.queued
                self.queued = {}
                for _, fn in ipairs(pending) do fn() end
            end,
        }""")
        adapter = self.h.load("src/transport/NativeDispatchAdapter.luau").new(
            self.h.load("src/transport/NativeCallPlan.luau"), executor)
        self.runtime["session"]["broker"]["transport"] = adapter
        ember = self.h.load("tests/ember_double.lua")()
        deps = lua_table(self.h.lua, {
            "Ember": ember, "Catalog": self.h.load("src/ui/Catalog.luau"),
            "Settings": self.h.load("src/storage/Settings.luau"),
            "EmberAdapter": self.h.load("src/ui/EmberAdapter.luau"),
            "AutomationRuntime": self.runtime,
        })
        app = self.h.load("src/App.luau").start(deps)
        app.Set(app, "collect.enabled", True)
        app.Set(app, "operations.enabled", True)
        app.Set(app, "operations.policy", "Highest tier")
        app.Resume(app)
        before = self.raw(active=[
            {"opId": "op_fence", "remaining": 25, "slot": 1},
            {"opId": "op_fence", "remaining": 0, "slot": 3},
        ])
        app.Step(app, before)
        executor.Drain(executor)
        self.assertEqual(executor["calls"][1]["remote"], "CollectOperation")
        self.assertEqual(executor["calls"][1]["method"], "InvokeServer")
        self.assertEqual(executor["calls"][1]["arity"], 1)
        self.assertEqual(executor["calls"][1]["args"][1], 2)
        self.assertEqual(len(list(executor["calls"].values())), 1)
        self.h.at(1)
        collected = self.raw(2, active=[
            {"opId": "op_fence", "remaining": 24, "slot": 1},
        ])
        app.Step(app, collected)
        self.assertEqual(self.runtime.Status(self.runtime)["outcomes"]["collect"],
                         "confirmed")
        executor.Drain(executor)
        self.assertEqual(executor["calls"][2]["remote"], "StartOperation")
        self.assertEqual(executor["calls"][2]["args"][1], "op_fence")
        self.h.at(2)
        started = self.raw(3, active=[
            {"opId": "op_fence", "remaining": 23, "slot": 1},
            {"opId": "op_fence", "remaining": 600, "slot": 3},
        ])
        started["native"]["cash"] = 800
        app.Step(app, started)
        self.assertEqual(self.runtime.Status(self.runtime)["outcomes"]["operations"],
                         "confirmed")
        app.Destroy(app)

    def test_failed_tab_source_blocks_only_its_own_feature(self):
        self.runtime["snapshotAssembler"] = self.h.lua.execute("""return {
            Enrich = function(self, raw)
                return raw, { jobs = 'Jobs source unavailable' }
            end }""")
        self.runtime["featurePages"] = lua_table(self.h.lua, {
            "jobs": "jobs", "collect": "operations",
            "operations": "operations"})
        self.runtime.Resume(self.runtime)
        self.step(settings=self.settings(True, False, False))
        self.assertEqual(len(self.h.transport["sent"]), 0)
        self.assertEqual(self.runtime.Status(self.runtime)["reasons"]["jobs"],
                         "Jobs source unavailable")
        self.step(settings=self.settings(True, False, True))
        self.assertEqual(self.h.transport["sent"][1]["feature"], "collect")

    def test_heist_collect_control_explains_unaddressable_result(self):
        self.runtime.Resume(self.runtime)
        raw = self.raw()
        raw["heistCatalog"] = lua_table(self.h.lua, [{
            "id": "h_a", "level": 1, "stake": 100,
            "energy": 2, "crateCount": 1, "crateChance": 1, "crateRarity": 2, "duration": 600, "cash": 200, "xp": 10, "helpGoal": 3}])
        raw["heistBoardProof"] = lua_table(self.h.lua, {
            "account": "user-a", "capturedAt": 0,
            "board": {"ok": True,
                "serverNow": raw["native"]["serverNow"],
                "rows": [], "result": {"heistId": "h_a",
                    "ok": True, "cash": 1000},
                "startsLeft": 1, "bustWait": 0}})
        settings = self.settings(False, False, False)
        settings["heistCollect"] = lua_table(self.h.lua, {"enabled": True})
        self.step(raw, settings)
        self.assertEqual(len(self.h.transport["sent"]), 0)
        self.assertIn("identity", self.runtime.Status(
            self.runtime)["reasons"]["heistCollect"])

    def test_unconfirmed_collect_releases_broker_but_keeps_exposure(self):
        self.runtime.Resume(self.runtime)
        self.step()
        self.h.at(45)
        self.step(self.raw(), self.settings(operations=False))
        status = self.runtime.Status(self.runtime)
        self.assertEqual(status["outcomes"]["collect"], "skipped_unconfirmed")
        self.assertEqual(status["uncertainCount"], 2)
        self.assertEqual(status["active"]["feature"], "jobs")
        self.assertEqual(self.h.transport["sent"][2]["feature"], "jobs")

    def test_skills_share_broker_and_point_exposure(self):
        self.runtime.Resume(self.runtime)
        settings = self.settings(False, False, False)
        settings["skills"] = lua_table(self.h.lua, {
            "enabled": True, "stat": "energy", "maxAllocations": 2,
            "batchSize": 2})
        self.step(settings=settings)
        proposal = self.h.transport["sent"][1]
        self.assertEqual(proposal["feature"], "skills")
        self.assertEqual(proposal["resources"]["skillPoints"], 2)
        self.h.transport["callbacks"][1](lua_table(self.h.lua, {"ok": True}))
        self.h.at(1)
        after = self.raw(2)
        after["native"]["skillPoints"] = 2
        after["native"]["allocs"]["energy"] = 2
        self.step(after, settings)
        self.assertEqual(self.runtime.Status(self.runtime)["outcomes"]["skills"],
                         "confirmed")
        self.assertEqual(len(self.h.transport["sent"]), 1)

    def test_skills_app_native_batch_confirms_selected_allocation(self):
        executor = self.h.lua.execute("""return {
            queued = {}, calls = {},
            Schedule = function(self, fn)
                self.queued[#self.queued + 1] = fn
            end,
            Invoke = function(self, remote, method, ...)
                self.calls[#self.calls + 1] = { remote = remote,
                    method = method, arity = select('#', ...),
                    args = table.pack(...) }
                return { ok = true }
            end,
            Drain = function(self)
                local pending = self.queued
                self.queued = {}
                for _, fn in ipairs(pending) do fn() end
            end,
        }""")
        adapter = self.h.load("src/transport/NativeDispatchAdapter.luau").new(
            self.h.load("src/transport/NativeCallPlan.luau"), executor)
        self.runtime["session"]["broker"]["transport"] = adapter
        app = self.h.load("src/App.luau").start(lua_table(self.h.lua, {
            "Ember": self.h.load("tests/ember_double.lua")(),
            "Catalog": self.h.load("src/ui/Catalog.luau"),
            "Settings": self.h.load("src/storage/Settings.luau"),
            "EmberAdapter": self.h.load("src/ui/EmberAdapter.luau"),
            "AutomationRuntime": self.runtime,
        }))
        app.Set(app, "skills.enabled", True)
        app.Set(app, "skills.custom.stat", "energy")
        app.Set(app, "skills.custom.maxAllocations", 2)
        app.Set(app, "skills.custom.batchSize", 2)
        app.Resume(app)
        app.Step(app, self.raw())
        executor.Drain(executor)
        self.assertEqual(executor["calls"][1]["remote"], "AllocateSkillPoint")
        self.assertEqual(executor["calls"][1]["method"], "InvokeServer")
        self.assertEqual(executor["calls"][1]["arity"], 2)
        self.assertEqual(executor["calls"][1]["args"][1], "energy")
        self.assertEqual(executor["calls"][1]["args"][2], 2)
        self.h.at(1)
        after = self.raw(2)
        after["native"]["skillPoints"] = 2
        after["native"]["allocs"]["energy"] = 2
        app.Step(app, after)
        self.assertEqual(self.runtime.Status(self.runtime)["outcomes"]["skills"],
                         "confirmed")
        self.h.at(2)
        capped = self.raw(3)
        capped["native"]["skillPoints"] = 2
        capped["native"]["allocs"]["energy"] = 2
        app.Step(app, capped)
        executor.Drain(executor)
        self.assertEqual(len(list(executor["calls"].values())), 1)
        app.Destroy(app)

    def test_boss_shop_send_uses_injected_usage_and_confirms_custody(self):
        self.runtime.Resume(self.runtime)
        settings = self.settings(False, False, False)
        settings["bossShop"] = lua_table(self.h.lua, {
            "enabled": True, "itemId": "crate_loot", "crateQuantity": 1,
            "tokenReserve": 20, "maxSends": 1})
        before = self.raw()
        before["native"]["inventory"] = lua_table(self.h.lua,
            {"boss_token": 50, "crate_loot": 0})
        before["bossShopProof"] = lua_table(self.h.lua, {
            "account": "user-a", "capturedAt": 0,
            "catalogKey": "saved-catalog", "items": [
                {"item": "crate_loot", "kind": "crate",
                 "price": 14, "unlocked": True}]})
        before["bossShopUsageProof"] = lua_table(self.h.lua,
            {"account": "user-a", "session": "run-a",
             "capturedAt": 0, "attempts": 19})
        self.step(before, settings)
        self.assertEqual(self.h.transport["sent"][1]["feature"], "bossShop")
        self.assertEqual(self.h.transport["sent"][1]["resources"]["bossTokens"], 14)
        self.h.transport["callbacks"][1](lua_table(self.h.lua, {"ok": True}))
        self.h.at(1)
        after = self.raw(2)
        after["native"]["inventory"] = lua_table(self.h.lua,
            {"boss_token": 36, "crate_loot": 1})
        after["bossShopProof"] = lua_table(self.h.lua, {
            "account": "user-a", "capturedAt": 1,
            "catalogKey": "saved-catalog", "items": [
                {"item": "crate_loot", "kind": "crate",
                 "price": 14, "unlocked": True}]})
        self.step(after, settings)
        self.assertEqual(self.runtime.Status(self.runtime)["outcomes"]["bossShop"],
                         "confirmed")
        self.assertEqual(len(self.h.transport["sent"]), 1)

    def test_group_claim_is_separate_and_replication_confirmed(self):
        self.runtime.Resume(self.runtime)
        settings = self.settings(False, False, False)
        settings["groupBonus"] = lua_table(self.h.lua, {"enabled": True})
        self.step(settings=settings)
        self.assertEqual(self.h.transport["sent"][1]["feature"], "groupBonus")
        self.h.transport["callbacks"][1](lua_table(self.h.lua, {"ok": True}))
        self.step(settings=settings)
        self.assertEqual(self.runtime.Status(self.runtime)["outcomes"]["groupBonus"],
                         None)
        self.h.at(1)
        after = self.raw(2)
        after["native"]["groupBonus"] = True
        self.step(after, settings)
        self.assertEqual(self.runtime.Status(self.runtime)["outcomes"]["groupBonus"],
                         "confirmed")

    def test_group_claim_needs_membership_without_blocking_jobs(self):
        self.runtime.Resume(self.runtime)
        settings = self.settings(True, False, False)
        settings["groupBonus"] = lua_table(self.h.lua, {"enabled": True})
        raw = self.raw()
        self.rewards_source["Membership"] = self.h.lua.eval(
            "function() return false, 0 end")
        raw["groupMembership"]["isMember"] = True
        self.step(raw, settings)
        self.assertEqual(self.h.transport["sent"][1]["feature"], "jobs")

    def test_monthly_remains_dormant_for_saved_disabled_config(self):
        self.runtime.Resume(self.runtime)
        settings = self.settings(False, False, False)
        settings["monthlyRewards"] = lua_table(self.h.lua, {"enabled": True})
        self.step(settings=settings)
        self.assertEqual(len(self.h.transport["sent"]), 0)
        self.assertIn("disabled", self.runtime.Status(self.runtime)
                      ["reasons"]["monthlyRewards"].lower())
        raw = self.raw()
        raw["monthlyConfig"]["enabled"] = True
        self.step(raw, settings)
        self.assertEqual(self.h.transport["sent"][1]["feature"], "monthlyRewards")

    def test_earned_trophy_claim_uses_one_broker_turn(self):
        self.runtime.Resume(self.runtime)
        settings = self.settings(False, False, False)
        settings["trophies"] = lua_table(self.h.lua, {"enabled": True})
        self.step(settings=settings)
        self.assertEqual(self.h.transport["sent"][1]["feature"], "trophies")
        self.assertEqual(self.h.transport["sent"][1]["intent"]["targetId"],
                         "t_eldersignet")
        self.h.transport["callbacks"][1](lua_table(self.h.lua, {"ok": True}))
        self.h.at(1)
        after = self.raw(2)
        after["native"]["derived"]["trophyReady"] = lua_table(self.h.lua, [])
        after["native"]["inventoryBound"]["t_eldersignet"] = 1
        self.step(after, settings)
        self.assertEqual(self.runtime.Status(self.runtime)["outcomes"]["trophies"],
                         "confirmed")

    def test_catalog_backed_cosmetic_claim_uses_same_broker_turn(self):
        self.runtime.Resume(self.runtime)
        settings = self.settings(False, False, False)
        settings["trophies"] = lua_table(self.h.lua, {"enabled": True})
        before = self.raw()
        before["native"]["derived"]["trophyReady"] = lua_table(
            self.h.lua, ["bg_reward"])
        before["trophyCatalog"] = lua_table(self.h.lua, [
            {"id": "bg_reward", "kind": "background",
             "tradeIn": False, "requiresItems": False}])
        self.step(before, settings)
        self.assertEqual(self.h.transport["sent"][1]["intent"]["targetId"],
                         "bg_reward")
        self.h.transport["callbacks"][1](lua_table(self.h.lua, {"ok": True}))
        self.h.at(1)
        after = self.raw(2)
        after["trophyCatalog"] = before["trophyCatalog"]
        after["native"]["derived"]["trophyReady"] = lua_table(self.h.lua, [])
        after["native"]["collectionBound"]["bg_reward"] = 1
        self.step(after, settings)
        self.assertEqual(self.runtime.Status(self.runtime)["outcomes"]["trophies"],
                         "confirmed")

    def test_crew_auto_equip_app_native_call_and_exact_sync(self):
        feature = self.h.load("src/tabs/crew/AutoEquipCrew.luau")
        descriptor = lua_table(self.h.lua, {"id": "crew", "reader": feature,
            "planner": feature, "evidence": feature})
        self.runtime["features"]["crew"] = descriptor
        self.runtime["order"][len(self.runtime["order"]) + 1] = descriptor
        executor = self.h.lua.execute("""return {
            queued = {}, calls = {},
            Schedule = function(self, fn) self.queued[#self.queued + 1] = fn end,
            Invoke = function(self, remote, method, ...)
                self.calls[#self.calls + 1] = { remote = remote,
                    method = method, arity = select('#', ...) }
                return { ok = true, changed = true }
            end,
            Drain = function(self)
                local pending = self.queued
                self.queued = {}
                for _, fn in ipairs(pending) do fn() end
            end,
        }""")
        plan = self.h.load("src/transport/NativeCallPlan.luau").withCrew(
            self.h.load("src/tabs/crew/CrewCallPlan.luau"))
        adapter = self.h.load("src/transport/NativeDispatchAdapter.luau").new(
            plan, executor)
        self.runtime["session"]["broker"]["transport"] = adapter
        app = self.h.load("src/App.luau").start(lua_table(self.h.lua, {
            "Ember": self.h.load("tests/ember_double.lua")(),
            "Catalog": self.h.load("src/ui/Catalog.luau"),
            "Settings": self.h.load("src/storage/Settings.luau"),
            "EmberAdapter": self.h.load("src/ui/EmberAdapter.luau"),
            "AutomationRuntime": self.runtime,
        }))
        app.Set(app, "crew.enabled", True)
        app.Resume(app)
        before = self.raw()
        before["native"]["crew"] = lua_table(self.h.lua, [
            {"name": "Player", "weapon": "w_old"},
            {"name": "Ally", "rarity": 4, "armor": "a_old"}])
        app.Step(app, before)
        executor.Drain(executor)
        self.assertEqual(len(executor["calls"]), 1,
            str(self.runtime.Status(self.runtime)["reasons"]["crew"]))
        self.assertEqual(executor["calls"][1]["remote"], "AutoEquipCrew")
        self.assertEqual(executor["calls"][1]["arity"], 0)
        self.h.at(1)
        after = self.raw(2)
        after["native"]["crew"] = lua_table(self.h.lua, [
            {"name": "Player", "weapon": "w_better"},
            {"name": "Ally", "rarity": 4, "armor": "a_old"}])
        app.Step(app, after)
        self.assertEqual(self.runtime.Status(self.runtime)["outcomes"]["crew"],
                         "confirmed")
        app.Destroy(app)

    def test_crew_sort_app_native_call_preserves_pinned_member(self):
        feature = self.h.load("src/tabs/crew/CrewSort.luau")
        descriptor = lua_table(self.h.lua, {"id": "crewSort", "reader": feature,
            "planner": feature, "evidence": feature})
        self.runtime["features"]["crewSort"] = descriptor
        self.runtime["order"][len(self.runtime["order"]) + 1] = descriptor
        executor = self.h.lua.execute("""return {
            queued = {}, calls = {},
            Schedule = function(self, fn) self.queued[#self.queued + 1] = fn end,
            Invoke = function(self, remote, method, ...)
                self.calls[#self.calls + 1] = { remote = remote,
                    arity = select('#', ...), args = table.pack(...) }
                return { ok = true, changed = true, pinned = 1 }
            end,
            Drain = function(self)
                local pending = self.queued
                self.queued = {}
                for _, fn in ipairs(pending) do fn() end
            end,
        }""")
        plan = self.h.load("src/transport/NativeCallPlan.luau").withCrew(
            self.h.load("src/tabs/crew/CrewCallPlan.luau"))
        adapter = self.h.load("src/transport/NativeDispatchAdapter.luau").new(
            plan, executor)
        self.runtime["session"]["broker"]["transport"] = adapter
        app = self.h.load("src/App.luau").start(lua_table(self.h.lua, {
            "Ember": self.h.load("tests/ember_double.lua")(),
            "Catalog": self.h.load("src/ui/Catalog.luau"),
            "Settings": self.h.load("src/storage/Settings.luau"),
            "EmberAdapter": self.h.load("src/ui/EmberAdapter.luau"),
            "AutomationRuntime": self.runtime,
        }))
        app.Set(app, "crewSort.enabled", True)
        app.Resume(app)
        before = self.raw()
        before["native"]["crew"] = lua_table(self.h.lua, [
            {"name": "Player"}, {"name": "Weak", "rarity": 1},
            {"name": "Pinned", "rarity": 3, "duty": {"city": "A"}},
            {"name": "Strong", "rarity": 5}])
        app.Step(app, before)
        executor.Drain(executor)
        self.assertEqual(len(executor["calls"]), 1,
            str(self.runtime.Status(self.runtime)["reasons"]["crewSort"]))
        self.assertEqual(executor["calls"][1]["remote"], "CrewAction")
        self.assertEqual(executor["calls"][1]["arity"], 4)
        self.assertEqual(executor["calls"][1]["args"][1], "sort")
        self.h.at(1)
        after = self.raw(2)
        after["native"]["crew"] = lua_table(self.h.lua, [
            {"name": "Player"}, {"name": "Strong", "rarity": 5},
            {"name": "Pinned", "rarity": 3, "duty": {"city": "A"}},
            {"name": "Weak", "rarity": 1}])
        app.Step(app, after)
        self.assertEqual(self.runtime.Status(self.runtime)["outcomes"]["crewSort"],
                         "confirmed")
        app.Destroy(app)

    def test_playtime_claim_waits_for_replicated_threshold(self):
        self.runtime.Resume(self.runtime)
        settings = self.settings(False, False, False)
        settings["playtime"] = lua_table(self.h.lua, {"enabled": True})
        early = self.raw()
        early["native"]["playtime"]["todaySeconds"] = 5399
        self.step(early, settings)
        self.assertEqual(len(self.h.transport["sent"]), 0)
        ready = self.raw()
        ready["weekendBuff"]["active"] = True
        self.step(ready, settings)
        self.assertEqual(self.h.transport["sent"][1]["feature"], "playtime")
        self.assertEqual(self.h.transport["sent"][1]["intent"]["index"], 5)
        self.assertEqual(self.h.transport["sent"][1]["intent"]
                         ["rewardKind"], "xpboost")
        self.h.transport["callbacks"][1](lua_table(self.h.lua, {"ok": True}))
        self.h.at(1)
        after = self.raw(2)
        after["native"]["playtime"]["laddersClaimed"]["5"] = 4
        self.step(after, settings)
        self.assertEqual(self.runtime.Status(self.runtime)["outcomes"]["playtime"],
                         "confirmed")

    def test_rewards_app_native_playtime_claim_marks_exact_rung(self):
        executor = self.install_native_adapter()
        app = self.start_test_app()
        app.Set(app, "playtime.enabled", True)
        app.Resume(app)
        app.Step(app, self.raw())
        executor.Drain(executor)
        self.assertEqual(executor["calls"][1]["remote"], "ClaimLadder")
        self.assertEqual(executor["calls"][1]["method"], "InvokeServer")
        self.assertEqual(executor["calls"][1]["arity"], 1)
        self.assertEqual(executor["calls"][1]["args"][1], 5)
        self.h.at(1)
        after = self.raw(2)
        after["native"]["playtime"]["laddersClaimed"]["5"] = 4
        app.Step(app, after)
        self.assertEqual(self.runtime.Status(self.runtime)["outcomes"]["playtime"],
                         "confirmed")
        app.Destroy(app)

    def test_rewards_app_native_group_claim_requires_membership(self):
        executor = self.install_native_adapter()
        app = self.start_test_app()
        app.Set(app, "groupBonus.enabled", True)
        app.Resume(app)
        app.Step(app, self.raw())
        executor.Drain(executor)
        self.assertEqual(executor["calls"][1]["remote"], "ClaimGroupBonus")
        self.assertEqual(executor["calls"][1]["method"], "InvokeServer")
        self.assertEqual(executor["calls"][1]["arity"], 0)
        self.h.at(1)
        after = self.raw(2)
        after["native"]["groupBonus"] = True
        app.Step(app, after)
        self.assertEqual(self.runtime.Status(self.runtime)["outcomes"]["groupBonus"],
                         "confirmed")
        app.Destroy(app)

    def test_rewards_app_native_monthly_enabled_future_config(self):
        executor = self.install_native_adapter()
        app = self.start_test_app()
        app.Set(app, "monthlyRewards.enabled", True)
        app.Resume(app)
        disabled = self.raw()
        app.Step(app, disabled)
        self.assertEqual(len(list(executor["calls"].values())), 0)
        enabled = self.raw()
        enabled["monthlyConfig"]["enabled"] = True
        app.Step(app, enabled)
        executor.Drain(executor)
        self.assertIsNotNone(executor["calls"][1],
            self.runtime.Status(self.runtime)["reasons"]["monthlyRewards"])
        self.assertEqual(executor["calls"][1]["remote"], "ClaimMonthly")
        self.assertEqual(executor["calls"][1]["method"], "InvokeServer")
        self.assertEqual(executor["calls"][1]["arity"], 0)
        self.h.at(1)
        after = self.raw(2)
        after["monthlyConfig"]["enabled"] = True
        after["native"]["monthly"] = lua_table(self.h.lua, {
            "month": "2026-10", "claimed": 1, "lastDay": 2026293})
        app.Step(app, after)
        self.assertEqual(self.runtime.Status(self.runtime)
                         ["outcomes"]["monthlyRewards"], "confirmed")
        app.Destroy(app)

    def test_events_app_native_free_briefcase_does_not_spend_key(self):
        executor = self.install_native_adapter()
        executor["reply"] = lua_table(self.h.lua,
            {"ok": True, "source": "free"})
        app = self.start_test_app()
        app.Set(app, "briefcases.enabled", True)
        app.Resume(app)
        app.Step(app, self.raw())
        executor.Drain(executor)
        self.assertEqual(executor["calls"][1]["remote"], "BriefcaseAction")
        self.assertEqual(executor["calls"][1]["method"], "InvokeServer")
        self.assertEqual(executor["calls"][1]["arity"], 2)
        self.assertEqual(executor["calls"][1]["args"][1], "open")
        self.assertEqual(executor["calls"][1]["args"][2], 2)
        self.h.at(1)
        after = self.raw(2)
        after["native"]["briefcase"]["free"] = 1
        after["native"]["briefcase"]["board"]["opened"]["c2"] = lua_table(
            self.h.lua, {"p": "gold3"})
        app.Step(app, after)
        self.assertEqual(self.runtime.Status(self.runtime)
                         ["outcomes"]["briefcases"], "confirmed")
        app.Destroy(app)

    def test_contract_entry_claim_uses_same_broker_and_row_identity(self):
        self.runtime.Resume(self.runtime)
        settings = self.settings(False, False, False)
        settings["contracts"] = lua_table(self.h.lua, {"enabled": True})
        raw = self.raw()
        now = raw["native"]["serverNow"]
        raw["native"]["derived"]["contractDayReset"] = now + 3600
        raw["native"]["derived"]["contractWeekReset"] = now + 86400
        self.step(raw, settings)
        self.assertEqual(self.h.transport["sent"][1]["feature"], "contracts")
        self.assertEqual(self.h.transport["sent"][1]["intent"]["rowId"],
                         "c_rounds")
        self.h.transport["callbacks"][1](lua_table(self.h.lua, {"ok": True}))
        self.h.at(1)
        after = self.raw(2)
        after["native"]["derived"]["contractDayReset"] = now + 3600
        after["native"]["derived"]["contractWeekReset"] = now + 86400
        after["native"]["contracts"]["daily"][1]["claimed"] = True
        self.step(after, settings)
        self.assertEqual(self.runtime.Status(self.runtime)["outcomes"]["contracts"],
                         "confirmed")

    def test_completion_bonus_is_separate_and_marker_confirmed(self):
        self.runtime.Resume(self.runtime)
        settings = self.settings(False, False, False)
        settings["bonuses"] = lua_table(self.h.lua, {"enabled": True})
        raw = self.raw()
        now = raw["native"]["serverNow"]
        raw["native"]["derived"]["contractDayReset"] = now + 3600
        raw["native"]["derived"]["contractWeekReset"] = now + 86400
        for row in raw["native"]["contracts"]["daily"].values():
            row["claimed"] = True
        self.step(raw, settings)
        self.assertEqual(self.h.transport["sent"][1]["feature"], "bonuses")
        self.assertEqual(self.h.transport["sent"][1]["intent"]["command"],
                         "claimbonus")
        self.h.transport["callbacks"][1](lua_table(self.h.lua, {"ok": True}))
        self.h.at(1)
        after = self.raw(2)
        after["native"]["derived"]["contractDayReset"] = now + 3600
        after["native"]["derived"]["contractWeekReset"] = now + 86400
        for row in after["native"]["contracts"]["daily"].values():
            row["claimed"] = True
        after["native"]["contracts"]["bonusClaimed"] = True
        self.step(after, settings)
        self.assertEqual(self.runtime.Status(self.runtime)["outcomes"]["bonuses"],
                         "confirmed")

    def test_contracts_app_native_claim_then_separate_bonus(self):
        executor = self.install_native_adapter()
        app = self.start_test_app()
        app.Set(app, "contracts.enabled", True)
        app.Set(app, "bonuses.enabled", True)
        app.Resume(app)
        before = self.raw()
        now = before["native"]["serverNow"]
        for row in list(before["native"]["contracts"]["daily"].values())[1:]:
            row["claimed"] = True
        before["native"]["derived"]["contractDayReset"] = now + 3600
        before["native"]["derived"]["contractWeekReset"] = now + 86400
        app.Step(app, before)
        executor.Drain(executor)
        self.assertEqual(executor["calls"][1]["remote"], "ContractAction")
        self.assertEqual(executor["calls"][1]["arity"], 3)
        self.assertEqual(executor["calls"][1]["args"][1], "claim")
        self.assertEqual(executor["calls"][1]["args"][2], 1)
        self.assertIsNone(executor["calls"][1]["args"][3])
        self.h.at(1)
        claimed = self.raw(2)
        for row in claimed["native"]["contracts"]["daily"].values():
            row["claimed"] = True
        claimed["native"]["derived"]["contractDayReset"] = now + 3600
        claimed["native"]["derived"]["contractWeekReset"] = now + 86400
        app.Step(app, claimed)
        self.assertEqual(self.runtime.Status(self.runtime)["outcomes"]["contracts"],
                         "confirmed")
        executor.Drain(executor)
        self.assertEqual(executor["calls"][2]["remote"], "ContractAction")
        self.assertEqual(executor["calls"][2]["args"][1], "claimbonus")
        self.assertEqual(executor["calls"][2]["arity"], 3)
        self.assertIsNone(executor["calls"][2]["args"][2])
        self.assertIsNone(executor["calls"][2]["args"][3])
        self.h.at(2)
        bonus = self.raw(3)
        for row in bonus["native"]["contracts"]["daily"].values():
            row["claimed"] = True
        bonus["native"]["derived"]["contractDayReset"] = now + 3600
        bonus["native"]["derived"]["contractWeekReset"] = now + 86400
        bonus["native"]["contracts"]["bonusClaimed"] = True
        app.Step(app, bonus)
        self.assertEqual(self.runtime.Status(self.runtime)["outcomes"]["bonuses"],
                         "confirmed")
        app.Destroy(app)

    def test_free_briefcase_pick_needs_reply_source_and_reveal(self):
        self.runtime.Resume(self.runtime)
        settings = self.settings(False, False, False)
        settings["briefcases"] = lua_table(self.h.lua, {"enabled": True})
        self.step(settings=settings)
        self.assertEqual(self.h.transport["sent"][1]["feature"], "briefcases")
        self.assertEqual(self.h.transport["sent"][1]["intent"]["index"], 2)
        self.h.transport["callbacks"][1](lua_table(self.h.lua, {
            "ok": True, "source": "free"}))
        self.h.at(1)
        after = self.raw(2)
        after["native"]["briefcase"]["free"] = 1
        after["native"]["briefcase"]["board"]["opened"]["c2"] = (
            lua_table(self.h.lua, {"p": "gold3"}))
        self.step(after, settings)
        self.assertEqual(self.runtime.Status(self.runtime)
                         ["outcomes"]["briefcases"], "confirmed")

    def test_bank_deposit_uses_shared_broker_and_exact_transfer(self):
        self.runtime.Resume(self.runtime)
        settings = self.settings(False, False, False)
        settings["bank"] = lua_table(self.h.lua, {"enabled": True,
            "depositThreshold": 10000, "cashToKeep": 5000})
        before = self.raw()
        before["native"]["cash"] = 50000
        before["purchaseSavings"]["amount"] = 15000
        self.step(before, settings)
        proposal = self.h.transport["sent"][1]
        self.assertEqual(proposal["feature"], "bank")
        self.assertEqual(proposal["intent"]["amount"], 45000)
        self.h.transport["callbacks"][1](lua_table(self.h.lua, {
            "ok": True, "fee": 4500, "kept": 40500}))
        self.h.at(1)
        after = self.raw(2)
        after["native"]["cash"] = 5000
        after["native"]["banked"] = 40600
        after["purchaseSavings"]["amount"] = 15000
        self.step(after, settings)
        self.assertEqual(self.runtime.Status(self.runtime)["outcomes"]["bank"],
                         "confirmed")

    def test_safehouse_next_tier_uses_shared_broker(self):
        self.runtime.Resume(self.runtime)
        settings = self.settings(False, False, False)
        settings["safehouse"] = lua_table(self.h.lua, {"enabled": True,
            "maxTier": 18, "maxCost": 100000, "cashReserve": 1000})
        before = self.raw()
        before["native"]["cash"] = 10000
        self.step(before, settings)
        self.assertEqual(self.h.transport["sent"][1]["feature"], "safehouse")
        self.assertEqual(self.h.transport["sent"][1]["intent"]["nextTier"], 4)
        self.h.transport["callbacks"][1](lua_table(self.h.lua, {"ok": True}))
        self.h.at(1)
        after = self.raw(2)
        after["native"]["safehouse"] = 4
        after["native"]["cash"] = 7000
        self.step(after, settings)
        self.assertEqual(self.runtime.Status(self.runtime)
                         ["outcomes"]["safehouse"], "confirmed")

    def test_supplied_funding_request_cannot_enable_disabled_purchase(self):
        self.runtime.Resume(self.runtime)
        settings = self.settings(False, False, False)
        settings["withdraw"] = lua_table(self.h.lua, {"enabled": True,
            "maxWithdrawal": 1000000, "allowOperations": False,
            "allowSafehouse": True})
        before = self.raw()
        before["native"]["banked"] = 20000
        before["fundingRequest"] = lua_table(self.h.lua, {
            "session": "run-a", "account": "user-a",
            "place": "73897506680154", "release": "release-a",
            "revision": 1, "capturedAt": 0,
            "purpose": "safehouse", "purchaseKey": "safehouse:4",
            "requiredCash": 8000})
        self.step(before, settings)
        self.assertEqual(len(self.h.transport["sent"]), 0)

    def test_funding_coordinator_replans_safehouse_after_transfer(self):
        self.runtime.Resume(self.runtime)
        settings = self.settings(False, False, False)
        settings["safehouse"] = lua_table(self.h.lua, {"enabled": True,
            "maxTier": 18, "maxCost": 100000, "cashReserve": 500})
        settings["withdraw"] = lua_table(self.h.lua, {"enabled": True,
            "maxWithdrawal": 1000000, "allowOperations": False,
            "allowSafehouse": True})
        before = self.raw()
        before["native"]["banked"] = 10000
        self.assertIsNone(before["fundingRequest"])
        self.step(before, settings)
        self.assertEqual(self.h.transport["sent"][1]["feature"], "withdraw")
        self.assertEqual(self.h.transport["sent"][1]["intent"]["amount"], 2500)
        self.h.transport["callbacks"][1](lua_table(self.h.lua, {"ok": True}))
        self.h.at(1)
        after = self.raw(2)
        after["native"]["cash"] = 3500
        after["native"]["banked"] = 7500
        self.step(after, settings)
        self.assertEqual(self.runtime.Status(self.runtime)
                         ["outcomes"]["withdraw"], "confirmed")
        self.assertEqual(self.h.transport["sent"][2]["feature"], "safehouse")
        self.assertEqual(len(self.h.transport["sent"]), 2)

    def test_bad_operation_state_does_not_stop_jobs(self):
        self.runtime.Resume(self.runtime)
        self.step(self.raw(operation_catalog=[]))
        self.assertEqual(self.h.transport["sent"][1]["feature"], "jobs")
        self.assertIn("catalog", self.runtime.Status(self.runtime)
                      ["reasons"]["operations"].lower())

    def test_property_build_uses_shared_broker_and_exact_count(self):
        self.runtime.Resume(self.runtime)
        raw = self.raw()
        raw["native"]["properties"] = lua_table(self.h.lua, {
            "p_a": {"owned": 1}, "p_b": {"owned": 0}})
        raw["propertyCatalog"] = lua_table(self.h.lua, [
            {"id": "p_a", "level": 1, "baseCost": 100,
             "incomePerHour": 10},
            {"id": "p_b", "level": 5, "baseCost": 200,
             "incomePerHour": 40}])
        raw["propertyProof"] = lua_table(self.h.lua, {
            "account": "user-a", "capturedAt": 0,
            "occupied": 1, "capacity": 3, "buildDiscount": 0})
        settings = lua_table(self.h.lua, {"properties": {
            "enabled": True, "policy": "Best value",
            "cashReserve": 0, "purchaseCap": 1000,
            "ownedLimit": 10}})
        self.step(raw, settings)
        sent = self.h.transport["sent"][1]
        self.assertEqual(sent["feature"], "properties")
        self.assertEqual(sent["intent"]["propId"], "p_b")
        self.h.transport["callbacks"][1](lua_table(self.h.lua, {"ok": True}))
        self.step(raw, settings)
        self.assertNotEqual(self.runtime.Status(self.runtime)
                            ["outcomes"]["properties"], "confirmed")
        self.h.at(1)
        newer = self.raw(revision=2)
        newer["native"]["properties"] = lua_table(self.h.lua, {
            "p_a": {"owned": 1}, "p_b": {"owned": 1}})
        newer["native"]["cash"] = 800
        self.step(newer, settings)
        self.assertEqual(self.runtime.Status(self.runtime)
                         ["outcomes"]["properties"], "confirmed")

    def test_property_app_native_call_uses_nil_slot_and_exact_build(self):
        executor = self.h.lua.execute("""return {
            queued = {}, calls = {},
            Schedule = function(self, fn)
                self.queued[#self.queued + 1] = fn
            end,
            Invoke = function(self, remote, method, ...)
                self.calls[#self.calls + 1] = { remote = remote,
                    method = method, arity = select('#', ...),
                    args = table.pack(...) }
                return { ok = true }
            end,
            Drain = function(self)
                local pending = self.queued
                self.queued = {}
                for _, fn in ipairs(pending) do fn() end
            end,
        }""")
        adapter = self.h.load("src/transport/NativeDispatchAdapter.luau").new(
            self.h.load("src/transport/NativeCallPlan.luau"), executor)
        self.runtime["session"]["broker"]["transport"] = adapter
        app = self.h.load("src/App.luau").start(lua_table(self.h.lua, {
            "Ember": self.h.load("tests/ember_double.lua")(),
            "Catalog": self.h.load("src/ui/Catalog.luau"),
            "Settings": self.h.load("src/storage/Settings.luau"),
            "EmberAdapter": self.h.load("src/ui/EmberAdapter.luau"),
            "AutomationRuntime": self.runtime,
        }))
        app.Set(app, "properties.enabled", True)
        app.Set(app, "properties.policy", "Best value")
        app.Set(app, "properties.custom.cashReserve", 0)
        app.Set(app, "properties.custom.purchaseCap", 1000)
        app.Resume(app)
        before = self.raw()
        before["native"]["properties"] = lua_table(self.h.lua, {
            "p_a": {"owned": 1}, "p_b": {"owned": 0}})
        before["propertyCatalog"] = lua_table(self.h.lua, [
            {"id": "p_a", "level": 1, "baseCost": 100,
             "incomePerHour": 10},
            {"id": "p_b", "level": 5, "baseCost": 200,
             "incomePerHour": 40},
        ])
        before["propertyProof"] = lua_table(self.h.lua, {
            "account": "user-a", "capturedAt": 0,
            "occupied": 1, "capacity": 3, "buildDiscount": 0})
        app.Step(app, before)
        executor.Drain(executor)
        self.assertEqual(executor["calls"][1]["remote"], "BuyProperty")
        self.assertEqual(executor["calls"][1]["method"], "InvokeServer")
        self.assertEqual(executor["calls"][1]["arity"], 2)
        self.assertEqual(executor["calls"][1]["args"][1], "p_b")
        self.assertIsNone(executor["calls"][1]["args"][2])
        self.h.at(1)
        after = self.raw(2)
        after["native"]["properties"] = lua_table(self.h.lua, {
            "p_a": {"owned": 1}, "p_b": {"owned": 1}})
        after["native"]["cash"] = 800
        app.Step(app, after)
        self.assertEqual(self.runtime.Status(self.runtime)["outcomes"]["properties"],
                         "confirmed")
        app.Destroy(app)

    def test_chest_app_uses_native_luck_and_confirms_opened_batch(self):
        chest = self.h.load("src/tabs/inventory/Chests.luau")
        spec = lua_table(self.h.lua, {"id": "chests", "reader": chest,
            "planner": chest, "evidence": chest})
        self.runtime["features"]["chests"] = spec
        self.h.lua.eval("function(rows, row) rows[#rows + 1] = row end")(
            self.runtime["order"], spec)
        self.runtime["modules"]["CrateLuckProducer"] = self.h.load(
            "src/tabs/inventory/CrateLuckProducer.luau")
        self.runtime["modules"]["crateLuckSource"] = self.h.load(
            "src/tabs/inventory/NativeCrateLuckSource.luau").new(
                self.h.lua.execute("""return { crateLuck = function(native)
                    return native.luckBonus end }"""), "release-a")[0]
        executor = self.install_native_adapter()
        executor["reply"] = lua_table(self.h.lua, {"ok": True,
            "opened": 2, "itemIds": ["prize_a", "prize_a"]})
        plan = self.h.load("src/transport/NativeCallPlan.luau")
        plan = plan.withInventory(plan.withCrew(
            self.h.load("src/tabs/crew/CrewCallPlan.luau")),
            self.h.load("src/tabs/inventory/InventoryCallPlan.luau"))
        adapter = self.h.load("src/transport/NativeDispatchAdapter.luau").new(
            plan, executor)
        self.runtime["session"]["broker"]["transport"] = adapter
        app = self.start_test_app()
        app.Set(app, "chests.enabled", True)
        app.Set(app, "chests.policy", "Largest stack")
        app.Set(app, "chests.custom.maxBatch", 2)
        app.Resume(app)
        before = self.raw()
        before["native"]["inventory"] = lua_table(self.h.lua,
            {"crate_a": 3})
        before["native"]["inventoryBound"] = lua_table(self.h.lua,
            {"crate_a": 2})
        before["native"]["luckBonus"] = 0.25
        before["crateLuckProof"] = lua_table(self.h.lua,
            {**self.h.session, "capturedAt": 0,
             "revision": 1, "luck": 0.9})
        before["ownedCrateCatalog"] = lua_table(self.h.lua,
            {"release": "release-a", "catalogKey": "a" * 64,
             "batchMax": 10, "crates": {"crate_a": True}})
        source = self.runtime["modules"]["crateLuckSource"]
        self.runtime["modules"]["crateLuckSource"] = None
        app.Step(app, before)
        self.assertEqual(len(executor["queued"]), 0)
        self.runtime["modules"]["crateLuckSource"] = source
        app.Step(app, before)
        executor.Drain(executor)
        self.assertEqual(len(executor["calls"]), 1,
            str((self.runtime.Status(self.runtime)["reason"],
                 self.runtime.Status(self.runtime)["reasons"]["chests"],
                 len(executor["queued"]))))
        self.assertEqual(executor["calls"][1]["remote"], "OpenCrate")
        self.assertEqual(executor["calls"][1]["arity"], 4)
        self.assertEqual(executor["calls"][1]["args"][1], "crate_a")
        self.assertFalse(executor["calls"][1]["args"][2])
        self.assertEqual(executor["calls"][1]["args"][3], 2)
        self.assertEqual(executor["calls"][1]["args"][4], 0.25)
        self.h.at(1)
        after = self.raw(2)
        after["native"]["inventory"] = lua_table(self.h.lua,
            {"crate_a": 1, "prize_a": 2})
        after["native"]["inventoryBound"] = lua_table(self.h.lua,
            {"crate_a": 2})
        after["native"]["luckBonus"] = 0.25
        after["ownedCrateCatalog"] = before["ownedCrateCatalog"]
        app.Step(app, after)
        self.assertEqual(self.runtime.Status(self.runtime)
                         ["outcomes"]["chests"], "confirmed")
        app.Destroy(app)

    def test_cosmetic_app_equips_without_losing_ownership(self):
        cosmetic = self.h.load("src/tabs/inventory/Cosmetics.luau").new(
            lua_table(self.h.lua, {"ITEMS_BY_ID": {
                "bg_old": {"id": "bg_old", "kind": "background",
                           "atk": 1, "def": 1},
                "bg_new": {"id": "bg_new", "kind": "background",
                           "atk": 5, "def": 3}}}),
            "a" * 64, "release-a")
        spec = lua_table(self.h.lua, {"id": "cosmetics",
            "reader": cosmetic, "planner": cosmetic,
            "evidence": cosmetic})
        self.runtime["features"]["cosmetics"] = spec
        self.h.lua.eval("function(rows, row) rows[#rows + 1] = row end")(
            self.runtime["order"], spec)
        executor = self.install_native_adapter()
        plan = self.h.load("src/transport/NativeCallPlan.luau")
        plan = plan.withInventory(plan.withCrew(
            self.h.load("src/tabs/crew/CrewCallPlan.luau")),
            self.h.load("src/tabs/inventory/InventoryCallPlan.luau"))
        self.runtime["session"]["broker"]["transport"] = self.h.load(
            "src/transport/NativeDispatchAdapter.luau").new(plan, executor)
        app = self.start_test_app()
        app.Set(app, "cosmetics.enabled", True)
        app.Set(app, "cosmetics.policy", "Balanced")
        app.Resume(app)
        before = self.raw()
        before["cosmeticSourceKey"] = "a" * 64
        before["native"]["equippedBackground"] = "bg_old"
        before["native"]["inventory"] = lua_table(self.h.lua,
            {"bg_old": 1, "bg_new": 1})
        before["native"]["collectionBound"] = self.h.lua.table()
        app.Step(app, before)
        executor.Drain(executor)
        self.assertEqual(executor["calls"][1]["remote"],
                         "EquipBackground")
        self.assertEqual(executor["calls"][1]["args"][1], "bg_new")
        self.h.at(1)
        after = self.raw(2)
        after["native"]["equippedBackground"] = "bg_new"
        after["native"]["inventory"] = lua_table(self.h.lua,
            {"bg_old": 1, "bg_new": 1})
        after["native"]["collectionBound"] = self.h.lua.table()
        app.Step(app, after)
        self.assertEqual(self.runtime.Status(self.runtime)
                         ["outcomes"]["cosmetics"], "confirmed")
        self.assertEqual(after["native"]["inventory"]["bg_new"], 1)
        app.Destroy(app)

    def test_restorative_app_uses_bound_player_sequence(self):
        restorative = self.h.load("src/tabs/inventory/Restoratives.luau")
        spec = lua_table(self.h.lua, {"id": "restoratives",
            "reader": restorative, "planner": restorative,
            "evidence": restorative})
        self.runtime["features"]["restoratives"] = spec
        self.h.lua.eval("function(rows, row) rows[#rows + 1] = row end")(
            self.runtime["order"], spec)
        executor = self.install_native_adapter()
        executor["reply"] = lua_table(self.h.lua, {"ok": True,
            "sequence": 5, "readyAt": 2000003,
            "resource": "health", "gain": 50})
        plan = self.h.load("src/transport/NativeCallPlan.luau")
        plan = plan.withInventory(plan.withCrew(
            self.h.load("src/tabs/crew/CrewCallPlan.luau")),
            self.h.load("src/tabs/inventory/InventoryCallPlan.luau"))
        self.runtime["session"]["broker"]["transport"] = self.h.load(
            "src/transport/NativeDispatchAdapter.luau").new(plan, executor)
        app = self.start_test_app()
        app.Set(app, "restoratives.enabled", True)
        app.Set(app, "restoratives.custom.healthBelow", 50)
        app.Resume(app)
        ids = (("con_bandages", "health", 25),
               ("con_medkit_small", "health", 50),
               ("con_medkit_large", "health", 100),
               ("con_energy_small", "energy", 25),
               ("con_energy", "energy", 50),
               ("con_energy_pack", "energy", 100),
               ("con_peanuts", "stamina", 25),
               ("con_sandwich", "stamina", 50),
               ("con_lunchbox", "stamina", 100))
        catalog = lua_table(self.h.lua, {"release": "release-a",
            "catalogKey": "a" * 64, "cooldown": 3,
            "items": [{"id": item, "pool": pool, "percent": percent}
                      for item, pool, percent in ids]})
        before = self.raw()
        before["restorativeCatalog"] = catalog
        before["native"]["serverNow"] = 2000000
        before["native"]["consumableUseSequence"] = 4
        before["native"]["consumableReadyAt"] = 1999999
        before["native"]["pools"] = lua_table(self.h.lua,
            {"health": 30, "energy": 100, "stamina": 50})
        before["native"]["stats"] = lua_table(self.h.lua,
            {"maxHealth": 100, "maxStamina": 100})
        before["native"]["derived"]["effMaxEnergy"] = 100
        before["native"]["inventory"] = lua_table(self.h.lua,
            {"con_medkit_small": 1})
        before["native"]["inventoryBound"] = lua_table(self.h.lua,
            {"con_medkit_small": 1})
        app.Step(app, before)
        executor.Drain(executor)
        self.assertEqual(executor["calls"][1]["remote"],
                         "UseConsumable")
        self.assertEqual(executor["calls"][1]["arity"], 3)
        self.assertEqual(executor["calls"][1]["args"][1],
                         "con_medkit_small")
        self.assertTrue(executor["calls"][1]["args"][2])
        self.assertEqual(executor["calls"][1]["args"][3], 4)
        self.h.at(1)
        after = self.raw(2)
        after["native"]["serverNow"] = 2000001
        after["native"]["consumableUseSequence"] = 5
        after["native"]["consumableReadyAt"] = 2000003
        after["native"]["pools"] = lua_table(self.h.lua,
            {"health": 80, "energy": 100, "stamina": 50})
        after["native"]["inventory"] = lua_table(self.h.lua,
            {"con_medkit_small": 1})
        after["native"]["inventoryBound"] = lua_table(self.h.lua,
            {"con_medkit_small": 0})
        app.Step(app, after)
        self.assertEqual(self.runtime.Status(self.runtime)
                         ["outcomes"]["restoratives"], "confirmed")
        app.Destroy(app)

    def test_collection_app_deposits_only_surplus_loose_copies(self):
        self.collection_app_case(False)

    def test_collection_app_keeps_reloaded_market_listing_and_configured_spare(self):
        self.collection_app_case(True)

    def collection_app_case(self, saved_market):
        donate = self.h.load("src/tabs/collection/CollectionDonate.luau")
        spec = lua_table(self.h.lua, {"id": "collectionDonate",
            "reader": donate, "planner": donate, "evidence": donate})
        self.runtime["features"]["collectionDonate"] = spec
        self.h.lua.eval("function(rows, row) rows[#rows + 1] = row end")(
            self.runtime["order"], spec)
        executor = self.install_native_adapter()
        executor["reply"] = lua_table(self.h.lua,
            {"ok": True, "moved": 1 if saved_market else 2})
        plan = self.h.load("src/transport/NativeCallPlan.luau")
        plan = plan.withCollection(plan.withInventory(
            plan.withCrew(self.h.load(
                "src/tabs/crew/CrewCallPlan.luau")),
            self.h.load("src/tabs/inventory/InventoryCallPlan.luau")),
            self.h.load("src/tabs/collection/CollectionCallPlan.luau"))
        self.runtime["session"]["broker"]["transport"] = self.h.load(
            "src/transport/NativeDispatchAdapter.luau").new(plan, executor)
        app = self.start_test_app()
        app.Set(app, "collectionDonate.enabled", True)
        app.Set(app, "collectionDonate.custom.maxBatch", 2)
        app.Set(app, "collectionDonate.custom.sparesToKeep", 1)
        app.Resume(app)
        before = self.raw()
        before["collectionCatalog"] = lua_table(self.h.lua, {
            "release": "release-a", "catalogKey": "a" * 64,
            "items": {"w_a": {"kind": "weapon", "rarity": 4}},
            "rarity": [1, 2, 3, 5],
            "tiers": [{"count": 1, "mult": 1},
                      {"count": 10, "mult": 2}]})
        before["native"]["inventory"] = lua_table(self.h.lua,
            {"w_a": 4})
        before["native"]["collection"] = lua_table(self.h.lua,
            {"w_a": 9})
        before["native"]["crew"] = lua_table(self.h.lua, [
            {"name": "Player", "weapon": "w_a"},
            {"name": "Ally", "rarity": 4}])
        amount = 2
        if saved_market:
            before.native.inventory.w_a = 5
            before.native.market = lua_table(self.h.lua, {"shopUntil": 2000, "listings": {}})
            market = self.h.load("src/tabs/blackMarket/MarketTransactions.luau")
            evidence = self.h.load("src/tabs/blackMarket/MarketListEvidence.luau")
            store, _ = market.new(self.storage, lua_table(self.h.lua, self.h.session), evidence)
            listing = self.h.proposal("marketSell", "listing")
            listing.preflightOnly = True
            listing.intent = lua_table(self.h.lua, {"kind": "marketList", "itemId": "w_a", "quantity": 2, "ask": 9})
            self.assertTrue(store.PrepareOwnedList(store, listing, before)[0])
            store, reason = market.new(self.storage, lua_table(self.h.lua, self.h.session), evidence)
            self.assertIsNone(reason)
            self.h.lua.globals().marketStore, self.h.lua.globals().runtimeCheckpoint = store, self.runtime.checkpoint
            owner = self.runtime.modules.ResourceReservations.new(lua_table(self.h.lua, self.h.session),
                self.h.lua.eval("function() return runtimeCheckpoint:Records() end"),
                self.h.lua.execute("return {{id='savedMarket',read=function() return marketStore:ReservationClaims() end}}"))
            self.runtime.reservationOwner, self.runtime.session.broker.policy.reservations = owner, owner
            amount = 1
        app.Step(app, before)
        executor.Drain(executor)
        self.assertEqual(len(executor["calls"]), 1,
            str((self.runtime.Status(self.runtime)["reason"],
                 self.runtime.Status(self.runtime)
                     ["reasons"]["collectionDonate"])))
        self.assertEqual(executor["calls"][1]["remote"],
                         "CollectionAction")
        self.assertEqual(executor["calls"][1]["arity"], 3)
        self.assertEqual(executor["calls"][1]["args"][1], "deposit")
        self.assertEqual(executor["calls"][1]["args"][2], "w_a")
        self.assertEqual(executor["calls"][1]["args"][3], amount)
        self.h.at(1)
        after = self.raw(2)
        after["native"]["inventory"] = lua_table(self.h.lua,
            {"w_a": 4 if saved_market else 2})
        after["native"]["collection"] = lua_table(self.h.lua,
            {"w_a": 9 + amount})
        after["native"]["crew"] = before["native"]["crew"]
        app.Step(app, after)
        self.assertEqual(self.runtime.Status(self.runtime)
                         ["outcomes"]["collectionDonate"],
                         "confirmed")
        app.Destroy(app)

    def test_shop_app_native_call_confirms_selected_cash_offer(self):
        self.runtime["modules"]["ShopQuoteProducer"] = self.h.load(
            "src/engine/ShopQuoteProducer.luau")
        self.runtime["modules"]["shopQuoteSource"] = self.h.lua.execute(
            """return { release = 'release-a',
                catalogKey = string.rep('a', 64),
                Stock = function(self, now)
                    return { w_a = true }, 1500, 4
                end,
                CashQuote = function(self, id, slot, raw)
                    return 120
                end,
            }""")
        executor = self.h.lua.execute("""return {
            queued = {}, calls = {},
            Schedule = function(self, fn)
                self.queued[#self.queued + 1] = fn
            end,
            Invoke = function(self, remote, method, ...)
                self.calls[#self.calls + 1] = { remote = remote,
                    method = method, arity = select('#', ...),
                    args = table.pack(...) }
                return { ok = true }
            end,
            Drain = function(self)
                local pending = self.queued
                self.queued = {}
                for _, fn in ipairs(pending) do fn() end
            end,
        }""")
        adapter = self.h.load("src/transport/NativeDispatchAdapter.luau").new(
            self.h.load("src/transport/NativeCallPlan.luau"), executor)
        self.runtime["session"]["broker"]["transport"] = adapter
        app = self.h.load("src/App.luau").start(lua_table(self.h.lua, {
            "Ember": self.h.load("tests/ember_double.lua")(),
            "Catalog": self.h.load("src/ui/Catalog.luau"),
            "Settings": self.h.load("src/storage/Settings.luau"),
            "EmberAdapter": self.h.load("src/ui/EmberAdapter.luau"),
            "AutomationRuntime": self.runtime,
        }))
        app.Set(app, "shop.enabled", True)
        app.Set(app, "shop.custom.itemId", "w_a")
        app.Set(app, "shop.custom.cashReserve", 100)
        app.Set(app, "shop.custom.purchaseCap", 200)
        app.Resume(app)
        def shop_raw(revision, cash, owned, bought, rotation_bought):
            raw = self.raw(revision)
            raw["native"]["cash"] = cash
            raw["native"]["serverNow"] = 1220.25
            raw["native"]["level"] = 10
            raw["native"]["inventory"] = lua_table(self.h.lua,
                {"w_a": owned})
            raw["native"]["shopBought"] = lua_table(self.h.lua,
                {"w_a": bought})
            raw["native"]["shopRotation"] = lua_table(self.h.lua,
                {"slot": 4, "bought": {"w_a": rotation_bought}})
            raw["native"]["autoBuyRules"] = lua_table(self.h.lua,
                {"on": False})
            raw["shopCatalog"] = lua_table(self.h.lua, {
                "release": "release-a", "key": "a" * 64,
                "offers": {"w_a": {"level": 1, "rarity": 1,
                    "base": 100, "ceiling": 150, "kind": "weapon",
                    "limit": 2}}})
            raw["shopQuoteProof"] = lua_table(self.h.lua, {
                **self.h.session, "revision": revision,
                "capturedAt": self.h.lua.globals().testNow,
                "catalogKey": "a" * 64, "slot": 4,
                "stock": {"w_a": True}, "quotes": {"w_a": 120}})
            return raw
        before = shop_raw(1, 1000, 0, 0, False)
        shop_context = self.h.load("src/game/Context.luau").new(self.h.contracts)
        current = shop_context.Read(shop_context, before,
            lua_table(self.h.lua, self.h.session), 0, 2)[0]
        direct, reason = self.h.load("src/game/ShopState.luau").read(
            before, current)
        self.assertIsNone(reason)
        app.Step(app, before)
        executor.Drain(executor)
        self.assertIsNotNone(executor["calls"][1],
            self.runtime.Status(self.runtime)["reasons"]["shop"])
        self.assertEqual(executor["calls"][1]["remote"], "BuyShopItem")
        self.assertEqual(executor["calls"][1]["method"], "InvokeServer")
        self.assertEqual(executor["calls"][1]["arity"], 3)
        self.assertEqual(executor["calls"][1]["args"][1], "w_a")
        self.assertIsNone(executor["calls"][1]["args"][2])
        self.assertEqual(executor["calls"][1]["args"][3], 120)
        self.h.at(1)
        after = shop_raw(2, 880, 1, 1, True)
        app.Step(app, after)
        self.assertEqual(self.runtime.Status(self.runtime)["outcomes"]["shop"],
                         "confirmed")
        app.Destroy(app)

    def test_heist_start_uses_shared_broker_and_exact_run(self):
        self.runtime.Resume(self.runtime)
        raw = self.raw()
        server_now = raw["native"]["serverNow"]
        raw["heistCatalog"] = lua_table(self.h.lua, [{
            "id": "h_low", "level": 10, "stake": 100,
            "energy": 2, "crateCount": 1, "crateChance": 1, "crateRarity": 2, "duration": 600, "cash": 200, "xp": 10, "helpGoal": 3}])
        raw["heistBoardProof"] = lua_table(self.h.lua, {
            "account": "user-a", "capturedAt": 0,
            "board": {"ok": True, "serverNow": server_now,
                      "rows": [], "startsLeft": 2, "bustWait": 0}})
        settings = lua_table(self.h.lua, {"heists": {
            "enabled": True, "policy": "Best chest"}})
        self.step(raw, settings)
        sent = self.h.transport["sent"][1]
        self.assertEqual(sent["feature"], "heists")
        self.assertEqual(sent["intent"]["heistId"], "h_low")
        self.h.transport["callbacks"][1](lua_table(self.h.lua, {
            "ok": True, "runId": "run-1"}))
        self.step(raw, settings)
        self.assertNotEqual(self.runtime.Status(self.runtime)
                            ["outcomes"]["heists"], "confirmed")
        self.h.at(1)
        after = self.raw(revision=2)
        after["heistBoardProof"] = lua_table(self.h.lua, {
            "account": "user-a", "capturedAt": 1,
            "board": {"ok": True, "serverNow": server_now,
                      "rows": [], "startsLeft": 1, "bustWait": 0,
                      "mine": {"id": "run-1", "heistId": "h_low",
                               "endsAt": server_now + 1200}}})
        self.step(after, settings)
        self.assertEqual(self.runtime.Status(self.runtime)
                         ["outcomes"]["heists"], "confirmed")

    def test_favor_help_uses_shared_broker_and_exact_row(self):
        self.runtime.Resume(self.runtime)
        raw = self.raw()
        server_now = raw["native"]["serverNow"]
        day = server_now // 86400
        raw["native"]["pools"]["energy"] = 20
        raw["heistCatalog"] = lua_table(self.h.lua, [{
            "id": "h_low", "level": 10, "stake": 100,
            "energy": 2, "helpCash": 200,
            "helpXp": 20}])
        row = {"id": "run-1", "ownerId": 42,
               "heistId": "h_low", "endsAt": server_now + 300,
               "friend": True, "helpsUsed": 0, "sabosUsed": 0}
        raw["heistBoardProof"] = lua_table(self.h.lua, {
            "account": "user-a", "capturedAt": 0,
            "board": {"ok": True, "serverNow": server_now,
                      "rows": [row], "favorsLeft": 12,
                      "helpFavorCost": 1, "helpEnergyCost": 2,
                      "helpMaxPerHeist": 5}})
        raw["favorUsageProof"] = lua_table(self.h.lua, {
            "account": "user-a", "capturedAt": 0,
            "day": day, "attempts": 0})
        settings = lua_table(self.h.lua, {"favors": {
            "enabled": True, "policy": "Best reward",
            "custom": {"maxDailyAttempts": 5,
                       "minFavorReserve": 5,
                       "minEnergyReserve": 10,
                       "relations": "Friends or Family"}}})
        self.step(raw, settings)
        self.assertEqual(self.h.transport["sent"][1]["feature"], "favors")
        self.h.transport["callbacks"][1](lua_table(self.h.lua,
                                                      {"ok": True}))
        self.step(raw, settings)
        self.assertNotEqual(self.runtime.Status(self.runtime)
                            ["outcomes"]["favors"], "confirmed")
        self.h.at(1)
        after = self.raw(revision=2)
        after["heistBoardProof"] = lua_table(self.h.lua, {
            "account": "user-a", "capturedAt": 1,
            "board": {"ok": True, "serverNow": server_now,
                      "rows": [{**row, "helpsUsed": 1}],
                      "favorsLeft": 11,
                      "helpFavorCost": 1, "helpEnergyCost": 2,
                      "helpMaxPerHeist": 5}})
        after["favorUsageProof"] = lua_table(self.h.lua, {
            "account": "user-a", "capturedAt": 1,
            "day": day, "attempts": 1})
        self.step(after, settings)
        self.assertEqual(self.runtime.Status(self.runtime)
                         ["outcomes"]["favors"], "confirmed")

    def test_city_boss_hit_uses_shared_broker_and_durable_count(self):
        self.runtime.Resume(self.runtime)
        raw = self.raw()
        server_now = raw["native"]["serverNow"]
        day = int(datetime.fromtimestamp(server_now,
            tz=timezone.utc).strftime("%Y%j"))
        raw["native"]["stats"] = lua_table(self.h.lua,
            {"maxHealth": 100})
        raw["native"]["pools"]["health"] = 80
        raw["native"]["pools"]["stamina"] = 12
        raw["native"]["bossStage"] = lua_table(self.h.lua, {
            "best": 1, "day": day, "done": {}, "hp": {}})
        stages = [{"stage": 1, "level": 5, "hp": 100,
                   "hitBackMax": 10},
                  {"stage": 2, "level": 10, "hp": 200,
                   "hitBackMax": 20}]
        raw["bossStageProof"] = lua_table(self.h.lua, {
            "account": "user-a", "capturedAt": 0,
            "staminaCost": 1, "stages": stages})
        settings = lua_table(self.h.lua, {"bosses": {"enabled": True}})
        self.step(raw, settings)
        self.assertEqual(self.h.transport["sent"][1]["feature"], "bosses")
        self.assertEqual(self.h.transport["sent"][1]
                         ["intent"]["stage"], 2)
        self.assertEqual(self.runtime.checkpoint.BossUsage(
            self.runtime.checkpoint, day, 0)["hits"], 1)
        self.h.transport["callbacks"][1](lua_table(self.h.lua,
                                                      {"ok": True}))
        self.h.at(1)
        after = self.raw(revision=2)
        after["native"]["stats"] = lua_table(self.h.lua,
            {"maxHealth": 100})
        after["native"]["pools"]["health"] = 80
        after["native"]["pools"]["stamina"] = 11
        after["native"]["bossStage"] = lua_table(self.h.lua, {
            "best": 1, "day": day, "done": {}, "hp": {"2": 150}})
        after["bossStageProof"] = lua_table(self.h.lua, {
            "account": "user-a", "capturedAt": 1,
            "staminaCost": 1, "stages": stages})
        after["bossUsageProof"] = lua_table(self.h.lua, {
            "account": "user-a", "capturedAt": 1, "day": day,
            "hits": 0, "stamina": 0, "lastServerNow": 0})
        self.step(after, settings)
        self.assertEqual(self.runtime.Status(self.runtime)
                         ["outcomes"]["bosses"], "confirmed")

    def test_sabotage_uses_shared_broker_and_exact_row(self):
        self.runtime.Resume(self.runtime)
        raw = self.raw()
        raw["native"]["family"] = lua_table(self.h.lua, {"id": "own-family"})
        server_now = raw["native"]["serverNow"]
        day = server_now // 86400
        raw["native"]["pools"]["energy"] = 20
        raw["heistCatalog"] = lua_table(self.h.lua, [{
            "id": "h_low", "level": 10, "stake": 100,
            "energy": 2}])
        row = {"id": "run-1", "ownerId": 99,
               "heistId": "h_low", "endsAt": server_now + 300,
               "friend": False, "famId": "other-family", "helpsUsed": 0, "sabosUsed": 0}
        raw["heistBoardProof"] = lua_table(self.h.lua, {
            "account": "user-a", "capturedAt": 0,
            "board": {"ok": True, "serverNow": server_now,
                      "rows": [row], "favorsLeft": 12,
                      "saboFavorCost": 2, "saboEnergyCost": 3,
                      "saboMaxPerHeist": 5}})
        raw["localUserIdProof"] = lua_table(self.h.lua, {
            "account": "user-a", "capturedAt": 0,
            "userId": 42})
        settings = lua_table(self.h.lua, {"sabotage": {
            "enabled": True}})
        self.step(raw, settings)
        self.assertEqual(self.h.transport["sent"][1]
                         ["feature"], "sabotage")
        self.assertEqual(self.runtime.checkpoint.SabotageUsage(
            self.runtime.checkpoint, day, 0)["attempts"], 1)
        self.h.transport["callbacks"][1](lua_table(self.h.lua,
                                                      {"ok": True}))
        self.h.at(1)
        after = self.raw(revision=2)
        after["native"]["family"] = lua_table(self.h.lua, {"id": "own-family"})
        after["heistBoardProof"] = lua_table(self.h.lua, {
            "account": "user-a", "capturedAt": 1,
            "board": {"ok": True, "serverNow": server_now,
                      "rows": [{**row, "sabosUsed": 1}],
                      "favorsLeft": 10,
                      "saboFavorCost": 2, "saboEnergyCost": 3,
                      "saboMaxPerHeist": 5}})
        after["localUserIdProof"] = lua_table(self.h.lua, {
            "account": "user-a", "capturedAt": 1,
            "userId": 42})
        self.step(after, settings)
        self.assertEqual(self.runtime.Status(self.runtime)
                         ["outcomes"]["sabotage"], "confirmed")

    def test_global_boss_claim_uses_shared_broker_and_run_cap(self):
        self.runtime.Resume(self.runtime)
        raw = self.raw()
        server_now = raw["native"]["serverNow"]
        start = server_now - 1000
        run = "hellfire_" + str(start)
        raw["native"]["gb"] = lua_table(self.h.lua, {
            "run": run, "dmg": 50, "hits": 2,
            "claimed": False})
        event = {"id": "hellfire", "startAt": start,
                 "endAt": server_now + 1000, "status": "done",
                 "hp": 10000, "dmg": 100,
                 "resultAt": server_now - 50}
        raw["globalBossProof"] = lua_table(self.h.lua, {
            "account": "user-a", "capturedAt": 0,
            "event": event})
        raw["localUserIdProof"] = lua_table(self.h.lua, {
            "account": "user-a", "capturedAt": 0,
            "userId": 42})
        settings = lua_table(self.h.lua, {"globalBossClaim": {
            "enabled": True}})
        self.step(raw, settings)
        self.assertEqual(self.h.transport["sent"][1]
                         ["feature"], "globalBossClaim")
        self.assertEqual(self.runtime.checkpoint.GlobalClaimUsage(
            self.runtime.checkpoint, run, 0)["attempts"], 1)
        self.h.transport["callbacks"][1](lua_table(self.h.lua,
                                                      {"ok": True, "medals": 2, "won": [{"i":"crate_loot","n":1}]}))
        self.h.at(1)
        after = self.raw(revision=2)
        after.native.inventoryBound.event_medal=2
        after.native.inventory.crate_loot=1
        after["native"]["gb"] = lua_table(self.h.lua, {
            "run": run, "dmg": 50, "hits": 2,
            "claimed": True, "medals":2, "won":[{"i":"crate_loot","n":1}]})
        after["globalBossProof"] = lua_table(self.h.lua, {
            "account": "user-a", "capturedAt": 1,
            "event": event})
        after["localUserIdProof"] = lua_table(self.h.lua, {
            "account": "user-a", "capturedAt": 1,
            "userId": 42})
        self.step(after, settings)
        self.assertEqual(self.runtime.Status(self.runtime)
                         ["outcomes"]["globalBossClaim"], "confirmed")

    def test_current_family_stage_claim_uses_shared_broker(self):
        self.runtime.Resume(self.runtime)
        raw = self.raw()
        now = raw["native"]["serverNow"]
        state = {"week": 100, "famId": 9, "inFamily": True,
                 "stage": 3, "resetAt": now + 1000,
                 "freeMax": 3, "freeUsed": 1,
                 "freeRegen": 60, "tickets": 0,
                 "myDmg": 100, "claims": [{"week": 100,
                     "stage": 1, "expiresAt": now + 500, "cash": 10}],
                 "claimedStages": []}
        raw["familyTakedownProof"] = lua_table(self.h.lua, {
            "account": "user-a", "capturedAt": 0,
            "state": state})
        raw["familyClaimUsageProof"] = lua_table(self.h.lua, {
            "account": "user-a", "capturedAt": 0,
            "week": 100, "stages": [1]})  # Caller proof is discarded.
        settings = lua_table(self.h.lua, {"familyBossClaims": {
            "enabled": True}})
        self.step(raw, settings)
        self.assertEqual(self.h.transport["sent"][1]
                         ["feature"], "familyBossClaims")
        self.assertEqual(self.runtime.checkpoint.FamilyClaimUsage(
            self.runtime.checkpoint, 100, 0)["stages"][1], 1)
        self.h.transport["callbacks"][1](lua_table(self.h.lua,
            {"ok": True}))
        self.h.at(1)
        after = self.raw(revision=2)
        after.native.cash = raw.native.cash + 10
        state["claims"] = []
        state["claimedStages"] = [1]
        after["familyTakedownProof"] = lua_table(self.h.lua, {
            "account": "user-a", "capturedAt": 1,
            "state": state})
        self.step(after, settings)
        self.assertEqual(self.runtime.Status(self.runtime)
                         ["outcomes"]["familyBossClaims"],
                         "confirmed")

    def test_free_family_attack_uses_shared_broker_without_ticket(self, fam_id=9):
        self.runtime.Resume(self.runtime)
        raw = self.raw()
        now = raw["native"]["serverNow"]
        raw["native"]["stats"] = lua_table(self.h.lua,
            {"maxHealth": 100})
        raw["native"]["pools"] = lua_table(self.h.lua,
            {"health": 80, "stamina": 5, "energy": 5})
        state = {"week": 100, "famId": fam_id, "inFamily": True,
            "stage": 2, "resetAt": now + 1000,
            "freeMax": 3, "freeUsed": 1,
            "freeRegen": 60, "tickets": 0,
            "myDmg": 100, "claims": [], "claimedStages": []}
        raw["familyTakedownProof"] = lua_table(self.h.lua, {
            "account": "user-a", "capturedAt": 0,
            "state": state})
        raw["familyAttackProof"] = lua_table(self.h.lua, {
            "account": "user-a", "capturedAt": 0,
            "week": 100, "famId": fam_id, "stage": 2,
            "staminaCost": 1, "hitBackMax": 20})
        raw["familyAttackUsageProof"] = lua_table(self.h.lua, {
            "account": "user-a", "capturedAt": 0,
            "week": 100, "famId": fam_id,
            "hits": 25, "lastServerNow": now})
        settings = lua_table(self.h.lua, {"familyBossAttacks": {
            "enabled": True}})
        self.step(raw, settings)
        self.assertEqual(self.h.transport["sent"][1]
                         ["feature"], "familyBossAttacks")
        self.assertEqual(self.runtime.checkpoint.FamilyAttackUsage(
            self.runtime.checkpoint, 100, fam_id, 0)["hits"], 1)
        self.h.transport["callbacks"][1](lua_table(self.h.lua,
            {"ok": True, "dmg": 50, "tickets": 0,
             "freeLeft": 1}))
        self.h.at(1)
        after = self.raw(revision=2)
        after["native"]["stats"] = lua_table(self.h.lua,
            {"maxHealth": 100})
        after["native"]["pools"] = lua_table(self.h.lua,
            {"health": 70, "stamina": 4, "energy": 5})
        state["freeUsed"] = 2
        state["myDmg"] = 150
        after["familyTakedownProof"] = lua_table(self.h.lua, {
            "account": "user-a", "capturedAt": 1,
            "state": state})
        after["familyAttackProof"] = lua_table(self.h.lua, {
            "account": "user-a", "capturedAt": 1,
            "week": 100, "famId": fam_id, "stage": 2,
            "staminaCost": 1, "hitBackMax": 20})
        self.step(after, settings)
        self.assertEqual(self.runtime.Status(self.runtime)
                         ["outcomes"]["familyBossAttacks"],
                         "confirmed")

    def test_string_family_attack_keeps_its_allowance_after_reload(self):
        self.test_free_family_attack_uses_shared_broker_without_ticket("family-native-abc")
        cp = self.h.load("src/storage/Checkpoint.luau").new(self.storage, None, None,
            self.h.load("src/storage/PendingAction.luau"))
        self.assertIsNone(cp.Load(cp, "user-a", self.h.session["place"], "release-a")[1])
        self.assertEqual(cp.FamilyAttackUsage(cp, 100, "family-native-abc", 1).hits, 1)
        self.assertIsNone(cp.FamilyAttackUsage(cp, 100, "other-family", 1))

    def test_global_boss_attack_uses_shared_broker_and_personal_hit(self):
        self.runtime.Resume(self.runtime)
        raw = self.raw()
        server_now = raw["native"]["serverNow"]
        start = server_now - 100
        run = "hellfire_" + str(start)
        raw["native"]["stats"] = lua_table(self.h.lua,
            {"maxHealth": 100})
        raw["native"]["pools"]["health"] = 80
        raw["native"]["pools"]["stamina"] = 10
        raw["native"]["gb"] = lua_table(self.h.lua, {
            "run": run, "hits": 2, "dmg": 50,
            "claimed": False})
        event = {"id": "hellfire", "startAt": start,
                 "endAt": server_now + 1000, "status": "live",
                 "hp": 10000, "dmg": 100}
        raw["globalBossProof"] = lua_table(self.h.lua, {
            "account": "user-a", "capturedAt": 0,
            "event": event})
        raw["localUserIdProof"] = lua_table(self.h.lua, {
            "account": "user-a", "capturedAt": 0,
            "userId": 42})
        settings = lua_table(self.h.lua, {"globalBossAttack": {
            "enabled": True}})
        self.step(raw, settings)
        self.assertEqual(self.h.transport["sent"][1]
                         ["feature"], "globalBossAttack")
        self.assertEqual(self.runtime.checkpoint.GlobalAttackUsage(
            self.runtime.checkpoint, run, 0)["hits"], 1)
        self.h.transport["callbacks"][1](lua_table(self.h.lua,
            {"ok": True, "dmg": 75}))
        self.h.at(1)
        after = self.raw(revision=2)
        after["native"]["gb"] = lua_table(self.h.lua, {
            "run": run, "hits": 3, "dmg": 125,
            "claimed": False})
        after["globalBossProof"] = lua_table(self.h.lua, {
            "account": "user-a", "capturedAt": 1,
            "event": event})
        after["localUserIdProof"] = lua_table(self.h.lua, {
            "account": "user-a", "capturedAt": 1,
            "userId": 42})
        self.step(after, settings)
        self.assertEqual(self.runtime.Status(self.runtime)
                         ["outcomes"]["globalBossAttack"], "confirmed")

    def test_planner_cannot_offer_under_another_feature_identity(self):
        self.runtime["features"]["operations"]["planner"]["propose"] = (
            self.h.lua.eval("function() return { feature = 'jobs', actionKey = 'a' } end"))
        self.runtime.Resume(self.runtime)
        self.step(settings=self.settings(collect=False))
        self.assertEqual(self.h.transport["sent"][1]["feature"], "jobs")
        self.assertIn("mismatch", self.runtime.Status(self.runtime)
                      ["reasons"]["operations"].lower())

    def test_disabled_and_stopped_runtime_cannot_send(self):
        self.runtime.Resume(self.runtime)
        self.step(settings=self.settings(False, False, False))
        self.assertEqual(len(self.h.transport["sent"]), 0)
        self.runtime.Stop(self.runtime)
        self.step()
        self.assertEqual(len(self.h.transport["sent"]), 0)

    def test_checkpoint_failure_blocks_every_feature(self):
        self.storage["Write"] = self.h.lua.eval("function() return false end")
        self.runtime.Resume(self.runtime)
        self.step()
        self.assertEqual(len(self.h.transport["sent"]), 0)
        self.assertTrue(self.runtime.Status(self.runtime)["storageFault"])

    def test_shared_runtime_appears_on_three_existing_ember_panels(self):
        ember = self.h.load("tests/ember_double.lua")()
        deps = lua_table(self.h.lua, {
            "Ember": ember, "Catalog": self.h.load("src/ui/Catalog.luau"),
            "Settings": self.h.load("src/storage/Settings.luau"),
            "EmberAdapter": self.h.load("src/ui/EmberAdapter.luau"),
            "AutomationRuntime": self.runtime,
        })
        self.app = self.h.load("src/App.luau").start(deps)
        for feature in ("jobs", "operations", "collect"):
            self.app.Set(self.app, feature + ".enabled", True)
        self.app.Set(self.app, "operations.policy", "Highest tier")
        self.app.Resume(self.app)
        self.app.Step(self.app, self.raw())
        self.assertEqual(self.h.transport["sent"][1]["feature"], "collect")
        self.assertIn("Awaiting", self.app.ui.features.collect.status.value)
        self.assertIn("broker", self.app.ui.features.jobs.status.value.lower())
        self.h.transport["callbacks"][1](lua_table(self.h.lua, {"ok": True}))
        self.app.Step(self.app, self.raw())
        self.assertNotIn("Confirmed", self.app.ui.features.collect.status.value)
        self.h.at(1)
        self.app.Step(self.app, self.raw(2, active=[]))
        self.assertIn("confirmed", self.app.ui.features.collect.status.value.lower())
        self.assertIn("Awaiting", self.app.ui.features.operations.status.value)

    def test_new_descriptors_receive_their_separate_app_switches(self):
        ember = self.h.load("tests/ember_double.lua")()
        deps = lua_table(self.h.lua, {
            "Ember": ember, "Catalog": self.h.load("src/ui/Catalog.luau"),
            "Settings": self.h.load("src/storage/Settings.luau"),
            "EmberAdapter": self.h.load("src/ui/EmberAdapter.luau"),
            "AutomationRuntime": self.runtime,
        })
        self.app = self.h.load("src/App.luau").start(deps)
        for feature in ("heists", "favors", "sabotage",
                        "bosses", "globalBossAttack",
                        "globalBossClaim", "familyBossAttacks",
                        "familyBossClaims",
                        "properties"):
            self.assertTrue(self.app.Set(self.app,
                feature + ".enabled", True)[0])
        self.app.Resume(self.app)
        self.app.Step(self.app, self.raw())
        status = self.runtime.Status(self.runtime)
        for feature in ("heists", "favors", "sabotage",
                        "bosses", "globalBossAttack",
                        "globalBossClaim", "familyBossAttacks",
                        "familyBossClaims",
                        "properties"):
            self.assertNotEqual(status["reasons"][feature], "Disabled")
            self.assertNotIn("UI only", self.app.ui.features[feature]
                             .status.value)

    def test_skills_ui_choice_is_visible_and_bounded(self):
        ember = self.h.load("tests/ember_double.lua")()
        deps = lua_table(self.h.lua, {
            "Ember": ember, "Catalog": self.h.load("src/ui/Catalog.luau"),
            "Settings": self.h.load("src/storage/Settings.luau"),
            "EmberAdapter": self.h.load("src/ui/EmberAdapter.luau"),
            "AutomationRuntime": self.runtime,
        })
        self.app = self.h.load("src/App.luau").start(deps)
        self.assertTrue(self.app.ui.features.skills.custom.visible)
        self.assertEqual(self.app.model["values"]["skills.custom.maxAllocations"], 1)
        self.assertFalse(self.app.Set(self.app, "skills.custom.batchSize", 101)[0])
        self.app.Set(self.app, "skills.enabled", True)
        self.app.Resume(self.app)
        self.app.Step(self.app, self.raw())
        self.assertEqual(self.h.transport["sent"][1]["feature"], "skills")
        self.assertIn("Awaiting", self.app.ui.features.skills.status.value)

    def test_group_panel_shows_shared_broker_status(self):
        ember = self.h.load("tests/ember_double.lua")()
        deps = lua_table(self.h.lua, {
            "Ember": ember, "Catalog": self.h.load("src/ui/Catalog.luau"),
            "Settings": self.h.load("src/storage/Settings.luau"),
            "EmberAdapter": self.h.load("src/ui/EmberAdapter.luau"),
            "AutomationRuntime": self.runtime,
        })
        self.app = self.h.load("src/App.luau").start(deps)
        self.app.Set(self.app, "groupBonus.enabled", True)
        self.app.Resume(self.app)
        self.app.Step(self.app, self.raw())
        self.assertEqual(self.h.transport["sent"][1]["feature"], "groupBonus")
        self.assertIn("Awaiting", self.app.ui.features.groupBonus.status.value)

    def test_monthly_panel_reports_native_disabled_config(self):
        ember = self.h.load("tests/ember_double.lua")()
        deps = lua_table(self.h.lua, {
            "Ember": ember, "Catalog": self.h.load("src/ui/Catalog.luau"),
            "Settings": self.h.load("src/storage/Settings.luau"),
            "EmberAdapter": self.h.load("src/ui/EmberAdapter.luau"),
            "AutomationRuntime": self.runtime,
        })
        self.app = self.h.load("src/App.luau").start(deps)
        self.app.Set(self.app, "monthlyRewards.enabled", True)
        self.app.Resume(self.app)
        self.app.Step(self.app, self.raw())
        self.assertEqual(len(self.h.transport["sent"]), 0)
        self.assertIn("disabled", self.app.ui.features.monthlyRewards.status.value)

    def test_earned_trophy_panel_reports_shared_status(self):
        ember = self.h.load("tests/ember_double.lua")()
        deps = lua_table(self.h.lua, {
            "Ember": ember, "Catalog": self.h.load("src/ui/Catalog.luau"),
            "Settings": self.h.load("src/storage/Settings.luau"),
            "EmberAdapter": self.h.load("src/ui/EmberAdapter.luau"),
            "AutomationRuntime": self.runtime,
        })
        self.app = self.h.load("src/App.luau").start(deps)
        self.app.Set(self.app, "trophies.enabled", True)
        self.app.Resume(self.app)
        self.app.Step(self.app, self.raw())
        self.assertEqual(self.h.transport["sent"][1]["feature"], "trophies")
        self.assertIn("Awaiting", self.app.ui.features.trophies.status.value)

    def test_playtime_panel_reports_shared_status(self):
        ember = self.h.load("tests/ember_double.lua")()
        deps = lua_table(self.h.lua, {
            "Ember": ember, "Catalog": self.h.load("src/ui/Catalog.luau"),
            "Settings": self.h.load("src/storage/Settings.luau"),
            "EmberAdapter": self.h.load("src/ui/EmberAdapter.luau"),
            "AutomationRuntime": self.runtime,
        })
        self.app = self.h.load("src/App.luau").start(deps)
        self.app.Set(self.app, "playtime.enabled", True)
        self.app.Resume(self.app)
        self.app.Step(self.app, self.raw())
        self.assertEqual(self.h.transport["sent"][1]["feature"], "playtime")
        self.assertIn("Awaiting", self.app.ui.features.playtime.status.value)

    def test_contract_panel_reports_shared_status(self):
        ember = self.h.load("tests/ember_double.lua")()
        deps = lua_table(self.h.lua, {
            "Ember": ember, "Catalog": self.h.load("src/ui/Catalog.luau"),
            "Settings": self.h.load("src/storage/Settings.luau"),
            "EmberAdapter": self.h.load("src/ui/EmberAdapter.luau"),
            "AutomationRuntime": self.runtime,
        })
        self.app = self.h.load("src/App.luau").start(deps)
        self.app.Set(self.app, "contracts.enabled", True)
        self.app.Resume(self.app)
        raw = self.raw()
        now = raw["native"]["serverNow"]
        raw["native"]["derived"]["contractDayReset"] = now + 3600
        raw["native"]["derived"]["contractWeekReset"] = now + 86400
        self.app.Step(self.app, raw)
        self.assertEqual(self.h.transport["sent"][1]["feature"], "contracts")
        self.assertIn("Awaiting", self.app.ui.features.contracts.status.value)

    def test_bonus_panel_reports_shared_status(self):
        ember = self.h.load("tests/ember_double.lua")()
        deps = lua_table(self.h.lua, {
            "Ember": ember, "Catalog": self.h.load("src/ui/Catalog.luau"),
            "Settings": self.h.load("src/storage/Settings.luau"),
            "EmberAdapter": self.h.load("src/ui/EmberAdapter.luau"),
            "AutomationRuntime": self.runtime,
        })
        self.app = self.h.load("src/App.luau").start(deps)
        self.app.Set(self.app, "bonuses.enabled", True)
        self.app.Resume(self.app)
        raw = self.raw()
        now = raw["native"]["serverNow"]
        raw["native"]["derived"]["contractDayReset"] = now + 3600
        raw["native"]["derived"]["contractWeekReset"] = now + 86400
        for row in raw["native"]["contracts"]["daily"].values():
            row["claimed"] = True
        self.app.Step(self.app, raw)
        self.assertEqual(self.h.transport["sent"][1]["feature"], "bonuses")
        self.assertIn("Awaiting", self.app.ui.features.bonuses.status.value)

    def test_free_briefcase_panel_reports_shared_status(self):
        ember = self.h.load("tests/ember_double.lua")()
        deps = lua_table(self.h.lua, {
            "Ember": ember, "Catalog": self.h.load("src/ui/Catalog.luau"),
            "Settings": self.h.load("src/storage/Settings.luau"),
            "EmberAdapter": self.h.load("src/ui/EmberAdapter.luau"),
            "AutomationRuntime": self.runtime,
        })
        self.app = self.h.load("src/App.luau").start(deps)
        self.app.Set(self.app, "briefcases.enabled", True)
        self.app.Resume(self.app)
        self.app.Step(self.app, self.raw())
        self.assertEqual(self.h.transport["sent"][1]["feature"], "briefcases")
        self.assertIn("Awaiting", self.app.ui.features.briefcases.status.value)

    def test_bank_panel_has_limits_and_reports_shared_status(self):
        ember = self.h.load("tests/ember_double.lua")()
        deps = lua_table(self.h.lua, {
            "Ember": ember, "Catalog": self.h.load("src/ui/Catalog.luau"),
            "Settings": self.h.load("src/storage/Settings.luau"),
            "EmberAdapter": self.h.load("src/ui/EmberAdapter.luau"),
            "AutomationRuntime": self.runtime,
        })
        self.app = self.h.load("src/App.luau").start(deps)
        self.assertEqual(self.app.model["values"]["bank.custom.depositThreshold"],
                         10000)
        self.assertFalse(self.app.Set(self.app,
            "bank.custom.cashToKeep", -1)[0])
        self.app.Set(self.app, "bank.enabled", True)
        self.app.Resume(self.app)
        raw = self.raw()
        raw["native"]["cash"] = 50000
        self.app.Step(self.app, raw)
        self.assertEqual(self.h.transport["sent"][1]["feature"], "bank")
        self.assertIn("Awaiting", self.app.ui.features.bank.status.value)

    def test_safehouse_panel_reports_shared_status(self):
        ember = self.h.load("tests/ember_double.lua")()
        deps = lua_table(self.h.lua, {
            "Ember": ember, "Catalog": self.h.load("src/ui/Catalog.luau"),
            "Settings": self.h.load("src/storage/Settings.luau"),
            "EmberAdapter": self.h.load("src/ui/EmberAdapter.luau"),
            "AutomationRuntime": self.runtime,
        })
        self.app = self.h.load("src/App.luau").start(deps)
        self.assertFalse(self.app.Set(self.app,
            "safehouse.custom.maxTier", 19)[0])
        self.app.Set(self.app, "safehouse.enabled", True)
        self.app.Resume(self.app)
        raw = self.raw()
        raw["native"]["cash"] = 10000
        self.app.Step(self.app, raw)
        self.assertEqual(self.h.transport["sent"][1]["feature"], "safehouse")
        self.assertIn("Awaiting", self.app.ui.features.safehouse.status.value)

    def test_withdraw_panel_requires_purchase_switch(self):
        ember = self.h.load("tests/ember_double.lua")()
        deps = lua_table(self.h.lua, {
            "Ember": ember, "Catalog": self.h.load("src/ui/Catalog.luau"),
            "Settings": self.h.load("src/storage/Settings.luau"),
            "EmberAdapter": self.h.load("src/ui/EmberAdapter.luau"),
            "AutomationRuntime": self.runtime,
        })
        self.app = self.h.load("src/App.luau").start(deps)
        self.app.Set(self.app, "withdraw.enabled", True)
        self.app.Resume(self.app)
        raw = self.raw()
        raw["native"]["banked"] = 20000
        raw["fundingRequest"] = lua_table(self.h.lua, {
            "session": "run-a", "account": "user-a",
            "place": "73897506680154", "release": "release-a",
            "revision": 1, "capturedAt": 0,
            "purpose": "safehouse", "purchaseKey": "safehouse:4",
            "requiredCash": 8000})
        self.app.Step(self.app, raw)
        self.assertEqual(len(self.h.transport["sent"]), 0)
        self.app.Set(self.app, "safehouse.enabled", True)
        self.app.Step(self.app, raw)
        self.assertEqual(self.h.transport["sent"][1]["feature"], "withdraw")
        self.assertIn("Awaiting", self.app.ui.features.withdraw.status.value)

    def test_money_app_native_withdraw_replans_enabled_purchase(self):
        executor = self.h.lua.execute("""return {
            queued = {}, calls = {},
            Schedule = function(self, fn)
                self.queued[#self.queued + 1] = fn
            end,
            Invoke = function(self, remote, method, ...)
                self.calls[#self.calls + 1] = { remote = remote,
                    method = method, arity = select('#', ...),
                    args = table.pack(...) }
                return { ok = true }
            end,
            Drain = function(self)
                local pending = self.queued
                self.queued = {}
                for _, fn in ipairs(pending) do fn() end
            end,
        }""")
        adapter = self.h.load("src/transport/NativeDispatchAdapter.luau").new(
            self.h.load("src/transport/NativeCallPlan.luau"), executor)
        self.runtime["session"]["broker"]["transport"] = adapter
        ember = self.h.load("tests/ember_double.lua")()
        app = self.h.load("src/App.luau").start(lua_table(self.h.lua, {
            "Ember": ember, "Catalog": self.h.load("src/ui/Catalog.luau"),
            "Settings": self.h.load("src/storage/Settings.luau"),
            "EmberAdapter": self.h.load("src/ui/EmberAdapter.luau"),
            "AutomationRuntime": self.runtime,
        }))
        app.Set(app, "withdraw.enabled", True)
        app.Set(app, "safehouse.enabled", True)
        app.Set(app, "safehouse.custom.maxTier", 4)
        app.Resume(app)
        before = self.raw()
        before["native"]["banked"] = 20000
        app.Step(app, before)
        executor.Drain(executor)
        self.assertEqual(executor["calls"][1]["remote"], "Withdraw")
        self.assertEqual(executor["calls"][1]["method"], "InvokeServer")
        self.assertEqual(executor["calls"][1]["arity"], 1)
        self.assertEqual(executor["calls"][1]["args"][1], 2000)
        self.h.at(1)
        funded = self.raw(2)
        funded["native"]["cash"] = 3000
        funded["native"]["banked"] = 18000
        app.Step(app, funded)
        self.assertEqual(self.runtime.Status(self.runtime)["outcomes"]["withdraw"],
                         "confirmed")
        executor.Drain(executor)
        self.assertEqual(executor["calls"][2]["remote"], "UpgradeSafehouse")
        self.assertEqual(executor["calls"][2]["arity"], 0)
        self.h.at(2)
        upgraded = self.raw(3)
        upgraded["native"]["cash"] = 0
        upgraded["native"]["banked"] = 18000
        upgraded["native"]["safehouse"] = 4
        app.Step(app, upgraded)
        self.assertEqual(self.runtime.Status(self.runtime)["outcomes"]["safehouse"],
                         "confirmed")
        self.h.at(3)
        capped = self.raw(4)
        capped["native"]["safehouse"] = 4
        capped["native"]["cash"] = 0
        capped["native"]["banked"] = 18000
        app.Step(app, capped)
        executor.Drain(executor)
        self.assertEqual(len(list(executor["calls"].values())), 2)
        app.Destroy(app)

    def test_money_app_native_deposit_preserves_selected_cash(self):
        executor = self.h.lua.execute("""return {
            queued = {}, calls = {},
            Schedule = function(self, fn)
                self.queued[#self.queued + 1] = fn
            end,
            Invoke = function(self, remote, method, amount)
                self.calls[#self.calls + 1] = { remote = remote,
                    method = method, amount = amount }
                return { ok = true, fee = 3500, kept = 31500 }
            end,
            Drain = function(self)
                local pending = self.queued
                self.queued = {}
                for _, fn in ipairs(pending) do fn() end
            end,
        }""")
        adapter = self.h.load("src/transport/NativeDispatchAdapter.luau").new(
            self.h.load("src/transport/NativeCallPlan.luau"), executor)
        self.runtime["session"]["broker"]["transport"] = adapter
        app = self.h.load("src/App.luau").start(lua_table(self.h.lua, {
            "Ember": self.h.load("tests/ember_double.lua")(),
            "Catalog": self.h.load("src/ui/Catalog.luau"),
            "Settings": self.h.load("src/storage/Settings.luau"),
            "EmberAdapter": self.h.load("src/ui/EmberAdapter.luau"),
            "AutomationRuntime": self.runtime,
        }))
        app.Set(app, "bank.enabled", True)
        app.Set(app, "bank.custom.cashToKeep", 15000)
        app.Resume(app)
        before = self.raw()
        before["native"]["cash"] = 50000
        app.Step(app, before)
        executor.Drain(executor)
        self.assertEqual(executor["calls"][1]["remote"], "BankDeposit")
        self.assertEqual(executor["calls"][1]["method"], "InvokeServer")
        self.assertEqual(executor["calls"][1]["amount"], 35000)
        self.h.at(1)
        after = self.raw(2)
        after["native"]["cash"] = 15000
        after["native"]["banked"] = 31600
        app.Step(app, after)
        self.assertEqual(self.runtime.Status(self.runtime)["outcomes"]["bank"],
                         "confirmed")
        app.Destroy(app)

    def test_shared_runtime_pauses_on_ember_render_failure(self):
        ember = self.h.load("tests/ember_double.lua")()
        deps = lua_table(self.h.lua, {
            "Ember": ember, "Catalog": self.h.load("src/ui/Catalog.luau"),
            "Settings": self.h.load("src/storage/Settings.luau"),
            "EmberAdapter": self.h.load("src/ui/EmberAdapter.luau"),
            "AutomationRuntime": self.runtime,
        })
        self.app = self.h.load("src/App.luau").start(deps)
        self.app.Set(self.app, "collect.enabled", True)
        self.app.Resume(self.app)
        self.app.ui.features.collect.status.throwNext = True
        result = self.app.Step(self.app, self.raw())
        self.assertFalse(result[0])
        self.assertEqual(len(self.h.transport["sent"]), 0)
        self.assertEqual(self.runtime.Status(self.runtime)["state"], "paused")

    def tearDown(self):
        if hasattr(self, "app"):
            self.app.Destroy(self.app)
        else:
            self.runtime.Close(self.runtime)


if __name__ == "__main__":
    unittest.main()
