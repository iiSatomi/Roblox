-- A rent reply confirms only with exact Gold custody and one new shop period.
local MarketRentEvidence = {}

local function integer(value, low, high)
    return type(value) == "number" and value == value
        and value >= low and value <= high and value % 1 == 0
end

local function finite(value, low, high)
    return type(value) == "number" and value == value
        and value >= low and value <= high
end

local function same(a, b, restart)
    if type(a) ~= "table" or type(b) ~= "table" then return false end
    for _, field in ipairs({ "session", "account", "place", "release" }) do
        if type(a[field]) ~= "string" or #a[field] == 0
            or #a[field] > 200 or type(b[field]) ~= "string" or #b[field] == 0
            or (a[field] ~= b[field] and not (restart and field == "session")) then
            return false
        end
    end
    return true
end

local function state(raw)
    local native = type(raw) == "table" and raw.native
    local market = type(native) == "table" and native.market
    if type(native) ~= "table" or native.fullSync ~= true
        or type(market) ~= "table"
        or type(native.inventory) ~= "table"
        or type(native.inventoryBound) ~= "table"
        or not finite(native.serverNow, 0, 9007199254740991)
        or not integer(market.shopUntil, 0, 9007199254740991)
        or not integer(native.inventory.gold_bar, 0, 1000000000)
        or not integer(native.inventoryBound.gold_bar, 0, 1000000000) then
        return nil
    end
    return { serverNow = native.serverNow,
        shopUntil = market.shopUntil,
        loose = native.inventory.gold_bar,
        bound = native.inventoryBound.gold_bar }
end

function MarketRentEvidence.capture(proposal, before)
    local intent = type(proposal) == "table" and proposal.intent
    if not same(proposal, before)
        or proposal.feature ~= "marketRent"
        or type(intent) ~= "table"
        or intent.kind ~= "marketRent"
        or intent.periods ~= 1
        or not integer(intent.cost, 1, 1000)
        or not integer(intent.durationSeconds, 3600, 2592000)
        or not integer(before.revision, 0, 9007199254740991)
        or proposal.revision ~= before.revision then
        return nil, "Market rental baseline mismatch"
    end
    local saved = state(before)
    if not saved or saved.loose < intent.cost then
        return nil, "Loose Gold unavailable for rental"
    end
    return { session = proposal.session, account = proposal.account,
        place = proposal.place, release = proposal.release,
        revision = proposal.revision, cost = intent.cost,
        durationSeconds = intent.durationSeconds,
        shopUntil = saved.shopUntil, serverNow = saved.serverNow,
        loose = saved.loose, bound = saved.bound }, nil
end

local function reconcile(proposal, beforeHeader, after, reply, baseline, restart)
    local intent = type(proposal) == "table" and proposal.intent
    if not same(proposal, beforeHeader)
        or not same(proposal, after, restart)
        or not same(proposal, baseline)
        or type(reply) ~= "table"
        or type(intent) ~= "table"
        or proposal.revision ~= baseline.revision
        or beforeHeader.revision ~= baseline.revision
        or intent.kind ~= "marketRent"
        or intent.periods ~= 1
        or intent.cost ~= baseline.cost
        or intent.durationSeconds ~= baseline.durationSeconds then
        return "pending"
    end
    local current = state(after)
    local newer = type(after) == "table" and integer(after.revision, baseline.revision + 1, 9007199254740991)
    if restart and type(after) == "table" and after.session ~= baseline.session then
        newer = integer(after.revision, 0, 9007199254740991) and current and current.serverNow > baseline.serverNow
    end
    if not current or not newer or current.serverNow < baseline.serverNow or reply.pending == true then return "pending" end
    -- Source quote extends max(now, existing expiry). Bound the unknown server
    -- processing instant by the two observed clocks; allow integer rounding.
    local earliest = math.floor(math.max(baseline.serverNow, baseline.shopUntil)) + baseline.durationSeconds
    local latest = math.ceil(math.max(current.serverNow, baseline.shopUntil)) + baseline.durationSeconds
    local advanced = current.serverNow >= baseline.serverNow
        and current.shopUntil > baseline.shopUntil
        and current.shopUntil >= earliest and current.shopUntil <= latest
        and current.shopUntil > current.serverNow
        and current.loose == baseline.loose - baseline.cost
        and current.bound == baseline.bound
    if reply.ok == false then
        return current.shopUntil == baseline.shopUntil and current.loose == baseline.loose
            and current.bound == baseline.bound and "rejected" or "pending"
    end
    if reply.ok == true and reply.pending ~= true and advanced then
        return "confirmed"
    end
    return "pending"
end

function MarketRentEvidence.evaluate(proposal, beforeHeader, after, reply, baseline)
    return reconcile(proposal, beforeHeader, after, reply, baseline, false)
end
function MarketRentEvidence.recoverSaved(data, after)
    if type(data) ~= "table" or type(data.baseline) ~= "table" then return nil end
    local expected = MarketRentEvidence.capture(data.proposal, data.before)
    if not expected then return nil end
    for key, value in pairs(expected) do if data.baseline[key] ~= value then return nil end end
    for key in pairs(data.baseline) do if expected[key] == nil then return nil end end
    local result = reconcile(data.proposal, data.before, after, data.reply, data.baseline, true)
    return (result == "confirmed" or result == "rejected") and result or nil
end

return MarketRentEvidence
