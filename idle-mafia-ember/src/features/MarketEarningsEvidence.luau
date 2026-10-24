-- A reply is not enough: require exact newer earnings-to-Gold transfer.
local MarketEarningsEvidence = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge and value % 1 == 0
end

local function matching(a, b)
    for _, field in ipairs({ "session", "account", "place", "release" }) do
        if type(a[field]) ~= "string" or #a[field] == 0
            or a[field] ~= b[field] then return false end
    end
    return true
end

local function state(raw)
    local native = type(raw) == "table" and raw.native
    if type(native) ~= "table" or native.fullSync ~= true
        or type(native.market) ~= "table"
        or type(native.inventory) ~= "table"
        or not integer(native.market.earnings, 0)
        or not integer(native.inventory.gold_bar, 0) then return nil end
    return native.market.earnings, native.inventory.gold_bar
end

function MarketEarningsEvidence.capture(proposal, before)
    local intent = type(proposal) == "table" and proposal.intent
    if type(proposal) ~= "table" or proposal.feature ~= "marketManage"
        or type(intent) ~= "table"
        or intent.kind ~= "marketCollectEarnings"
        or not integer(intent.earningsBefore, 1)
        or not integer(intent.goldBefore, 0)
        or type(before) ~= "table" or not matching(proposal, before)
        or proposal.revision ~= before.revision then
        return nil, "Market earnings baseline mismatch"
    end
    local earnings, gold = state(before)
    if earnings ~= intent.earningsBefore or gold ~= intent.goldBefore then
        return nil, "Market earnings changed before collection"
    end
    return { session = proposal.session, account = proposal.account,
        place = proposal.place, release = proposal.release,
        revision = proposal.revision, earnings = earnings,
        gold = gold }, nil
end

function MarketEarningsEvidence.evaluate(proposal, beforeHeader, after,
    reply, baseline)
    if type(proposal) ~= "table" or type(beforeHeader) ~= "table"
        or type(after) ~= "table" or type(reply) ~= "table"
        or type(baseline) ~= "table"
        or not matching(proposal, beforeHeader)
        or not matching(proposal, after)
        or not matching(proposal, baseline)
        or proposal.revision ~= baseline.revision
        or beforeHeader.revision ~= baseline.revision then
        return "pending"
    end
    local earnings, gold = state(after)
    if earnings == nil then return "pending" end
    local advanced = type(after.revision) == "number"
        and after.revision > baseline.revision
        and earnings == 0 and gold == baseline.gold + baseline.earnings
    if reply.ok == false then return advanced and "pending" or "rejected" end
    if reply.ok == true and advanced then return "confirmed" end
    return "pending"
end

return MarketEarningsEvidence
