"""Use reviewed native luck components without nested native require calls."""
import unittest

from engine_harness import Harness


class NativeCrateLuckBindingTests(unittest.TestCase):
    def setUp(self):
        self.h = h = Harness()
        self.f = h.load("tests/fixtures/prestige-client.lua")
        h.lua.globals().f = self.f
        h.lua.execute("""
            f.territory = {
                crateLuck = function() error('Cannot require a non-RobloxScript module from a RobloxScript') end,
                fromData = function(data, key) assert(key == 'crateLuck'); return data.luck end,
            }
            f.buffs = {luck = function(mw, now) assert(mw == f.mw); return now == 100 and .1 or 0 end}
            f.clock = {now = function() return f.now end}
            f.now = 100
            f.mw:Add(f.node('TerritoryBonusRules', 'ModuleScript')).Value = f.territory
            f.mw:Add(f.node('GlobalBuffKinds', 'ModuleScript')).Value = f.buffs
            f.mw:Add(f.node('ServerClock', 'ModuleScript')).Value = f.clock
        """)
        self.binding, reason = h.load("src/transport/NativeClientBindings.luau").read(
            self.f.game, self.f.requireModule)
        self.assertIsNone(reason)
        self.source, reason = h.load("src/tabs/inventory/NativeCrateLuckSource.luau").new(
            self.binding.currentCrateLuck, "release-a")
        self.assertIsNone(reason)

    def test_current_territory_plus_live_global_bonus_without_nested_require(self):
        data = self.h.lua.table_from({"luck": .04})
        self.assertAlmostEqual(self.source.Read(self.source, data), .14)
        self.f.now = 101
        self.assertAlmostEqual(self.source.Read(self.source, data), .04)
        data.luck = .08
        self.assertAlmostEqual(self.source.Read(self.source, data), .08)

    def test_retired_module_or_changed_native_helper_cannot_supply_luck(self):
        mutations = (
            "f.mw.children.TerritoryBonusRules.Parent = nil",
            "f.mw.children.GlobalBuffKinds = f.node('GlobalBuffKinds', 'ModuleScript')",
            "f.mw.children.ServerClock.Parent = nil",
            "f.territory.fromData = function() return 9 end",
            "f.buffs.luck = function() return 9 end",
            "f.clock.now = function() return 100 end",
            "f.players.LocalPlayer = {}",
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self.setUp()
                self.assertAlmostEqual(self.source.Read(self.source, self.h.lua.table_from({"luck": .04})), .14)
                self.h.lua.execute(mutation)
                ok, _ = self.h.lua.eval('function(source) return pcall(source.Read, source, {luck=.04}) end')(self.source)
                self.assertFalse(ok)


if __name__ == '__main__':
    unittest.main()
