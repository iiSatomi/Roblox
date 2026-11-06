"""Actual App combines owned native/profile/history/usage facts; player dispatcher remains blocked."""
import unittest
import test_player_profile_app as fixture
from engine_harness import lua_table

class PlayerTargetViewAppTests(unittest.TestCase):
    def setUp(self):
        self.base=fixture.PlayerProfileAppTests();self.base.setUp();self.f=self.base.f;self.h=self.f.h;self.source=self.base.source
        self.source.CombatFrame=self.h.lua.eval("""function(self,native,rows)
            self.frameCalls=(self.frameCalls or 0)+1;local targets={}
            for _,row in ipairs(rows) do targets[tostring(row.userId)]={remainingDaily=5,cooldownLeft=0,sameFamily=false,manualWarning=false} end
            return {ownUserId=1,ownFamilyId='own-family',attack=200,health=native.pools.health,
                maxHealth=100,stamina=native.pools.stamina,hospitalHealth=20,staminaCost=1,scoutCost=1,maxStaminaCost=5,
                targetCooldown=30,dailyTargetCap=5,fightVariance=.2,fightVarianceCap=5000,
                busy=false,shielded=false,globalCooldown=0,targets=targets}
        end""")
        self.f.tab.nativeReadSource=self.source;self.f.tab.frameReader=self.source.CombatFrame
        self.f.result.before.native.stats=lua_table(self.h.lua,{'maxHealth':100})
        self.f.result.before.native.family=lua_table(self.h.lua,{'id':'own-family'})
    def ready(self):
        self.base.begin_profile();self.f.executor.queued[2]();self.h.at(.5);self.f.step()
    def view(self):
        raw=self.f.runtime.allowanceSnapshot
        context=lua_table(self.h.lua,{**self.h.session,'revision':raw.revision,'capturedAt':raw.capturedAt,'serverNow':raw.native.serverNow})
        return self.f.tab.ReadSelection(self.f.tab,raw,context)
    def test_current_owned_target_view_reaches_actual_app_without_any_player_mutation(self):
        self.ready();view,why=self.view();self.assertIsNotNone(view,why)
        self.assertEqual((view.attack,view.targets[1].staminaCost,view.targets[1].scoutCost),(200,2,1))
        self.assertFalse(view.targets[1].friend);self.assertIsNone(view.targets[1].stats)
        self.assertEqual((view.attackSpent,view.scoutSpent),(0,0));self.assertEqual(self.f.executor.calls,2)
        self.assertEqual(len(self.f.runtime.checkpoint.Records(self.f.runtime.checkpoint)),0)
    def test_changed_frame_callable_is_not_executed_or_promoted(self):
        self.ready();self.source.CombatFrame=self.h.lua.eval('function() error("replacement must not execute") end')
        self.h.at(.75);self.f.step();self.assertIsNone(self.view()[0])
    def test_disable_stops_native_frame_work_and_raw_caller_frame_is_erased(self):
        self.ready();calls=self.source.frameCalls;self.assertGreater(calls or 0,0)
        self.f.app.Set(self.f.app,'combat.enabled',False)
        self.f.result.before.hitListProof=lua_table(self.h.lua,{'nativeFrame':{'attack':9999999}})
        self.h.at(.75);self.f.step();self.assertEqual(self.source.frameCalls,calls)
        self.assertIsNone(self.f.runtime.allowanceSnapshot.hitListProof.nativeFrame)
    def tearDown(self):self.base.tearDown()
