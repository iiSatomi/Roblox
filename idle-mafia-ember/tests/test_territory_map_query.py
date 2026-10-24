"""Saved Territory map read is bounded and fences stale replies."""
import unittest

from engine_harness import Harness, lua_table


class TerritoryMapQueryTests(unittest.TestCase):
    def test_city_scoped_read_and_stale_reply(self):
        h = Harness()
        query = h.load("src/tabs/territory/TerritoryMapQuery.luau").new()
        first, reason = query.Prepare(query, "vespera")
        self.assertIsNone(reason)
        self.assertEqual(first["remote"], "TerritoryView")
        self.assertEqual(first["args"][1], "map")
        self.assertEqual(first["args"][2], "vespera")
        second, _ = query.Prepare(query, "exiles")
        reply = lua_table(h.lua, {"ok": True, "city": "exiles",
            "totalDistricts": 2,
            "territoryCapacity": {"familyId": "fam-a"},
            "districts": [{"id": "district-a", "mine": True}]})
        self.assertIsNone(query.Accept(query, first, reply)[0])
        result, reason = query.Accept(query, second, reply)
        self.assertIsNone(reason)
        self.assertEqual(result["cityId"], "exiles")
        self.assertEqual(result["districts"][1]["id"], "district-a")
        self.assertTrue(result["districts"][1]["mine"])
        self.assertEqual(result["territoryCapacity"]["familyId"], "fam-a")

    def test_rejects_wrong_city_and_invalid_ownership(self):
        h = Harness()
        query = h.load("src/tabs/territory/TerritoryMapQuery.luau").new()
        request, _ = query.Prepare(query, "vespera")
        self.assertIsNone(query.Accept(query, request,
            lua_table(h.lua, {"ok": True, "city": "exiles",
                "districts": []}))[0])
        request, _ = query.Prepare(query, "vespera")
        self.assertIsNone(query.Accept(query, request,
            lua_table(h.lua, {"ok": True, "city": "vespera",
                "districts": [{"id": "d", "mine": "yes"}]}))[0])


if __name__ == "__main__":
    unittest.main()
