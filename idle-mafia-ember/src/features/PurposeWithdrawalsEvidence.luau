-- Exact cash gain and banked decrease must precede purchase replan.
local PurposeWithdrawalsEvidence = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value < math.huge and value >= minimum and value % 1 == 0
end

local function matching(a, b)
    for _, field in ipairs({ "session", "account", "place", "release" }) do
        if type(a[field]) ~= "string" or #a[field] == 0
            or a[field] ~= b[field] then return false end
    end
    return true
end

local function balances(raw)
    local native = type(raw) == "table" and raw.native
    if type(native) ~= "table" or native.fullSync ~= true
        or not integer(native.cash, 0)
        or not integer(native.banked, 0) then return nil end
    return native.cash, native.banked
end

function PurposeWithdrawalsEvidence.capture(proposal, before)
    local intent = type(proposal) == "table" and proposal.intent
    if type(proposal) ~= "table" or proposal.feature ~= "withdraw"
        or type(intent) ~= "table" or intent.kind ~= "purposeWithdrawal"
        or not integer(intent.amount, 1)
        or not integer(intent.requiredCash, 1)
        or type(intent.purchaseKey) ~= "string"
        or #intent.purchaseKey == 0
        or type(before) ~= "table" or not matching(proposal, before)
        or proposal.revision ~= before.revision then
        return nil, "Withdrawal baseline mismatch"
    end
    local cash, banked = balances(before)
    local request = before.fundingRequest
    if not cash or banked < intent.amount
        or intent.requiredCash - cash ~= intent.amount
        or type(request) ~= "table"
        or request.account ~= proposal.account
        or request.capturedAt ~= before.capturedAt
        or request.purpose ~= intent.purpose
        or request.purchaseKey ~= intent.purchaseKey
        or request.requiredCash ~= intent.requiredCash then
        return nil, "Purchase shortfall changed before withdrawal"
    end
    return { session = proposal.session, account = proposal.account,
        place = proposal.place, release = proposal.release,
        revision = proposal.revision, purpose = intent.purpose,
        purchaseKey = intent.purchaseKey, amount = intent.amount,
        cash = cash, banked = banked }, nil
end

function PurposeWithdrawalsEvidence.evaluate(proposal, beforeHeader, after,
    reply, baseline)
    if type(proposal) ~= "table" or type(beforeHeader) ~= "table"
        or type(after) ~= "table" or type(reply) ~= "table"
        or type(baseline) ~= "table"
        or not matching(proposal, beforeHeader)
        or not matching(proposal, after)
        or not matching(proposal, baseline)
        or proposal.revision ~= baseline.revision
        or beforeHeader.revision ~= baseline.revision
        or type(proposal.intent) ~= "table"
        or proposal.intent.amount ~= baseline.amount
        or proposal.intent.purpose ~= baseline.purpose
        or proposal.intent.purchaseKey ~= baseline.purchaseKey then
        return "pending"
    end
    local request = after.fundingRequest
    if request ~= nil and (type(request) ~= "table"
        or request.purpose ~= baseline.purpose
        or request.purchaseKey ~= baseline.purchaseKey) then
        return "pending"
    end
    local cash, banked = balances(after)
    if not cash then return "pending" end
    local advanced = type(after.revision) == "number"
        and after.revision > baseline.revision
        and cash == baseline.cash + baseline.amount
        and banked == baseline.banked - baseline.amount
    if reply.ok == false then return advanced and "pending" or "rejected" end
    if reply.ok == true and advanced then return "confirmed" end
    return "pending"
end

return PurposeWithdrawalsEvidence
