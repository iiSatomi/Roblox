"""Custom high-value rules belong to settled owned actions, never later settings."""
import unittest
import test_high_value_memory as fixture

class HighValueRulesTests(unittest.TestCase):
    def setUp(self):
        self.m=fixture.HighValueMemoryTests();self.m.setUp();self.h=self.m.h
    def rules(self,promote=500,below=100,hits=3):
        i=self.m.f.p.intent;i.highPromoteCash=promote;i.highDemoteBelow=below;i.highDemoteHits=hits
    def test_nondefault_thresholds_promote_demote_and_reload(self):
        self.rules();self.assertTrue(self.m.record(1,500)[0]);self.assertEqual(self.m.status().count,1)
        self.assertEqual(self.m.owner.Summary(self.m.owner).highValue.version,2)
        for n in (2,3):self.assertTrue(self.m.record(n,99)[0]);self.assertEqual(self.m.status().count,1)
        self.assertTrue(self.m.record(4,99)[0]);self.assertEqual(self.m.status().count,0)
        self.m.owner=self.m.new();self.assertTrue(self.m.status().known)
    def test_zero_low_threshold_disables_demotion_and_promotion_wins_overlap(self):
        self.rules(below=0,hits=1);self.m.record(1,500)
        for n in range(2,7):self.assertTrue(self.m.record(n,0)[0])
        self.assertEqual(self.m.status().count,1)
        self.rules(promote=500,below=1000,hits=1)
        self.assertTrue(self.m.record(7,500)[0]);self.assertEqual(self.m.status().count,1)
        self.assertTrue(self.m.record(8,499)[0]);self.assertEqual(self.m.status().count,0)
    def test_rule_changes_are_future_only_and_each_receipt_keeps_its_own_rules(self):
        self.rules();self.m.record(1,500)
        self.rules(promote=1000,below=100,hits=2)
        self.assertEqual(self.m.status().count,1)
        self.m.record(2,99);self.assertEqual(self.m.status().count,1)
        self.rules(promote=1000,below=100,hits=3)
        self.m.record(3,99);self.assertEqual(self.m.status().count,1)
        self.m.record(4,99);self.assertEqual(self.m.status().count,0)
        rows=self.m.owner.Summary(self.m.owner).recent
        self.assertEqual((rows[1].highPromoteCash,rows[2].highDemoteHits,rows[3].highDemoteHits),(500,2,3))
    def test_100_low_hits_remain_exact_past_the_32_sample_window(self):
        self.rules(hits=100);self.assertTrue(self.m.record(1,500)[0])
        for n in range(2,101):self.assertTrue(self.m.record(n,0)[0])
        self.assertEqual(self.m.owner.Summary(self.m.owner).highValue.targets['42'].lowStreak,99)
        self.m.owner=self.m.new();self.assertEqual(self.m.status().count,1)
        self.assertTrue(self.m.record(101,0)[0]);self.assertEqual(self.m.status().count,0)
    def test_pending_rules_are_bound_to_baseline_and_recovery_not_mutable_intent(self):
        self.rules();self.assertTrue(self.m.record(1,500)[0])
        self.assertEqual(self.m.f.baseline.highPromoteCash,500)
        self.m.f.p.intent.highPromoteCash=1000
        self.assertIsNone(self.m.f.e.outcome(self.m.f.data(),self.m.f.after))
    def test_invalid_or_partial_custom_rules_refuse_capture(self):
        for field,value in [('highPromoteCash',0),('highPromoteCash',1000000000000001),('highDemoteBelow',-1),
                ('highDemoteHits',0),('highDemoteHits',101),('highDemoteHits',1.5),('highDemoteHits',True),('highDemoteHits',None)]:
            self.rules();self.m.f.p.intent[field]=value
            self.assertIsNone(self.m.f.e.capture(self.m.f.p,self.m.f.before)[0],(field,value))
    def test_compacted_memory_cannot_skip_a_recent_custom_low_or_promotion(self):
        self.rules()
        for n in range(1,34):self.assertTrue(self.m.record(n,1,100+n)[0])
        self.m.record(34,500);self.m.record(35,0)
        target=self.m.storage.data[self.m.owner.key].highValue.targets['42'];target.lowStreak=0
        self.assertIsNone(self.m.module.new(self.m.storage,self.h.lua.table_from(self.h.session),self.m.f.e)[0])
    def test_custom_tags_survive_a_full_window_of_default_rules_without_reclassification(self):
        self.rules();self.m.record(1,500)
        for key in ('highPromoteCash','highDemoteBelow','highDemoteHits'):self.m.f.p.intent[key]=None
        for n in range(2,36):self.assertTrue(self.m.record(n,100000000)[0])
        self.m.owner=self.m.new();tag=self.m.owner.Summary(self.m.owner).highValue.targets['42']
        self.assertEqual((tag.lastHighCash,tag.lowStreak),(500,0));self.assertEqual(self.m.status().count,1)
    def test_custom_rules_maximum_envelope_still_fits_storage_and_selected_recovery(self):
        import json
        import test_redundant_store as disk_fixture
        from engine_harness import lua_table
        self.m.test_full_target_history_envelope_fits_actual_redundant_store()
        raw=disk_fixture.plain(self.m.owner.Summary(self.m.owner));cash=raw['recent'][0]['receipt']['cashConfirmed']
        raw['highValue'].update(version=2,rules='owned-action-rules-v1')
        for row in raw['recent']:row.update(highPromoteCash=cash,highDemoteBelow=1000000000000000,highDemoteHits=100)
        self.m.storage.data[self.m.owner.key]=lua_table(self.h.lua,raw);self.m.owner=self.m.new()
        payload=disk_fixture.plain(self.m.owner.Summary(self.m.owner))
        self.assertLess(len(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()),800000)
        disk=disk_fixture.RedundantStoreTests();disk.setUp()
        self.assertTrue(disk.store.Write(disk.store,'full-custom-memory',lua_table(disk.h.lua,payload)))
        before=self.m.f.before;before.native.serverNow=self.m.f.now+4097
        before.hitListProof.rows=lua_table(self.h.lua,[{'userId':i} for i in range(101,229)])
        before.playerFightHistoryProof=self.m.owner.Proof(self.m.owner,before,True)
        self.m.f.p.intent.target=228;self.m.f.p.intent.highValueOnly=True
        pending=self.h.load('src/storage/PendingAction.luau')
        saved,why=pending.Capture(self.m.f.p,before,self.m.f.baseline);self.assertIsNotNone(saved,why)
        self.assertEqual(pending.Decode(saved).before.playerFightHistoryProof.highValue.targets['228'].userId,228)
