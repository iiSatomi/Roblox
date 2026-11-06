"""Current BossStages quotes are bounded and tied to one full Sync."""
import unittest

from engine_harness import Harness, lua_table


class NativeBossCatalogTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.source = self.h.load("src/tabs/combat/NativeBossCatalog.luau")
        self.stages = self.h.lua.execute("""return {
            MAX_STAGE = 100000,
            get = function(stage)
                return { stage = stage, level = 1,
                    hp = 100 + stage, hitBackMax = 10 }
            end,
            crateUnlocked = function(native, item, day)
                return item == 'crate_loot'
                    and native.bossStage.best >= 1
                    and day == 2026298
            end,
            SHOP = { gear = { { item = 'w_policebaton', price = 2500 } },
                crates = { { item = 'crate_loot', price = 14 } } },
        }""")
        self.catalog = self.source.new(self.stages,
            lua_table(self.h.lua, {"BOSS": {"staminaCost": 2}}),
            "a" * 64, "release-a")

    def raw(self, best=1, full=True):
        return self.h.snapshot(native={"fullSync": full,
            "serverNow": 1792890000, "level": 10,
            "stats": {"maxHealth": 100},
            "pools": {"health": 100, "stamina": 10},
            "bossStage": {"best": best, "day": 2026298,
                "done": {}, "hp": {}},
            "inventory": {"boss_token": 2500},
            "inventoryBound": {}})

    def test_stage_and_shop_proofs_feed_existing_readers(self):
        raw = self.raw()
        enriched, reason = self.catalog.Enrich(self.catalog, raw)
        self.assertIsNone(reason)
        self.assertEqual(enriched.bossStageProof.stages[2].stage, 2)
        self.assertEqual(enriched.bossStageProof.staminaCost, 2)
        self.assertTrue(enriched.bossShopProof["items"][1].unlocked)
        self.assertTrue(enriched.bossShopProof["items"][2].unlocked)
        context = lua_table(self.h.lua, {**self.h.session,
            "revision": raw.revision, "capturedAt": raw.capturedAt,
            "serverNow": enriched.native.serverNow})
        boss, boss_reason = self.h.load(
            "src/game/BossStageState.luau").read(enriched, context)
        shop, shop_reason = self.h.load(
            "src/game/BossShopState.luau").read(enriched, context)
        self.assertIsNone(boss_reason)
        self.assertIsNone(shop_reason)
        self.assertEqual(boss.staminaCost, 2)
        self.assertEqual(shop.tokens, 2500)
        self.assertIsNone(raw.bossStageProof)

    def test_no_proof_from_partial_or_changed_release(self):
        self.assertIsNone(self.catalog.Enrich(
            self.catalog, self.raw(full=False))[0])
        changed = self.raw()
        changed.release = "another-release"
        self.assertIsNone(self.catalog.Enrich(self.catalog, changed)[0])

    def test_stage_work_is_bounded_at_high_progress(self):
        enriched, reason = self.catalog.Enrich(
            self.catalog, self.raw(best=100000))
        self.assertIsNone(reason)
        rows = enriched.bossStageProof.stages
        self.assertEqual(len(rows), 129)
        self.assertEqual(rows[1].stage, 99872)
        self.assertEqual(rows[129].stage, 100000)


if __name__ == "__main__":
    unittest.main()
