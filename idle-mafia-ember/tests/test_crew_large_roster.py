"""Late Crew slots remain usable across tab readers and native call descriptions."""
import unittest

import test_crew_training as training_fixture
from engine_harness import Harness, lua_table


class CrewLargeRosterTests(unittest.TestCase):
    def test_46_member_roster_reads_and_last_equipment_affects_action_identity(self):
        h = Harness()
        members = [{"name": "Player"}] + [{"name": f"Member{i}", "rarity": 4} for i in range(2, 47)]
        raw = h.snapshot(native={"fullSync": True, "crew": members,
                                "inventory": {}, "inventoryBound": {}})
        context = lua_table(h.lua, {**h.session, "revision": 1, "capturedAt": 0, "itemsById": {}})
        roster = h.load("src/tabs/crew/RosterState.luau")
        view, reason = roster.read(raw, context)
        self.assertIsNone(reason)
        self.assertEqual(view.members[46].name, "Member46")
        equip = h.load("src/tabs/crew/AutoEquipCrew.luau")
        before, reason = equip.read(raw, context)
        self.assertIsNone(reason)
        raw.native.crew[46].weapon = "w_upgrade"
        after, reason = equip.read(raw, context)
        self.assertIsNone(reason)
        self.assertNotEqual(before.fingerprint, after.fingerprint)
        order = h.load("src/tabs/crew/CrewSort.luau").read(raw, context)[0]
        self.assertEqual(order.count, 46)
        raw.native.crew[47] = lua_table(h.lua, {"name": "OutsideBound", "rarity": 4})
        self.assertIsNone(roster.read(raw, context)[0])
        self.assertIsNone(equip.read(raw, context)[0])

    def test_training_can_select_slot46_and_describe_native_high_tier_quote(self):
        base = training_fixture.CrewTrainingTests()
        base.setUp()
        for slot in range(4, 47):
            base.raw.native.crew[slot] = lua_table(base.h.lua, {"name": f"Member{slot}", "healId":f"member-{slot}", "rarity": 4})
        base.raw.native.crew[46].rarity = 8
        proposal = base.plan()
        self.assertEqual(proposal.intent.slot, 46)
        self.assertIsNotNone(base.feature.capture(proposal, base.raw)[0])
        proposal.intent.quotedCost = 1250000000000
        plan = base.h.load("src/tabs/crew/CrewCallPlan.luau")
        call, reason = plan.describe(proposal)
        self.assertIsNone(reason)
        self.assertEqual((call.args[1], call.args[2], call.arity), ("train", 46, 4))
        self.assertIsNone(call.args[3])


if __name__ == "__main__":
    unittest.main()
