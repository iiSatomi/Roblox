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


if __name__ == "__main__":
    unittest.main()
