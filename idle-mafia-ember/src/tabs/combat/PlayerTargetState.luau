-- Read-only ordinary-fight facts. No target selection or attack proposal.
local PlayerTargetState = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value < math.huge and value >= minimum and value % 1 == 0
end

local function nonempty(value)
    return type(value) == "string" and #value > 0
end

local function finite(value)
    return type(value) == "number" and value == value
        and value >= 0 and value < math.huge
end

local function dense(rows)
    if type(rows) ~= "table" or #rows > 128 then return false end
    local count = 0
    for key in pairs(rows) do
        if not integer(key, 1) or key > #rows then return false end
        count = count + 1
    end
    return count == #rows
end

function PlayerTargetState.read(raw, context, rules)
    if type(raw) ~= "table" or type(context) ~= "table"
        or type(rules) ~= "table" then
        return nil, "Missing Combat target input"
    end
    for _, field in ipairs({ "session", "account", "place", "release",
        "revision", "capturedAt" }) do
        if raw[field] ~= context[field] then
            return nil, "Combat snapshot header changed"
        end
    end
    local native, proof = raw.native, raw.hitListProof
    local pools = type(native) == "table" and native.pools
    local daily = type(native) == "table" and native.attackDaily
    if type(native) ~= "table" or native.fullSync ~= true
        or not integer(native.serverNow, 0)
        or context.serverNow ~= native.serverNow
        or type(pools) ~= "table"
        or not finite(pools.health)
        or not finite(pools.stamina)
        or type(daily) ~= "table"
        or daily.day ~= math.floor(native.serverNow / 86400)
        or type(daily.counts) ~= "table"
        or type(proof) ~= "table"
        or proof.account ~= context.account
        or proof.capturedAt ~= context.capturedAt
        or not dense(proof.rows)
        or not integer(rules.hospitalHealth, 1)
        or not integer(rules.staminaCost, 1)
        or not integer(rules.dailyTargetCap, 1) then
        return nil, "Current Combat target and daily proof required"
    end
    local rows, seen = {}, {}
    for index, item in ipairs(proof.rows) do
        local key = type(item) == "table" and tostring(item.userId)
        local count = key and daily.counts[key]
        if type(item) ~= "table" or not integer(item.userId, 1)
            or seen[item.userId] or not nonempty(item.name)
            or not integer(item.level, 1)
            or (item.shielded ~= nil
                and (type(item.shielded) ~= "number"
                    or item.shielded ~= item.shielded
                    or item.shielded == math.huge
                    or item.shielded == -math.huge))
            or (count ~= nil and not integer(count, 0)) then
            return nil, "Invalid Combat target or daily count"
        end
        seen[item.userId] = true
        local remaining = math.max(0, rules.dailyTargetCap - (count or 0))
        rows[index] = { userId = item.userId, name = item.name,
            level = item.level, shielded = (item.shielded or 0) > 0,
            remainingDaily = remaining }
    end
    return { session = context.session, account = context.account,
        place = context.place, release = context.release,
        revision = context.revision, capturedAt = context.capturedAt,
        serverNow = native.serverNow, health = pools.health,
        stamina = pools.stamina,
        resourceReady = pools.health >= rules.hospitalHealth
            and pools.stamina >= rules.staminaCost,
        rows = rows }, nil
end

return PlayerTargetState
