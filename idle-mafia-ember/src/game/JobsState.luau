-- Fresh ordinary Jobs view from a complete replicated Sync and current catalog.
local JobsState = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value < math.huge and value >= minimum and value % 1 == 0
end

local function nonnegative(value)
    return type(value) == "number" and value == value
        and value >= 0 and value < math.huge
end

local function arrayLength(value)
    if type(value) ~= "table" then return nil end
    local size = #value
    for key in pairs(value) do
        if type(key) ~= "number" or key % 1 ~= 0 or key < 1
            or key > size then return nil end
    end
    for index = 1, size do
        if value[index] == nil then return nil end
    end
    return size
end

function JobsState.read(raw, context)
    if type(raw) ~= "table" or type(context) ~= "table" then
        return nil, "Missing Jobs state or context"
    end
    for _, field in ipairs({ "session", "account", "place", "release",
        "revision", "capturedAt" }) do
        if raw[field] ~= context[field] then
            return nil, "Jobs snapshot header changed"
        end
    end
    local native = raw.native
    if type(native) ~= "table" or native.fullSync ~= true then
        return nil, "Complete native Sync required"
    end
    local owner = context.owners and context.owners.jobs
    if not owner or owner.activity ~= "inactive" then
        return nil, "Native Jobs controller owns or may own Jobs"
    end
    if type(raw.catalogKey) ~= "string" or #raw.catalogKey == 0
        or not integer(native.level, 1) or type(native.jobs) ~= "table"
        or type(native.pools) ~= "table"
        or not nonnegative(native.pools.energy)
        or native.pools.energy ~= context.resources.energy then
        return nil, "Jobs player state incomplete"
    end
    local catalogCount = arrayLength(raw.jobCatalog)
    local masteryCount = arrayLength(raw.masteryRules)
    if not catalogCount or catalogCount == 0 or catalogCount > 256
        or not masteryCount or masteryCount == 0 or masteryCount > 20 then
        return nil, "Jobs catalog or mastery rules missing"
    end
    local mastery = {}
    for index, rule in ipairs(raw.masteryRules) do
        if type(rule) ~= "table" or not integer(rule.completions, 1)
            or not nonnegative(rule.energyDiscount)
            or rule.energyDiscount >= 1
            or (index > 1 and rule.completions <= mastery[index - 1].completions) then
            return nil, "Invalid mastery rule"
        end
        mastery[index] = {
            completions = rule.completions,
            energyDiscount = rule.energyDiscount,
        }
    end
    local jobs, seen = {}, {}
    for index, item in ipairs(raw.jobCatalog) do
        if type(item) ~= "table" or type(item.id) ~= "string"
            or #item.id == 0 or seen[item.id]
            or not integer(item.level, 1) or not integer(item.energy, 1)
            or not nonnegative(item.cash) or not nonnegative(item.xp) then
            return nil, "Invalid or duplicate Job catalog entry"
        end
        seen[item.id] = true
        local record = native.jobs[item.id]
        if record ~= nil and type(record) ~= "table" then
            return nil, "Invalid Job progress record"
        end
        record = record or {}
        local tier = record.masteryTier or 0
        local completions = record.completions or 0
        local progress = record.masteryProgress or 0
        if not integer(tier, 0) or tier > masteryCount
            or not nonnegative(completions) or not nonnegative(progress) then
            return nil, "Invalid Job mastery progress"
        end
        local discount = tier > 0 and mastery[tier].energyDiscount or 0
        local cost = math.max(1, math.floor(item.energy * (1 - discount) + 0.5))
        jobs[index] = {
            id = item.id, level = item.level, cost = cost,
            cash = item.cash, xp = item.xp,
            masteryTier = tier,
            masteryProgress = math.max(completions, progress),
        }
    end
    return {
        session = context.session, account = context.account,
        place = context.place, release = context.release,
        revision = context.revision, capturedAt = context.capturedAt,
        catalogKey = raw.catalogKey, level = native.level,
        energy = native.pools.energy, jobs = jobs, masteryRules = mastery,
    }, nil
end

return JobsState
