-- Complete native Operation state for ordinary starts; never estimates readiness.
local OperationsState = {}

local function finite(value)
    return type(value) == "number" and value == value
        and value >= 0 and value < math.huge
end

local function signed(value)
    return type(value) == "number" and value == value
        and value > -math.huge and value < math.huge
end

local function integer(value, minimum)
    return finite(value) and value >= minimum and value % 1 == 0
end

local function arraySize(value, maximum)
    if type(value) ~= "table" or #value > maximum then return nil end
    local size = #value
    for key in pairs(value) do
        if not integer(key, 1) or key > size then return nil end
    end
    for index = 1, size do
        if value[index] == nil then return nil end
    end
    return size
end

local function crateScore(id, chance, crates)
    if id == nil and chance == nil then return 0 end
    if type(id) ~= "string" or #id == 0 or not finite(chance)
        or chance > 1 or type(crates) ~= "table" then return nil end
    local crate = crates[id]
    local count = type(crate) == "table" and arraySize(crate.buckets, 32)
    if not count or count == 0 then return nil end
    local weight, rarity = 0, 0
    for _, bucket in ipairs(crate.buckets) do
        if type(bucket) ~= "table" or not finite(bucket.weight)
            or bucket.weight <= 0 or not integer(bucket.rarity, 1) then
            return nil
        end
        weight = weight + bucket.weight
        rarity = rarity + bucket.weight * bucket.rarity
    end
    if not finite(weight) or not finite(rarity) or weight == 0 then return nil end
    return chance * rarity / weight
end

local function copyCatalog(raw, crates)
    local size = arraySize(raw, 256)
    if not size or size == 0 then return nil end
    local copied, seen = {}, {}
    for index, item in ipairs(raw) do
        if type(item) ~= "table" or type(item.id) ~= "string"
            or #item.id == 0 or seen[item.id]
            or not integer(item.level or 1, 1)
            or not integer(item.respect or 0, 0)
            or not finite(item.cost) or not finite(item.cash)
            or not finite(item.xp) or not finite(item.duration)
            or item.duration <= 0 then return nil end
        for _, pair in ipairs({ { item.crate, item.crateChance },
            { item.bonusCrate, item.bonusCrateChance } }) do
            local crateId, chance = pair[1], pair[2]
            if (crateId ~= nil or chance ~= nil)
                and (type(crateId) ~= "string" or #crateId == 0
                    or not finite(chance) or chance > 1) then return nil end
        end
        seen[item.id] = true
        local primary = crateScore(item.crate, item.crateChance, crates)
        local bonus = crateScore(item.bonusCrate, item.bonusCrateChance, crates)
        local chest = nil
        if primary ~= nil and bonus ~= nil then chest = primary + bonus end
        copied[index] = {
            id = item.id, order = index, level = item.level or 1,
            respect = item.respect or 0, cost = item.cost,
            cash = item.cash, xp = item.xp, duration = item.duration,
            chestScore = chest,
        }
    end
    return copied, seen
end

function OperationsState.read(raw, context)
    if type(raw) ~= "table" or type(context) ~= "table" then
        return nil, "Missing Operations state or context"
    end
    for _, field in ipairs({ "session", "account", "place", "release",
        "revision", "capturedAt" }) do
        if raw[field] ~= context[field] then
            return nil, "Operations snapshot header changed"
        end
    end
    local native = raw.native
    if type(native) ~= "table" or native.fullSync ~= true then
        return nil, "Complete native Sync required"
    end
    if not integer(native.level, 1)
        or (native.maxLevel ~= nil and not integer(native.maxLevel, 0))
        or not finite(native.respect) or not finite(native.cash)
        or not context.resources or context.resources.cash ~= native.cash
        or type(raw.catalogKey) ~= "string" or #raw.catalogKey == 0 then
        return nil, "Operations player state incomplete"
    end
    local operations, known = copyCatalog(raw.operationCatalog, raw.crateCatalog)
    if not operations then return nil, "Operations catalog missing or invalid" end
    local running = native.operations
    local active = running and running.active
    local count = arraySize(active, 4)
    if not count then return nil, "Operations active slots missing or invalid" end
    local highest = math.max(native.level, native.maxLevel or 0)
    local slotCount = 1 + (highest >= 15 and 1 or 0)
        + (highest >= 30 and 1 or 0)
        + (type(native.derived) == "table"
            and native.derived.fourthSlot == true and 1 or 0)
    if count > slotCount then return nil, "Operations exceed unlocked slots" end
    local occupied, copiedActive = {}, {}
    for index, entry in ipairs(active) do
        if type(entry) ~= "table" or type(entry.opId) ~= "string"
            or not known[entry.opId] or not signed(entry.remaining) then
            return nil, "Invalid active Operation"
        end
        local slot = entry.slot
        if slot ~= nil and (not integer(slot, 1) or slot > 4
            or occupied[slot]) then return nil, "Duplicate or invalid Operation slot" end
        if slot then occupied[slot] = true end
        copiedActive[index] = { opId = entry.opId,
            remaining = entry.remaining, slot = slot }
    end
    return {
        session = context.session, account = context.account,
        place = context.place, release = context.release,
        revision = context.revision, capturedAt = context.capturedAt,
        catalogKey = raw.catalogKey, level = native.level,
        highestLevel = highest, respect = native.respect, cash = native.cash,
        slotCount = slotCount, openSlots = slotCount - count,
        active = copiedActive, operations = operations,
    }, nil
end

return OperationsState
