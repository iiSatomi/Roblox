-- Confirm chosen stat and point balance together; a reply alone is pending.
local SkillsEvidence = {}

local function matching(a, b)
    for _, field in ipairs({ "session", "account", "place", "release" }) do
        if type(a[field]) ~= "string" or #a[field] == 0
            or a[field] ~= b[field] then return false end
    end
    return true
end

local function state(raw, stat)
    local native = type(raw) == "table" and raw.native
    if type(native) ~= "table" or native.fullSync ~= true
        or type(native.allocs) ~= "table"
        or type(native.skillPoints) ~= "number"
        or native.skillPoints < 0 or native.skillPoints >= math.huge
        or native.skillPoints % 1 ~= 0 then
        return nil
    end
    local value = native.allocs[stat] or 0
    if type(value) ~= "number" or value < 0 or value >= math.huge
        or value % 1 ~= 0 then return nil end
    return value, native.skillPoints
end

function SkillsEvidence.capture(proposal, before)
    local intent = type(proposal) == "table" and proposal.intent
    if type(proposal) ~= "table" or proposal.feature ~= "skills"
        or type(intent) ~= "table" or intent.kind ~= "skillAllocation"
        or type(intent.stat) ~= "string" or type(intent.count) ~= "number"
        or intent.count < 1 or intent.count > 100 or intent.count % 1 ~= 0
        or type(proposal.resources) ~= "table"
        or type(proposal.resources.skillPoints) ~= "number"
        or type(before) ~= "table" or not matching(proposal, before)
        or proposal.revision ~= before.revision then
        return nil, "Skills baseline mismatch"
    end
    local allocated, points = state(before, intent.stat)
    if not allocated or allocated ~= intent.from
        or points < proposal.resources.skillPoints then
        return nil, "Selected Skills state changed"
    end
    return { session = proposal.session, account = proposal.account,
        place = proposal.place, release = proposal.release,
        revision = proposal.revision, stat = intent.stat,
        count = intent.count, allocated = allocated,
        points = points, cost = proposal.resources.skillPoints }, nil
end

function SkillsEvidence.evaluate(proposal, beforeHeader, after, reply, baseline)
    if type(proposal) ~= "table" or type(beforeHeader) ~= "table"
        or type(after) ~= "table" or type(reply) ~= "table"
        or type(baseline) ~= "table"
        or not matching(proposal, beforeHeader)
        or not matching(proposal, after)
        or not matching(proposal, baseline)
        or proposal.revision ~= baseline.revision
        or beforeHeader.revision ~= baseline.revision
        or type(proposal.intent) ~= "table"
        or proposal.intent.stat ~= baseline.stat
        or proposal.intent.count ~= baseline.count then return "pending" end
    local allocated, points = state(after, baseline.stat)
    if not allocated then return "pending" end
    local advanced = type(after.revision) == "number"
        and after.revision > baseline.revision
        and allocated == baseline.allocated + baseline.count
        and points == baseline.points - baseline.cost
    if reply.ok == false then return advanced and "pending" or "rejected" end
    if reply.ok == true and advanced then return "confirmed" end
    return "pending"
end

return SkillsEvidence
