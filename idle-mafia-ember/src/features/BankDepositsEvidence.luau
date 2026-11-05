-- Reply kept/fee must match exact newer cash-to-bank transfer.
local BankDepositsEvidence = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value < math.huge and value >= minimum and value % 1 == 0
end

local function balance(value)
    return type(value) == "number" and value == value
        and value < math.huge and value >= 0
end

local function matching(a, b, restart)
    for _, field in ipairs({ "session", "account", "place", "release" }) do
        if type(a[field]) ~= "string" or #a[field] == 0
            or type(b[field]) ~= "string" or #b[field] == 0
            or ((not restart or field ~= "session") and a[field] ~= b[field]) then return false end
    end
    return true
end

local function state(raw)
    local native = type(raw) == "table" and raw.native
    if type(native) ~= "table" or native.fullSync ~= true
        or not balance(native.cash)
        or not balance(native.banked) then return nil end
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
        cash = cash, banked = banked, noFee = intent.noFee,
        serverNow = native.serverNow, sourceKey = config.catalogKey,
        sourceRelease = config.release }, nil
end

local function reconcile(proposal, beforeHeader, after,
    reply, baseline, restart)
    if type(proposal) ~= "table" or type(beforeHeader) ~= "table"
        or type(after) ~= "table" or type(reply) ~= "table"
        or type(baseline) ~= "table"
        or not matching(proposal, beforeHeader)
        or not matching(proposal, after, restart)
        or not matching(proposal, baseline)
        or proposal.revision ~= baseline.revision
        or beforeHeader.revision ~= baseline.revision
        or type(proposal.intent) ~= "table"
        or proposal.intent.amount ~= baseline.amount then return "pending" end
    local cash, banked = state(after)
    if not cash or reply.pending == true or reply.code == "pending"
        or reply.code == "presence" or reply.code == "rate_limited" or reply.code == "busy" then return "pending" end
    local validReply = integer(reply.fee, 0)
        and integer(reply.kept, 1)
        and reply.fee + reply.kept == baseline.amount
        and (not baseline.noFee or reply.fee == 0)
    local advanced = integer(after.revision, 0)
        and (restart and after.session ~= proposal.session or after.revision > baseline.revision)
        and cash == baseline.cash - baseline.amount
        and validReply and banked == baseline.banked + reply.kept
    if reply.ok == false then
        return cash == baseline.cash and banked == baseline.banked and "rejected" or "pending"
    end
    if reply.ok == true and advanced then return "confirmed" end
    return "pending"
end

function BankDepositsEvidence.evaluate(proposal, beforeHeader, after, reply, baseline)
    return reconcile(proposal, beforeHeader, after, reply, baseline, false)
end

local function equal(a, b)
    if type(a) ~= type(b) then return false end
    if type(a) ~= "table" then return a == b end
    for key, value in pairs(a) do if not equal(value, b[key]) then return false end end
    for key in pairs(b) do if a[key] == nil then return false end end
    return true
end

function BankDepositsEvidence.recoverSaved(data, after)
    if type(data) ~= "table" or type(data.reply) ~= "table" or type(after) ~= "table"
        or type(after.native) ~= "table" or after.native.fullSync ~= true
        or type(data.before) ~= "table" or type(data.before.native) ~= "table" then return nil end
    local expected = BankDepositsEvidence.capture(data.proposal, data.before)
    if not expected or not equal(expected, data.baseline) then return nil end
    local beforeConfig, currentConfig = data.before.bankConfig, after.bankConfig
    if type(beforeConfig) ~= "table" or type(currentConfig) ~= "table"
        or beforeConfig.release ~= data.proposal.release or currentConfig.release ~= data.proposal.release
        or type(beforeConfig.catalogKey) ~= "string" or #beforeConfig.catalogKey ~= 64
        or not beforeConfig.catalogKey:match("^[%x]+$")
        or currentConfig.catalogKey ~= beforeConfig.catalogKey
        or currentConfig.depositFee ~= beforeConfig.depositFee then return nil end
    local beforeTime, afterTime = data.before.native.serverNow, after.native.serverNow
    if not balance(beforeTime) or not balance(afterTime) or afterTime < beforeTime
        or (after.session ~= data.proposal.session and afterTime <= beforeTime) then return nil end
    if not integer(after.revision, 0)
        or (after.session == data.proposal.session and after.revision <= data.before.revision) then return nil end
    local resources = data.proposal.resources
    if type(resources) ~= "table" then return nil end
    if resources.cash ~= expected.amount then return nil end
    for key, value in pairs(resources) do if key ~= "cash" and value ~= 0 then return nil end end
    local outcome = reconcile(data.proposal, data.before, after, data.reply, expected, true)
    return (outcome == "confirmed" or outcome == "rejected") and outcome or nil
end

return BankDepositsEvidence
