-- Reply kept/fee must match exact newer cash-to-bank transfer.
local BankDepositsEvidence = {}

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

local function state(raw)
    local native = type(raw) == "table" and raw.native
    if type(native) ~= "table" or native.fullSync ~= true
        or not integer(native.cash, 0)
        or not integer(native.banked, 0) then return nil end
    return native.cash, native.banked
end

function BankDepositsEvidence.capture(proposal, before)
    local intent = type(proposal) == "table" and proposal.intent
    if type(proposal) ~= "table" or proposal.feature ~= "bank"
        or type(intent) ~= "table" or intent.kind ~= "bankDeposit"
        or not integer(intent.amount, 1)
        or not integer(intent.keepCash, 0)
        or type(intent.noFee) ~= "boolean"
        or type(intent.expectedFeeRate) ~= "number"
        or intent.expectedFeeRate < 0
        or intent.expectedFeeRate > 1
        or type(before) ~= "table" or not matching(proposal, before)
        or proposal.revision ~= before.revision then
        return nil, "Bank deposit baseline mismatch"
    end
    local cash, banked = state(before)
    local savings = before.purchaseSavings
    local native, config = before.native, before.bankConfig
    local currentNoFee = type(native) == "table"
        and type(native.derived) == "table"
        and native.derived.noBankFees
    local fee = type(config) == "table"
        and config.depositFee
    if not cash or cash < intent.amount + intent.keepCash
        or type(currentNoFee) ~= "boolean"
        or currentNoFee ~= intent.noFee
        or type(fee) ~= "number" or fee ~= fee
        or fee < 0 or fee > 1
        or (currentNoFee and 0 or fee) ~= intent.expectedFeeRate
        or type(savings) ~= "table"
        or savings.account ~= proposal.account
        or savings.session ~= proposal.session
        or savings.place ~= proposal.place
        or savings.release ~= proposal.release
        or savings.revision ~= before.revision
        or savings.capturedAt ~= before.capturedAt
        or not integer(savings.amount, 0)
        or cash - intent.amount < savings.amount then
        return nil, "Bank deposit no longer preserves savings"
    end
    return { session = proposal.session, account = proposal.account,
        place = proposal.place, release = proposal.release,
        revision = proposal.revision, amount = intent.amount,
        cash = cash, banked = banked, noFee = intent.noFee }, nil
end

function BankDepositsEvidence.evaluate(proposal, beforeHeader, after,
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
        or proposal.intent.amount ~= baseline.amount then return "pending" end
    local cash, banked = state(after)
    if not cash then return "pending" end
    local validReply = integer(reply.fee, 0)
        and integer(reply.kept, 1)
        and reply.fee + reply.kept == baseline.amount
        and (not baseline.noFee or reply.fee == 0)
    local advanced = type(after.revision) == "number"
        and after.revision > baseline.revision
        and cash == baseline.cash - baseline.amount
        and validReply and banked == baseline.banked + reply.kept
    if reply.ok == false then return advanced and "pending" or "rejected" end
    if reply.ok == true and advanced then return "confirmed" end
    return "pending"
end

return BankDepositsEvidence
