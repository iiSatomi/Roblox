"""Read-only legacy settlement inspection preserves original evidence and scope."""
import unittest

import test_favor_help as favor_fixture
from engine_harness import ROOT, lua_table


def plain(value):
    return {k:plain(v) for k,v in value.items()} if hasattr(value,'items') else value


class LegacyCompletionReceiptTests(unittest.TestCase):
    def setUp(self):
        self.f = favor_fixture.FavorHelpTests(); self.f.setUp()
        self.h = self.f.h
        self.path = 'src/storage/LegacyCompletionReceipts.luau'
        self.pending = self.h.load('src/storage/PendingAction.luau')
        self.deps = lua_table(self.h.lua, {'identity': self.h.session,
            'modules': {'PendingAction': self.pending, 'FavorHelpEvidence': self.f.evidence}})

    def inspect(self, kind, value):
        self.assertTrue((ROOT / self.path).is_file(), 'Typed legacy receipt inspector required')
        return self.h.load(self.path).Inspect(kind, value, self.deps)

    def legacy_blob(self, blob):
        def encode(value):
            if not hasattr(value, 'items'): return value
            return {'entries': {('s:' + key if isinstance(key,str) else 'n:' + str(key)):encode(child)
                                for key,child in value.items()}}
        return lua_table(self.h.lua, {'version':1,'payload':encode(self.pending.Decode(blob))})

    def heist(self):
        before = self.f.raw()
        p, why = self.f.planner.propose(self.f.view(before)[0], self.f.settings(), self.f.reserve())
        self.assertIsNone(why)
        current = self.f.evidence.capture(p, before)[0]
        fields = ('session','account','place','release','revision','rowId','heistId','ownerId',
                  'helpsBefore','favorsBefore','favorCost','serverDay','usageAttemptsBefore')
        baseline = lua_table(self.h.lua, {k: current[k] for k in fields})
        reply = lua_table(self.h.lua, {'ok': True})
        after = self.f.raw(revision=2, favors=11, helps=1, attempts=1)
        after.native.pools.energy = 18
        observed = lua_table(self.h.lua, {k: v for k, v in p.items()})
        observed.revision = 2
        return lua_table(self.h.lua, {'version': 1, 'generation': 4,
            **{k: self.h.session[k] for k in ('account','place','release')},
            'receipt': {'outcome': 'confirmed', 'record': {'sequence': 7,
                'actionName': 'help', 'arg1': p.intent.rowId, 'sent': True, 'sentAt': 0,
                'data': self.legacy_blob(self.pending.Capture(p, before, baseline, reply)[0])},
                'observation': self.legacy_blob(self.pending.Capture(observed, after,
                    lua_table(self.h.lua, {'kind': 'heistObservation'}), reply)[0])}})

    def recall(self):
        member = {'key':'id:member-a','name':'A','rarity':1,'train':0,'duty':'district-a',
            'token':'deployment-a','at':90,'stationed':False,'injured':0,'recalled':0,
            'training':False,'rolling':False,'pending':False,'weapon':False,'armor':False,'vehicle':False}
        target = {'districtId':'district-a','userId':42,'memberIndex':2,'memberName':'A',
            'rarity':1,'deploymentId':'deployment-a','at':90}
        return lua_table(self.h.lua, {'version':1,'lastRequestId':100001,
            'receipt':{'outcome':'confirmed','record':{
                **{k:self.h.session[k] for k in ('account','place','release')},
                'userId':42,'requestId':100001,'actionKey':'recall:original',
                'cooldownSeconds':600,'replyReceived':True,'stage':'observed',
                'sentServerNow':100,'target':target,'settled':dict(target),
                'baseline':{'session':'original-session','revision':1,'capturedAt':0,
                    'serverNow':100,'familyId':'family-a','size':2,'members':{'2':member}}}}})

    def test_inactive_exact_heist_receipt_returns_detached_historical_summary(self):
        value = self.heist()
        original = plain(value)
        summary, why = self.inspect('heist', value)
        self.assertIsNone(why)
        self.assertEqual((summary.kind, summary.legacyVersion, summary.outcome), ('heist',1,'confirmed'))
        self.assertEqual(summary.sequenceFloor,7)
        self.assertEqual(summary.receiptCountFloor,1)
        self.assertIsNone(summary.nativeJob, 'No native epoch is invented for old receipts')
        self.assertTrue(summary.historicalOnly)
        self.assertFalse(summary.nativeContinuityVerified)
        self.assertEqual(plain(value),original)
        summary.originalScope.account = 'changed'
        self.assertEqual(value.account,self.h.session['account'])
        self.assertEqual(self.pending.Decode(value.receipt.record.data).baseline.favorCost,1)

    def test_heist_scope_active_transient_ambiguous_or_changed_observation_is_refused(self):
        for mode in ('scope','active','version','pending','busy','argument','baseline','observation','unsupported'):
            with self.subTest(mode=mode):
                value=self.heist()
                if mode=='scope': value.account='another-account'
                elif mode=='active': value.active=value.receipt.record
                elif mode=='version': value.version=2
                elif mode=='argument': value.receipt.record.arg1='another-row'
                else:
                    data=self.pending.Decode(value.receipt.record.data)
                    if mode=='pending': data.reply.pending=True
                    elif mode=='busy': data.reply.code='busy'
                    elif mode=='baseline': data.baseline.favorsBefore=999
                    elif mode=='unsupported': data.proposal.feature='heists'
                    elif mode=='observation':
                        observation=self.pending.Decode(value.receipt.observation)
                        observation.before.heistBoardProof.board.favorsLeft=12
                        value.receipt.observation=self.pending.Capture(observation.proposal,
                            observation.before,observation.baseline,observation.reply)[0]
                    value.receipt.record.data=self.pending.Capture(data.proposal,data.before,data.baseline,data.reply)[0]
                self.assertIsNone(self.inspect('heist',value)[0])

    def test_observed_recall_retains_request_floor_without_fabricated_attempt_total(self):
        value=self.recall()
        original=plain(value)
        summary, why=self.inspect('recall',value)
        self.assertIsNone(why)
        self.assertEqual(summary.requestFloor,100001)
        self.assertEqual(summary.receiptCountFloor,1)
        self.assertIsNone(summary.attempted)
        self.assertEqual(summary.originalScope.userId,42)
        self.assertEqual(plain(value),original)
        self.assertTrue(summary.affectedIntents.territoryRecall)
        summary.originalScope.release='changed'
        self.assertEqual(value.receipt.record.release,self.h.session['release'])

    def test_recall_active_scope_target_member_timestamp_and_unobserved_changes_are_refused(self):
        for mode in ('active','scope','version','target','member','time','stage','reply','extra'):
            with self.subTest(mode=mode):
                value=self.recall(); record=value.receipt.record
                if mode=='active': value.transaction=record
                elif mode=='scope': record.release='another-release'
                elif mode=='version': value.version=2
                elif mode=='target': record.settled.deploymentId='another-deployment'
                elif mode=='member': record.baseline.members['2'].key='deployment:deployment-a'
                elif mode=='time': record.requestId=record.requestId-10000
                elif mode=='stage': record.stage='settled'
                elif mode=='reply': record.replyReceived=False
                else: record.nativeEpoch='invented'
                self.assertIsNone(self.inspect('recall',value)[0])


if __name__ == '__main__': unittest.main()
