"""Native Shop quote source is bound to a complete rotation and Sync."""
import unittest

from engine_harness import Harness, lua_table


class ShopQuoteProducerTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.producer = self.h.load(
            "src/engine/ShopQuoteProducer.luau")
        self.raw = self.h.snapshot(native={"fullSync": True,
            "serverNow": 1220, "shopRotation": {"slot": 4,
                "bought": {}}, "cash": 1000, "level": 10,
            "inventory": {}, "shopBought": {}},
            shopCatalog={"release": "release-a", "key": "a" * 64,
                "offers": {"w_a": {"level": 1, "rarity": 1,
                    "base": 100, "ceiling": 150,
                    "kind": "weapon"}}})
        self.context = lua_table(self.h.lua, {**self.h.session,
            "revision": 1, "capturedAt": 0})
        self.source = self.h.lua.execute("""return {
            release = 'release-a', catalogKey = string.rep('a', 64),
            Stock = function(self, now)
                return { w_a = true }, 1500, 4
            end,
            CashQuote = function(self, id, slot, raw) return 120 end,
        }""")

    def derive(self):
        return self.producer.derive(self.raw, self.context,
                                    self.source)

    def test_current_stock_and_cash_quote(self):
        proof, reason = self.derive()
        self.assertIsNone(reason)
        self.assertEqual(proof["slot"], 4)
        self.assertTrue(proof["stock"]["w_a"])
        self.assertEqual(proof["quotes"]["w_a"], 120)
        self.assertEqual(proof["account"], "user-a")
        self.raw["shopQuoteProof"] = proof
        shop = self.h.load("src/game/ShopState.luau")
        view, reason = shop.read(self.raw, self.context)
        self.assertIsNone(reason)
        self.assertEqual(view["offers"]["w_a"]["cost"], 120)

    def test_rotation_source_and_quote_fail_closed(self):
        self.raw["native"]["serverNow"] = 1499
        self.assertIsNone(self.derive()[0])
        self.raw["native"]["serverNow"] = 1220
        self.source["catalogKey"] = "b" * 64
        self.assertIsNone(self.derive()[0])
        self.source["catalogKey"] = "a" * 64
        self.source["CashQuote"] = self.h.lua.eval(
            "function() return 151 end")
        self.assertIsNone(self.derive()[0])


if __name__ == "__main__":
    unittest.main()
