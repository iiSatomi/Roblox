"""Saved Boss Shop source only supports a read-only quote until live adapters."""
import unittest

from engine_harness import Harness, lua_table


class BossShopStateTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.reader = self.h.load("src/game/BossShopState.luau")
        self.context = self.h.load("src/game/Context.luau").new(
            self.h.contracts, None, None, None, None, None,
            self.reader)

    def snapshot(self):
        return self.h.snapshot(native={"fullSync": True,
            "inventory": {"boss_token": 120, "crate_loot": 2},
            "inventoryBound": {"boss_token": 30}},
            bossShopProof={"account": "user-a", "capturedAt": 0,
                "catalogKey": "saved-boss-catalog",
                "items": [{"item": "crate_loot", "kind": "crate",
                           "price": 14, "unlocked": True},
                          {"item": "w_policebaton", "kind": "gear",
                           "price": 2500, "unlocked": True}]})

    def test_reads_current_token_and_item_counts(self):
        raw = self.snapshot()
        context, reason = self.context.Read(self.context, raw,
            lua_table(self.h.lua, self.h.session), 0, 2)
        self.assertIsNone(reason)
        view = context["bossShop"]
        self.assertEqual(view["tokens"], 150)
        self.assertEqual(view["items"][1]["owned"], 2)
        self.assertEqual(view["items"][2]["price"], 2500)

    def test_rejects_stale_catalog_duplicate_and_corrupt_custody(self):
        raw = self.snapshot()
        raw["bossShopProof"]["capturedAt"] = -1
        self.assertIsNone(self.reader.read(raw, raw)[0])
        raw = self.snapshot()
        raw["bossShopProof"]["items"][2]["item"] = "crate_loot"
        self.assertIsNone(self.reader.read(raw, raw)[0])
        raw = self.snapshot()
        raw["native"]["inventoryBound"]["boss_token"] = -1
        self.assertIsNone(self.reader.read(raw, raw)[0])


if __name__ == "__main__":
    unittest.main()
