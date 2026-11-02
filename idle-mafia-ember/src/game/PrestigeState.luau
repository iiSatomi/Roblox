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
        assert(integer(level, math.max(previous, 1)),
            "Invalid Prestige level")
        copy[index] = level
        previous = level
    end
    local self = setmetatable({ levels = copy, release = release,
        key = fingerprint:lower() }, Methods)
    self.read = function(raw, context)
        local view, reason = PrestigeState.read(raw, context)
        if not view then return nil, reason end
        if view.catalogKey ~= self.key or view.release ~= self.release then
            return nil, "Prestige source changed"
        end
        for index = 1, 6 do
            if raw.prestigeCatalog.levels[index] ~= self.levels[index] then
                return nil, "Prestige source thresholds changed"
            end
        end
        return view, nil
    end
    return self
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
    for _, field in ipairs({ "session", "account", "place", "release" }) do
        if type(context[field]) ~= "string" or #context[field] == 0 or #context[field] > 200 then
            return nil, "Invalid Prestige snapshot identity"
        end
    end
    if not integer(context.revision, 0) or context.revision > 9007199254740991
        or type(context.capturedAt) ~= "number" or context.capturedAt ~= context.capturedAt
        or context.capturedAt < 0 or context.capturedAt >= math.huge then
        return nil, "Invalid Prestige snapshot header"
    end
    local native, catalog = raw.native, raw.prestigeCatalog
    if type(native) ~= "table" or native.fullSync ~= true
        or not integer(native.level, 1)
        or not integer(native.prestige, 0) or native.prestige > 6
        or type(catalog) ~= "table"
        or catalog.release ~= context.release
        or type(catalog.key) ~= "string" or #catalog.key ~= 64
        or not catalog.key:match("^[%x]+$")
        or type(catalog.levels) ~= "table"
        or #catalog.levels ~= 6 then
        return nil, "Complete Prestige rank proof required"
    end
    if native.level > 9007199254740991
        or (native.xp ~= nil and (type(native.xp) ~= "number" or native.xp ~= native.xp
            or native.xp < 0 or native.xp > 9007199254740991)) then
        return nil, "Invalid Prestige level or EXP"
    end
    local count, previous = 0, 0
    for key in pairs(catalog.levels) do
        if not integer(key, 1) or key > 6 then
            return nil, "Invalid Prestige rank catalog"
        end
        count = count + 1
    end
    if count ~= 6 then return nil, "Invalid Prestige rank catalog" end
    for index = 1, 6 do
        local level = catalog.levels[index]
        if not integer(level, math.max(previous, 1)) then
            return nil, "Invalid Prestige rank catalog"
        end
        previous = level
    end
    local rank = native.prestige
    local required = rank < 6 and catalog.levels[rank + 1] or nil
    if required ~= nil and not integer(required, 1) then
        return nil, "Invalid next Prestige level"
    end
    local view = { session = context.session, account = context.account,
        place = context.place, release = context.release,
        revision = context.revision, capturedAt = context.capturedAt,
        catalogKey = catalog.key, rank = rank, level = native.level,
        nextRank = required and rank + 1 or nil,
        requiredLevel = required,
        ready = required ~= nil and native.level >= required,
        xp = native.xp, xpKnown = native.xp ~= nil,
        resetLevel = 1, resetXp = 0 }
    view.preview = "Current level " .. tostring(view.level) .. " -> 1; current EXP "
        .. (view.xpKnown and tostring(view.xp) or "unavailable") .. " -> 0"
        .. (view.nextRank and "; rank " .. rank .. " -> " .. view.nextRank or "; maximum rank")
    local usage = raw.prestigeUsageProof
    local matched = type(usage) == "table"
    for _, field in ipairs({ "session", "account", "place", "release", "revision", "capturedAt" }) do
        if not matched or usage[field] ~= context[field] then matched = false; break end
    end
    if matched and integer(usage.attempted, 0) and usage.attempted <= 6
        and type(usage.controllersClear) == "boolean" then
        view.attempted, view.controllersClear = usage.attempted, usage.controllersClear
    end
    return view, nil
end

Methods.read = PrestigeState.read

return PrestigeState
