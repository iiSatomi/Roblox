"""Read-only Black Market browse requests are bounded and reply-fenced."""
import unittest

from engine_harness import Harness, lua_table


class MarketBrowseTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.module = self.h.load("src/features/MarketBrowse.luau")
        self.browse = self.module.new(5)

    def test_first_all_page_preserves_nil_third_argument(self):
        request, reason = self.browse.Prepare(self.browse,
            lua_table(self.h.lua, {"kind": "all", "page": 1}))
        self.assertIsNone(reason)
        self.assertEqual(request["remote"], "MarketAction")
        self.assertEqual(request["arity"], 4)
        self.assertEqual(request["args"][1], "browse")
        self.assertEqual(request["args"][2], "all")
        self.assertIsNone(request["args"][3])
        self.assertEqual(request["args"][4], 1)

    def test_bad_scope_and_page_do_not_issue_request(self):
        for scope in ({"kind": "all", "page": 6},
                      {"kind": "group", "arg": "unknown", "page": 1},
                      {"kind": "item", "arg": "", "page": 1},
                      {"kind": "all", "page": 1.5}):
            with self.subTest(scope=scope):
                self.assertIsNone(self.browse.Prepare(self.browse,
                    lua_table(self.h.lua, scope))[0])

    def test_saved_group_and_item_scopes(self):
        group = self.browse.Prepare(self.browse,
            lua_table(self.h.lua, {"kind": "group", "arg": "weapon",
                                    "page": 3}))[0]
        self.assertEqual([group["args"][i] for i in range(1, 5)],
                         ["browse", "group", "weapon", 3])
        item = self.browse.Prepare(self.browse,
            lua_table(self.h.lua, {"kind": "item", "arg": "w_baton",
                                    "page": 1}))[0]
        self.assertEqual([item["args"][i] for i in range(1, 5)],
                         ["browse", "item", "w_baton", 1])

    def test_reply_is_copied_and_old_request_is_ignored(self):
        first = self.browse.Prepare(self.browse,
            lua_table(self.h.lua, {"kind": "all", "page": 1}))[0]
        second = self.browse.Prepare(self.browse,
            lua_table(self.h.lua, {"kind": "all", "page": 2}))[0]
        reply = lua_table(self.h.lua, {"ok": True, "pages": 2,
            "more": False, "stale": False, "small": False,
            "rows": [{"id": 9, "item": "w_baton", "qty": 1,
                      "price": 50, "t": 100}]})
        self.assertIsNone(self.browse.Accept(self.browse, first, reply)[0])
        result, reason = self.browse.Accept(self.browse, second, reply)
        self.assertIsNone(reason)
        self.assertEqual(result["rows"][1]["item"], "w_baton")
        reply["rows"][1]["price"] = 1
        self.assertEqual(result["rows"][1]["price"], 50)
        self.assertIsNone(self.browse.Accept(self.browse, second, reply)[0])

    def test_sparse_listing_rows_cannot_be_silently_truncated(self):
        request = self.browse.Prepare(self.browse,
            lua_table(self.h.lua, {"kind": "all", "page": 1}))[0]
        reply = self.h.lua.execute("""return { ok = true, pages = 1,
            rows = {
                [1] = { id = 1, item = 'w_baton', qty = 1, price = 10 },
                [3] = { id = 3, item = 'w_baton', qty = 1, price = 20 },
            } }""")
        self.assertIsNone(self.browse.Accept(self.browse, request, reply)[0])

    def test_rejects_malformed_reply_and_closes(self):
        request = self.browse.Prepare(self.browse,
            lua_table(self.h.lua, {"kind": "all", "page": 1}))[0]
        bad = lua_table(self.h.lua, {"ok": True,
            "rows": [{"id": 9, "item": "w_baton", "qty": -1, "price": 50}]})
        self.assertIsNone(self.browse.Accept(self.browse, request, bad)[0])
        empty_id = lua_table(self.h.lua, {"ok": True,
            "rows": [{"id": "", "item": "w_baton", "qty": 1,
                      "price": 50}]})
        self.assertIsNone(self.browse.Accept(self.browse, request, empty_id)[0])
        self.browse.Close(self.browse)
        self.assertIsNone(self.browse.Prepare(self.browse,
            lua_table(self.h.lua, {"kind": "all", "page": 1}))[0])


if __name__ == "__main__":
    unittest.main()
