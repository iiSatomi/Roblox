"""Source-shaped ordinary Operation start inputs; no game transport."""
import unittest

from engine_harness import Harness, lua_table


class OperationsStateTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.context = self.h.load("src/game/Context.luau").new(self.h.contracts)
        self.reader = self.h.load("src/game/OperationsState.luau")

    def raw(self, **changes):
        data = {
            "catalogKey": "ops-build-1",
            "operationCatalog": [
                {"id": "op_fence", "duration": 600, "cost": 200,
                 "cash": 1500, "xp": 20},
                {"id": "op_truck", "duration": 3600, "cost": 4000,
                 "cash": 18000, "xp": 180, "level": 8},
            ],
            "native": {"fullSync": True, "level": 15, "maxLevel": 15,
                       "respect": 100, "cash": 5000,
                       "derived": {"fourthSlot": False},
                       "operations": {"active": [
                           {"opId": "op_fence", "remaining": 20, "slot": 1},
                       ]}},
        }
        data.update(changes)
        return self.h.snapshot(**data)

    def read(self, raw):
        context, reason = self.context.Read(
            self.context, raw, lua_table(self.h.lua, self.h.session),
            self.h.lua.globals().testNow, 2)
        self.assertIsNone(reason)
        return self.reader.read(raw, context)

    def test_complete_state_copies_catalog_and_free_slot_count(self):
        view, reason = self.read(self.raw())
        self.assertIsNone(reason)
        self.assertEqual(view["slotCount"], 2)
        self.assertEqual(view["openSlots"], 1)
        self.assertEqual(view["cash"], 5000)
        self.assertEqual(view["operations"][2]["id"], "op_truck")
        self.assertEqual(view["operations"][2]["level"], 8)

    def test_full_sync_and_required_fields_are_mandatory(self):
        for native in (
            {"fullSync": False, "level": 15, "cash": 5000,
             "respect": 100, "operations": {"active": []}},
            {"fullSync": True, "level": 15, "cash": 5000,
             "respect": 100, "operations": {}},
            {"fullSync": True, "level": 15, "cash": 5000,
             "respect": 100, "operations": {"active": [{"opId": "op_fence"}]}},
        ):
            with self.subTest(native=native):
                view, reason = self.read(self.raw(native=native))
                self.assertIsNone(view)
                self.assertTrue(reason)

    def test_level_slots_and_fourth_slot_follow_native_entitlement(self):
        raw = self.raw()
        raw["native"]["level"] = 30
        raw["native"]["maxLevel"] = 30
        raw["native"]["derived"]["fourthSlot"] = True
        view, reason = self.read(raw)
        self.assertIsNone(reason)
        self.assertEqual(view["slotCount"], 4)
        self.assertEqual(view["openSlots"], 3)

    def test_duplicate_catalog_and_overfull_or_duplicate_slots_block(self):
        raw = self.raw()
        raw["operationCatalog"][2]["id"] = "op_fence"
        self.assertIsNone(self.read(raw)[0])
        raw = self.raw()
        active = raw["native"]["operations"]["active"]
        active[2] = lua_table(self.h.lua, {"opId": "op_truck", "remaining": 0, "slot": 1})
        self.assertIsNone(self.read(raw)[0])
        active[2]["slot"] = 2
        active[3] = lua_table(self.h.lua, {"opId": "op_fence", "remaining": 0, "slot": 3})
        self.assertIsNone(self.read(raw)[0])


if __name__ == "__main__":
    unittest.main()
