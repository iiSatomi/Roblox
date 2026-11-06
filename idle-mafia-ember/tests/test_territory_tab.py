"""Territory holdings are identity-bound; station/residency sends stay blocked."""
import unittest

from engine_harness import Harness, lua_table


class TerritoryTabTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.reader = self.h.load("src/tabs/territory/TerritoryState.luau")
        self.blocked = self.h.load("src/tabs/territory/TerritoryBlocked.luau")
        self.context = self.h.load("src/game/Context.luau").new(
            self.h.contracts)

    def test_holdings_require_matching_family(self):
        raw = self.h.snapshot(native={"fullSync": True,
            "family": {"id": "fam-a"}})
        query = self.h.load(
            "src/tabs/territory/TerritoryMapQuery.luau").new()
        request, reason = query.Prepare(query, "vespera", raw)
        self.assertIsNone(reason)
        accepted, reason = query.Accept(query, request,
            lua_table(self.h.lua, {"ok": True, "city": "vespera",
                "totalDistricts": 2,
                "territoryCapacity": {"familyId": "fam-a"},
                "districts": [{"id": "d1", "mine": True},
                              {"id": "d2", "mine": False}]}))
        self.assertIsNone(reason)
        attach = self.h.load(
            "src/tabs/territory/ReadAttachment.luau")
        raw, reason = attach.attach(raw, accepted)
        self.assertIsNone(reason)
        context = self.context.Read(self.context, raw,
            lua_table(self.h.lua, self.h.session), 0, 2)[0]
        view, reason = self.reader.read(raw, context)
        self.assertIsNone(reason)
        self.assertEqual((view["held"], view["totalDistricts"]), (1, 2))
        raw["territoryMap"]["territoryCapacity"]["familyId"] = "fam-b"
        self.assertIsNone(self.reader.read(raw, context)[0])
        raw["territoryMap"]["territoryCapacity"]["familyId"] = "fam-a"
        raw["revision"] = 2
        self.assertIsNone(self.reader.read(raw, context)[0])

    def test_accepted_read_cannot_attach_to_newer_sync(self):
        raw = self.h.snapshot(native={"fullSync": True,
            "family": {"id": "fam-a"}})
        query = self.h.load(
            "src/tabs/territory/TerritoryMapQuery.luau").new()
        request, _ = query.Prepare(query, "vespera", raw)
        accepted, _ = query.Accept(query, request,
            lua_table(self.h.lua, {"ok": True, "city": "vespera",
                "territoryCapacity": {"familyId": "fam-a"},
                "districts": [{"id": "d1", "mine": True}]}))
        attach = self.h.load(
            "src/tabs/territory/ReadAttachment.luau")
        newer = self.h.snapshot(revision=2, native={"fullSync": True,
            "family": {"id": "fam-a"}})
        self.assertIsNone(attach.attach(newer, accepted)[0])

    def test_residency_attachment_requires_same_sync_and_map_district(self):
        raw = self.h.snapshot(native={"fullSync": True,
            "family": {"id": "fam-a"}})
        map_query = self.h.load(
            "src/tabs/territory/TerritoryMapQuery.luau").new()
        request, _ = map_query.Prepare(map_query, "vespera", raw)
        accepted, _ = map_query.Accept(map_query, request,
            lua_table(self.h.lua, {"ok": True, "city": "vespera",
                "territoryCapacity": {"familyId": "fam-a"},
                "districts": [{"id": "d1", "mine": False}]}))
        residency_query = self.h.load(
            "src/tabs/territory/ResidencyQuery.luau").new()
        residency_request, _ = residency_query.Prepare(
            residency_query, "d1", raw)
        residency, _ = residency_query.Accept(residency_query,
            residency_request, lua_table(self.h.lua, {"ok": True,
                "districtId": "d1", "admission": "open",
                "kind": "landlord", "rent": 3}))
        attach = self.h.load(
            "src/tabs/territory/ReadAttachment.luau")
        combined, reason = attach.attach(raw, accepted, residency)
        self.assertIsNone(reason)
        self.assertEqual(combined["residencyView"]["districtId"], "d1")
        residency["districtId"] = "other"
        self.assertIsNone(attach.attach(raw, accepted, residency)[0])

    def test_tab_descriptors_never_propose_mutations(self):
        entry = self.h.load("src/tabs/territory/Module.luau")
        tab = entry.new(lua_table(self.h.lua, {
            "TerritoryMapQuery": self.h.load(
                "src/tabs/territory/TerritoryMapQuery.luau"),
            "ResidencyQuery": self.h.load(
                "src/tabs/territory/ResidencyQuery.luau"),
            "TerritoryState": self.reader,
            "ReadAttachment": self.h.load(
                "src/tabs/territory/ReadAttachment.luau"),
            "TerritoryBlocked": self.blocked,
        }))
        self.assertEqual([d["id"] for d in tab.Descriptors(tab).values()],
                         ["territoryWatch", "station", "residency"])
        registry = self.h.load("src/engine/FeatureRegistry.luau")
        catalog = self.h.load("src/ui/Catalog.luau")
        specs, reason = registry.fromTabs(
            lua_table(self.h.lua, [tab]), catalog)
        self.assertIsNone(reason)
        self.assertEqual(len(specs), 3)
        self.assertIsNone(self.blocked.propose()[0])
        self.assertIsNone(self.blocked.capture()[0])

    def test_tab_owns_optional_read_runtime_factory(self):
        entry = self.h.load("src/tabs/territory/Module.luau")
        tab = entry.new(lua_table(self.h.lua, {
            "TerritoryMapQuery": self.h.load(
                "src/tabs/territory/TerritoryMapQuery.luau"),
            "ResidencyQuery": self.h.load(
                "src/tabs/territory/ResidencyQuery.luau"),
            "TerritoryState": self.reader,
            "ReadAttachment": self.h.load(
                "src/tabs/territory/ReadAttachment.luau"),
            "TerritoryBlocked": self.blocked,
            "TerritoryReadRuntime": self.h.load(
                "src/tabs/territory/TerritoryReadRuntime.luau"),
        }))
        budget = self.h.load("src/engine/ReadBudget.luau").new(
            self.h.clock, lua_table(self.h.lua, [
                {"id": "territoryMap", "interval": 30},
                {"id": "residencyView", "interval": 30}]), 8, 120)
        executor = self.h.lua.execute("""return {
            Schedule = function() end, Invoke = function() end }
        """)
        runtime, reason = tab.NewReadRuntime(tab, budget, executor,
            self.h.lua.eval("function() return nil end"),
            self.h.lua.eval("function() end"))
        self.assertIsNone(reason)
        raw = self.h.snapshot(native={"fullSync": True,
            "family": {"id": "fam-a"}})
        self.assertTrue(runtime.QueueMap(runtime, "vespera", raw)[0])
        runtime.Close(runtime)

    def test_residency_view_is_bounded_and_stale_fenced(self):
        query = self.h.load(
            "src/tabs/territory/ResidencyQuery.luau").new()
        first, _ = query.Prepare(query, "d1")
        second, _ = query.Prepare(query, "d2")
        self.assertEqual((second["remote"], second["args"][1],
                          second["args"][2], second["args"][3]),
                         ("ResidencyAction", "view", "d2", 1))
        reply = lua_table(self.h.lua, {"ok": True,
            "districtId": "d2", "admission": "open",
            "kind": "landlord", "rent": 3, "share": 0.25,
            "count": 20, "capacity": 500})
        self.assertIsNone(query.Accept(query, first, reply)[0])
        view, reason = query.Accept(query, second, reply)
        self.assertIsNone(reason)
        self.assertEqual((view["status"], view["rent"]), ("none", 3))
        wrong, _ = query.Prepare(query, "d1")
        self.assertIsNone(query.Accept(query, wrong, reply)[0])


if __name__ == "__main__":
    unittest.main()
