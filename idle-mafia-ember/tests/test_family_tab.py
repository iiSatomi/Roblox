"""Family info is read-only; all three resource spends remain blocked."""
import unittest

from engine_harness import Harness, lua_table


class FamilyTabTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.query = self.h.load("src/tabs/family/FamilyQuery.luau").new()
        self.reader = self.h.load("src/game/FamilyState.luau")
        self.blocked = self.h.load("src/features/FamilyBlocked.luau")
        self.context = self.h.load("src/game/Context.luau").new(
            self.h.contracts)

    def test_bounded_info_and_stale_reply(self):
        request, reason = self.query.Prepare(self.query)
        self.assertIsNone(reason)
        self.assertEqual(request["args"][1], "info")
        later, _ = self.query.Prepare(self.query)
        self.assertIsNone(self.query.Accept(self.query, request,
            lua_table(self.h.lua, {"ok": True,
                "family": {"id": "fam-a", "level": 1,
                           "perks": {"jobCut": 1}}}))[0])
        result, reason = self.query.Accept(self.query, later,
            lua_table(self.h.lua, {"ok": True,
                "family": {"id": "fam-a", "level": 1,
                           "perks": {"jobCut": 1}}}))
        self.assertIsNone(reason)
        self.assertEqual(result["perks"]["jobCut"], 1)

    def test_resource_snapshot_and_all_sends_blocked(self):
        raw = self.h.snapshot(native={"fullSync": True,
            "family": {"id": "fam-a"}, "cash": 1000,
            "pools": {"stamina": 50},
            "inventory": {"gold_bar": 3}},
            familyInfo={"id": "fam-a", "perks": {"jobCut": 1}})
        context = self.context.Read(self.context, raw,
            lua_table(self.h.lua, self.h.session), 0, 2)[0]
        view, reason = self.reader.read(raw, context)
        self.assertIsNone(reason)
        self.assertEqual((view["cash"], view["stamina"], view["gold"]),
                         (1000, 50, 3))
        self.assertIsNone(self.blocked.propose(view,
            lua_table(self.h.lua, {"enabled": True}))[0])
        self.assertIsNone(self.blocked.capture()[0])


if __name__ == "__main__":
    unittest.main()
