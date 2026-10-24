-- Collection proof uses a selected ready index and matching active-run removal.
local OperationsCollectEvidence = {}

local function nonempty(value)
    return type(value) == "string" and #value > 0
end

local function matching(a, b)
    for _, field in ipairs({ "session", "account", "place", "release" }) do
        if not nonempty(a[field]) or a[field] ~= b[field] then return false end
    end
    return true
end

local function runs(raw, opId)
    local native = type(raw) == "table" and raw.native
    local operations = type(native) == "table" and native.operations
    local active = type(operations) == "table" and operations.active
    if not native or native.fullSync ~= true or type(active) ~= "table"
        or #active > 4 then return nil end
    local total, selected = 0, 0
    for index, entry in ipairs(active) do
        if type(entry) ~= "table" or not nonempty(entry.opId)
            or type(entry.remaining) ~= "number"
            or entry.remaining ~= entry.remaining
            or entry.remaining == math.huge
            or entry.remaining == -math.huge then return nil end
        total = index
        if entry.opId == opId then selected = selected + 1 end
    end
    for key in pairs(active) do
        if type(key) ~= "number" or key % 1 ~= 0 or key < 1
            or key > total then return nil end
    end
    return total, selected, active
end

function OperationsCollectEvidence.capture(proposal, before)
    local intent = type(proposal) == "table" and proposal.intent
    if type(proposal) ~= "table" or proposal.feature ~= "collect"
        or type(intent) ~= "table" or intent.kind ~= "operationCollect"
        or not nonempty(intent.targetId)
        or type(intent.index) ~= "number" or intent.index % 1 ~= 0
        or intent.index < 1 or intent.index > 4
        or type(before) ~= "table" or not matching(proposal, before)
        or proposal.revision ~= before.revision then
        return nil, "Operation collection baseline mismatch"
    end
    local total, count, active = runs(before, intent.targetId)
    local entry = active and active[intent.index]
    if not total or not entry or entry.opId ~= intent.targetId
        or entry.remaining > 0 then
        return nil, "Selected Operation is not ready at current index"
    end
    return {
        session = proposal.session, account = proposal.account,
        place = proposal.place, release = proposal.release,
        revision = proposal.revision, opId = intent.targetId,
        index = intent.index, total = total, count = count,
    }, nil
end

function OperationsCollectEvidence.evaluate(proposal, beforeHeader, after,
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
        or proposal.intent.targetId ~= baseline.opId
        or proposal.intent.index ~= baseline.index then return "pending" end
    local total, count = runs(after, baseline.opId)
    if not total then return "pending" end
    local removed = total < baseline.total and count < baseline.count
    if reply.ok == false then return removed and "pending" or "rejected" end
    if reply.ok == true and removed
        and type(after.revision) == "number"
        and after.revision > baseline.revision then return "confirmed" end
    return "pending"
end

return OperationsCollectEvidence
