-- Bind compatibility to values read from the current client, never caller identity.
local NativeClientObserver = {}
local Methods = {}
Methods.__index = Methods

local requiredFunctions = {
    "DoJob", "BossAction", "StartOperation", "CollectOperation",
    "GetHitList",
}

local function integer(value, minimum, maximum)
    return type(value) == "number" and value == value
        and value % 1 == 0 and value >= minimum and value <= maximum
end

local function child(parent, name, class)
    if parent == nil then return nil end
    local value = parent:FindFirstChild(name)
    if value == nil or value.Parent ~= parent
        or not value:IsA(class) then return nil end
    return value
end

local function moduleValue(parent, name, requireModule)
    local module = child(parent, name, "ModuleScript")
    if module == nil then return nil end
    return requireModule(module)
end

local function sourceParts(game, requireModule)
    local players = game:GetService("Players")
    local replicated = game:GetService("ReplicatedStorage")
    local player = players and players.LocalPlayer
    local mw = child(replicated, "MW", "Folder")
    local remotes = child(mw, "Remotes", "Folder")
    if player == nil or type(player.Name) ~= "string"
        or #player.Name == 0 or mw == nil or remotes == nil
        or not integer(game.PlaceId, 1, 9999999999999999)
        or not integer(game.PlaceVersion, 1, 999999999) then
        return nil
    end
    local version = moduleValue(mw, "GameVersion", requireModule)
    local config = moduleValue(mw, "Config", requireModule)
    local briefcase = moduleValue(mw, "BriefcaseRules", requireModule)
    local gameData = moduleValue(mw, "GameData", requireModule)
    if type(version) ~= "string" or #version == 0
        or type(config) ~= "table"
        or type(config.PRESTIGE) ~= "table"
        or type(config.PRESTIGE.levelByRank) ~= "table"
        or type(config.BANK) ~= "table"
        or type(config.BANK.depositFee) ~= "number"
        or config.BANK.depositFee ~= config.BANK.depositFee
        or config.BANK.depositFee < 0
        or config.BANK.depositFee > 1
        or type(briefcase) ~= "table"
        or not integer(briefcase.FREE_PICKS_PER_DAY, 1, 100)
        or type(gameData) ~= "table"
        or type(gameData.JOBS) ~= "table" then
        return nil
    end
    local ranks = config.PRESTIGE.levelByRank
    local rankKeys = 0
    for key in pairs(ranks) do
        if not integer(key, 1, 6) then return nil end
        rankKeys = rankKeys + 1
    end
    if rankKeys ~= 6 then return nil end
    local parts = { "idle-mafia-client-contract-v1",
        tostring(game.PlaceId), tostring(game.PlaceVersion), version,
        tostring(config.BANK.depositFee),
        tostring(briefcase.FREE_PICKS_PER_DAY) }
    for index = 1, 6 do
        if not integer(ranks[index], 1, 10000) then return nil end
        parts[#parts + 1] = tostring(ranks[index])
    end
    local jobs = gameData.JOBS
    if #jobs < 1 or #jobs > 256 then return nil end
    local jobKeys = 0
    for key in pairs(jobs) do
        if not integer(key, 1, #jobs) then return nil end
        jobKeys = jobKeys + 1
    end
    if jobKeys ~= #jobs then return nil end
    parts[#parts + 1] = tostring(#jobs)
    for index = 1, #jobs do
        local row = jobs[index]
        if type(row) ~= "table" or type(row.id) ~= "string"
            or #row.id == 0 or #row.id > 120 then return nil end
        parts[#parts + 1] = tostring(#row.id) .. ":" .. row.id
    end
    local names, seen = {}, {}
    local children = remotes:GetChildren()
    if #children < 1 or #children > 256 then return nil end
    for _, remote in ipairs(children) do
        local name = remote.Name
        if remote.Parent ~= remotes or type(name) ~= "string"
            or #name == 0 or #name > 80
            or not name:match("^[%w_]+$") or seen[name] then
            return nil
        end
        local class = remote:IsA("RemoteFunction")
            and "RemoteFunction" or remote:IsA("RemoteEvent")
            and "RemoteEvent" or nil
        if class == nil then return nil end
        seen[name] = class
        names[#names + 1] = name .. ":" .. class
    end
    if seen.Sync ~= "RemoteEvent" then return nil end
    for _, name in ipairs(requiredFunctions) do
        if seen[name] ~= "RemoteFunction" then return nil end
    end
    table.sort(names)
    parts[#parts + 1] = tostring(#names)
    for _, name in ipairs(names) do parts[#parts + 1] = name end
    return { place = tostring(game.PlaceId),
        account = player.Name, gameVersion = version,
        canonical = table.concat(parts, "|") }
end

function NativeClientObserver.new(game, requireModule, hash)
    assert(game ~= nil and type(requireModule) == "function"
        and type(hash) == "function", "Missing current-client readers")
    return setmetatable({ game = game,
        requireModule = requireModule, hash = hash }, Methods)
end

function Methods:Read()
    local ok, values = pcall(sourceParts,
        self.game, self.requireModule)
    if not ok or values == nil then
        return nil, "Current client contract unavailable"
    end
    local hashed, digest = pcall(self.hash,
        values.canonical, "sha256")
    if not hashed or type(digest) ~= "string" or #digest ~= 64
        or not digest:match("^[%x]+$") then
        return nil, "Current client SHA-256 unavailable"
    end
    return { place = values.place,
        account = values.account,
        gameVersion = values.gameVersion,
        fingerprint = digest:lower() }, nil
end

return NativeClientObserver
