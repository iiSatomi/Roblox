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

    def test_authoritative_mode_never_promotes_projects_or_refreshes_sync_freshness(self):
        reader=self.h.load('src/transport/NativeSnapshotReader.luau').new(
            lua_table(self.h.lua,self.h.session),self.h.clock,'a'*64,True)
        changed=lua_table(self.h.lua,{"cash":999,"serverNow":101})
        reader.ObserveChanged(reader,changed)
        self.assertIsNone(reader.Capture(reader)[0])
        reader.ObserveSync(reader,lua_table(self.h.lua,{"cash":5,"serverNow":100}))
        self.h.at(3);reader.ObserveChanged(reader,changed)
        snapshot=reader.Capture(reader)[0]
        self.assertEqual(snapshot.native.cash,5)
        self.assertEqual(snapshot.capturedAt,0)
        self.assertEqual(snapshot.revision,1)
        self.assertTrue(snapshot.native.fullSync)
        reader.ObserveSync(reader,changed)
        self.assertEqual(reader.Capture(reader)[0].capturedAt,3)
        self.assertEqual(reader.Capture(reader)[0].native.cash,999)

    def test_heist_board_proof_is_bound_to_one_full_sync(self):
        self.reader.ObserveSync(self.reader,
            lua_table(self.h.lua, {"cash": 5}))
        full = self.reader.Capture(self.reader)[0]
        query = self.h.load("src/tabs/heists/BoardQuery.luau").new(
            lua_table(self.h.lua, self.h.session))
        staged, reason = query.Stage(query, full,
            lua_table(self.h.lua, {"ok": True, "rows": []}))
        self.assertIsNone(reason)
        self.assertTrue(self.reader.AttachHeistBoard(self.reader, staged))
        staged["heistBoardProof"]["board"]["ok"] = False
        proof = self.reader.Capture(self.reader)[0]["heistBoardProof"]
        self.assertTrue(proof["board"]["ok"])
        forged = self.reader.Capture(self.reader)[0]
        forged["native"]["cash"] = 6
        forged["heistBoardProof"] = proof
        self.assertFalse(self.reader.AttachHeistBoard(self.reader, forged))
        stale = lua_table(self.h.lua, {
            **self.h.session, "revision": 0, "capturedAt": 0,
            "native": {"fullSync": True},
            "heistBoardProof": {"account": "user-a", "capturedAt": 0,
                "board": {"ok": True, "rows": []}},
        })
        self.assertFalse(self.reader.AttachHeistBoard(self.reader, stale))
        self.assertTrue(self.reader.ObserveChanged(self.reader,
            lua_table(self.h.lua, {"cash": 6})))
        self.assertIsNone(self.reader.Capture(self.reader)[0]["heistBoardProof"])
        self.assertFalse(self.reader.AttachHeistBoard(self.reader, staged))

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
