-- Locate the current public MWClient State and replicated Remotes instances.
local NativeClientBindings = {}

local function child(parent, name, class)
    if parent == nil then return nil end
    local value = parent:FindFirstChild(name)
    if value == nil or value.Parent ~= parent
        or not value:IsA(class) then return nil end
    return value
end

local function resolve(game, requireModule)
    local players = game:GetService("Players")
    local player = players and players.LocalPlayer
    local scripts = player and child(player, "PlayerScripts", "PlayerScripts")
    local client = child(scripts, "MWClient", "LocalScript")
    local stateModule = child(client, "State", "ModuleScript")
    local replicated = game:GetService("ReplicatedStorage")
    local mw = child(replicated, "MW", "Folder")
    local remotes = child(mw, "Remotes", "Folder")
    local sync = child(remotes, "Sync", "RemoteEvent")
    if stateModule == nil or sync == nil then return nil end
    local state = requireModule(stateModule)
    if type(state) ~= "table" or type(state.data) ~= "table"
        or type(state.latest) ~= "function"
        or type(state.onChanged) ~= "function"
        or type(state.lastSyncClock) ~= "number"
        or state.lastSyncClock ~= state.lastSyncClock then
        return nil
    end
    local latest = state.latest()
    if type(latest) ~= "table" then return nil end
    local dailyBuffRules, config, gameData, gearSets
    local dailyModule = child(mw, "DailyBuffRules", "ModuleScript")
    if dailyModule then
        local ok, value = pcall(requireModule, dailyModule)
        if ok and type(value) == "table"
            and type(value.isWeekend) == "function" then
            dailyBuffRules = value
        end
    end
    local configModule = child(mw, "Config", "ModuleScript")
    if configModule then
        local ok, value = pcall(requireModule, configModule)
        if ok and type(value) == "table" then config = value end
    end
    local gameDataModule = child(mw, "GameData", "ModuleScript")
    if gameDataModule then
        local ok, value = pcall(requireModule, gameDataModule)
        if ok and type(value) == "table" then gameData = value end
    end
    local gearSetsModule = child(mw, "GearSets", "ModuleScript")
    if gearSetsModule then
        local ok, value = pcall(requireModule, gearSetsModule)
        if ok and type(value) == "table" then gearSets = value end
    end
    if type(config) ~= "table" or type(config.COMBAT) ~= "table"
        or type(gameData) ~= "table" or type(gearSets) ~= "table"
        or type(gearSets.slotBonus) ~= "function" then
        return nil
    end
    local groupLookup
    if type(player.IsInGroup) == "function" then
        groupLookup = function(groupId)
            return player:IsInGroup(groupId)
        end
    end
    return { moduleFolder = mw, remotesFolder = remotes,
        nativeState = state, stateModule = stateModule,
        currentDailyBuffRules = dailyBuffRules,
        config = config, gameData = gameData,
        gearSets = gearSets, combatRules = config.COMBAT,
        groupLookup = groupLookup }
end

function NativeClientBindings.read(game, requireModule)
    if game == nil or type(requireModule) ~= "function" then
        return nil, "Missing current-client bindings"
    end
    local ok, result = pcall(resolve, game, requireModule)
    if not ok or result == nil then
        return nil, "Current MWClient State or Remotes unavailable"
    end
    return result, nil
end

return NativeClientBindings
