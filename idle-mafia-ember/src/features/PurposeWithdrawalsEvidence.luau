-- Exact cash gain and banked decrease must precede purchase replan.
local PurposeWithdrawalsEvidence = {}

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

local function balances(raw)
    local native = type(raw) == "table" and raw.native
    if type(native) ~= "table" or native.fullSync ~= true
        or not balance(native.cash)
        or not balance(native.banked) then return nil end
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
        or math.ceil(intent.requiredCash - cash) ~= intent.amount
        or type(request) ~= "table"
        or request.session ~= proposal.session
        or request.account ~= proposal.account
        or request.place ~= proposal.place
        or request.release ~= proposal.release
        or request.revision ~= proposal.revision
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
        cash = cash, banked = banked, serverNow = before.native.serverNow,
        sourceKey = type(before.bankConfig) == "table" and before.bankConfig.catalogKey or nil,
        sourceRelease = type(before.bankConfig) == "table" and before.bankConfig.release or nil }, nil
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
        or proposal.intent.amount ~= baseline.amount
        or proposal.intent.purpose ~= baseline.purpose
        or proposal.intent.purchaseKey ~= baseline.purchaseKey then
        return "pending"
    end
    local request = after.fundingRequest
    if request ~= nil and (type(request) ~= "table"
        or request.session ~= after.session
        or request.account ~= after.account
        or request.place ~= after.place
        or request.release ~= after.release
        or request.revision ~= after.revision
        or request.capturedAt ~= after.capturedAt
        or request.purpose ~= baseline.purpose
        or request.purchaseKey ~= baseline.purchaseKey) then
        return "pending"
    end
    local cash, banked = balances(after)
    if not cash then return "pending" end
    if reply.pending == true or reply.code == "pending" or reply.code == "presence"
        or reply.code == "rate_limited" or reply.code == "busy" then return "pending" end
    local advanced = integer(after.revision, 0)
        and (restart and after.session ~= proposal.session or after.revision > baseline.revision)
        and cash == baseline.cash + baseline.amount
        and banked == baseline.banked - baseline.amount
    if reply.ok == false then
        return cash == baseline.cash and banked == baseline.banked
            and "rejected" or "pending"
    end
    if reply.ok == true and advanced then return "confirmed" end
    return "pending"
end

function PurposeWithdrawalsEvidence.evaluate(proposal, beforeHeader, after, reply, baseline)
    return reconcile(proposal, beforeHeader, after, reply, baseline, false)
end

local function equal(a, b)
    if type(a) ~= type(b) then return false end
    if type(a) ~= "table" then return a == b end
    for key, value in pairs(a) do if not equal(value, b[key]) then return false end end
    for key in pairs(b) do if a[key] == nil then return false end end
    return true
end

function PurposeWithdrawalsEvidence.recoverSaved(data, after)
    if type(data) ~= "table" or type(data.reply) ~= "table" or type(after) ~= "table"
        or type(after.native) ~= "table" or after.native.fullSync ~= true
        or type(data.before) ~= "table" or type(data.before.native) ~= "table" then return nil end
    local expected = PurposeWithdrawalsEvidence.capture(data.proposal, data.before)
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
    local purpose = data.proposal.intent.purpose
    if purpose ~= "heists" and purpose ~= "operations" and purpose ~= "properties"
        and purpose ~= "safehouse" and purpose ~= "shop" then return nil end
    for _, value in pairs(resources) do if value ~= 0 then return nil end end
    local outcome = reconcile(data.proposal, data.before, after, data.reply, expected, true)
    return (outcome == "confirmed" or outcome == "rejected") and outcome or nil
end

return PurposeWithdrawalsEvidence
