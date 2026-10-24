-- Ordinary Operation start evidence. No reward or collection inference.
local OperationsEvidence = {}

local function nonempty(value)
    return type(value) == "string" and #value > 0
end

local function matching(a, b)
    for _, field in ipairs({ "session", "account", "place", "release" }) do
        if not nonempty(a[field]) or a[field] ~= b[field] then return false end
    end
    return true
end

local function counts(raw, target)
    local native = type(raw) == "table" and raw.native
    local operations = type(native) == "table" and native.operations
    local active = type(operations) == "table" and operations.active
    if not native or native.fullSync ~= true or type(active) ~= "table"
        or #active > 4 then return nil end
    local total, matchingCount = 0, 0
    for index, entry in ipairs(active) do
        if type(entry) ~= "table" or not nonempty(entry.opId)
            or type(entry.remaining) ~= "number"
            or entry.remaining ~= entry.remaining
            or entry.remaining == math.huge
            or entry.remaining == -math.huge then return nil end
        total = index
        if entry.opId == target then matchingCount = matchingCount + 1 end
    end
    for key in pairs(active) do
        if type(key) ~= "number" or key % 1 ~= 0 or key < 1
            or key > total then return nil end
    end
    return total, matchingCount
end

function OperationsEvidence.capture(proposal, before)
    if type(proposal) ~= "table" or proposal.feature ~= "operations"
        or type(proposal.intent) ~= "table"
        or proposal.intent.kind ~= "operationStart"
        or not nonempty(proposal.intent.targetId)
        or type(before) ~= "table" or not matching(proposal, before)
        or proposal.revision ~= before.revision then
        return nil, "Operation proposal or baseline mismatch"
    end
    local total, targetCount = counts(before, proposal.intent.targetId)
    if not total then return nil, "Complete Operation baseline missing" end
    return {
        session = proposal.session, account = proposal.account,
        place = proposal.place, release = proposal.release,
        revision = proposal.revision, opId = proposal.intent.targetId,
        total = total, targetCount = targetCount,
    }, nil
end

function OperationsEvidence.evaluate(proposal, beforeHeader, after, reply, baseline)
    if type(proposal) ~= "table" or type(beforeHeader) ~= "table"
        or type(after) ~= "table" or type(baseline) ~= "table"
        or type(reply) ~= "table" or not matching(proposal, beforeHeader)
        or not matching(proposal, baseline) or not matching(proposal, after)
        or baseline.revision ~= beforeHeader.revision
        or proposal.revision ~= baseline.revision
        or type(proposal.intent) ~= "table"
        or baseline.opId ~= proposal.intent.targetId then return "pending" end
    local total, targetCount = counts(after, baseline.opId)
    if not total then return "pending" end
    local advanced = total > baseline.total
        and targetCount > baseline.targetCount
    if reply.ok == false then return advanced and "pending" or "rejected" end
    if reply.ok == true and advanced
        and type(after.revision) == "number"
        and after.revision > baseline.revision then return "confirmed" end
    return "pending"
end

return OperationsEvidence
