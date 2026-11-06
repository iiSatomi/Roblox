"""Operations tab copies saved quotes and crate odds into an observed Sync."""
import unittest

from engine_harness import Harness, lua_table


class NativeOperationsCatalogTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.catalog_module = self.h.load(
            "src/tabs/operations/NativeOperationsCatalog.luau")
        self.game = lua_table(self.h.lua, {
            "OPERATIONS": [
                {"id": "op_fence", "duration": 600, "cost": 200,
                 "cash": 1500, "xp": 20, "crate": "crate_loot",
                 "crateChance": 0.1},
                {"id": "op_truck", "duration": 3600, "cost": 4000,
                 "cash": 18000, "xp": 180, "level": 8},
            ],
            "CRATES": {"crate_loot": {"buckets": [
                {"weight": 60, "rarity": 1},
                {"weight": 40, "rarity": 3},
            ]}},
        })

    def adapter(self):
        return self.catalog_module.new(self.game, "b" * 64, "release-a")

    def test_observed_sync_feeds_both_operation_planners(self):
        tab = self.h.load("src/tabs/operations/Module.luau").new(
            lua_table(self.h.lua, {
                "NativeOperationsCatalog": self.catalog_module,
                "OperationsState": self.h.load(
                    "src/game/OperationsState.luau"),
                "OperationsStart": self.h.load(
                    "src/features/OperationsStart.luau"),
                "OperationsEvidence": self.h.load(
                    "src/features/OperationsEvidence.luau"),
                "OperationsCollect": self.h.load(
                    "src/features/OperationsCollect.luau"),
                "OperationsCollectEvidence": self.h.load(
                    "src/features/OperationsCollectEvidence.luau"),
                "gameData": self.game, "fingerprint": "b" * 64,
                "release": "release-a",
            }))
        self.assertEqual(tab["id"], "operations")
        self.assertEqual([tab.Descriptors(tab)[i]["id"] for i in (1, 2)],
                         ["operations", "collect"])
        reader = self.h.load("src/transport/NativeSnapshotReader.luau").new(
            lua_table(self.h.lua, self.h.session), self.h.clock)
        reader.ObserveSync(reader, lua_table(self.h.lua, {
            "level": 15, "maxLevel": 15, "respect": 100,
            "cash": 5000, "operations": {"active": [
                {"opId": "op_truck", "remaining": 0, "slot": 1}]}}))
        raw, reason = tab.Enrich(tab, reader.Capture(reader)[0])
        self.assertIsNone(reason)
        context = self.h.load("src/game/Context.luau").new(self.h.contracts)
        facts = context.Read(context, raw,
            lua_table(self.h.lua, self.h.session), 0, 2)[0]
        view, reason = tab.Descriptors(tab)[1]["reader"].read(raw, facts)
        self.assertIsNone(reason)
        start = tab.Descriptors(tab)[1]["planner"].propose(view,
            lua_table(self.h.lua, {"enabled": True,
                "policy": "Best chest"}), lua_table(self.h.lua, {}))[0]
        self.assertEqual(start["intent"]["targetId"], "op_fence")
        collect = tab.Descriptors(tab)[2]["planner"].propose(view,
            lua_table(self.h.lua, {"enabled": True}))[0]
        self.assertEqual(collect["intent"]["index"], 1)

    def test_malformed_or_changed_source_fails_closed(self):
        adapter = self.adapter()
        self.game["OPERATIONS"][1]["cost"] = 9999
        raw = self.h.snapshot(native={"fullSync": True})
        enriched = adapter.Enrich(adapter, raw)[0]
        self.assertEqual(enriched["operationCatalog"][1]["cost"], 200)
        self.assertIsNone(adapter.Enrich(adapter,
            self.h.snapshot(release="wrong", native={"fullSync": True}))[0])
        self.assertIsNone(adapter.Enrich(adapter,
            self.h.snapshot(native={"fullSync": False}))[0])
        self.game["OPERATIONS"][2]["id"] = "op_fence"
        with self.assertRaises(Exception):
            self.adapter()


if __name__ == "__main__":
    unittest.main()
