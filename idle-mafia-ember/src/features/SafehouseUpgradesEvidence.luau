-- Exact newer tier increase proves the selected upgrade, not reply alone.
local SafehouseUpgradesEvidence = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value < math.huge and value >= minimum and value % 1 == 0
end

local function balance(value, minimum)
    return type(value) == "number" and value == value
        and value < math.huge and value >= minimum
end

local function matching(a, b, restart)
    for _, field in ipairs({ "session", "account", "place", "release" }) do
        if type(a[field]) ~= "string" or #a[field] == 0
            or type(b[field]) ~= "string" or #b[field] == 0
            or (not restart or field ~= "session") and a[field] ~= b[field] then return false end
    end
    return true
end

local function tier(raw, catalogKey)
    local native = type(raw) == "table" and raw.native
    if type(native) ~= "table" or native.fullSync ~= true
        or not integer(native.safehouse, 1) or native.safehouse > 18
        or raw.catalogKey ~= catalogKey then return nil end
    return native.safehouse
end

function SafehouseUpgradesEvidence.capture(proposal, before)
    local intent = type(proposal) == "table" and proposal.intent
    if type(proposal) ~= "table" or proposal.feature ~= "safehouse"
        or type(intent) ~= "table" or intent.kind ~= "safehouseUpgrade"
        or not integer(intent.fromTier, 1)
        or intent.nextTier ~= intent.fromTier + 1
        or not integer(intent.expectedCost, 1)
        or type(proposal.resources) ~= "table"
        or proposal.resources.cash ~= intent.expectedCost
        or not integer(intent.cashReserve, 0)
        or type(intent.catalogKey) ~= "string" or #intent.catalogKey == 0
        or type(before) ~= "table" or not matching(proposal, before)
        or proposal.revision ~= before.revision then
        return nil, "Safehouse upgrade baseline mismatch"
    end
    local current = tier(before, intent.catalogKey)
    local quote = type(before.safehouseCatalog) == "table"
        and before.safehouseCatalog[intent.nextTier]
    if current ~= intent.fromTier or type(quote) ~= "table"
        or quote.cost ~= intent.expectedCost
        or not balance(before.native.cash,
            intent.expectedCost + intent.cashReserve)
        or not integer(before.native.level, quote.level)
            and not integer(before.native.maxLevel, quote.level) then
        return nil, "Selected Safehouse tier is no longer affordable"
    end
    return { session = proposal.session, account = proposal.account,
        place = proposal.place, release = proposal.release,
        revision = proposal.revision, fromTier = current,
        nextTier = intent.nextTier, catalogKey = intent.catalogKey,
        beforeCash = before.native.cash, serverNow = before.native.serverNow,
        expectedCost = intent.expectedCost }, nil
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
        or type(proposal.intent) ~= "table"
        or proposal.intent.fromTier ~= baseline.fromTier
        or proposal.intent.nextTier ~= baseline.nextTier
        or reply.pending == true or reply.code == "pending" or reply.code == "busy"
        or reply.code == "rate_limited" or reply.code == "presence" then
        return "pending"
    end
    local current = tier(after, baseline.catalogKey)
    local native = after.native
    if not current or not balance(native.cash, 0)
        or not balance(baseline.beforeCash, baseline.expectedCost)
        or not integer(baseline.expectedCost, 1) then return "pending" end
    local observed = integer(after.revision, 0) and after.revision > baseline.revision
    if restart then
        if type(beforeHeader.native) ~= "table" or not balance(beforeHeader.native.serverNow, 0)
            or not balance(native.serverNow, 0) or native.serverNow < beforeHeader.native.serverNow then return "pending" end
        if after.session ~= baseline.session then observed = native.serverNow > beforeHeader.native.serverNow end
    end
    if reply.ok == false then
        return observed and current == baseline.fromTier and native.cash == baseline.beforeCash
            and "rejected" or "pending"
    end
    local originalClock = baseline.serverNow
    if restart and originalClock == nil then originalClock = beforeHeader.native.serverNow end
    local exactDebit = native.cash == baseline.beforeCash - baseline.expectedCost
    -- The exact next tier plus this owned terminal reply proves the upgrade.
    -- A later noncontradictory wallet does not claim an exact debit or income rate.
    local paidOutcome = balance(originalClock, 0) and balance(native.serverNow, 0)
        and native.serverNow > originalClock
        and native.cash >= baseline.beforeCash - baseline.expectedCost
    if reply.ok == true and observed and current == baseline.nextTier
        and (exactDebit or paidOutcome) then return "confirmed" end
    return "pending"
end

function SafehouseUpgradesEvidence.evaluate(proposal, beforeHeader, after, reply, baseline)
    return reconcile(proposal, beforeHeader, after, reply, baseline, false)
end
local function equal(a, b)
    if type(a) ~= type(b) then return false end
    if type(a) ~= "table" then return a == b end
    for key, value in pairs(a) do if not equal(value, b[key]) then return false end end
    for key in pairs(b) do if a[key] == nil then return false end end
    return true
end
function SafehouseUpgradesEvidence.recoverSaved(data, after)
    if type(data) ~= "table" or type(data.baseline) ~= "table" or type(data.reply) ~= "table" then return nil end
    local baseline = SafehouseUpgradesEvidence.capture(data.proposal, data.before)
    if not baseline then return nil end
    -- Original receipts keep their exact schema and historical native clock.
    if data.baseline.serverNow == nil then baseline.serverNow = nil end
    if not equal(baseline, data.baseline) then return nil end
    for key, value in pairs(data.proposal.resources) do
        if key ~= "cash" and value ~= 0 then return nil end
    end
    local result = reconcile(data.proposal, data.before, after, data.reply, baseline, true)
    return (result == "confirmed" or result == "rejected") and result or nil
end

return SafehouseUpgradesEvidence
