"""Durable ordinary fight memory uses canonical settled-receipt validators."""
import unittest

from engine_harness import Harness, lua_table


class PlayerFightLedgerTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        h = self.h
        self.evidence = h.load('src/tabs/combat/PlayerFightEvidence.luau').new(
            h.load('src/tabs/combat/FightReceipts.luau'))
        self.module = h.load('src/tabs/combat/PlayerFightLedger.luau')
        self.store = h.lua.execute("""return {strictRecovery=true,data={},
            Read=function(self,k) return self.data[k] end,
            Write=function(self,k,v) self.data[k]=v;return true end}""")
        self.ledger,reason = self.module.new(self.store,lua_table(h.lua,h.session),self.evidence)
        self.assertIsNone(reason)

    def attempt(self, number, target=456, cash=1000000000, fight_id=None):
        h = self.h
        before = h.snapshot(revision=number,captured_at=number,native={'fullSync':True,
            'serverNow':100+number,'pools':{'stamina':20,'health':100},'attackDaily':{'day':0,'counts':{}}})
        head = {k:before[k] for k in ('session','account','place','release','revision','capturedAt')}
        before.playerFightProof = lua_table(h.lua,{**head,'sourceKey':'a'*64})
        before.hitListProof = lua_table(h.lua,{'account':before.account,'capturedAt':before.capturedAt,
            'rows':[{'userId':target,'name':'Target'+str(target),'level':10,'stamina':1,'shielded':False}]})
        before.playerFightUsageProof = lua_table(h.lua,{'account':before.account,'capturedAt':before.capturedAt,
            'usage':{'lanes':{'combat':{'attack':{'attempted':0,'spent':0}}}}})
        proposal = lua_table(h.lua,{**head,'feature':'combat','requestId':number,'actionKey':'owned:'+str(number),
            'resources':{'stamina':1},'intent':{'kind':'playerAttack','target':target,
                'targetName':'Target'+str(target),'targetLevel':10,'expectedStaminaCost':1,
                'attemptedBefore':0,'spentBefore':0,'sourceKey':'a'*64,'serverNow':100+number}})
        baseline,reason = self.evidence.capture(proposal,before)
        self.assertIsNone(reason)
        first = {'ok':True,'won':True,'fightId':fight_id or 'fight:'+str(number),'cashStage':1,
            'cashPending':True,'rewardsPending':True,'targetName':'Target'+str(target),
            'targetLevel':10,'targetShownLevel':10,'staminaCost':1,
            'targetDaily':{'day':0,'count':1,'serverNow':100+number}}
        receipt = {**first,'cashStage':4,'cashPending':False,'rewardsPending':False,
            'cashConfirmed':cash,'stolen':cash,'xp':1,'respect':1}
        after = h.snapshot(revision=number+1,captured_at=number+1,native={'fullSync':True,'serverNow':101+number})
        after.playerFightProof = lua_table(h.lua,{
            **{k:after[k] for k in ('session','account','place','release','revision','capturedAt')},
            'sourceKey':'a'*64,'attempts':[{'feature':'combat','actionKey':proposal.actionKey,
                'target':target,'status':'settled','initial':first,'receipt':receipt}]})
        data = lua_table(h.lua,{'proposal':proposal,'before':before,'baseline':baseline,'reply':first})
        self.assertIsNotNone(self.evidence.outcome(data,after))
        return data,after

    def record(self, number, **changes):
        data,after = self.attempt(number,**changes)
        ok,reason = self.ledger.Record(self.ledger,data,after)
        self.assertTrue(ok,reason)
        return data,after

    def test_three_low_settlements_demote_and_restart_preserves_exact_threshold_history(self):
        _,after = self.record(1)
        self.assertTrue(self.ledger.IsHighValue(self.ledger,after,456))
        self.record(2,cash=99999999)
        _,after = self.record(3,cash=100000000)  # Exact low threshold breaks the streak.
        self.assertEqual(self.ledger.Summary(self.ledger).highValue.targets['456'].lowStreak,0)
        self.record(4,cash=99999999)
        _,after = self.record(5,cash=99999999)
        restarted,reason = self.module.new(self.store,lua_table(self.h.lua,self.h.session),self.evidence)
        self.assertIsNone(reason)
        self.ledger = restarted
        self.assertTrue(self.ledger.IsHighValue(self.ledger,after,456))
        _,after = self.record(6,cash=99999999)
        self.assertFalse(self.ledger.IsHighValue(self.ledger,after,456))
        self.assertEqual(self.ledger.Summary(self.ledger).highValue.count,0)

    def test_duplicate_request_is_idempotent_and_reused_fight_id_is_refused(self):
        data,after = self.record(1)
        self.assertTrue(self.ledger.Record(self.ledger,data,after)[0])
        self.assertEqual(self.ledger.Summary(self.ledger).fights,1)
        data,after = self.attempt(2,fight_id='fight:1')
        self.assertFalse(self.ledger.Record(self.ledger,data,after)[0])
        self.assertEqual(self.ledger.Summary(self.ledger).fights,1)

    def test_129th_high_target_blocks_high_only_instead_of_dropping_owned_memory(self):
        for index in range(1,130):
            _,after = self.record(index,target=1000+index)
        status = self.ledger.HighValueStatus(self.ledger,after)
        self.assertFalse(status.known)
        self.assertEqual(status.retained,128)
        self.assertEqual(self.ledger.Summary(self.ledger).fights,129)
        self.assertIsNone(self.ledger.HighValueTargets(self.ledger,after))
        restarted,reason = self.module.new(self.store,lua_table(self.h.lua,self.h.session),self.evidence)
        self.assertIsNone(reason)
        self.assertFalse(restarted.HighValueStatus(restarted,after).known)

    def test_torn_write_and_corrupt_owned_history_cannot_become_new_lookup_authority(self):
        _,after = self.record(1)
        self.store.Write = self.h.lua.eval('function(self,k,v) self.data[k]=v;return false end')
        data,after = self.attempt(2,cash=0)
        self.assertFalse(self.ledger.Record(self.ledger,data,after)[0])
        self.assertFalse(self.ledger.HighValueStatus(self.ledger,after).known)
        self.assertIsNone(self.ledger.SavedTargets(self.ledger,after))
        restarted,reason = self.module.new(self.store,lua_table(self.h.lua,self.h.session),self.evidence)
        self.assertIsNone(reason)
        self.assertEqual(restarted.Summary(restarted).fights,2)
        saved = self.store.data[restarted.key]
        saved.highValue.targets['456'].history[1].cash = 1
        refused,reason = self.module.new(self.store,lua_table(self.h.lua,self.h.session),self.evidence)
        self.assertIsNone(refused)
        self.assertIn('Corrupt',reason)


if __name__ == '__main__': unittest.main()
