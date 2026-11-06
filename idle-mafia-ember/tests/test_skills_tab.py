"""Skills source adapter copies current cost steps into the tab."""
import unittest

from engine_harness import Harness, lua_table


RULES = {stat: ({"baseCost": 1, "costMultiplier": 2}
                if stat == "property" else
                {"baseCost": 1,
                 "costEvery": 3 if stat in ("attack", "defense") else 5})
         for stat in ("energy", "stamina", "health", "attack",
                      "defense", "property")}


class SkillsTabTests(unittest.TestCase):
    def test_reviewed_rules_feed_existing_planner(self):
        h = Harness()
        module = h.load("src/tabs/skills/Module.luau")
        deps = lua_table(h.lua, {
            "NativeSkillCatalog": h.load(
                "src/tabs/skills/NativeSkillCatalog.luau"),
            "SkillsState": h.load("src/game/SkillsState.luau"),
            "Skills": h.load("src/features/Skills.luau"),
            "SkillsEvidence": h.load("src/features/SkillsEvidence.luau"),
            "config": {"LEVEL": {"allocation": RULES}},
            "fingerprint": "a" * 64, "release": "release-a"})
        tab = module.new(deps)
        raw = h.snapshot(release="release-a", native={
            "fullSync": True, "skillPoints": 10,
            "allocs": {"energy": 4}})
        enriched, reason = tab.Enrich(tab, raw)
        self.assertIsNone(reason)
        self.assertEqual(enriched["skillRules"]["energy"]["costEvery"], 5)
        context_reader = h.load("src/game/Context.luau").new(h.contracts)
        context = context_reader.Read(context_reader, enriched,
                                      lua_table(h.lua, h.session), 0, 2)[0]
        view, reason = deps["SkillsState"].read(enriched, context)
        self.assertIsNone(reason)
        proposal, reason = deps["Skills"].propose(view,
            lua_table(h.lua, {"enabled": True, "stat": "energy",
                              "maxAllocations": 8, "batchSize": 2}))
        self.assertIsNone(reason)
        self.assertEqual(proposal["intent"]["count"], 2)
        self.assertEqual(proposal["resources"]["skillPoints"], 3)


if __name__ == "__main__":
    unittest.main()
