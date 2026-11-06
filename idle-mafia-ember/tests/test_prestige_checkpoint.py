"""Durable scoped Prestige attempt accounting shares the existing checkpoint owner."""
import unittest
import test_checkpoint_request_ids as fixture
from engine_harness import lua_table

class PrestigeCheckpointTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.CheckpointRequestIdsTests();self.f.setUp();self.h=self.f.h;self.cp=self.f.cp;self.storage=self.f.storage
    def usage(self,cp=None):
        cp=cp or self.cp;self.assertIsNotNone(cp.PrestigeUsage,'Prestige checkpoint owner is missing')
        value,why=cp.PrestigeUsage(cp,self.before());self.assertIsNotNone(value,why);return value
    def before(self):return self.h.snapshot(native={'fullSync':True,'prestige':0,'level':200,'xp':1234})
    def proposal(self,attempted=0,rank=0,limit=2):
        p=self.h.proposal('prestige','prestige:'+str(rank)+':'+str(rank+1));p.resources=self.h.lua.table()
        p.intent=lua_table(self.h.lua,{'kind':'prestigeReset','rankBefore':rank,'nextRank':rank+1,'levelBefore':200,'xpBefore':1234,
            'catalogKey':'a'*64,'requiredLevel':200,'allowReset':True,'targetRank':6,'maxResets':limit,'attemptedBefore':attempted})
        return p
    def save(self,p=None):
        return self.cp.Save(self.cp,p or self.proposal(),self.before(),lua_table(self.h.lua,{'rank':0,'level':200,'xp':1234}))
    def test_attempt_is_saved_with_numbered_action_and_retained_after_success_and_reload(self):
        self.assertEqual(self.usage().attempted,0);self.assertTrue(self.save()[0])
        self.assertEqual(self.usage().attempted,1);self.assertEqual(self.cp.Records(self.cp)[1].prestigeOrdinal,1)
        self.assertTrue(self.cp.Resolve(self.cp,'prestige:0:1','confirmed')[0])
        self.assertEqual(self.usage(self.f.new()).attempted,1)
    def test_cap_and_exact_prior_count_reject_forged_or_exhausted_attempts(self):
        self.assertTrue(self.save()[0]);self.cp.Resolve(self.cp,'prestige:0:1','rejected')
        self.assertFalse(self.save(self.proposal(attempted=0,rank=1))[0])
        self.assertTrue(self.save(self.proposal(attempted=1,rank=1))[0]);self.cp.Resolve(self.cp,'prestige:1:2','rejected')
        self.assertEqual(self.usage().attempted,2)
        self.assertFalse(self.save(self.proposal(attempted=2,rank=2))[0])
    def test_known_unsent_refund_is_exact_and_returned_or_unknown_attempts_keep_charge(self):
        self.assertTrue(self.save()[0]);self.assertTrue(self.cp.Resolve(self.cp,'prestige:0:1','schedule_failed')[0])
        self.assertEqual(self.usage().attempted,0)
        self.assertTrue(self.save()[0]);self.cp.RecordReply(self.cp,'prestige:0:1',lua_table(self.h.lua,{'ok':False}))
        self.assertFalse(self.cp.Resolve(self.cp,'prestige:0:1','schedule_failed')[0])
        self.assertEqual(self.usage().attempted,1)
        self.assertTrue(self.cp.Resolve(self.cp,'prestige:0:1','rejected')[0]);self.assertEqual(self.usage().attempted,1)
    def test_unknown_saved_attempt_is_not_replayed_or_treated_as_zero_on_reload(self):
        self.assertTrue(self.save()[0]);fresh=self.f.new()
        self.assertEqual(self.usage(fresh).attempted,1)
        self.assertFalse(fresh.Save(fresh,self.proposal(),self.before(),lua_table(self.h.lua,{'rank':0}))[0])
    def test_legacy_record_without_owned_ordinal_leaves_usage_unknown(self):
        self.assertTrue(self.save()[0]);data=self.storage.data[self.cp.ScopeKey(self.cp)]
        data.records[1].prestigeOrdinal=None;data.prestigeAttempts=None
        fresh=self.f.new();self.assertIsNotNone(fresh.PrestigeUsage)
        self.assertIsNone(fresh.PrestigeUsage(fresh,self.before())[0])
        self.assertFalse(fresh.Save(fresh,self.proposal(rank=1),self.before(),lua_table(self.h.lua,{'rank':0}))[0])
    def test_corrupt_attempt_count_or_ordinal_refuses_load(self):
        self.assertTrue(self.save()[0]);key=self.cp.ScopeKey(self.cp);data=self.storage.data[key]
        for bad in (-1,7,1.5,'1'):
            data.prestigeAttempts=bad;fresh=self.f.module.new(self.storage,None,None,self.f.pending)
            self.assertIsNone(fresh.Load(fresh,'user-a',self.h.session['place'],'release-a')[0])
        data.prestigeAttempts=1;data.records[1].prestigeOrdinal=2
        fresh=self.f.module.new(self.storage,None,None,self.f.pending)
        self.assertIsNone(fresh.Load(fresh,'user-a',self.h.session['place'],'release-a')[0])
    def test_failed_write_does_not_publish_attempt_or_rewrite_a_newer_owner(self):
        fresh=self.f.new();self.assertTrue(fresh.Save(fresh,self.proposal(),self.before(),lua_table(self.h.lua,{'rank':0}))[0])
        self.assertFalse(self.save()[0]);self.assertEqual(self.usage(fresh).attempted,1)
    def test_caller_cannot_choose_the_owned_ordinal(self):
        p=self.proposal();p.prestigeOrdinal=6;self.assertTrue(self.save(p)[0])
        self.assertEqual(self.cp.Records(self.cp)[1].prestigeOrdinal,1)

    def test_duplicate_owned_ordinals_in_different_records_refuse_load(self):
        self.assertTrue(self.save()[0]);self.assertTrue(self.save(self.proposal(attempted=1,rank=1))[0])
        stored=self.storage.data[self.cp.ScopeKey(self.cp)];row=stored.records[2]
        data=self.f.pending.Decode(row.recovery,row);data.proposal.intent.attemptedBefore=0
        row.recovery=self.f.pending.Capture(data.proposal,data.before,data.baseline)[0];row.prestigeOrdinal=1
        fresh=self.f.module.new(self.storage,None,None,self.f.pending)
        self.assertIsNone(fresh.Load(fresh,'user-a',self.h.session['place'],'release-a')[0])
