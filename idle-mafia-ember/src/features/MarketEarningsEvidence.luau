-- A reply is not enough: require exact newer earnings-to-Gold transfer.
local MarketEarningsEvidence = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value <= 9007199254740991 and value % 1 == 0
end
local function timestamp(value)
    return type(value) == "number" and value == value and value >= 0 and value <= 9007199254740991
end

local function matching(a, b, restart)
    if type(a) ~= "table" or type(b) ~= "table" then return false end
    for _, field in ipairs({ "session", "account", "place", "release" }) do
        if type(a[field]) ~= "string" or #a[field] == 0
            or type(b[field]) ~= "string" or #b[field] == 0
            or (a[field] ~= b[field] and not (restart and field == "session")) then return false end
    end
    return true
end

local function state(raw)
    local native = type(raw) == "table" and raw.native
    local inventory = type(native) == "table" and native.inventory
    local gold = type(inventory) == "table"
        and inventory.gold_bar
    if gold == nil then gold = 0 end
    if type(native) ~= "table" or native.fullSync ~= true
        or type(native.market) ~= "table"
        or type(native.inventory) ~= "table"
        or not integer(native.market.earnings, 0)
        or not integer(gold, 0) then return nil end
    return native.market.earnings, gold
end

function MarketEarningsEvidence.capture(proposal, before)
    local intent = type(proposal) == "table" and proposal.intent
    if type(proposal) ~= "table" or proposal.feature ~= "marketManage"
        or type(intent) ~= "table"
        or intent.kind ~= "marketCollectEarnings"
        or not integer(intent.earningsBefore, 1)
        or not integer(intent.goldBefore, 0)
        or not integer(proposal.revision, 0) or type(proposal.resources) ~= "table"
        or next(proposal.resources) ~= nil
        or type(before) ~= "table" or not matching(proposal, before)
        or proposal.revision ~= before.revision then
        return nil, "Market earnings baseline mismatch"
    end
    for key in pairs(intent) do
        if key ~= "kind" and key ~= "earningsBefore" and key ~= "goldBefore" then return nil, "Unknown payout intent" end
    end
    local earnings, gold = state(before)
    if earnings ~= intent.earningsBefore or gold ~= intent.goldBefore then
        return nil, "Market earnings changed before collection"
    end
    return { session = proposal.session, account = proposal.account,
        place = proposal.place, release = proposal.release,
        revision = proposal.revision, earnings = earnings,
        gold = gold, serverNow = timestamp(before.native.serverNow) and before.native.serverNow or nil }, nil
end

local function reconcile(proposal, beforeHeader, after, reply, baseline, restart)
    if type(proposal) ~= "table" or type(beforeHeader) ~= "table"
        or type(after) ~= "table" or type(reply) ~= "table"
        or type(baseline) ~= "table"
        or not matching(proposal, beforeHeader)
        or not matching(proposal, after, restart)
        or not matching(proposal, baseline)
        or proposal.revision ~= baseline.revision
        or beforeHeader.revision ~= baseline.revision
        or type(proposal.intent) ~= "table" or proposal.intent.kind ~= "marketCollectEarnings"
        or proposal.intent.earningsBefore ~= baseline.earnings or proposal.intent.goldBefore ~= baseline.gold
        or type(proposal.resources) ~= "table" or next(proposal.resources) ~= nil then
        return "pending"
    end
    local earnings, gold = state(after)
    local newer = integer(after.revision, 0) and after.revision > baseline.revision
    if restart and after.session ~= beforeHeader.session then
        newer = integer(after.revision, 0) and timestamp(baseline.serverNow)
            and timestamp(after.native and after.native.serverNow) and after.native.serverNow > baseline.serverNow
    end
    if earnings == nil or not newer or reply.pending == true or reply.code == "rate_limited"
        or reply.code == "presence" or reply.code == "busy" then return "pending" end
    local advanced = earnings == 0 and gold == baseline.gold + baseline.earnings
    if reply.ok == false then
        return earnings == baseline.earnings and gold == baseline.gold and "rejected" or "pending"
    end
    if reply.ok == true and advanced then return "confirmed" end
    return "pending"
end

function MarketEarningsEvidence.evaluate(proposal, beforeHeader, after, reply, baseline)
    return reconcile(proposal, beforeHeader, after, reply, baseline, false)
end

function MarketEarningsEvidence.recoverSaved(data, after)
    if type(data) ~= "table" or type(data.baseline) ~= "table" then return nil end
    local expected = MarketEarningsEvidence.capture(data.proposal, data.before)
    if not expected then return nil end
    for key, value in pairs(expected) do if data.baseline[key] ~= value then return nil end end
    for key in pairs(data.baseline) do if expected[key] == nil then return nil end end
    local result = reconcile(data.proposal, data.before, after, data.reply, data.baseline, true)
    return (result == "confirmed" or result == "rejected") and result or nil
end

return MarketEarningsEvidence
