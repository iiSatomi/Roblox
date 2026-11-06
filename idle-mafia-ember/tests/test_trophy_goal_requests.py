"""Selected Trophy goal requests are read-only and require explicit borrowing."""
import unittest

from engine_harness import Harness, lua_table


class TrophyGoalRequestTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.module = self.h.load("src/tabs/trophies/TrophyGoalRequests.luau")

    def view(self, status="notReady", route="level", revision=1):
        return lua_table(self.h.lua, {
            "session": "session-a", "account": "account-a", "place": "place-a",
            "release": "release-a", "revision": revision,
            "catalogKey": "items-a", "byId": {
                "t_streetname": {"id": "t_streetname", "kind": "trophy",
                                 "status": status, "route": route}}})

    def test_selected_ordinary_route_requires_its_own_opt_in(self):
        settings = lua_table(self.h.lua, {"enabled": True,
            "goalId": "t_streetname", "borrowJobs": True})
        result, reason = self.module.derive(self.view(), settings)
        self.assertIsNone(reason)
        request = result["requests"][1]
        self.assertEqual(request["origin"], "trophyFocus")
        self.assertEqual(request["targetId"], "t_streetname")
        self.assertEqual(request["routes"][1], "jobs")
        settings["borrowJobs"] = False
        self.assertEqual(len(list(self.module.derive(self.view(), settings)[0]["requests"].values())), 0)

    def test_owned_ready_and_consuming_routes_do_not_borrow(self):
        settings = lua_table(self.h.lua, {"enabled": True,
            "goalId": "t_streetname", "borrowJobs": True})
        for status in ("owned", "manualTradeIn"):
            result, reason = self.module.derive(self.view(status=status), settings)
            self.assertIsNone(reason)
            self.assertEqual(len(list(result["requests"].values())), 0)
        result, _ = self.module.derive(self.view(route="unsupported"), settings)
        self.assertEqual(len(list(result["requests"].values())), 0)

    def test_newer_same_catalog_state_proves_ready_or_owned(self):
        before = self.view()
        settings = lua_table(self.h.lua, {"enabled": True,
            "goalId": "t_streetname", "borrowJobs": True})
        request = self.module.derive(before, settings)[0]["requests"][1]
        self.assertEqual(self.module.observe(before, self.view("ready", revision=2),
                                             request), "ready")
        self.assertEqual(self.module.observe(before, self.view("owned", revision=2),
                                             request), "owned")
        self.assertEqual(self.module.observe(before, self.view("ready"),
                                             request), "pending")

    def test_personal_heist_completion_requires_start_and_collection_routes(self):
        settings = lua_table(self.h.lua, {"enabled": True,
            "goalId": "t_streetname", "borrowHeists": True})
        result, reason = self.module.derive(self.view(route="heist"), settings)
        self.assertIsNone(reason)
        self.assertEqual(list(result.requests[1].routes.values()),
                         ["heists", "heistCollect"])

    def test_help_and_sabotage_are_never_borrowed_as_personal_starts(self):
        settings = lua_table(self.h.lua, {"enabled": True,
            "goalId": "t_streetname", "borrowHeists": True})
        for route in ("favor", "sabotage"):
            result, reason = self.module.derive(self.view(route=route), settings)
            self.assertIsNone(reason)
            self.assertEqual(len(result.requests), 0)


if __name__ == "__main__":
    unittest.main()
