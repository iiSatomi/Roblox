"""Personal Heists, sabotage and Favors remain separate tab permissions."""
import unittest

from engine_harness import Harness, lua_table


class HeistsFavorsTabTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.catalog = self.h.load("src/ui/Catalog.luau")
        self.registry = self.h.load("src/engine/FeatureRegistry.luau")
        self.heists = self.h.load("src/tabs/heists/Module.luau")
        self.favors = self.h.load("src/tabs/favors/Module.luau")
        self.deps = {
            "NativeHeistCatalog": self.h.load(
                "src/tabs/heists/NativeHeistCatalog.luau"),
            "SequenceRecovery": self.h.load(
                "src/tabs/heists/SequenceRecovery.luau"),
            "BoardQuery": self.h.load(
                "src/tabs/heists/BoardQuery.luau"),
            "BoardReadRuntime": self.h.load(
                "src/tabs/heists/BoardReadRuntime.luau"),
            "identity": self.h.session,
            "gameData": {"HEISTS": [{"id": "h_a", "level": 1,
                "stake": 100, "energy": 2, "crateCount": 1}]},
            "fingerprint": "a" * 64, "release": "release-a",
        }
        for reader in ("HeistBoardState", "SabotageState", "FavorsState"):
            self.deps[reader] = self.h.load("src/game/" + reader + ".luau")
        for name in ("HeistStart", "HeistStartEvidence",
                     "HeistCollect", "HeistCollectEvidence", "Sabotage",
                     "SabotageEvidence", "FavorHelp", "FavorHelpEvidence"):
            self.deps[name] = self.h.load("src/features/" + name + ".luau")

    def test_descriptors_register_only_on_their_own_pages(self):
        deps = lua_table(self.h.lua, self.deps)
        tabs = lua_table(self.h.lua,
                         [self.heists.new(deps), self.favors.new(deps)])
        specs, reason = self.registry.fromTabs(tabs, self.catalog)
        self.assertIsNone(reason)
        self.assertEqual([specs[i]["id"] for i in range(1, 5)],
                         ["heists", "heistCollect", "sabotage", "favors"])
        raw, source_reason = tabs[1].Enrich(tabs[1],
            self.h.snapshot(native={"fullSync": True}))
        self.assertIsNone(source_reason)
        self.assertEqual(raw["heistCatalog"][1]["id"], "h_a")
        record = lua_table(self.h.lua, {"account": "user-a",
            "place": "73897506680154", "release": "release-a",
            "actionName": "collect", "sequence": 2,
            "actionKey": "collect:a", "sentAt": 1, "sent": True})
        call, reason = tabs[1].StatusCall(tabs[1], record,
            lua_table(self.h.lua, self.h.session))
        self.assertIsNone(reason)
        self.assertEqual(call["args"][1], "status")
        self.assertEqual(tabs[1].BoardCall(tabs[1])["args"][1], "board")
        self.assertEqual(tabs[2].BoardCall(tabs[2])["args"][1], "board")

    def test_missing_action_fails_at_tab_boundary(self):
        del self.deps["SabotageEvidence"]
        with self.assertRaises(Exception):
            self.heists.new(lua_table(self.h.lua, self.deps))

    def test_tab_constructs_bounded_board_reader(self):
        tab = self.heists.new(lua_table(self.h.lua, self.deps))
        snapshot = self.h.snapshot(native={"fullSync": True})
        self.h.lua.globals().heist_current = snapshot
        budget = self.h.load("src/engine/ReadBudget.luau").new(
            self.h.clock, lua_table(self.h.lua, [
                {"id": "heistBoard", "interval": 15}]), 8, 120)
        executor = self.h.lua.execute("""return {
            calls = {}, Schedule = function(self, fn) fn() end,
            Invoke = function(self, remote, method, action)
                self.calls[#self.calls + 1] = {remote, method, action}
                return {ok = true, serverNow = 2000000,
                    rows = {}, startsLeft = 1}
            end,
        }""")
        self.h.lua.globals().heist_results = self.h.lua.table_from([])
        current = self.h.lua.eval("function() return heist_current end")
        result = self.h.lua.eval("""function(value, reason)
            heist_results[#heist_results + 1] = {value = value,
                reason = reason}
        end""")
        reader = tab.NewBoardRead(tab, budget, executor, current, result)
        self.assertTrue(reader.Queue(reader, snapshot)[0])
        self.assertEqual(reader.Step(reader), "scheduled")
        self.assertEqual(executor["calls"][1][3], "board")
        self.assertIsNotNone(self.h.lua.globals().heist_results[1]["value"])

    def test_staged_board_and_saved_catalog_feed_result_reader(self):
        tab = self.heists.new(lua_table(self.h.lua, self.deps))
        native = {"fullSync": True, "serverNow": 2000000,
                  "level": 12, "cash": 20000,
                  "pools": {"energy": 50}}
        snapshot = self.h.snapshot(native=native)
        reply = lua_table(self.h.lua, {"ok": True,
            "serverNow": 2000000, "rows": [],
            "result": {"heistId": "h_a", "ok": True,
                       "cash": 500, "xp": 10},
            "startsLeft": 1, "bustWait": 0})
        staged, reason = tab.StageBoard(tab, snapshot, reply)
        self.assertIsNone(reason)
        raw, reason = tab.Enrich(tab, staged)
        self.assertIsNone(reason)
        context = self.h.load("src/game/Context.luau").new(self.h.contracts)
        facts = context.Read(context, raw,
            lua_table(self.h.lua, self.h.session), 0, 2)[0]
        view, reason = self.deps["HeistBoardState"].read(raw, facts)
        self.assertIsNone(reason)
        self.assertEqual(view["resultSummary"]["cash"], 500)
        self.assertFalse(view["resultAddressable"])

    def test_favors_tab_stages_bounded_read_only_board(self):
        tab = self.favors.new(lua_table(self.h.lua, self.deps))
        snapshot = self.h.snapshot(native={"fullSync": True})
        board = lua_table(self.h.lua, {"ok": True, "serverNow": 2000000,
            "rows": [], "favorsLeft": 5, "helpFavorCost": 1,
            "helpEnergyCost": 2, "helpMaxPerHeist": 5})
        staged, reason = tab.StageBoard(tab, snapshot, board)
        self.assertIsNone(reason)
        self.assertEqual(staged["heistBoardProof"]["board"]["favorsLeft"], 5)
        board["favorsLeft"] = 0
        self.assertEqual(staged["heistBoardProof"]["board"]["favorsLeft"], 5)

    def test_favors_exposes_shared_board_read_capability(self):
        tab = self.favors.new(lua_table(self.h.lua, self.deps))
        snapshot = self.h.snapshot(native={"fullSync": True})
        self.h.lua.globals().favor_current = snapshot
        budget = self.h.load("src/engine/ReadBudget.luau").new(
            self.h.clock, lua_table(self.h.lua, [
                {"id": "heistBoard", "interval": 15}]), 8, 120)
        executor = self.h.lua.execute("""return {
            calls = {}, Schedule = function(self, fn) fn() end,
            Invoke = function(self, remote, method, action)
                self.calls[#self.calls + 1] = {remote, method, action}
                return {ok = true, serverNow = 2000000,
                    rows = {}, favorsLeft = 5}
            end,
        }""")
        self.h.lua.globals().favor_results = self.h.lua.table_from([])
        current = self.h.lua.eval("function() return favor_current end")
        result = self.h.lua.eval("""function(value, reason)
            favor_results[#favor_results + 1] = {value = value,
                reason = reason}
        end""")
        reader = tab.NewBoardRead(tab, budget, executor, current, result)
        self.assertTrue(reader.Queue(reader, snapshot)[0])
        self.assertEqual(reader.Step(reader), "scheduled")
        self.assertEqual(executor["calls"][1][3], "board")
        self.assertEqual(self.h.lua.globals().favor_results[1]["value"]
            ["heistBoardProof"]["board"]["favorsLeft"], 5)


    def test_shared_board_source_serves_favors_without_mutating_heists(self):
        tab = self.heists.new(lua_table(self.h.lua, self.deps))
        reader = self.h.load("src/transport/NativeSnapshotReader.luau").new(
            lua_table(self.h.lua, self.h.session), self.h.clock, "a" * 64)
        reader.ObserveSync(reader, lua_table(self.h.lua, {"serverNow": 2000000, "level": 12,
            "cash": 20000, "pools": {"energy": 50}}))
        sources = tab.ReadSources(tab, reader)
        self.assertTrue(sources[1].enabled(lua_table(self.h.lua, {"favors": {"enabled": True}})))
        lane = self.h.load("src/engine/RequestLane.luau").new(self.h.clock)
        budget = self.h.load("src/engine/ReadBudget.luau").new(self.h.clock,
            lua_table(self.h.lua, [{"id": "heistBoard", "interval": 5}]), 5, 60)
        executor = self.h.lua.execute("""return {calls=0,
            Schedule=function(self,fn) self.queued=fn; return true end,
            InvokeOwned=function(self,token,remote,method,command)
                assert(remote=='HeistAction' and command=='board')
                self.calls=self.calls+1
                return {ok=true,serverNow=2000000,rows={},startsLeft=1,bustWait=0}
            end}""")
        self.h.lua.globals().boardNativeReader = reader
        coordinator = self.h.load("src/transport/ReadCoordinator.luau").new(lua_table(self.h.lua, {
            "clock": self.h.clock, "lane": lane, "budget": budget, "executor": executor,
            "sources": sources, "currentSnapshot": self.h.lua.eval("function() return boardNativeReader:Capture() end")}))
        raw = reader.Capture(reader)[0]
        self.assertEqual(coordinator.Step(coordinator, raw, lua_table(self.h.lua, {"heistBoard": True})), "queued")
        executor.queued()
        proof = reader.Capture(reader)[0].heistBoardProof
        self.assertIsNotNone(proof)
        self.assertEqual(proof.sourceKey, "a" * 64)
        self.assertEqual(executor.calls, 1)
        tab.Close(tab)
        self.assertIsNone(tab.StageBoard(tab, raw, proof.board)[0])
        coordinator.Close(coordinator)
        reader.Close(reader)


if __name__ == "__main__":
    unittest.main()
