"""Saved Market price history is a read query with bounded 120-second cache."""
import unittest

from engine_harness import Harness, lua_table


class MarketPricesTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.prices = self.h.load("src/features/MarketPrices.luau").new(
            self.h.clock)

    def test_query_keeps_two_trailing_nil_arguments(self):
        request, reason = self.prices.Prepare(self.prices, "w_baton")
        self.assertIsNone(reason)
        self.assertEqual(request["remote"], "MarketAction")
        self.assertEqual(request["arity"], 4)
        self.assertEqual([request["args"][i] for i in range(1, 5)],
                         ["prices", "w_baton", None, None])

    def test_valid_history_is_copied_cached_and_expires(self):
        request = self.prices.Prepare(self.prices, "w_baton")[0]
        reply = lua_table(self.h.lua, {"ok": True,
            "recent": [{"price": 10}, {"price": 12}],
            "days": [{"day": 20261022, "qty": 2, "avg": 11}]})
        result, reason = self.prices.Accept(self.prices, request, reply)
        self.assertIsNone(reason)
        self.assertEqual(result["recent"][2]["price"], 12)
        result["recent"][2]["price"] = 2
        reply["recent"][2]["price"] = 1
        self.assertEqual(self.prices.Get(self.prices, "w_baton")["recent"][2]["price"], 12)
        self.h.at(119)
        self.assertIsNotNone(self.prices.Get(self.prices, "w_baton"))
        self.h.at(120)
        self.assertIsNone(self.prices.Get(self.prices, "w_baton"))

    def test_stale_or_invalid_response_never_enters_cache(self):
        first = self.prices.Prepare(self.prices, "w_baton")[0]
        second = self.prices.Prepare(self.prices, "a_jacket")[0]
        valid = lua_table(self.h.lua, {"ok": True, "recent": [], "days": []})
        self.assertIsNone(self.prices.Accept(self.prices, first, valid)[0])
        bad = lua_table(self.h.lua, {"ok": True,
            "recent": [{"price": -1}], "days": []})
        self.assertIsNone(self.prices.Accept(self.prices, second, bad)[0])
        self.assertIsNone(self.prices.Get(self.prices, "a_jacket"))

    def test_close_fences_pending_queries(self):
        request = self.prices.Prepare(self.prices, "w_baton")[0]
        self.prices.Close(self.prices)
        valid = lua_table(self.h.lua, {"ok": True, "recent": [], "days": []})
        self.assertIsNone(self.prices.Accept(self.prices, request, valid)[0])
        self.assertIsNone(self.prices.Prepare(self.prices, "w_baton")[0])

    def test_sparse_history_is_rejected_instead_of_truncated(self):
        request = self.prices.Prepare(self.prices, "w_baton")[0]
        reply = self.h.lua.execute("""return { ok = true,
            recent = {
                [1] = { price = 10 }, [3] = { price = 12 },
            }, days = {} }""")
        self.assertIsNone(self.prices.Accept(self.prices, request, reply)[0])
        self.assertIsNone(self.prices.Get(self.prices, "w_baton"))


if __name__ == "__main__":
    unittest.main()
