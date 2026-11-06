"""Current native observations applied to the recovered release's own fixtures."""
import unittest
import test_crew_replacement as replacement
import test_territory_stationing as stationing
import test_territory_tab as territory
from engine_harness import lua_table


class RestoredTerritoryRegressions(unittest.TestCase):
    def test_capacity_uses_ordering_marker_not_seconds_clock(self):
        f = territory.TerritoryTabTests(); f.setUp()
        raw = f.h.snapshot(native={'fullSync': True, 'serverNow': 1793949072,
                                  'family': {'id': 'fam-a'}})
        query = f.h.load('src/tabs/territory/TerritoryMapQuery.luau').new()
        request, _ = query.Prepare(query, 'jade_harbor', raw)
        accepted, reason = query.Accept(query, request, lua_table(f.h.lua, {
            'ok': True, 'city': 'jade_harbor', 'totalDistricts': 1,
            'territoryCapacity': {'familyId': 'fam-a', 'held': 15, 'maximum': 15,
                                  'checkedAt': 1793949072032},
            'districts': [{'id': 'd1', 'mine': True}]}))
        self.assertIsNone(reason)
        raw, reason = f.h.load('src/tabs/territory/ReadAttachment.luau').attach(raw, accepted)
        self.assertIsNone(reason)
        view, reason = f.reader.read(raw, raw)
        self.assertIsNone(reason)
        self.assertEqual((view.familyCapacity.held, view.familyCapacity.available), (15, 0))
        raw.native.territoryCapacity = lua_table(f.h.lua, {
            'familyId': 'fam-a', 'held': 14, 'maximum': 15, 'checkedAt': 1793949072032})
        self.assertIsNone(f.reader.read(raw, raw)[0])

    def test_rate_limited_negative_dismissal_keeps_custody(self):
        f = replacement.CrewReplacementTests(); f.setUp()
        proposal, before = f.prepare()
        baseline, reason = f.source.capture(proposal, before)
        self.assertIsNone(reason)
        self.assertTrue(f.tx.MarkSending(f.tx, before, 1)[0])
        reply = lua_table(f.h.lua, {'ok': False, 'code': 'rate_limited'})
        self.assertTrue(f.tx.AcceptReply(f.tx, proposal.actionKey, reply)[0])
        self.assertEqual(f.source.evaluate(proposal, before, f.raw(revision=2), reply, baseline), 'pending')
        f.tx.Reconcile(f.tx, f.raw(revision=2), 2)
        self.assertIsNotNone(f.tx.Active(f.tx))

    def test_unselected_legacy_deployment_keeps_identity_and_blocks_selection(self):
        f = stationing.TerritoryStationingTests(); f.setUp()
        raw = f.before()
        legacy = raw.native.crew[3]
        legacy.healId, legacy.duty, legacy.dutyToken = None, 'd2', 'legacy-deployment'
        view, reason = f.module.read(raw, raw)
        self.assertIsNone(reason)
        self.assertEqual(view.members[3].key, 'deployment:legacy-deployment')
        self.assertIsNotNone(f.module.propose(view, f.settings(minHome=1))[0])
        self.assertIsNone(f.module.propose(view, f.settings(memberSlot=3, minHome=0))[0])
        raw.native.crew[4].dutyToken = 'legacy-deployment'
        self.assertIsNone(f.module.read(raw, raw)[0])
