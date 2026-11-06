"""Actual App high-only admission, durable outcomes, queue fencing and opt-ins."""
import unittest
import test_player_combat_planner_app as fixture
import test_player_fight_evidence as evidence_fixture
from engine_harness import lua_table

class HighValueAppTests(unittest.TestCase):
    def setUp(self):
        self.b=fixture.PlayerCombatPlannerAppTests();self.b.setUp();self.f=self.b.f;self.h=self.b.h;self.app=self.b.app
    def high(self,lookup=False):
        self.assertTrue(self.app.Set(self.app,'combat.custom.targetSource','High value only + lookup' if lookup else 'High value only')[0])
    def promote(self,close=False,cash=1000000000):
        for packet in (self.f.result.initial,self.f.result.final):packet['cashEstimate']=cash
        self.f.result.final.update(cashConfirmed=cash,stolen=cash)
        self.h.lua.globals().fixtureFightReply=lua_table(self.h.lua,self.f.result.initial)
        self.f.begin();self.f.send()
        if close:
            self.f.source.callback('fightcash','',lua_table(self.h.lua,self.f.result.final));self.app.Destroy(self.app)
        else:self.f.settle();self.app.Destroy(self.app)
        self.h.session['session']='high-value-reload'
        raw=self.f.result.before;raw.session=self.h.session['session'];raw.revision=1;raw.capturedAt=1
        raw.native.serverNow+=86400;raw.native.attackDaily.day+=1;raw.native.attackDaily.counts=self.h.lua.table();self.h.at(1)
        self.f.result.day=raw.native.attackDaily.day
        self.f.start();self.app=self.f.app;self.b.app=self.app;self.b.seed(False)
        for key,value in [('minimumPayout',0),('minSamples',0),('maxAttackSpend',10),('maxStaminaCost',5)]:
            self.app.Set(self.app,'combat.custom.'+key,value)
    def append(self,n,cash,target=42,age=100):
        f=evidence_fixture.PlayerFightEvidenceTests();f.provided_h=self.h;f.setUp()
        f.p.requestId=n;f.p.actionKey='owned-history:'+str(n);at=self.f.result.before.native.serverNow-age+n
        name='Target B' if target==42 else 'Target_'+str(target)
        f.p.intent.target=target;f.p.intent.targetName=name
        f.before.hitListProof.rows[1].userId=target;f.before.hitListProof.rows[1].name=name
        f.after.native.attackDaily.counts=lua_table(self.h.lua,{str(target):1})
        f.p.intent.serverNow=at;f.before.native.serverNow=at;f.after.native.serverNow=at+1
        f.before.capturedAt=0;f.after.capturedAt=0
        f.before.native.attackDaily.day=int(at//86400);f.after.native.attackDaily.day=int(at//86400)
        for packet in (f.initial,f.final):
            packet['fightId']='history-'+str(n);packet['cashEstimate']=cash;packet['targetName']=name
            if 'targetDaily' in packet:packet['targetDaily'].update(serverNow=at,day=int(at//86400))
        f.final.update(cashConfirmed=cash,stolen=cash)
        attempt=f.after.playerFightProof.attempts[1];attempt.actionKey=f.p.actionKey;attempt.target=target
        attempt.initial=lua_table(self.h.lua,f.initial);attempt.receipt=lua_table(self.h.lua,f.final)
        f.baseline=f.e.capture(f.p,f.before)[0];self.assertIsNotNone(f.baseline)
        self.assertTrue(self.f.ledger.Record(self.f.ledger,f.data(),f.after)[0])
    def test_no_tag_or_forged_snapshot_tag_can_authorize_fight(self):
        self.high();raw=self.f.result.before
        raw.playerFightHistoryProof=lua_table(self.h.lua,{**self.h.session,'revision':raw.revision,'capturedAt':raw.capturedAt,
            'recent':[],'highValue':{'known':True,'count':1,'lastRequestId':0,'targets':{'42':{'userId':42,'history':[]}}}})
        self.app.Set(self.app,'combat.enabled',True);self.app.Resume(self.app);self.f.step()
        self.assertEqual(len(self.f.executor.queued),0);self.assertEqual(self.f.executor.calls,0)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).combatMemory.count,0)
    def test_exact_confirmed_promotion_reloads_and_reaches_real_adapter_only_with_budget(self):
        self.promote();self.high();self.app.Set(self.app,'combat.custom.maxAttackSpend',0)
        self.app.Set(self.app,'combat.enabled',True);self.app.Resume(self.app);self.f.step()
        self.assertEqual(len(self.f.executor.queued),0)
        self.app.Set(self.app,'combat.custom.maxAttackSpend',10);self.f.step()
        self.assertEqual(len(self.f.executor.queued),1)
        self.assertTrue(self.f.runtime.checkpoint.Recovery(self.f.runtime.checkpoint,self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)[1].actionKey)[0].proposal.intent.highValueOnly)
        self.f.send();self.assertEqual(self.f.executor.calls,1)
    def test_graceful_unload_preserves_promotion_and_recovery_does_not_double_count(self):
        self.promote(close=True);self.f.step()
        status=self.f.runtime.Status(self.f.runtime);self.assertEqual(status.recoveries.combat,'confirmed')
        self.assertEqual(status.combatMemory.count,1);self.assertEqual(self.f.ledger.Summary(self.f.ledger).fights,1)
        self.assertEqual(self.f.executor.calls,0)
    def test_queued_demotion_refuses_without_refunding_previous_sent_allowance(self):
        self.promote();self.high();self.f.begin()
        for n in (2,3,4):self.append(n,0)
        self.f.executor.queued[1]();self.assertEqual(self.f.executor.calls,0)
        self.assertEqual(self.f.runtime.checkpoint.Allowance(self.f.runtime.checkpoint,'combat')[0].attackSpent,5)
        self.assertEqual(self.f.ledger.HighValueStatus(self.f.ledger,self.f.result.before).count,0)
    def test_disable_source_change_and_unload_fence_queued_high_attack(self):
        for change in ('disable','source','unload'):
            if change!='disable':self.tearDown();self.setUp()
            self.promote();self.high();self.f.begin()
            if change=='unload':self.app.Destroy(self.app)
            else:
                self.app.Set(self.app,'combat.enabled' if change=='disable' else 'combat.custom.targetSource',False if change=='disable' else 'Saved and new')
                self.f.step()
            self.f.executor.queued[1]();self.assertEqual(self.f.executor.calls,0)
    def test_tag_does_not_implicitly_enable_scout_and_status_is_read_only(self):
        self.promote();self.f.tab.playerProfiles.cache['42'].statsHidden=True;self.f.tab.playerProfiles.cache['42'].defense=None;self.high();self.app.Set(self.app,'combat.enabled',True)
        self.app.Resume(self.app);self.f.step();self.assertEqual(len(self.f.executor.queued),0)
        for _ in range(5):self.assertEqual(self.f.runtime.Status(self.f.runtime).combatMemory.count,1)
        self.assertEqual(self.f.executor.calls,0)
        self.app.Set(self.app,'combat.custom.allowScout',True);self.app.Set(self.app,'combat.custom.maxScoutSpend',5);self.f.step()
        self.assertEqual(len(self.f.executor.queued),1)
    def test_disabled_high_source_keeps_cheap_status_without_projecting_target_histories(self):
        self.promote();self.high();self.f.step()
        self.assertFalse(self.app.model['values']['combat.enabled'])
        self.assertIsNone(self.f.runtime.allowanceSnapshot.playerFightHistoryProof.highValue)
        self.assertEqual(self.f.runtime.Status(self.f.runtime).combatMemory.count,1)
        self.assertEqual(self.f.executor.calls,0)
    def tearDown(self):
        if hasattr(self,'f'):self.f.tearDown()
