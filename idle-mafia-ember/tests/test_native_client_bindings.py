"""Resolve the live MWClient State and Remotes from current instances."""
import unittest

from engine_harness import Harness


class NativeClientBindingsTests(unittest.TestCase):
    def test_current_instance_paths_and_state_api(self):
        h = Harness()
        game, state, remotes, state_module = h.lua.execute("""
            local function node(name, class)
                local value = { Name = name, ClassName = class, children = {} }
                function value:IsA(kind) return self.ClassName == kind end
                function value:FindFirstChild(key) return self.children[key] end
                function value:Add(child)
                    self.children[child.Name] = child
                    child.Parent = self
                    return child
                end
                return value
            end
            local replicated = node('ReplicatedStorage', 'ReplicatedStorage')
            local remotes = replicated:Add(node('MW', 'Folder'))
                :Add(node('Remotes', 'Folder'))
            remotes:Add(node('Sync', 'RemoteEvent'))
            local mw = remotes.Parent
            mw:Add(node('DailyBuffRules', 'ModuleScript')).Value = {
                isWeekend = function() return true end }
            mw:Add(node('Config', 'ModuleScript')).Value = {
                GROUP = { id = 123 } }
            local scripts = node('PlayerScripts', 'PlayerScripts')
            local stateModule = scripts:Add(node('MWClient', 'LocalScript'))
                :Add(node('State', 'ModuleScript'))
            local state = { data = { cash = 10 }, lastSyncClock = 5,
                latest = function() return { cash = 10 } end,
                onChanged = function() return { Disconnect = function() end } end }
            stateModule.Value = state
            local player = node('user-a', 'Player')
            function player:IsInGroup(id) return id == 123 end
            player:Add(scripts)
            local players = { LocalPlayer = player }
            local game = {}
            function game:GetService(name)
                if name == 'Players' then return players end
                if name == 'ReplicatedStorage' then return replicated end
            end
            return game, state, remotes, stateModule
        """)
        require = h.lua.eval("function(module) return module.Value end")
        bindings = h.load("src/transport/NativeClientBindings.luau")
        found, reason = bindings.read(game, require)
        self.assertIsNone(reason)
        same = h.lua.eval("function(a, b) return a == b end")
        self.assertTrue(same(found.remotesFolder, remotes))
        self.assertTrue(same(found.nativeState, state))
        self.assertIsNotNone(found.currentDailyBuffRules)
        self.assertEqual(found.config.GROUP.id, 123)
        self.assertTrue(found.groupLookup(123))
        self.assertFalse(found.groupLookup(124))
        state_module.Parent = None
        self.assertIsNone(bindings.read(game, require)[0])


if __name__ == "__main__":
    unittest.main()
