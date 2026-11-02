-- Ordinary Operation start evidence. No reward or collection inference.
local OperationsEvidence = {}

local function nonempty(value)
    return type(value) == "string" and #value > 0
end

local function slot(value)
    return type(value) == "number" and value % 1 == 0
        and value >= 1 and value <= 4
end

local function finite(value)
    return type(value) == "number" and value == value
        and value >= 0 and value < math.huge
end

local function matching(a, b, restart)
    for _, field in ipairs({ "session", "account", "place", "release" }) do
        if not nonempty(a[field]) or not nonempty(b[field])
            or (not restart or field ~= "session") and a[field] ~= b[field] then return false end
    end
    return true
end

local function counts(raw, target)
    local native = type(raw) == "table" and raw.native
    local operations = type(native) == "table" and native.operations
    local active = type(operations) == "table" and operations.active
    if not native or native.fullSync ~= true or type(active) ~= "table"
        or #active > 4 then return nil end
    local total, matchingCount, slots = 0, 0, {}
    for index, entry in ipairs(active) do
        if type(entry) ~= "table" or not nonempty(entry.opId)
            or type(entry.remaining) ~= "number"
            or entry.remaining ~= entry.remaining
            or entry.remaining == math.huge
            or entry.remaining == -math.huge
            or not slot(entry.slot) or slots[entry.slot] then return nil end
        total = index
        if entry.opId == target then matchingCount = matchingCount + 1 end
        slots[entry.slot] = entry.opId
    end
    for key in pairs(active) do
        if type(key) ~= "number" or key % 1 ~= 0 or key < 1
            or key > total then return nil end
    end
    return total, matchingCount, slots
end

function OperationsEvidence.capture(proposal, before)
    if type(proposal) ~= "table" or proposal.feature ~= "operations"
        or type(proposal.intent) ~= "table"
        or proposal.intent.kind ~= "operationStart"
        or not nonempty(proposal.intent.targetId)
        or not finite(proposal.intent.expectedCost)
        or not nonempty(proposal.intent.catalogKey)
        or type(before) ~= "table" or not matching(proposal, before)
        or proposal.revision ~= before.revision
        or before.catalogKey ~= proposal.intent.catalogKey then
        return nil, "Operation proposal or baseline mismatch"
    end
    local catalog = before.operationCatalog
    if type(catalog) ~= "table" then
        return nil, "Operation quote catalog missing"
    end
    local quoted, matches = nil, 0
    for _, entry in ipairs(catalog) do
        if type(entry) ~= "table" then
            return nil, "Invalid Operation quote catalog"
        end
        if entry.id == proposal.intent.targetId then
            matches = matches + 1
            quoted = entry.cost
        end
    end
    if matches ~= 1 or not finite(quoted)
        or quoted ~= proposal.intent.expectedCost then
        return nil, "Operation quote changed before send"
    end
    local total, targetCount, slots = counts(before,
        proposal.intent.targetId)
    if not total then return nil, "Complete Operation baseline missing" end
    local cash = before.native.cash
    if not finite(cash) or cash < proposal.intent.expectedCost then
        return nil, "Operation quote has no funded cash baseline"
    end
    return {
        session = proposal.session, account = proposal.account,
        place = proposal.place, release = proposal.release,
        revision = proposal.revision, opId = proposal.intent.targetId,
        total = total, targetCount = targetCount,
        cash = cash, cost = proposal.intent.expectedCost,
        slots = slots,
    }, nil
end

local function reconcile(proposal, beforeHeader, after, reply, baseline, restart)
    if type(proposal) ~= "table" or type(beforeHeader) ~= "table"
        or type(after) ~= "table" or type(baseline) ~= "table"
        or type(reply) ~= "table" or not matching(proposal, beforeHeader)
        or not matching(proposal, baseline) or not matching(proposal, after, restart)
        or baseline.revision ~= beforeHeader.revision
        or proposal.revision ~= baseline.revision
        or type(proposal.intent) ~= "table"
        or baseline.opId ~= proposal.intent.targetId
        or baseline.cost ~= proposal.intent.expectedCost then return "pending" end
    local total, targetCount, slots = counts(after, baseline.opId)
    if not total then return "pending" end
    if type(baseline.slots) ~= "table" then return "pending" end
    local newSlots = 0
    for nativeSlot, opId in pairs(baseline.slots) do
        if slots[nativeSlot] ~= opId then return "pending" end
    end
    for nativeSlot, opId in pairs(slots) do
        local original = baseline.slots[nativeSlot]
        if original == nil then
            if opId ~= baseline.opId then return "pending" end
            newSlots = newSlots + 1
        elseif original ~= opId then
            return "pending"
        end
    end
    local advanced = total == baseline.total + 1
        and targetCount == baseline.targetCount + 1
        and newSlots == 1
        and finite(baseline.cash) and finite(baseline.cost)
        and finite(after.native.cash)
        and after.native.cash == baseline.cash - baseline.cost
    if restart and (type(beforeHeader.native) ~= "table"
        or not finite(beforeHeader.native.serverNow) or not finite(after.native.serverNow)
        or after.native.serverNow < beforeHeader.native.serverNow) then return "pending" end
    if reply.ok == false then return advanced and "pending" or "rejected" end
    if reply.ok == true and advanced
        and (restart or type(after.revision) == "number"
            and after.revision > baseline.revision) then return "confirmed" end
    return "pending"
end

function OperationsEvidence.evaluate(proposal, beforeHeader, after, reply, baseline)
    return reconcile(proposal, beforeHeader, after, reply, baseline, false)
end
local function same(a, b)
    if type(a) ~= type(b) then return false end
    if type(a) ~= "table" then return a == b end
    for key, value in pairs(a) do if not same(value, b[key]) then return false end end
    for key in pairs(b) do if a[key] == nil then return false end end
    return true
end
function OperationsEvidence.recoverSaved(data, after)
    if type(data) ~= "table" or type(data.baseline) ~= "table" then return nil end
    local expected = OperationsEvidence.capture(data.proposal, data.before)
    if not expected or not same(expected, data.baseline)
        or type(data.proposal.resources) ~= "table" or data.proposal.resources.cash ~= expected.cost then return nil end
    for key, value in pairs(data.proposal.resources) do
        if key ~= "cash" and value ~= 0 then return nil end
    end
    local result = reconcile(data.proposal, data.before, after, data.reply, expected, true)
    return (result == "confirmed" or result == "rejected") and result or nil
end

return OperationsEvidence
