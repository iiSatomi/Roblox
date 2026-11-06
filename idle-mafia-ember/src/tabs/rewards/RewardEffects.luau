-- A claim marker needs the source-defined effect in the same newer full Sync.
local RewardEffects = {}
local MAX = 9007199254740991

local function number(value)
    return type(value) == "number" and value == value and value >= 0 and value <= MAX
end

local function count(value)
    return number(value) and value % 1 == 0
end

local function balances(native, id)
    if type(native.inventory) ~= "table" or type(native.inventoryBound) ~= "table" then return nil end
    local loose, bound = native.inventory[id], native.inventoryBound[id]
    if loose == nil then loose = 0 end
    if bound == nil then bound = 0 end
    if not count(loose) or not count(bound) then return nil end
    return {loose = loose, bound = bound}
end

local function same(a, b)
    if type(a) ~= type(b) then return false end
    if type(a) ~= "table" then return a == b end
    for key, value in pairs(a) do if not same(value, b[key]) then return false end end
    for key in pairs(b) do if a[key] == nil then return false end end
    return true
end

local function read(spec, raw)
    local native = raw.native
    if spec.kind == "item" then return balances(native, spec.itemId) end
    if spec.kind == "mystery" then
        local result = {}
        for id in pairs(spec.items) do
            result[id] = balances(native, id)
            if result[id] == nil then return nil end
        end
        return result
    end
    if spec.kind == "cash" then return number(native.cash) and native.cash or nil end
    if spec.kind == "refill" then
        local pools = native.pools
        local capacity = spec.pool == "energy" and type(native.derived) == "table"
            and native.derived.effMaxEnergy or spec.pool == "stamina"
            and type(native.stats) == "table" and native.stats.maxStamina
        local current = type(pools) == "table" and pools[spec.pool]
        if not number(capacity) or capacity <= 0 or not number(current) or current > capacity then return nil end
        return {current = current, capacity = capacity}
    end
    if spec.kind == "xpboost" then
        local ending = native.xpBoostEnd
        if ending == nil then ending = 0 end
        if not number(ending) then return nil end
        return {ending = ending, now = native.serverNow}
    end
    return nil
end

local function acquired(before, after, amount, bound)
    if bound == true then return after.bound - before.bound == amount and after.loose == before.loose end
    if bound == false then return after.loose - before.loose == amount and after.bound == before.bound end
    return after.loose >= before.loose and after.bound >= before.bound
        and (after.loose - before.loose) + (after.bound - before.bound) == amount
end

local function effect(spec, before, after, reply)
    if spec.kind == "item" then return acquired(before, after, spec.amount, spec.bound) end
    if spec.kind == "cash" then return after == before + spec.amount end
    if spec.kind == "refill" then return after.capacity == before.capacity and after.current == before.capacity end
    if spec.kind == "xpboost" then
        return after.ending > before.ending and after.now >= before.now
            and after.ending >= before.now + spec.seconds and after.ending <= after.now + spec.seconds
    end
    if spec.kind == "mystery" then
        local id = reply.mystery
        if type(id) ~= "string" or not spec.items[id] or not acquired(before[id], after[id], 1) then return false end
        for other in pairs(spec.items) do
            if other ~= id and not same(before[other], after[other]) then return false end
        end
        return true
    end
    return false
end

function RewardEffects.new(source, marker, lane, weekendSource)
    assert(type(source) == "table" and type(source.RewardSpec) == "function"
        and type(marker) == "table" and type(marker.capture) == "function"
        and type(marker.evaluate) == "function"
        and (lane == "playtime" or lane == "monthlyRewards"), "Missing reward effect dependencies")
    local result = {}
    local function withWeekend(raw)
        if lane ~= "playtime" or weekendSource == nil then return raw end
        if type(raw) ~= "table" then return raw end
        local copied = {}
        for key, value in pairs(raw) do copied[key] = value end
        copied.weekendBuff = nil
        if type(raw.native) ~= "table" or type(weekendSource) ~= "table"
            or weekendSource.release ~= raw.release
            or type(weekendSource.IsWeekend) ~= "function" then return copied end
        local native = raw.native
        if not number(native.serverNow) then return copied end
        local ok, active = pcall(weekendSource.IsWeekend, weekendSource, native.serverNow)
        local dated, day = pcall(os.date, "!%Y%j", math.floor(native.serverNow))
        if ok and type(active) == "boolean" and dated then
            copied.weekendBuff = {active = active, day = tonumber(day)}
        end
        return copied
    end
    local function captureEffect(raw, slot)
        raw = withWeekend(raw)
        local spec, reason = source:RewardSpec(raw, lane, slot)
        if not spec then return nil, reason end
        local value = read(spec, raw)
        if value == nil then return nil, "Reward effect baseline unavailable" end
        if spec.kind == "xpboost" and value.ending > value.now then
            return nil, "Active XP boost stacking rule is not established"
        end
        return {spec = spec, value = value}, nil
    end
    function result:Supports(raw, slot)
        local captured, reason = captureEffect(raw, slot)
        return captured ~= nil, reason
    end
    function result.capture(proposal, before)
        local baseline, reason = marker.capture(proposal, before)
        if not baseline then return nil, reason end
        local slot = lane == "playtime" and proposal.intent.index or proposal.intent.nextDay
        local captured, why = captureEffect(before, slot)
        if not captured then return nil, why end
        return {marker = baseline, spec = captured.spec, value = captured.value}, nil
    end
    function result.evaluate(proposal, beforeHeader, after, reply, baseline)
        if type(baseline) ~= "table" or type(baseline.spec) ~= "table"
            or type(reply) ~= "table" or reply.pending == true or reply.code == "rate_limited" or reply.code == "presence" then return "pending" end
        local status = marker.evaluate(proposal, beforeHeader, after, reply, baseline.marker)
        if status ~= "confirmed" and status ~= "rejected" then return "pending" end
        after = withWeekend(after)
        local spec = source:RewardSpec(after, lane, baseline.spec.slot)
        if not spec or not same(spec, baseline.spec) then return "pending" end
        local value = read(spec, after)
        if value == nil then return "pending" end
        if status == "rejected" then return same(value, baseline.value) and "rejected" or "pending" end
        if lane == "playtime" and after.native.playtime.laddersClaimed[tostring(spec.slot)] ~= spec.tier then return "pending" end
        return effect(spec, baseline.value, value, reply) and "confirmed" or "pending"
    end
    function result.recoverSaved(data, after)
        if type(data) ~= "table" or type(data.reply) ~= "table" or type(data.baseline) ~= "table"
            or type(marker.recoverSaved) ~= "function" or data.reply.pending == true
            or data.reply.code == "rate_limited" or data.reply.code == "presence" then return nil end
        local baseline = result.capture(data.proposal, data.before)
        if not baseline or not same(baseline, data.baseline) then return nil end
        local status = marker.recoverSaved({proposal = data.proposal, before = data.before,
            reply = data.reply, baseline = baseline.marker}, after)
        if status ~= "confirmed" and status ~= "rejected" then return nil end
        after = withWeekend(after)
        local spec = source:RewardSpec(after, lane, baseline.spec.slot)
        if not spec or not same(spec, baseline.spec) then return nil end
        local value = read(spec, after)
        if value == nil then return nil end
        if status == "rejected" then return same(value, baseline.value) and "rejected" or nil end
        if lane == "playtime" and after.native.playtime.laddersClaimed[tostring(spec.slot)] ~= spec.tier then return nil end
        return effect(spec, baseline.value, value, data.reply) and "confirmed" or nil
    end
    return result
end

return RewardEffects
