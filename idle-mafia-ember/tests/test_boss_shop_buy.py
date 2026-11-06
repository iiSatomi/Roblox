"""Selected Boss Shop spending needs exact quote, custody and durable cap."""
import unittest

from engine_harness import Harness, lua_table


class BossShopBuyTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.shop = self.h.load("src/game/BossShopState.luau")
        self.context = self.h.load("src/game/Context.luau").new(
            self.h.contracts, None, None, None, None, None, self.shop)
        self.reader = self.h.load("src/game/BossShopBuyState.luau")
        self.planner = self.h.load("src/features/BossShopBuy.luau")
        self.evidence = self.h.load("src/features/BossShopBuyEvidence.luau")
        self.store = self.h.lua.execute("""return { data = {}, strictRecovery = true,
            Read = function(self, key) return self.data[key] end,
            Write = function(self, key, value) self.data[key] = value end }""")
        self.module = self.h.load("src/storage/Checkpoint.luau")
        self.ledger = self.module.new(self.store)
        self.ledger.Load(self.ledger, "user-a", "73897506680154", "release-a")

    def raw(self, revision=1, tokens=150, owned=2, price=14,
            unlocked=True, attempts=0):
        return self.h.snapshot(revision=revision,
            native={"fullSync": True,
                    "inventory": {"boss_token": tokens, "crate_loot": owned},
                    "inventoryBound": {"boss_token": 0}},
            bossShopProof={"account": "user-a", "capturedAt": 0,
                           "catalogKey": "saved-catalog",
                           "items": [{"item": "crate_loot", "kind": "crate",
                                      "price": price, "unlocked": unlocked},
                                     {"item": "w_policebaton", "kind": "gear",
                                      "price": 100, "unlocked": True}]},
            bossShopUsageProof={"account": "user-a", "session": "run-a",
                                "capturedAt": 0, "attempts": attempts})

    def propose(self, raw=None, item="crate_loot", quantity=1,
                reserve=0, cap=2, uncertain=0):
        raw = raw or self.raw()
        context = self.context.Read(self.context, raw,
            lua_table(self.h.lua, self.h.session), 0, 2)[0]
        view = self.reader.read(raw, context)[0]
        settings = lua_table(self.h.lua, {"enabled": True, "itemId": item,
            "crateQuantity": quantity, "tokenReserve": reserve,
            "maxSends": cap})
        return self.planner.propose(view, settings,
            lua_table(self.h.lua, {"uncertainBossTokens": uncertain}))

    def test_quote_unlock_reserve_and_quantity(self):
        proposal, reason = self.propose(quantity=10)
        self.assertIsNone(reason)
        self.assertEqual(proposal["resources"]["bossTokens"], 140)
        self.assertEqual(proposal["intent"]["quantity"], 10)
        self.assertIsNone(self.propose(quantity=2)[0])
        self.assertIsNone(self.propose(reserve=11, quantity=10)[0])
        self.assertIsNone(self.propose(uncertain=11, quantity=10)[0])
        self.assertIsNone(self.propose(self.raw(unlocked=False))[0])
        self.assertIsNone(self.propose(item="not-in-catalog")[0])
        gear, _ = self.propose(item="w_policebaton", quantity=10)
        self.assertEqual(gear["intent"]["quantity"], 1)

    def test_preflight_and_replication_are_exact(self):
        before = self.raw()
        proposal = self.propose(before)[0]
        baseline, reason = self.evidence.capture(proposal, before)
        self.assertIsNone(reason)
        changed_quote = self.raw(price=15)
        self.assertIsNone(self.evidence.capture(proposal, changed_quote)[0])
        after = self.raw(revision=2, tokens=136, owned=3, attempts=1)
        yes = lua_table(self.h.lua, {"ok": True})
        self.assertEqual(self.evidence.evaluate(proposal, before,
            after, yes, baseline), "confirmed")
        self.assertEqual(self.evidence.evaluate(proposal, before,
            self.raw(revision=2, tokens=136, owned=2), yes, baseline),
            "pending")
        self.assertEqual(self.evidence.evaluate(proposal, before,
            self.raw(revision=2, tokens=150, owned=3), yes, baseline),
            "pending")
        self.assertEqual(self.evidence.evaluate(proposal, before,
            after, lua_table(self.h.lua, {"ok": False}), baseline),
            "pending")

    def test_sent_attempt_survives_reload_and_caps(self):
        first = self.propose(cap=1)[0]
        self.assertTrue(self.ledger.Save(self.ledger, first)[0])
        restarted = self.module.new(self.store)
        self.assertIsNone(restarted.Load(restarted,
            "user-a", "73897506680154", "release-a")[1])
        self.assertEqual(restarted.BossShopUsage(restarted,
            "run-a", 0)["attempts"], 1)
        self.assertIsNone(self.propose(self.raw(attempts=1), cap=1)[0])
        second = self.propose(self.raw(attempts=1), cap=2)[0]
        self.assertTrue(restarted.Save(restarted, second)[0])
        self.assertFalse(restarted.Save(restarted, second)[0])
        self.assertEqual(restarted.BossShopUsage(restarted,
            "run-a", 0)["attempts"], 2)


if __name__ == "__main__":
    unittest.main()
