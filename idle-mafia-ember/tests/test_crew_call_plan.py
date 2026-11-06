"""Crew calls stay primitive at the broker boundary and preserve native arity."""
import unittest

from engine_harness import Harness, lua_table


class CrewCallPlanTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        plan = self.h.load("src/transport/NativeCallPlan.luau").withCrew(
            self.h.load("src/tabs/crew/CrewCallPlan.luau"))
        self.executor = self.h.lua.execute("""return {
            queued = {}, calls = {},
            Schedule = function(self, fn) self.queued[#self.queued + 1] = fn end,
            Invoke = function(self, remote, method, ...)
                self.calls[#self.calls + 1] = {remote = remote,
                    arity = select('#', ...), args = table.pack(...)}
                return {ok = true}
            end,
            Drain = function(self)
                local queued = self.queued
                self.queued = {}
                for _, fn in ipairs(queued) do fn() end
            end,
        }""")
        self.adapter = self.h.load("src/transport/NativeDispatchAdapter.luau").new(
            plan, self.executor)

    def test_all_reviewed_crew_intents_cross_validator_and_adapter(self):
        cases = [
            ("crew", {"kind": "crewAutoEquip"}, "AutoEquipCrew", 0, []),
            ("crewSort", {"kind": "crewSort"}, "CrewAction", 4,
             ["sort", None, None, None]),
            ("crewHeal", {"kind": "crewHeal", "slot": 2,
                          "memberId": "injury-a", "expectedCost": 5, "injuredUntil": 1600},
             "CrewAction", 3, ["heal", 2, {"memberId": "injury-a", "injuredUntil": 1600}]),
            ("crewTrain", {"kind": "crewTrain", "slot": 2,
                           "quotedCost": 600, "catalogKey": "reviewed"},
             "CrewAction", 4, ["train", 2, None, None]),
            ("crewHire", {"kind": "crewHire", "slot": 2,
                          "tier": "street", "cost": 11000,
                          "catalogKey": "reviewed"},
             "CrewAction", 4, ["hire", "street", 11000, None]),
            ("crewGear", {"kind": "crewGear", "slot": 1,
                          "gearKind": "weapon", "itemId": "new_w",
                          "sourceKey": "reviewed"},
             "CrewEquip", 3, [1, "weapon", "new_w"]),
        ]
        for feature, intent, remote, arity, args in cases:
            with self.subTest(feature=feature):
                proposal = self.h.proposal(feature, feature + ":test")
                proposal["intent"] = lua_table(self.h.lua, intent)
                proposal["resources"] = lua_table(self.h.lua, {})
                validated, reason = self.h.contracts.validateProposal(
                    proposal, self.h.snapshot())
                self.assertIsNone(reason)
                allowed, reason, token = self.adapter.Validate(
                    self.adapter, validated)
                self.assertTrue(allowed, reason)
                self.assertTrue(self.adapter.Send(self.adapter, validated,
                    self.h.lua.eval("function(_reply) end"),
                    self.h.lua.eval("function() return true end"), token))
                self.executor.Drain(self.executor)
                call = self.executor["calls"][len(self.executor["calls"])]
                self.assertEqual((call["remote"], call["arity"]),
                                 (remote, arity))
                actual = [dict(call.args[i].items()) if hasattr(call.args[i], "items") else call.args[i]
                          for i in range(1, arity + 1)]
                self.assertEqual(actual, args)

    def test_unreviewed_item_heal_and_controller_do_not_dispatch(self):
        for feature, kind in (("crewHealItems", "crewHealItems"),
                              ("crewRoll", "crewAutoRoll")):
            proposal = self.h.proposal(feature, feature + ":test")
            proposal["intent"] = lua_table(self.h.lua, {"kind": kind})
            self.assertFalse(self.adapter.Validate(self.adapter, proposal)[0])
        self.assertEqual(len(self.executor["calls"]), 0)

    def test_native_elite_quote_and_late_slot_are_not_rejected_by_legacy_limits(self):
        plan = self.h.load("src/tabs/crew/CrewCallPlan.luau")
        call, reason = plan.describe(lua_table(self.h.lua, {"feature": "crewHire", "intent": {
            "kind": "crewHire", "slot": 46, "tier": "elite", "cost": 12500000000,
            "catalogKey": "reviewed"}}))
        self.assertIsNone(reason)
        self.assertEqual(call.args[3], 12500000000)
        self.assertIsNone(call.args[4])


if __name__ == "__main__":
    unittest.main()
