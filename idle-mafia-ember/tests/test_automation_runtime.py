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
                Write = function(self, key, value) self.data[key] = value end }
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
        self.step(self.raw(3, active=[{"opId": "op_fence", "remaining": 600}]),
                  self.settings(operations=False, collect=False))
        self.assertEqual(self.h.transport["sent"][3]["feature"], "jobs")
        self.assertEqual(self.runtime.Status(self.runtime)["outcomes"]["operations"],
                         "confirmed")

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
            "energy": 2, "crateCount": 1}])
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
        after["native"]["cash"] = 7100
        self.step(after, settings)
        self.assertEqual(self.runtime.Status(self.runtime)
                         ["outcomes"]["safehouse"], "confirmed")

    def test_withdrawal_needs_enabled_purchase_purpose(self):
        self.runtime.Resume(self.runtime)
        settings = self.settings(False, False, False)
        settings["withdraw"] = lua_table(self.h.lua, {"enabled": True,
            "maxWithdrawal": 1000000, "allowOperations": False,
            "allowSafehouse": True})
        before = self.raw()
        before["native"]["banked"] = 20000
        before["fundingRequest"] = lua_table(self.h.lua, {
            "account": "user-a", "capturedAt": 0,
            "purpose": "safehouse", "purchaseKey": "safehouse:4",
            "requiredCash": 8000})
        self.step(before, settings)
        self.assertEqual(self.h.transport["sent"][1]["feature"], "withdraw")
        self.assertEqual(self.h.transport["sent"][1]["intent"]["amount"], 7000)
        self.h.transport["callbacks"][1](lua_table(self.h.lua, {"ok": True}))
        self.h.at(1)
        after = self.raw(2)
        after["native"]["cash"] = 8000
        after["native"]["banked"] = 13000
        self.step(after, settings)
        self.assertEqual(self.runtime.Status(self.runtime)
                         ["outcomes"]["withdraw"], "confirmed")

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
        self.step(newer, settings)
        self.assertEqual(self.runtime.Status(self.runtime)
                         ["outcomes"]["properties"], "confirmed")

    def test_heist_start_uses_shared_broker_and_exact_run(self):
        self.runtime.Resume(self.runtime)
        raw = self.raw()
        server_now = raw["native"]["serverNow"]
        raw["heistCatalog"] = lua_table(self.h.lua, [{
            "id": "h_low", "level": 10, "stake": 100,
            "energy": 2, "crateCount": 1}])
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
            "enabled": True, "policy": "Best reward"}})
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
        server_now = raw["native"]["serverNow"]
        day = server_now // 86400
        raw["native"]["pools"]["energy"] = 20
        raw["heistCatalog"] = lua_table(self.h.lua, [{
            "id": "h_low", "level": 10, "stake": 100,
            "energy": 2}])
        row = {"id": "run-1", "ownerId": 99,
               "heistId": "h_low", "endsAt": server_now + 300,
               "friend": False, "helpsUsed": 0, "sabosUsed": 0}
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
                                                      {"ok": True}))
        self.h.at(1)
        after = self.raw(revision=2)
        after["native"]["gb"] = lua_table(self.h.lua, {
            "run": run, "dmg": 50, "hits": 2,
            "claimed": True})
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
                     "stage": 1, "expiresAt": now + 500}],
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
        state["claims"] = []
        state["claimedStages"] = [1]
        after["familyTakedownProof"] = lua_table(self.h.lua, {
            "account": "user-a", "capturedAt": 1,
            "state": state})
        self.step(after, settings)
        self.assertEqual(self.runtime.Status(self.runtime)
                         ["outcomes"]["familyBossClaims"],
                         "confirmed")

    def test_free_family_attack_uses_shared_broker_without_ticket(self):
        self.runtime.Resume(self.runtime)
        raw = self.raw()
        now = raw["native"]["serverNow"]
        raw["native"]["stats"] = lua_table(self.h.lua,
            {"maxHealth": 100})
        raw["native"]["pools"] = lua_table(self.h.lua,
            {"health": 80, "stamina": 5, "energy": 5})
        state = {"week": 100, "famId": 9, "inFamily": True,
            "stage": 2, "resetAt": now + 1000,
            "freeMax": 3, "freeUsed": 1,
            "freeRegen": 60, "tickets": 0,
            "myDmg": 100, "claims": [], "claimedStages": []}
        raw["familyTakedownProof"] = lua_table(self.h.lua, {
            "account": "user-a", "capturedAt": 0,
            "state": state})
        raw["familyAttackProof"] = lua_table(self.h.lua, {
            "account": "user-a", "capturedAt": 0,
            "week": 100, "famId": 9, "stage": 2,
            "staminaCost": 1, "hitBackMax": 20})
        raw["familyAttackUsageProof"] = lua_table(self.h.lua, {
            "account": "user-a", "capturedAt": 0,
            "week": 100, "famId": 9,
            "hits": 25, "lastServerNow": now})
        settings = lua_table(self.h.lua, {"familyBossAttacks": {
            "enabled": True}})
        self.step(raw, settings)
        self.assertEqual(self.h.transport["sent"][1]
                         ["feature"], "familyBossAttacks")
        self.assertEqual(self.runtime.checkpoint.FamilyAttackUsage(
            self.runtime.checkpoint, 100, 9, 0)["hits"], 1)
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
            "week": 100, "famId": 9, "stage": 2,
            "staminaCost": 1, "hitBackMax": 20})
        self.step(after, settings)
        self.assertEqual(self.runtime.Status(self.runtime)
                         ["outcomes"]["familyBossAttacks"],
                         "confirmed")

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
            "account": "user-a", "capturedAt": 0,
            "purpose": "safehouse", "purchaseKey": "safehouse:4",
            "requiredCash": 8000})
        self.app.Step(self.app, raw)
        self.assertEqual(len(self.h.transport["sent"]), 0)
        self.app.Set(self.app, "safehouse.enabled", True)
        self.app.Step(self.app, raw)
        self.assertEqual(self.h.transport["sent"][1]["feature"], "withdraw")
        self.assertIn("Awaiting", self.app.ui.features.withdraw.status.value)

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
