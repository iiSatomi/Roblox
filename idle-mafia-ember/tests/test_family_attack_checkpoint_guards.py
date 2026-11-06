"""Family attack permission and fractional spacing survive exact checkpoint transitions."""
import unittest
from engine_harness import Harness, lua_table


class FamilyAttackCheckpointGuardTests(unittest.TestCase):
    def setUp(self):
        self.h=Harness()
        self.pending=self.h.load('src/storage/PendingAction.luau')
        self.module=self.h.load('src/storage/Checkpoint.luau')
        self.store=self.h.lua.execute('''return {strictRecovery=true,data={},Read=function(self,k) return self.data[k] end,
            Write=function(self,k,v) self.data[k]=v;return true end}''')
        self.cp=self.owner()

    def owner(self):
        cp=self.module.new(self.store,None,None,self.pending)
        self.assertIsNone(cp.Load(cp,'user-a',self.h.session['place'],'release-a')[1])
        return cp

    def proposal(self,unknown=True,hits=0,last=0,now=1050.25):
        p=self.h.proposal('familyBossAttacks','family:'+str(hits))
        p.resources=lua_table(self.h.lua,{'stamina':1})
        intent={'kind':'familyBossAttack','week':100,'famId':9,'stage':6,'hitsBefore':hits,
            'lastServerNowBefore':last,'serverNow':now,'expectedStaminaCost':1}
        if unknown:
            intent.update(uncalculatedHitBack=True,allowUncalculatedHitBack=True,attackSourceKey='a'*64)
        else: intent['expectedHitBackMax']=20
        p.intent=lua_table(self.h.lua,intent)
        return p

    def save(self,p,cp=None):
        cp=cp or self.cp
        return cp.Save(cp,p,self.h.snapshot(native={'fullSync':True,'serverNow':p.intent.serverNow}),
            lua_table(self.h.lua,{'original':True}))

    def test_fractional_overtime_hit_survives_reply_reload_and_consumes_unknown_permission(self):
        p=self.proposal()
        self.assertTrue(self.save(p)[0])
        self.assertTrue(self.cp.RecordReply(self.cp,p.actionKey,lua_table(self.h.lua,{'ok':True}))[0])
        restored=self.owner()
        usage=restored.FamilyAttackUsage(restored,100,9,1)
        self.assertEqual((usage.hits,usage.lastServerNow),(1,1050.25))
        self.assertFalse(restored.Resolve(restored,p.actionKey,'schedule_failed')[0])
        self.assertTrue(restored.Resolve(restored,p.actionKey,'confirmed')[0])
        again=self.proposal(hits=1,last=1050.25,now=1055.25)
        self.assertFalse(self.save(again,self.owner())[0])
        known=self.proposal(unknown=False,hits=1,last=1050.25,now=1055.25)
        self.assertTrue(self.save(known,self.owner())[0])

    def test_unknown_permission_fields_and_finite_timestamps_cannot_be_forged(self):
        for key,value in (('allowUncalculatedHitBack',False),('allowUncalculatedHitBack','true'),
            ('attackSourceKey','bad'),('expectedHitBackMax',20),('uncalculatedHitBack',False),
            ('serverNow',float('inf')),('lastServerNowBefore',float('nan'))):
            with self.subTest(key=key,value=value):
                self.setUp();p=self.proposal(now=1050);p.intent.stage=5;p.intent[key]=value
                self.assertFalse(self.save(p)[0])
                self.assertEqual(len(self.cp.Records(self.cp)),0)

    def test_known_unsent_restores_only_its_exact_family_usage_and_retains_request_highwater(self):
        p=self.proposal();self.assertTrue(self.save(p)[0])
        self.assertTrue(self.cp.Resolve(self.cp,p.actionKey,'schedule_failed')[0])
        restored=self.owner();usage=restored.FamilyAttackUsage(restored,100,9,1)
        self.assertEqual((usage.hits,usage.lastServerNow,restored.requestHighwater),(0,0,1))
        self.assertTrue(self.save(self.proposal(unknown=False),restored)[0])
        next_hit=self.proposal(unknown=False,hits=1,last=1050.25,now=1055.25)
        self.assertTrue(self.save(next_hit,restored)[0])
        self.assertFalse(restored.Resolve(restored,p.actionKey,'schedule_failed')[0])


if __name__=='__main__': unittest.main()
