"""Actual read-only Watch App path distinguishes city holdings and Family cap."""
import unittest
import test_territory_shared_sources as fixture
from engine_harness import lua_table

class TerritoryWatchRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.TerritorySharedSourcesTests();self.f.setUp();self.h=self.f.h
        self.app,self.runtime=self.f.start_app()
        self.f.executor.mapReply=lua_table(self.h.lua,{'ok':True,'city':'vespera','totalDistricts':1,
            'territoryCapacity':{'familyId':'fam-a','held':8,'maximum':10,'checkedAt':1000},
            'districts':[{'id':'d1','holderId':'fam-a','shieldUntil':1100}]})
    def tearDown(self):self.app.Destroy(self.app);self.f.tearDown()
    def choose(self):
        self.app.Set(self.app,'territoryWatch.enabled',True);self.app.Resume(self.app)
    def pump(self):
        for index in range(7):
            self.h.at(index*.1);self.app.Step(self.app,self.f.reader.Capture(self.f.reader)[0])
            queued,self.f.executor.queued=self.f.executor.queued,self.h.lua.table()
            for callback in queued.values():callback()
    def test_native_holder_and_family_capacity_are_preserved_and_displayed(self):
        self.choose();self.pump();status=self.runtime.Status(self.runtime)
        self.assertIn('1/1 held',status.reasons.territoryWatch)
        self.assertIn('Family 8/10',status.reasons.territoryWatch)
        self.assertEqual(len(self.h.transport.sent),0)
        self.assertEqual(len(self.runtime.checkpoint.Records(self.runtime.checkpoint)),0)
    def test_newer_capacity_from_same_native_sync_wins_without_changing_city_count(self):
        self.f.native.territoryCapacity=lua_table(self.h.lua,{'familyId':'fam-a','held':9,'maximum':10,'checkedAt':1001})
        self.f.reader.ObserveSync(self.f.reader,self.f.native);self.choose();self.pump()
        self.assertIn('Family 9/10',self.runtime.Status(self.runtime).reasons.territoryWatch)
    def test_family_over_capacity_is_visible_without_invented_admission(self):
        self.f.executor.mapReply.territoryCapacity.held=11
        self.choose();self.pump();self.assertIn('Family 11/10',self.runtime.Status(self.runtime).reasons.territoryWatch)
        self.assertEqual(len(self.h.transport.sent),0)
    def test_unknown_capacity_is_reported_as_unknown(self):
        cap=self.f.executor.mapReply.territoryCapacity;cap.held=cap.maximum=cap.checkedAt=None
        self.choose();self.pump()
        self.assertIn('Family capacity unavailable',self.runtime.Status(self.runtime).reasons.territoryWatch)
    def test_malformed_partial_capacity_is_not_displayed_as_complete(self):
        self.f.executor.mapReply.territoryCapacity.maximum=None
        self.choose();self.pump()
        self.assertNotIn('Family 8/',self.runtime.Status(self.runtime).reasons.territoryWatch)
        self.assertIsNone(self.f.reader.Capture(self.f.reader)[0].territoryMap)
    def test_capacity_projection_is_not_aliased_to_returned_reply(self):
        self.choose();self.pump();self.f.executor.mapReply.territoryCapacity.held=100
        self.assertEqual(self.f.reader.Capture(self.f.reader)[0].territoryMap.territoryCapacity.held,8)
    def test_conflicting_native_mine_and_holder_are_refused(self):
        self.f.executor.mapReply.districts[1].mine=False
        self.choose();self.pump();self.assertIsNone(self.f.reader.Capture(self.f.reader)[0].territoryMap)
    def test_pending_reply_does_not_become_watch_facts(self):
        self.f.executor.mapReply.pending=True;self.choose();self.pump()
        self.assertIsNone(self.f.reader.Capture(self.f.reader)[0].territoryMap)
    def test_all_off_has_no_read_or_mutation(self):
        self.pump();self.assertEqual(len(self.f.executor.calls),0);self.assertEqual(len(self.h.transport.sent),0)
