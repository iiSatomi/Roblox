"""A saved Sync payload is the only authority for a complete native view."""
import unittest

from engine_harness import Harness, lua_table


class NativeSnapshotReaderTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        module = self.h.load("src/transport/NativeSnapshotReader.luau")
        self.reader = module.new(lua_table(self.h.lua, self.h.session),
                                 self.h.clock)

    def test_change_events_cannot_establish_full_sync(self):
        changed = lua_table(self.h.lua, {"cash": 5})
        self.assertFalse(self.reader.ObserveChanged(self.reader, changed))
        self.assertIsNone(self.reader.Capture(self.reader)[0])
        self.assertTrue(self.reader.ObserveSync(self.reader, changed))
        view, reason = self.reader.Capture(self.reader)
        self.assertIsNone(reason)
        self.assertTrue(view["fullSync"])
        self.assertTrue(view["native"]["fullSync"])
        self.assertEqual(view["revision"], 1)
        self.assertEqual(view["data"]["cash"], 5)

    def test_copies_mutable_native_data_and_advances_revision(self):
        raw = lua_table(self.h.lua, {"acc": {"energy": 10}})
        self.assertTrue(self.reader.ObserveSync(self.reader, raw))
        raw["acc"]["energy"] = 0
        first = self.reader.Capture(self.reader)[0]
        self.assertEqual(first["data"]["acc"]["energy"], 10)
        first["data"]["acc"]["energy"] = 1
        self.assertEqual(self.reader.Capture(self.reader)[0]["data"]["acc"]["energy"], 10)
        self.h.at(2)
        self.assertTrue(self.reader.ObserveChanged(self.reader,
            lua_table(self.h.lua, {"acc": {"energy": 9}})))
        second = self.reader.Capture(self.reader)[0]
        self.assertEqual(second["revision"], 2)
        self.assertEqual(second["capturedAt"], 2)
        self.assertFalse(second["fullSync"])
        self.assertFalse(second["native"]["fullSync"])
        self.assertEqual(second["data"]["acc"]["energy"], 9)
        self.assertTrue(self.reader.ObserveSync(self.reader,
            lua_table(self.h.lua, {"acc": {"energy": 8}})))
        self.assertTrue(self.reader.Capture(self.reader)[0]["fullSync"])

    def test_invalid_change_does_not_replace_last_good_view(self):
        self.assertTrue(self.reader.ObserveSync(self.reader,
            lua_table(self.h.lua, {"cash": 5})))
        bad = self.h.lua.eval("function() end")
        self.assertFalse(self.reader.ObserveChanged(self.reader, bad))
        view = self.reader.Capture(self.reader)[0]
        self.assertEqual(view["revision"], 1)
        self.assertEqual(view["data"]["cash"], 5)

    def test_context_owner_readiness_requires_the_observed_sync(self):
        context = self.h.load("src/game/Context.luau").new(
            self.h.contracts, None, None, None, None, None, None, None)
        native = lua_table(self.h.lua, {"level": 1, "jobs": {},
                                        "pools": {"energy": 10}})
        self.assertTrue(self.reader.ObserveSync(self.reader, native))
        full = self.reader.Capture(self.reader)[0]
        view, reason = context.Read(context, full,
            lua_table(self.h.lua, self.h.session), 0, 2)
        self.assertIsNone(reason)
        self.assertEqual(view["owners"]["jobs"]["activity"], "inactive")
        self.assertTrue(self.reader.ObserveChanged(self.reader, native))
        duplicate = self.reader.Capture(self.reader)[0]
        self.assertEqual(duplicate["revision"], 1)
        self.assertTrue(duplicate["fullSync"])
        native["level"] = 2
        self.assertTrue(self.reader.ObserveChanged(self.reader, native))
        partial = self.reader.Capture(self.reader)[0]
        view = context.Read(context, partial,
            lua_table(self.h.lua, self.h.session), 0, 2)[0]
        self.assertEqual(view["owners"]["jobs"]["activity"], "unknown")

    def test_close_fences_late_events_and_clears_account_data(self):
        self.assertTrue(self.reader.ObserveSync(self.reader,
            lua_table(self.h.lua, {"cash": 5})))
        self.reader.Close(self.reader)
        self.assertFalse(self.reader.ObserveSync(self.reader,
            lua_table(self.h.lua, {"cash": 10})))
        self.assertFalse(self.reader.ObserveChanged(self.reader,
            lua_table(self.h.lua, {"cash": 20})))
        self.assertIsNone(self.reader.Capture(self.reader)[0])


if __name__ == "__main__":
    unittest.main()
