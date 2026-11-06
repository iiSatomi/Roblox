"""Reserve a fresh-Sync window for dependent Territory reads without aging proofs."""
import unittest
from lupa import LuaError
from engine_harness import lua_table
import test_territory_shared_sources as fixture


class TerritoryReadFreshnessTests(unittest.TestCase):
    def setUp(self):
        self.f = fixture.TerritorySharedSourcesTests(); self.f.setUp()
        self.h = self.f.h
        self.f.coordinator.Close(self.f.coordinator)
        self.f.settings = lua_table(self.h.lua, {'station': {'enabled': True, 'districtId': 'd1'}})
        self.budget = self.h.load('src/engine/ReadBudget.luau').new(self.h.clock,
            lua_table(self.h.lua, [{'id': row.id, 'interval': row.interval} for row in self.f.sources.values()]), 5, 60)
        self.deps = lua_table(self.h.lua, {'clock': self.h.clock, 'lane': self.f.lane,
            'budget': self.budget, 'executor': self.f.executor, 'sources': self.f.sources,
            'currentSnapshot': self.h.lua.eval('function() return territoryNativeReader:Capture() end')})
        self.coordinator_module = self.h.load('src/transport/ReadCoordinator.luau')
        self.f.coordinator = self.coordinator_module.new(self.deps)
        self.h.lua.globals().timedReadPriorInvoke = self.f.executor.InvokeOwned
        self.h.lua.globals().timedReadFinish = lambda: self.h.at(self.h.clock.Now(self.h.clock) + .12)
        self.f.executor.InvokeOwned = self.h.lua.eval('''function(self,...)
            local reply=timedReadPriorInvoke(self,...); timedReadFinish(); return reply
        end''')

    def tearDown(self): self.f.tearDown()

    def source(self, id): return next(row for row in self.f.sources.values() if row.id == id)

    def test_late_completion_cadence_defers_without_budget_then_next_sync_allows_station_proposal(self):
        # A prior map finished 1.9 seconds after Sync; completion-relative15s
        # cadence next becomes due near the end of the next2s freshness window.
        self.h.at(1.8)
        _, token = self.budget.Due(self.budget, lua_table(self.h.lua, {'territoryMap': True}))
        self.h.at(1.9); self.assertTrue(self.budget.Finish(self.budget, token, True))
        self.h.at(15); self.f.native.serverNow = 1015
        self.f.native.crew = lua_table(self.h.lua, [{'name': 'Player'},
            {'name': 'Selected', 'rarity': 4, 'healId': 'selected'},
            {'name': 'Home', 'rarity': 3, 'healId': 'home'}])
        self.f.reader.ObserveSync(self.f.reader, self.f.native)
        self.h.at(16.9)
        before = self.budget.Status(self.budget).territoryMap
        self.assertEqual(self.f.step(), 'idle')
        self.assertEqual(len(self.f.executor.calls), 0)
        after = self.budget.Status(self.budget).territoryMap
        self.assertEqual((after.nextAt, after.failures), (before.nextAt, before.failures))
        self.assertIsNone(self.f.lane.Status(self.f.lane).active)
        self.assertEqual(self.f.coordinator.Status(self.f.coordinator).reasons.territoryMap,
                         'Read deferred until a fresh Sync')
        # It is still due, so the next genuine Sync starts both reads promptly.
        self.h.at(30); self.f.native.serverNow = 1030
        self.f.reader.ObserveSync(self.f.reader, self.f.native)
        self.h.at(30.25); self.assertEqual(self.f.step(), 'queued')
        self.h.at(30.5); self.assertEqual(self.f.step(), 'queued')
        raw = self.f.reader.Capture(self.f.reader)[0]
        self.assertIsNotNone(raw.territoryMap)
        self.assertIsNotNone(raw.territoryDistrict)
        self.assertLess(self.h.clock.Now(self.h.clock) - raw.capturedAt, 2)
        self.assertEqual([row.args[1] for row in self.f.executor.calls.values()], ['map', 'district'])
        station = self.h.load('src/tabs/territory/Stationing.luau')
        state = station.new(lua_table(self.h.lua, {'TERRITORY': {'garrisonCap': 10}}),
            lua_table(self.h.lua, {'DISTRICTS_BY_ID': {'d1': {'city': 'vespera'}}}), 'a' * 64, 'release-a')
        raw, reason = state.Enrich(state, raw); self.assertIsNone(reason)
        raw.stationReservationProof = lua_table(self.h.lua, {**self.h.session,
            'revision': raw.revision, 'capturedAt': raw.capturedAt, 'members': {}, 'attempted': 0})
        view, reason = station.read(raw, raw); self.assertIsNone(reason)
        proposal, reason = station.propose(view, lua_table(self.h.lua, {'enabled': True,
            'districtId': 'd1', 'memberSlot': 2, 'minHome': 1, 'maxAttempts': 1}))
        self.assertIsNotNone(proposal, reason)
        self.assertEqual((proposal.intent.kind, proposal.intent.memberKey), ('territoryStation', 'id:selected'))
        self.assertIsNotNone(station.capture(proposal, raw)[0])

    def test_admitted_map_return_uses_existing_two_second_result_bound(self):
        self.h.at(.9); self.assertEqual(self.f.step(drain=False), 'queued')
        self.h.at(1.1)
        self.assertEqual(self.f.step(drain=False), 'in_flight')
        self.f.executor.queued[1]()
        self.assertIsNotNone(self.f.reader.Capture(self.f.reader)[0].territoryMap)
        self.assertIsNone(self.f.coordinator.Status(self.f.coordinator).reasons.territoryMap)

    def test_unrelated_read_keeps_existing_freshness_window(self):
        self.f.settings = lua_table(self.h.lua, {'residency': {'enabled': True, 'districtId': 'd1'}})
        self.h.at(1.8); self.assertEqual(self.f.step(), 'queued')
        self.assertEqual(self.f.executor.calls[1].args[1], 'view')
        self.assertIsNotNone(self.f.reader.Capture(self.f.reader)[0].residencyView)
        self.assertIsNone(self.f.coordinator.Status(self.f.coordinator).reasons.territoryMap)

    def test_invalid_start_age_rejected_and_constructor_captures_it(self):
        source = self.source('territoryMap')
        for value in (0, -1, 2.01, '1', True, float('inf'), float('nan')):
            with self.subTest(value=value):
                source.latestStartAge = value
                with self.assertRaises(LuaError): self.coordinator_module.new(self.deps)
        source.latestStartAge = 2
        self.h.at(1.8)
        # The existing owner's copied1s limit cannot be widened by changing a spec.
        self.assertEqual(self.f.step(), 'idle')
        self.assertEqual(len(self.f.executor.calls), 0)


if __name__ == '__main__': unittest.main()
