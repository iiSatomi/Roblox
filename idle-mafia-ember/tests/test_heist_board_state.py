"""Read-only personal Heist board boundaries from saved client source."""
import unittest

from engine_harness import Harness, lua_table


class HeistBoardStateTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.context = self.h.load("src/game/Context.luau").new(self.h.contracts)
        self.reader = self.h.load("src/game/HeistBoardState.luau")

    def raw(self, mine=None, result=None, query=None):
        return self.h.snapshot(native={"fullSync": True,
                "serverNow": 2000000},
            heistCatalog=[{"id": "h_a", "level": 1,
                "stake": 100, "energy": 2}],
            heistBoardProof={"account": "user-a", "capturedAt": 0,
                "query": query, "board": {"ok": True, "serverNow": 2000000,
                    "mine": mine, "result": result, "rows": [],
                    "startsLeft": 1, "bustWait": 0}})

    def view(self, raw):
        context = self.context.Read(self.context, raw,
            lua_table(self.h.lua, self.h.session), 0, 2)[0]
        return self.reader.read(raw, context)

    def test_idle_active_and_settling_are_distinct(self):
        idle, reason = self.view(self.raw())
        self.assertIsNone(reason)
        self.assertEqual(idle["state"], "idle")
        active, _ = self.view(self.raw(mine={"id": "run-1",
            "heistId": "h_a", "endsAt": 2000300}))
        self.assertEqual(active["state"], "active")
        self.assertEqual(active["mineId"], "run-1")
        settling, _ = self.view(self.raw(mine={"id": "run-1",
            "heistId": "h_a", "endsAt": 2000300,
            "settling": True}))
        self.assertEqual(settling["state"], "settling")

    def test_result_is_visible_but_not_addressable_for_collect(self):
        view, _ = self.view(self.raw(result={"heistId": "h_a",
            "ok": True, "cash": 1000, "xp": 20,
            "gold": 1, "crates": 2, "crateId": "crate_heist"}))
        self.assertEqual(view["state"], "result")
        self.assertEqual(view["resultHeistId"], "h_a")
        self.assertFalse(view["resultAddressable"])
        self.assertEqual(view["resultSummary"]["cash"], 1000)
        self.assertEqual(view["resultSummary"]["gold"], 1)
        self.assertEqual(view["resultSummary"]["crateId"], "crate_heist")

    def test_invalid_result_reward_shape_fails_closed(self):
        self.assertIsNone(self.view(self.raw(result={"heistId": "h_a",
            "ok": True, "cash": -1}))[0])
        self.assertIsNone(self.view(self.raw(result={"heistId": "h_a",
            "ok": True, "crates": 1}))[0])

    def test_wrong_query_identity_and_ambiguous_board_fail(self):
        self.assertIsNone(self.view(self.raw(query="other"))[0])
        raw = self.raw()
        raw["heistBoardProof"]["account"] = "other"
        self.assertIsNone(self.view(raw)[0])
        raw = self.raw(mine={"id": "run-1", "heistId": "h_a",
            "endsAt": 2000300}, result={"heistId": "h_a", "ok": True})
        self.assertIsNone(self.view(raw)[0])

    def test_missing_run_id_or_unknown_catalog_target_fail(self):
        self.assertIsNone(self.view(self.raw(mine={"heistId": "h_a",
            "endsAt": 2000300}))[0])
        self.assertIsNone(self.view(self.raw(mine={"id": "run-1",
            "heistId": "unknown", "endsAt": 2000300}))[0])

    def test_optional_board_timing_stays_unknown(self):
        raw = self.raw(mine={"id": "run-1", "heistId": "h_a",
            "endsAt": 2000300})
        board = raw["heistBoardProof"]["board"]
        board["serverNow"] = None
        board["startsLeft"] = None
        board["bustWait"] = None
        view, reason = self.view(raw)
        self.assertIsNone(reason)
        self.assertEqual(view["state"], "active")
        self.assertFalse(view["clockKnown"])
        self.assertIsNone(view["startsLeft"])

    def test_shared_context_keeps_heist_board_known_or_unknown(self):
        reader = self.h.load("src/game/Context.luau").new(
            self.h.contracts, None, None, self.reader)
        raw = self.raw()
        view, reason = reader.Read(reader, raw,
            lua_table(self.h.lua, self.h.session), 0, 2)
        self.assertIsNone(reason)
        self.assertEqual(view["heists"]["state"], "idle")
        raw["heistBoardProof"]["account"] = "other"
        view, reason = reader.Read(reader, raw,
            lua_table(self.h.lua, self.h.session), 0, 2)
        self.assertIsNone(reason)
        self.assertEqual(view["heists"]["status"], "unknown")


if __name__ == "__main__":
    unittest.main()
