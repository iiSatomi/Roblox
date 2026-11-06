"""Observe reviewed FamilyBossView preflight without calling its attack handler."""
import unittest
from engine_harness import Harness


class NativeFamilyBossControllerTests(unittest.TestCase):
    def setUp(self):
        self.h=Harness()
        self.f=self.h.lua.eval('''function(f)
            f.game.PlaceVersion=654
            f.config.COMBAT.hospitalHealth=20
            f.config.FAMILY_BOSS={staminaCost=1,stages={{},{},{},{},{}}}
            f.data.stats={maxHealth=100};f.data.pools={health=100,stamina=5};f.data.family={id=9}
            local remote=f.remotes:Add(f.node('FamilyBossAction','RemoteFunction'))
            f.wrapped.FamilyBossAction={Name='FamilyBossAction',Instance=remote,
                InvokeServer=function() error('Read-only controller invoked remote') end}
            local function attack() error('Read-only controller invoked native attack') end
            local function invoke() error('Read-only controller invoked native wrapper') end
            local function init() error('Read-only controller initialized native UI') end
            local function any() end
            f.familyApi={init=init,show=any,hide=any,refresh=any}
            f.familyModule=f.client:Add(f.node('FamilyTab','ModuleScript'))
                :Add(f.node('FamilyBossView','ModuleScript'))
            f.familyModule.Value=f.familyApi
            f.familyInit={[1]=f.ctx,[6]=attack}
            f.familyAttack={[2]=false,[3]=0,[4]=f.ctx,[5]=any,[18]=invoke}
            f.upvalues[init]=f.familyInit;f.upvalues[attack]=f.familyAttack;f.upvalues[invoke]={f.ctx}
            return f
        end''')(self.h.load('tests/fixtures/prestige-client.lua'))

    def bind(self):
        return self.h.load('src/tabs/combat/NativeFamilyBossController.luau').bind(
            self.f.game,self.f.requireModule,self.f.readUpvalues)

    def native(self):
        return self.h.lua.eval('''function(f) return {fullSync=true,userId=123,
            stats={maxHealth=100},pools={health=100,stamina=5},family={id=9}} end''')(self.f)

    def test_reads_only_native_cost_hospital_and_controller_flags_without_a_damage_bound(self):
        source=self.bind();self.assertIsNotNone(source)
        frame=source.Read(self.native())
        self.assertEqual((frame.staminaCost,frame.hospitalHealth),(1,20))
        self.assertFalse(frame.hitBackKnown)
        self.assertIsNone(frame.hitBackMax)
        self.assertTrue(frame.controllersClear)
        self.f.familyAttack[2]=True
        self.assertFalse(source.Read(self.native()).controllersClear)
        self.assertTrue(source.Busy())

    def test_source_layout_identity_or_quote_changes_retire_binding(self):
        for change in ('context','invoke','version','config','module','cachedState'):
            with self.subTest(change=change):
                self.setUp();source=self.bind();self.assertTrue(source.Current())
                if change=='context':self.f.familyAttack[4]=self.h.lua.table()
                if change=='invoke':self.f.familyAttack[18]=self.h.lua.eval('function() end')
                if change=='version':self.f.game.PlaceVersion=655
                if change=='config':self.f.config.FAMILY_BOSS.staminaCost=2
                if change=='module':self.f.familyModule.Parent=None
                if change=='cachedState':self.f.familyInit[16]=self.h.lua.table()
                self.assertFalse(source.Current())
                self.assertIsNone(source.Read(self.native()))
                self.assertTrue(source.Busy())

    def test_complete_snapshot_must_match_current_native_health_and_stamina(self):
        source=self.bind();raw=self.native()
        raw.pools.health=99
        self.assertIsNone(source.Read(raw))
        raw.pools.health=100;raw.pools.stamina=4
        self.assertIsNone(source.Read(raw))
        raw.pools.stamina=5;raw.fullSync=False
        self.assertIsNone(source.Read(raw))

    def test_current_binding_exposes_the_read_only_family_controller(self):
        found,reason=self.h.load('src/transport/NativeClientBindings.luau').read(
            self.f.game,self.f.requireModule,self.f.readUpvalues,None,None,
            self.h.load('src/tabs/combat/NativeFamilyBossController.luau'))
        self.assertIsNone(reason)
        self.assertIsNotNone(found.currentFamilyBossController)
        self.assertTrue(found.currentFamilyBossController.Current())


if __name__=='__main__':unittest.main()
