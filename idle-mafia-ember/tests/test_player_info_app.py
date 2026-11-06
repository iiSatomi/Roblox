"""Player tab reads the actual App/runtime without enabling features or sending requests."""
import unittest
import test_player_combat_planner_app as fixture
from engine_harness import lua_table

class PlayerInfoAppTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.PlayerCombatPlannerAppTests();self.f.setUp();self.h=self.f.h
        self.f.app.Destroy(self.f.app)
        original=self.f.tab_factory
        self.f.f.tab_factory=original
        # Existing actual App fixture accepts the same dependency set; add read-only UI/state modules.
        self.f.f.f.base.runtime.modules.PlayerInfoState=self.h.load('src/game/PlayerInfoState.luau')
        self.f.f.f.base.runtime.modules.playerInfoSource=self.h.lua.execute("return {Current=function() return true end,Read=function(_,n) return {userId=1,name='LocalUser',displayName='Local Display',propertyMultiplier=1,properties={}} end}")
        self.f.f.start();self.f.app=self.f.f.app
        raw=self.f.f.result.before;raw.native.userId=1;raw.native.level=20;raw.native.cash=1000
        raw.native.derived=lua_table(self.h.lua,{'incomePerHour':2000,'statBreakdown':{'atk':{'total':150},'def':{'total':120}}})
        self.f.seed(False)
        self.f.f.step()
    def test_read_only_player_snapshot_is_available_with_every_feature_off(self):
        r=self.f.f.runtime.Status(self.f.f.runtime).playerInfo
        self.assertIsNotNone(r);self.assertEqual((r.attack,r.defense,r.propertyPerHour),(150,120,2000))
        self.assertIsNotNone(self.f.f.app.ui.playerTab)
        self.assertIn('150',self.f.f.app.ui.playerTab.fields.attack.Get(self.f.f.app.ui.playerTab.fields.attack))
        self.assertEqual(len(self.f.f.executor.queued),0);self.assertEqual(self.f.f.executor.calls,0)
        self.assertFalse(self.f.f.runtime.Status(self.f.f.runtime).active)
    def test_native_source_replacement_cannot_supply_forged_player_identity(self):
        source=self.f.f.runtime.modules.playerInfoSource
        source.Read=self.h.lua.eval("function() return {userId=42,name='Injected',propertyMultiplier=999} end")
        self.h.at(.25);raw=self.f.f.result.before;raw.revision+=1;raw.capturedAt=.25;self.f.f.step(raw)
        r=self.f.f.runtime.Status(self.f.f.runtime).playerInfo
        self.assertIsNone(r.name);self.assertIsNone(r.propertyPerHour)
    def test_real_confirmed_mug_updates_player_cash_rate_without_counting_balance_changes(self):
        f,h=self.f.f,self.h
        for key,value in {'minimumPayout':0,'minSamples':0,'maxAttackSpend':5,'maxScoutSpend':0,'maxStaminaCost':5}.items():
            f.app.Set(f.app,'combat.custom.'+key,value)
        f.begin();f.send()
        raw=f.result.after;raw.native.userId=1;raw.native.stats=lua_table(h.lua,{'maxHealth':100})
        raw.native.derived=lua_table(h.lua,{'incomePerHour':2000,'statBreakdown':{'atk':{'total':150},'def':{'total':120}}})
        raw.native.cash=999999999;f.settle()
        info=f.runtime.Status(f.runtime).playerInfo
        self.assertEqual(info.mugCash,f.result.final['cashConfirmed']);self.assertIsNone(info.mugPerHour)
        h.at(60);raw.revision=3;raw.capturedAt=60;raw.native.serverNow+=60;f.step(raw)
        info=f.runtime.Status(f.runtime).playerInfo
        self.assertEqual(info.mugPerHour,f.result.final['cashConfirmed']*60)
        self.assertEqual(info.combinedPerHour,info.mugPerHour+2000)
        self.assertEqual(f.executor.calls,1);self.assertIn('/hr',f.app.ui.playerTab.fields.mugIncome.Get(f.app.ui.playerTab.fields.mugIncome))
    def tearDown(self):self.f.tearDown()
