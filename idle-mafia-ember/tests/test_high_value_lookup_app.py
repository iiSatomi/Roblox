"""High-only lookup uses durable tags past the global receipt window."""
import unittest
import test_saved_search_app as fixture
import test_high_value_app as app_fixture

class HighValueLookupAppTests(unittest.TestCase):
    def setUp(self):
        self.b=fixture.SavedSearchAppTests();self.b.setUp();self.f=self.b.f;self.h=self.b.h;self.app=self.b.app
    def append(self,n,cash,target=42):app_fixture.HighValueAppTests.append(self,n,cash,target,age=86400)
    def enable(self,lookup=True):
        self.assertTrue(self.app.Set(self.app,'combat.custom.targetSource','High value only + lookup' if lookup else 'High value only')[0])
        self.app.Set(self.app,'combat.enabled',True);self.app.Resume(self.app);self.f.step()
    def test_tag_survives_global_compaction_and_lookup_retains_independent_spending_optins(self):
        self.append(2,1000000000)
        for n in range(3,36):self.append(n,1,100+n)
        self.assertNotIn(42,[row.target for row in self.f.ledger.Summary(self.f.ledger).recent.values()])
        self.enable();self.assertEqual(len(self.f.executor.queued),1);self.f.executor.queued[1]()
        self.assertEqual(self.f.executor.log[1].remote,'SearchTarget')
        self.b.tick(2);self.f.executor.queued[2]();self.b.tick(3)
        self.assertEqual(self.f.runtime.allowanceSnapshot.hitListProof.rows[1].userId,42)
        self.assertTrue(self.f.runtime.allowanceSnapshot.playerFightHistoryProof.highValue.targets['42'])
        self.assertEqual(len(self.f.executor.queued),2);self.assertEqual(len(self.f.executor.log),2)
        self.assertEqual(self.app.model['values']['combat.custom.maxAttackSpend'],0)
    def test_high_only_without_lookup_does_not_search_or_scan_catalog(self):
        self.append(2,1000000000)
        self.f.ledger.HighValueTargets=self.h.lua.eval('function() error("Unexpected catalog scan") end')
        self.enable(False);self.assertEqual(len(self.f.executor.queued),0);self.assertEqual(len(self.f.executor.log),0)
    def test_no_tag_and_demoted_tag_do_not_queue_lookup(self):
        self.enable();self.assertEqual(len(self.f.executor.queued),0)
        self.append(2,1000000000)
        for n in (3,4,5):self.append(n,0)
        self.f.step();self.assertEqual(len(self.f.executor.queued),0)
    def test_disabling_lookup_before_send_fences_read(self):
        self.append(2,1000000000);self.enable();self.assertEqual(len(self.f.executor.queued),1)
        self.app.Set(self.app,'combat.custom.targetSource','High value only');self.f.step();self.f.executor.queued[1]()
        self.assertEqual(len(self.f.executor.log),0)
    def tearDown(self):
        if hasattr(self,'b'):self.b.tearDown()
