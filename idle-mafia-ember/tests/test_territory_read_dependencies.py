"""Unavailable map dependencies do not consume native-read failure backoff."""
import unittest

from engine_harness import Harness, lua_table


class TerritoryReadDependencyTests(unittest.TestCase):
    def test_real_coordinator_with_five_second_sync_keeps_dependent_reads_eligible_only_with_map(self):
        h = Harness()
        reader = h.load("src/transport/NativeSnapshotReader.luau").new(
            lua_table(h.lua, h.session), h.clock, "a" * 64)
        deps = {"fingerprint": "a" * 64, "release": "release-a",
            "gameData": {"DISTRICTS_BY_ID": {"d1": {"city": "jade_harbor"}}}}
        for name in ("TerritoryMapQuery", "DistrictQuery", "ResidencyQuery", "ReadAttachment"):
            deps[name] = h.load("src/tabs/territory/" + name + ".luau")
        owner = h.load("src/tabs/territory/TerritoryReadSources.luau").new(lua_table(h.lua, deps))
        sources = owner.Sources(owner, reader)
        specs = [{"id": row.id, "interval": row.interval} for row in sources.values()]
        budget = h.load("src/engine/ReadBudget.luau").new(h.clock, lua_table(h.lua, specs), 5, 60)
        state = h.lua.execute("""return {queued={},calls={},
            Schedule=function(self,fn) self.queued[#self.queued+1]=fn end,
            InvokeOwned=function(self,_,remote,method,command)
                self.calls[#self.calls+1]=command
                if command=='map' then return {ok=true,city='jade_harbor',totalDistricts=1,
                    territoryCapacity={familyId='fam-a'},districts={{id='d1',mine=true}}} end
                return {ok=true,district={id='d1',mine=true,holderId='fam-a',garrisonCount=2,revision=1}}
            end,
            Drain=function(self) local q=self.queued;self.queued={};for _,fn in ipairs(q) do fn() end end}""")
        h.lua.globals().dependencyReader = reader
        coordinator = h.load("src/transport/ReadCoordinator.luau").new(lua_table(h.lua, {
            "clock": h.clock, "lane": h.load("src/engine/RequestLane.luau").new(h.clock),
            "budget": budget, "executor": state, "sources": sources,
            "currentSnapshot": h.lua.eval("function() return dependencyReader:Capture() end")}))
        settings = lua_table(h.lua, {"station": {"enabled": True, "custom": {"districtId": "d1"}}})
        saw_both = []
        for second in range(32):
            h.at(second)
            if second % 5 == 0:
                reader.ObserveSync(reader, lua_table(h.lua, {"serverNow": 100 + second, "family": {"id": "fam-a"}}))
            raw, _ = reader.Capture(reader)
            eligible = {row.id: row.enabled(settings, None, raw) for row in sources.values()}
            coordinator.Step(coordinator, raw, lua_table(h.lua, eligible))
            state.Drain(state)
            self.assertEqual(budget.Status(budget).territoryDistrict.failures, 0, second)
            current, _ = reader.Capture(reader)
            if current.territoryMap is not None and current.territoryDistrict is not None:
                saw_both.append(second)
        self.assertIn(1, saw_both)
        self.assertIn(16, saw_both)
        self.assertIn(31, saw_both)
        self.assertEqual(list(state.calls.values()).count("district"), 3)


if __name__ == "__main__":
    unittest.main()
