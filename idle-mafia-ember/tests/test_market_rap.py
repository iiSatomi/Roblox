"""Native Black Market RAP batches are bounded read-only research."""
import unittest

from engine_harness import Harness, lua_table


class MarketRapTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.rap = self.h.load("src/features/MarketRap.luau").new(
            self.h.clock)

    def test_native_batch_shape_and_defensive_copy(self):
        ids = lua_table(self.h.lua, ["w_baton", "crate_boss"])
        request, reason = self.rap.Prepare(self.rap, ids)
        self.assertIsNone(reason)
        self.assertEqual(request["remote"], "MarketAction")
        self.assertEqual(request["arity"], 4)
        self.assertEqual(request["args"][1], "rap")
        self.assertEqual([request["args"][2][i] for i in (1, 2)],
                         ["w_baton", "crate_boss"])
        ids[1] = "changed"
        self.assertEqual(request["args"][2][1], "w_baton")
        self.assertIsNone(request["args"][3])
        self.assertIsNone(request["args"][4])

    def test_matching_reply_is_copied_cached_and_expires(self):
        request = self.rap.Prepare(self.rap,
            lua_table(self.h.lua, ["w_baton"]))[0]
        reply = lua_table(self.h.lua, {"ok": True, "values": {
            "w_baton": {"quantity": 507, "sales": 412,
                        "average": 3.0039447731755, "available": True}}})
        result, reason = self.rap.Accept(self.rap, request, reply)
        self.assertIsNone(reason)
        self.assertEqual(result["values"]["w_baton"]["sales"], 412)
        result["values"]["w_baton"]["sales"] = 0
        reply["values"]["w_baton"]["sales"] = 0
        self.assertEqual(self.rap.Get(self.rap, "w_baton")["sales"], 412)
        self.assertEqual(self.rap.Get(self.rap, "w_baton")["itemId"], "w_baton")
        self.assertIsNone(self.rap.Prepare(self.rap,
            lua_table(self.h.lua, ["w_baton"]))[0])
        self.h.at(120)
        self.assertIsNone(self.rap.Get(self.rap, "w_baton"))
        self.assertIsNotNone(self.rap.Prepare(self.rap,
            lua_table(self.h.lua, ["w_baton"]))[0])

    def test_sparse_duplicate_oversize_and_invalid_ids_are_rejected(self):
        for ids in (["w_baton", "w_baton"], [""], ["x" * 121],
                    ["item" + str(i) for i in range(21)]):
            with self.subTest(ids=ids[:2]):
                self.assertIsNone(self.rap.Prepare(self.rap,
                    lua_table(self.h.lua, ids))[0])
        sparse = self.h.lua.execute("return { [1] = 'w_baton', [3] = 'crate_boss' }")
        self.assertIsNone(self.rap.Prepare(self.rap, sparse)[0])

    def test_missing_extra_or_malformed_reply_never_enters_cache(self):
        request = self.rap.Prepare(self.rap,
            lua_table(self.h.lua, ["w_baton"]))[0]
        for values in ({}, {"w_baton": {"quantity": -1,
                       "sales": 1, "average": 3, "available": True}},
                       {"w_baton": {"quantity": 1, "sales": 1,
                       "average": 3, "available": True},
                       "crate_boss": {"quantity": 1, "sales": 1,
                       "average": 3, "available": True}}):
            with self.subTest(values=values):
                result, _ = self.rap.Accept(self.rap, request,
                    lua_table(self.h.lua, {"ok": True, "values": values}))
                self.assertIsNone(result)
                self.assertIsNone(self.rap.Get(self.rap, "w_baton"))

    def test_stale_reply_and_close_are_fenced(self):
        first = self.rap.Prepare(self.rap,
            lua_table(self.h.lua, ["w_baton"]))[0]
        second = self.rap.Prepare(self.rap,
            lua_table(self.h.lua, ["crate_boss"]))[0]
        reply = lua_table(self.h.lua, {"ok": True, "values": {
            "w_baton": {"quantity": 1, "sales": 1,
                        "average": 3, "available": True}}})
        self.assertIsNone(self.rap.Accept(self.rap, first, reply)[0])
        self.rap.Close(self.rap)
        self.assertIsNone(self.rap.Accept(self.rap, second, reply)[0])
        self.assertIsNone(self.rap.Prepare(self.rap,
            lua_table(self.h.lua, ["w_baton"]))[0])


if __name__ == "__main__":
    unittest.main()
