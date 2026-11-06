"""Combat owns six action slices and two explicitly blocked fights."""
import unittest

from engine_harness import Harness, lua_table


ROWS = [
    ("bosses", "BossesState", "Bosses", "BossesEvidence"),
    ("globalBossAttack", "GlobalBossAttackState", "GlobalBossAttack", "GlobalBossAttackEvidence"),
    ("globalBossClaim", "GlobalBossClaimState", "GlobalBossClaim", "GlobalBossClaimEvidence"),
    ("familyBossAttacks", "FamilyBossAttackState", "FamilyBossAttacks", "FamilyBossAttacksEvidence"),
    ("familyBossClaims", "FamilyBossClaimState", "FamilyBossClaims", "FamilyBossClaimsEvidence"),
    ("bossShop", "BossShopBuyState", "BossShopBuy", "BossShopBuyEvidence"),
]


class CombatTabModuleTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.entry = self.h.load("src/tabs/combat/Module.luau")
        self.registry = self.h.load("src/engine/FeatureRegistry.luau")
        self.catalog = self.h.load("src/ui/Catalog.luau")
        self.deps = {}
        self.deps["HitListQuery"] = self.h.load("src/tabs/combat/HitListQuery.luau")
        self.deps["PlayerTargetState"] = self.h.load(
            "src/tabs/combat/PlayerTargetState.luau")
        self.deps["BlockedFight"] = self.h.load(
            "src/tabs/combat/BlockedFight.luau")
        self.deps["combatRules"] = {"hospitalHealth": 20,
            "staminaCost": 1, "dailyTargetCap": 5}
        self.deps["identity"] = self.h.session
        for _, reader, planner, evidence in ROWS:
            self.deps[reader] = self.h.load("src/game/" + reader + ".luau")
            self.deps[planner] = self.h.load("src/features/" + planner + ".luau")
            self.deps[evidence] = self.h.load("src/features/" + evidence + ".luau")

    def test_all_combat_controls_register_under_combat(self):
        tab = self.entry.new(lua_table(self.h.lua, self.deps))
        self.assertEqual(tab["id"], "combat")
        specs, reason = self.registry.fromTabs(
            lua_table(self.h.lua, [tab]), self.catalog)
        self.assertIsNone(reason)
        self.assertEqual([specs[i]["id"] for i in range(1, 9)],
                         ["combat", "warCombat"] + [row[0] for row in ROWS])
        for index in (1, 2):
            proposal, blocker = specs[index]["planner"].propose(None,
                lua_table(self.h.lua, {"enabled": True}))
            self.assertIsNone(proposal)
            self.assertIn("unverified", blocker)

    def test_missing_combat_piece_fails_at_tab_boundary(self):
        del self.deps["BossShopBuyEvidence"]
        with self.assertRaises(Exception):
            self.entry.new(lua_table(self.h.lua, self.deps))

    def test_current_boss_catalog_enriches_combat_snapshot(self):
        self.deps["NativeBossCatalog"] = self.h.load(
            "src/tabs/combat/NativeBossCatalog.luau")
        self.deps["bossStages"] = self.h.lua.execute("""return {
            MAX_STAGE = 100000,
            get = function(stage) return { stage = stage,
                level = 1, hp = 100, hitBackMax = 10 } end,
            crateUnlocked = function() return false end,
            SHOP = { gear = { { item = 'w_policebaton', price = 2500 } },
                crates = { { item = 'crate_loot', price = 14 } } },
        }""")
        self.deps["config"] = {"BOSS": {"staminaCost": 2}}
        self.deps["fingerprint"] = "a" * 64
        self.deps["release"] = "release-a"
        tab = self.entry.new(lua_table(self.h.lua, self.deps))
        raw = self.h.snapshot(native={"fullSync": True,
            "serverNow": 1792890000,
            "bossStage": {"best": 1}})
        enriched, reason = tab.Enrich(tab, raw)
        self.assertIsNone(reason)
        self.assertEqual(enriched.bossStageProof.stages[2].stage, 2)
        self.assertEqual(enriched.bossShopProof["items"][1].price, 2500)

    def test_missing_city_state_does_not_hide_independent_boss_rows(self):
        self.deps["NativeBossCatalog"] = self.h.load(
            "src/tabs/combat/NativeBossCatalog.luau")
        self.deps["bossStages"] = self.h.lua.execute("""return {
            MAX_STAGE = 100000,
            get = function(stage) return { stage = stage,
                level = 1, hp = 100, hitBackMax = 10 } end,
            crateUnlocked = function() return false end,
            SHOP = { gear = { { item = 'w_policebaton', price = 2500 } },
                crates = { { item = 'crate_loot', price = 14 } } },
        }""")
        self.deps["config"] = {"BOSS": {"staminaCost": 2}}
        self.deps["fingerprint"] = "a" * 64
        self.deps["release"] = "release-a"
        tab = self.entry.new(lua_table(self.h.lua, self.deps))
        raw = self.h.snapshot(native={"fullSync": True,
            "serverNow": 1792890000})
        enriched, reason = tab.Enrich(tab, raw)
        self.assertIsNone(reason)
        same = self.h.lua.eval("function(a, b) return a == b end")
        self.assertIsNone(enriched.bossStageProof)
        self.assertEqual(enriched.native.serverNow, raw.native.serverNow)

    def test_hit_list_call_and_staging_are_read_only_and_identity_bound(self):
        tab = self.entry.new(lua_table(self.h.lua, self.deps))
        call = tab.HitListCall(tab, True)
        self.assertEqual(call["remote"], "GetHitList")
        self.assertIs(call["args"][1], True)
        self.assertEqual(call["kind"], "readOnly")
        snapshot = self.h.snapshot(native={"fullSync": True})
        reply = lua_table(self.h.lua, {"ok": True, "list": [
            {"userId": 42, "name": "Target", "level": 10,
             "online": False, "stamina": 2, "shielded": 0}]})
        staged, reason = tab.StageHitList(tab, snapshot, reply)
        self.assertIsNone(reason)
        self.assertEqual(staged["hitListProof"]["rows"][1]["userId"], 42)
        reply["list"][1]["userId"] = 99
        self.assertEqual(staged["hitListProof"]["rows"][1]["userId"], 42)
        snapshot["account"] = "another-account"
        self.assertIsNone(tab.StageHitList(tab, snapshot, reply)[0])

    def test_current_mixed_boolean_and_numeric_shields_pass_through_tab_reader(self):
        tab = self.entry.new(lua_table(self.h.lua, self.deps))
        now = 2000000
        raw = self.h.snapshot(native={"fullSync": True, "serverNow": now,
            "pools": {"health": 80, "stamina": 3},
            "attackDaily": {"day": now // 86400, "counts": {}}})
        reply = lua_table(self.h.lua, {"ok": True, "list": [
            {"userId": 42, "name": "Target A", "level": 89, "shielded": False},
            {"userId": 43, "name": "Target B", "level": 136, "shielded": 14961},
            {"userId": 44, "name": "Target C", "level": 128, "shielded": True}]})
        staged, reason = tab.StageHitList(tab, raw, reply)
        self.assertIsNotNone(staged, reason)
        view, reason = tab.ReadTargets(tab, staged, lua_table(self.h.lua, {
            **self.h.session, "revision": 1, "capturedAt": 0, "serverNow": now}))
        self.assertIsNotNone(view, reason)
        self.assertEqual([row.shielded for row in view.rows.values()], [False, True, True])
        self.assertEqual([row.remainingDaily for row in view.rows.values()], [5, 5, 5])
        self.assertEqual(len(self.h.transport.sent), 0)

    def test_combat_tab_exposes_read_only_target_facts(self):
        tab = self.entry.new(lua_table(self.h.lua, self.deps))
        now = 2000000
        raw = self.h.snapshot(native={"fullSync": True, "serverNow": now,
            "pools": {"health": 80, "stamina": 3},
            "attackDaily": {"day": now // 86400, "counts": {"42": 1}}},
            hitListProof={"account": "user-a", "capturedAt": 0,
                "rows": [{"userId": 42, "name": "Target", "level": 10}]})
        context = lua_table(self.h.lua, {**self.h.session, "revision": 1,
            "capturedAt": 0, "serverNow": now})
        view, reason = tab.ReadTargets(tab, raw, context)
        self.assertIsNone(reason)
        self.assertEqual(view["rows"][1]["remainingDaily"], 4)

    def test_target_search_requires_matching_echo_and_never_sends(self):
        tab = self.entry.new(lua_table(self.h.lua, self.deps))
        call, reason = tab.SearchCall(tab, "Target")
        self.assertIsNone(reason)
        self.assertEqual(call["remote"], "SearchTarget")
        self.assertEqual(call["args"][1], "Target")
        self.assertEqual(call["kind"], "readOnly")
        self.assertIsNone(tab.SearchCall(tab, " " * 4)[0])
        snapshot = self.h.snapshot(native={"fullSync": True})
        reply = lua_table(self.h.lua, {"ok": True, "search": "Target",
            "list": [{"userId": 42, "name": "Target", "level": 10}]})
        staged, reason = tab.StageSearch(tab, snapshot, reply, "Target")
        self.assertIsNone(reason)
        self.assertEqual(staged["hitListProof"]["search"], "Target")
        self.assertIsNone(tab.StageSearch(tab, snapshot, reply, "Other")[0])


    def test_failed_current_global_source_erases_supplied_proof_without_hiding_city(self):
        source = self.h.lua.execute("""return {closed=false,
            Enrich=function() return nil,'source missing' end,
            Close=function(self) self.closed=true end}""")
        self.deps["globalBossSource"] = source
        tab = self.entry.new(lua_table(self.h.lua, self.deps))
        raw = self.h.snapshot(native={"fullSync": True},
            globalBossProof={"event": {"id": "untrusted"}}, localUserIdProof={"userId": 99})
        enriched, reason = tab.Enrich(tab, raw)
        self.assertIsNone(reason)
        self.assertIsNone(enriched.globalBossProof)
        self.assertIsNone(enriched.localUserIdProof)
        tab.Close(tab)
        self.assertTrue(source.closed)

    def test_actual_constructor_owns_history_but_keeps_unfinished_player_planner_blocked(self):
        self.deps['FightReceipts']=self.h.load('src/tabs/combat/FightReceipts.luau')
        self.deps['PlayerFightEvidence']=self.h.load('src/tabs/combat/PlayerFightEvidence.luau')
        self.deps['PlayerFightLedger']=self.h.load('src/tabs/combat/PlayerFightLedger.luau')
        self.deps['storage']=self.h.lua.execute("""return {strictRecovery=true,data={},Read=function(self,k) return self.data[k] end,
            Write=function(self,k,v) self.data[k]=v;return true end}""")
        tab=self.entry.new(lua_table(self.h.lua,self.deps));self.assertIsNotNone(tab.playerLedger)
        raw=self.h.snapshot();raw.playerFightHistoryProof=lua_table(self.h.lua,{'forged':True})
        enriched,why=tab.Enrich(tab,raw);self.assertIsNone(why)
        self.assertIsNone(enriched.playerFightHistoryProof.forged)
        self.assertEqual(len(enriched.playerFightHistoryProof.recent),0)
        spec=tab.Descriptors(tab)[1];self.assertIsNotNone(spec.recoverSaved)
        self.assertIsNotNone(spec.recordOutcome)
        self.assertIsNone(spec.planner.propose(None,lua_table(self.h.lua,{'enabled':True}))[0])
        tab.Close(tab);self.assertIsNone(tab.playerLedger.Proof(tab.playerLedger,raw))

    def test_current_profile_owner_is_constructed_and_closed_with_combat(self):
        self.deps['PlayerProfileQuery']=self.h.load('src/tabs/combat/PlayerProfileQuery.luau')
        self.deps['fingerprint']='a'*64
        self.deps['nativeReadSource']=self.h.lua.execute('return {Current=function() return true end,Friendship=function() return false end}')
        tab=self.entry.new(lua_table(self.h.lua,self.deps));self.assertIsNotNone(tab.playerProfiles)
        tab.Close(tab);self.assertIsNone(tab.playerProfiles.Read(tab.playerProfiles,self.h.snapshot()))


if __name__ == "__main__":
    unittest.main()
