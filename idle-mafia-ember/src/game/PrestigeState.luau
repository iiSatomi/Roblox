-- Rank-specific readiness from the reviewed Config and full native Sync.
local PrestigeState = {}
local Methods = {}
Methods.__index = Methods

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge and value % 1 == 0
end

function PrestigeState.new(config, fingerprint, release)
    local source = type(config) == "table" and config.PRESTIGE
    local levels = type(source) == "table" and source.levelByRank
    assert(type(source) == "table" and source.maxRank == 6
        and type(levels) == "table" and #levels == source.maxRank
        and type(fingerprint) == "string" and #fingerprint == 64
        and fingerprint:match("^[%x]+$")
        and type(release) == "string" and #release > 0,
        "Missing reviewed Prestige source")
    local copy, count, previous = {}, 0, 0
    for key in pairs(levels) do
        assert(integer(key, 1) and key <= source.maxRank,
            "Sparse Prestige level source")
        count = count + 1
    end
    assert(count == source.maxRank, "Sparse Prestige level source")
    for index, level in ipairs(levels) do
        assert(integer(level, previous), "Invalid Prestige level")
        copy[index] = level
        previous = level
    end
    return setmetatable({ levels = copy, release = release,
        key = fingerprint:lower() }, Methods)
end

function Methods:Enrich(snapshot)
    if type(snapshot) ~= "table" or snapshot.release ~= self.release
        or type(snapshot.native) ~= "table"
        or snapshot.native.fullSync ~= true then
        return nil, "Prestige needs a matching full Sync"
    end
    local result, levels = {}, {}
    for key, value in pairs(snapshot) do result[key] = value end
    for index, value in ipairs(self.levels) do levels[index] = value end
    result.prestigeCatalog = { key = self.key,
        release = self.release, levels = levels }
    return result, nil
end

function PrestigeState.read(raw, context)
    if type(raw) ~= "table" or type(context) ~= "table" then
        return nil, "Missing Prestige state"
    end
    for _, field in ipairs({ "session", "account", "place", "release",
        "revision", "capturedAt" }) do
        if raw[field] ~= context[field] then
            return nil, "Prestige snapshot changed"
        end
    end
    local native, catalog = raw.native, raw.prestigeCatalog
    if type(native) ~= "table" or native.fullSync ~= true
        or not integer(native.level, 1)
        or not integer(native.prestige, 0) or native.prestige > 6
        or type(catalog) ~= "table"
        or catalog.release ~= context.release
        or type(catalog.key) ~= "string" or #catalog.key ~= 64
        or type(catalog.levels) ~= "table"
        or #catalog.levels ~= 6 then
        return nil, "Complete Prestige rank proof required"
    end
    local rank = native.prestige
    local required = rank < 6 and catalog.levels[rank + 1] or nil
    if required ~= nil and not integer(required, 1) then
        return nil, "Invalid next Prestige level"
    end
    return { session = context.session, account = context.account,
        place = context.place, release = context.release,
        revision = context.revision, capturedAt = context.capturedAt,
        catalogKey = catalog.key, rank = rank, level = native.level,
        nextRank = required and rank + 1 or nil,
        requiredLevel = required,
        ready = required ~= nil and native.level >= required,
        resetLevel = 1, resetXp = 0 }, nil
end

Methods.read = PrestigeState.read

return PrestigeState
