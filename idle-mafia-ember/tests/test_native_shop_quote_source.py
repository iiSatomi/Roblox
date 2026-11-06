"""Saved Shop stock and discount calls are bound to current source modules."""
import unittest

from engine_harness import Harness, lua_table


class NativeShopQuoteSourceTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.module = self.h.load(
            "src/tabs/shop/NativeQuoteSource.luau")
        self.current = self.h.lua.execute("""local current = {
            gameData = { SHOP = {
                { item = 'w_a', price = 150 },
                { item = 'gold_a', goldPrice = 1 },
            }, ITEMS_BY_ID = {
                w_a = { kind = 'weapon' },
                gold_a = { kind = 'weapon' },
            } },
            util = {
                shopStock = function(_, now)
                    return { w_a = true }, 1500, 4
                end,
                shopPrice = function(offer, slot)
                    return offer.price
                end,
            },
            territory = {
                fromData = function(data, kind)
                    return data.discount
                end,
                shopPrice = function(price, discount, sale, decree)
                    return price - discount - sale - decree
                end,
            },
            globalBuff = { sale = function(_, now) return 10 end },
            decree = { pctFor = function(_, kind, familyId)
                return familyId == 3 and 5 or 0
            end },
            clock = { now = function() return 1220 end },
            mw = {},
        }
        return current""")
        self.source, self.reason = self.module.new(
            self.current, "release-a", "a" * 64)

    def test_stock_and_discounted_cash_quote(self):
        self.assertIsNone(self.reason)
        stock, next_at, slot = self.source.Stock(self.source, 1220)
        self.assertTrue(stock["w_a"])
        self.assertEqual((next_at, slot), (1500, 4))
        raw = lua_table(self.h.lua, {"native": {
            "serverNow": 1220, "discount": 15,
            "family": {"id": 3}}})
        self.assertEqual(self.source.CashQuote(self.source,
            "w_a", 4, raw), 120)
        self.assertIsNone(self.source.CashQuote(self.source,
            "gold_a", 4, raw))
        raw = self.h.snapshot(native={"fullSync": True,
            "serverNow": 1220, "shopRotation": {"slot": 4},
            "discount": 15, "family": {"id": 3}},
            shopCatalog={"release": "release-a", "key": "a" * 64,
                "offers": {"w_a": {"ceiling": 150}}})
        context = lua_table(self.h.lua, {**self.h.session,
            "revision": 1, "capturedAt": 0})
        producer = self.h.load("src/engine/ShopQuoteProducer.luau")
        proof, reason = producer.derive(raw, context, self.source)
        self.assertIsNone(reason)
        self.assertEqual(proof["quotes"]["w_a"], 120)

    def test_stale_clock_and_bad_source_fail_closed(self):
        self.assertIsNone(self.module.new(
            self.h.lua.table(), "release-a", "a" * 64)[0])
        raw = lua_table(self.h.lua, {"native": {
            "serverNow": 1220, "discount": 15,
            "family": {"id": 3}}})
        self.current["clock"]["now"] = self.h.lua.eval(
            "function() return 1223 end")
        self.assertIsNone(self.source.CashQuote(self.source,
            "w_a", 4, raw))
        self.assertIsNone(self.source.Stock(self.source, 1220))


if __name__ == "__main__":
    unittest.main()
