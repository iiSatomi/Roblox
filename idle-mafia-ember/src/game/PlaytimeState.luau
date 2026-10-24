-- Earned daily ladder view from replicated seconds, never local timer estimates.
local PlaytimeState = {}

local kinds = { cash = true, energy = true, stamina = true,
    seals = true, xpboost = true, gold = true, mystery = true, crate = true }

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value < math.huge and value >= minimum and value % 1 == 0
end

local function array(value, size)
    if type(value) ~= "table" or #value ~= size then return false end
    for key in pairs(value) do
        if not integer(key, 1) or key > size then return false end
    end
    for index = 1, size do if value[index] == nil then return false end end
    return true
end

local function reward(value)
    if type(value) ~= "table" or not kinds[value.kind] then return nil end
    local kind = value.kind
    if kind == "cash" and not (integer(value.flat, 1)
        or integer(value.minutes, 1)) then return nil end
    if (kind == "seals" or kind == "gold")
        and not integer(value.amount, 1) then return nil end
    if kind == "xpboost" and not integer(value.minutes, 1) then return nil end
    if kind == "crate" and (type(value.crate) ~= "string"
        or #value.crate == 0) then return nil end
    if value.bound ~= nil and type(value.bound) ~= "boolean" then return nil end
    return { kind = kind, amount = value.amount,
        item = value.crate, bound = value.bound == true }
end

local function catalog(source, tier)
    if not array(source, 7) then return nil end
    local result, last = {}, 0
    for index, item in ipairs(source) do
        if type(item) ~= "table" or not integer(item.seconds, 1)
            or item.seconds <= last or not reward(item) then return nil end
        last = item.seconds
        local selected = item
        if item.weekend ~= nil then
            if not reward(item.weekend) then return nil end
        end
        if item.tiers ~= nil then
            if type(item.tiers) ~= "table" then return nil end
            for key, option in pairs(item.tiers) do
                if not integer(key, 2) or key > 4 or not reward(option) then
                    return nil
                end
            end
            for level = tier, 2, -1 do
                if item.tiers[level] then
                    selected = item.tiers[level]
                    break
                end
            end
        end
        result[index] = { seconds = item.seconds,
            normal = reward(selected), weekend = item.weekend and reward(item.weekend) }
    end
    return result
end

function PlaytimeState.read(raw, context)
    if type(raw) ~= "table" or type(context) ~= "table" then
        return nil, "Missing playtime state or context"
    end
    for _, field in ipairs({ "session", "account", "place", "release",
        "revision", "capturedAt" }) do
        if raw[field] ~= context[field] then
            return nil, "Playtime snapshot header changed"
        end
    end
    local native = raw.native
    if type(native) ~= "table" or native.fullSync ~= true
        or type(native.playtime) ~= "table" then
        return nil, "Complete native playtime Sync required"
    end
    local now = context.serverNow
    if not integer(now, 0) or native.serverNow ~= now
        or now % 86400 < 5 or now % 86400 > 86395 then
        return nil, "Current server UTC day required"
    end
    local today = tonumber(os.date("!%Y%j", now))
    local weekend = raw.weekendBuff
    if type(weekend) ~= "table" or type(weekend.active) ~= "boolean"
        or weekend.day ~= today then
        return nil, "Same-day weekend state required"
    end
    local playtime = native.playtime
    local claimed = playtime.laddersClaimed or {}
    if not integer(playtime.todaySeconds, 0)
        or not integer(native.level, 1)
        or (native.maxLevel ~= nil and not integer(native.maxLevel, 0))
        or type(claimed) ~= "table" or not array(raw.ladderTiers, 4)
        or type(raw.catalogKey) ~= "string" or #raw.catalogKey == 0 then
        return nil, "Playtime progress or catalog incomplete"
    end
    local last = 0
    for _, threshold in ipairs(raw.ladderTiers) do
        if not integer(threshold, 1) or threshold <= last then
            return nil, "Invalid ladder tiers"
        end
        last = threshold
    end
    local tier, highest = 1, math.max(native.level, native.maxLevel or 0)
    for index, threshold in ipairs(raw.ladderTiers) do
        if threshold <= highest then tier = index end
    end
    local rungs = catalog(raw.ladderCatalog, tier)
    if not rungs then return nil, "Invalid playtime ladder catalog" end
    for key, marker in pairs(claimed) do
        local index = type(key) == "string" and tonumber(key) or nil
        if not integer(index, 1) or index > #rungs
            or tostring(index) ~= key or not integer(marker, 1)
            or marker > 4 then return nil, "Invalid ladder claim marker" end
    end
    local ready = {}
    for index, rung in ipairs(rungs) do
        if claimed[tostring(index)] == nil
            and playtime.todaySeconds >= rung.seconds then
            local prize = weekend.active and rung.weekend or rung.normal
            ready[#ready + 1] = { index = index,
                rewardKind = prize.kind, rewardAmount = prize.amount,
                rewardItem = prize.item, rewardBound = prize.bound }
        end
    end
    return {
        session = context.session, account = context.account,
        place = context.place, release = context.release,
        revision = context.revision, capturedAt = context.capturedAt,
        catalogKey = raw.catalogKey, today = today,
        todaySeconds = playtime.todaySeconds, ready = ready,
    }, nil
end

return PlaytimeState
