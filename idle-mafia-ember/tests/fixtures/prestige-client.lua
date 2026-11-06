-- In-memory Roblox boundary for the current native Prestige controller contract.
local function node(name, class)
    local value = {Name = name, ClassName = class, children = {}}
    function value:IsA(kind)
        return self.ClassName == kind or kind == "GuiObject" and self.ClassName == "Frame"
    end
    function value:FindFirstChild(key) return self.children[key] end
    function value:GetChildren()
        local result = {}
        for _, child in pairs(self.children) do result[#result + 1] = child end
        return result
    end
    function value:Add(child)
        self.children[child.Name], child.Parent = child, self
        return child
    end
    return value
end
local replicated = node("ReplicatedStorage", "ReplicatedStorage")
local mw = replicated:Add(node("MW", "Folder"))
local remotes = mw:Add(node("Remotes", "Folder"))
remotes:Add(node("Sync", "RemoteEvent"))
local remote = remotes:Add(node("PrestigeAction", "RemoteFunction"))
local player = node("user-a", "Player")
player.UserId = 123
local scripts = player:Add(node("PlayerScripts", "PlayerScripts"))
local client = scripts:Add(node("MWClient", "LocalScript"))
local playerGui = player:Add(node("PlayerGui", "PlayerGui"))
local gui = playerGui:Add(node("MWGui", "ScreenGui"))
local root = gui:Add(node("Root", "Frame")):Add(node("Modals", "Frame"))
local modal = root:Add(node("PrestigeModal", "Frame"))
local confirmationModal = root:Add(node("ConfirmModal", "Frame"))
root.Visible, modal.Visible, confirmationModal.Visible = false, false, false
local data = {userId = 123, prestige = 0, level = 200, xp = 25}
local state = {data = data, lastSyncClock = 0,
    latest = function() return data end, onChanged = function() end}
client:Add(node("State", "ModuleScript")).Value = state
local config, gameData = {COMBAT = {}}, {}
mw:Add(node("Config", "ModuleScript")).Value = config
mw:Add(node("GameData", "ModuleScript")).Value = gameData
mw:Add(node("GearSets", "ModuleScript")).Value = {slotBonus = function() return 0 end}
local rules = {
    canPrestige = function(value) return value.prestige < 6 and value.level >= 200 end,
    rankOf = function(value) return value.prestige end,
}
mw:Add(node("Prestige", "ModuleScript")).Value = rules
local invoke = function() error("Read-only controller must not invoke a remote") end
local linked = {Name = "PrestigeAction", Instance = remote, InvokeServer = invoke}
local wrapped = {PrestigeAction = linked}
function wrapped:FindFirstChild(name) return self[name] end
client:Add(node("RemoteLink", "ModuleScript")).Value = {wrap = function(folder)
    assert(folder == remotes)
    return wrapped
end}
local function init() end
local function open() end
local function confirm() end
local function close() end
local function any() end
local function paint() end
local modalApi, fightApi = {init = init, open = open}, {confirm = confirm}
client:Add(node("PrestigeModal", "ModuleScript")).Value = modalApi
client:Add(node("FightTab", "ModuleScript")).Value = fightApi
local ctx = {State = state, Config = config, player = player, gui = gui,
    confirmDialog = confirm, Remotes = wrapped}
local upvalues = {
    [init] = {ctx, root, modal, close, false, rules, any, paint},
    [open] = {ctx, rules, paint, root, modal},
    [confirm] = {[1] = root, [4] = ctx},
}
local players = {LocalPlayer = player}
local game = {PlaceId = 73897506680154, PlaceVersion = 655}
function game:GetService(name)
    if name == "Players" then return players end
    if name == "ReplicatedStorage" then return replicated end
    error("Unexpected service: " .. tostring(name))
end
return {game = game, requireModule = function(module) return module.Value end,
    readUpvalues = function(fn) return upvalues[fn] end, data = data, ctx = ctx,
    init = upvalues[init], shown = upvalues[open], confirmation = upvalues[confirm],
    modal = modal, root = root, confirmationModal = confirmationModal,
    modalApi = modalApi, fightApi = fightApi, rules = rules, state = state,
    linked = linked, remote = remote, player = player, players = players,
    node = node, client = client, mw = mw, remotes = remotes,
    config = config, gameData = gameData, wrapped = wrapped, upvalues = upvalues}
