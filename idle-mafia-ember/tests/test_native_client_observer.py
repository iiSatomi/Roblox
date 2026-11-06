"""A current client must supply its own release and remote-contract evidence."""
import hashlib
import unittest

from engine_harness import Harness


FIXTURE = """
local function node(name, class)
    local value = { Name = name, ClassName = class, children = {} }
    function value:IsA(kind) return self.ClassName == kind end
    function value:FindFirstChild(key) return self.children[key] end
    function value:GetChildren()
        local result = {}
        for _, child in pairs(self.children) do result[#result + 1] = child end
        return result
    end
    function value:Add(child)
        self.children[child.Name] = child
        child.Parent = self
        return child
    end
    return value
end
local replicated = node('ReplicatedStorage', 'ReplicatedStorage')
local mw = replicated:Add(node('MW', 'Folder'))
local remotes = mw:Add(node('Remotes', 'Folder'))
for _, name in ipairs({ 'Sync', 'DoJob', 'BossAction',
    'StartOperation', 'CollectOperation', 'GetHitList' }) do
    remotes:Add(node(name, name == 'Sync' and 'RemoteEvent'
        or 'RemoteFunction'))
end
mw:Add(node('GameVersion', 'ModuleScript')).Value = '0.26.530'
mw:Add(node('Config', 'ModuleScript')).Value = {
    PRESTIGE = { levelByRank = { 200, 200, 200, 210, 220, 230 } },
    BANK = { depositFee = 0.1 },
}
mw:Add(node('BriefcaseRules', 'ModuleScript')).Value = {
    FREE_PICKS_PER_DAY = 12,
}
mw:Add(node('GameData', 'ModuleScript')).Value = {
    JOBS = { { id = 'watch' }, { id = 'drive' } },
}
local players = { LocalPlayer = { Name = 'user-a' } }
local game = { PlaceId = 73897506680154, PlaceVersion = 590 }
function game:GetService(name)
    if name == 'Players' then return players end
    if name == 'ReplicatedStorage' then return replicated end
end
return game, mw, remotes, players
"""


class NativeClientObserverTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.game, self.mw, self.remotes, self.players = self.h.lua.execute(
            FIXTURE)
        self.require = self.h.lua.eval("function(module) return module.Value end")
        self.h.lua.globals().hashPython = lambda text, alg: hashlib.sha256(
            text.encode("utf-8")).hexdigest() if alg == "sha256" else None
        self.hash = self.h.lua.eval(
            "function(text, alg) return hashPython(text, alg) end")
        self.module = self.h.load("src/transport/NativeClientObserver.luau")
        self.observer = self.module.new(self.game, self.require, self.hash)

    def test_reads_live_identity_and_stable_contract_fingerprint(self):
        first, reason = self.observer.Read(self.observer)
        self.assertIsNone(reason)
        self.assertEqual(first.place, "73897506680154")
        self.assertEqual(first.account, "user-a")
        self.assertEqual(first.gameVersion, "0.26.530")
        self.assertEqual(len(first.fingerprint), 64)
        self.assertEqual(first.fingerprint,
            self.observer.Read(self.observer)[0].fingerprint)
        self.players.LocalPlayer.Name = "user-b"
        second = self.observer.Read(self.observer)[0]
        self.assertEqual(second.account, "user-b")
        self.assertEqual(second.fingerprint, first.fingerprint)

    def test_release_or_remote_change_changes_fingerprint(self):
        original = self.observer.Read(self.observer)[0].fingerprint
        self.game.PlaceVersion = 591
        self.assertNotEqual(self.observer.Read(self.observer)[0].fingerprint,
            original)
        self.game.PlaceVersion = 590
        self.mw.children.GameData.Value.JOBS[1].id = "changed"
        self.assertNotEqual(self.observer.Read(self.observer)[0].fingerprint,
            original)
        self.mw.children.GameData.Value.JOBS[1].id = "watch"
        self.remotes.children.BossAction.ClassName = "RemoteEvent"
        self.assertIsNone(self.observer.Read(self.observer)[0])

    def test_missing_current_instance_fails_closed(self):
        self.mw.children.GameVersion.Parent = None
        self.assertIsNone(self.observer.Read(self.observer)[0])

    def test_malformed_live_catalog_fails_closed(self):
        self.mw.children.GameData.Value.JOBS["hidden"] = {"id": "extra"}
        self.assertIsNone(self.observer.Read(self.observer)[0])

    def test_unreviewed_prestige_tier_or_nonfinite_fee_fails_closed(self):
        config = self.mw.children.Config.Value
        config.PRESTIGE.levelByRank[7] = 240
        self.assertIsNone(self.observer.Read(self.observer)[0])
        config.PRESTIGE.levelByRank[7] = None
        config.BANK.depositFee = float("inf")
        self.assertIsNone(self.observer.Read(self.observer)[0])


if __name__ == "__main__":
    unittest.main()
