-- Conservative ordinary-Job evidence. A reply alone is never success.
local JobsEvidence = {}

local function count(value)
    return type(value) == "number" and value == value
        and value >= 0 and value < math.huge and value % 1 == 0
end

local function selectedCost(raw, targetId)
    local native = raw.native
    if type(native) ~= "table" or native.fullSync ~= true
        or native.autoJob ~= nil or not count(native.level)
        or type(native.pools) ~= "table"
        or not count(native.pools.energy)
        or type(native.jobs) ~= "table"
        or type(raw.jobCatalog) ~= "table"
        or type(raw.masteryRules) ~= "table" then
        return nil
    end
    local selected
    for _, job in ipairs(raw.jobCatalog) do
        if type(job) == "table" and job.id == targetId then
            if selected then return nil end
            selected = job
        end
    end
    if not selected or not count(selected.level)
        or selected.level < 1 or selected.level > native.level
        or not count(selected.energy) or selected.energy < 1 then
        return nil
    end
    local record = native.jobs[targetId]
    if record ~= nil and type(record) ~= "table" then return nil end
    local tier = record and record.masteryTier or 0
    if not count(tier) or tier > #raw.masteryRules then return nil end
    local discount = 0
    if tier > 0 then
        local rule = raw.masteryRules[tier]
        if type(rule) ~= "table" or type(rule.energyDiscount) ~= "number"
            or rule.energyDiscount ~= rule.energyDiscount
            or rule.energyDiscount < 0
            or rule.energyDiscount >= 1 then return nil end
        discount = rule.energyDiscount
    end
    return math.max(1, math.floor(selected.energy
        * (1 - discount) + 0.5))
end

local function matchingIdentity(a, b)
    for _, field in ipairs({ "session", "account", "place", "release" }) do
        if type(a[field]) ~= "string" or a[field] ~= b[field] then return false end
    end
    return true
end

function JobsEvidence.capture(proposal, before)
    if type(proposal) ~= "table" or proposal.feature ~= "jobs"
        or type(proposal.intent) ~= "table"
        or type(proposal.intent.targetId) ~= "string"
        or #proposal.intent.targetId == 0 or type(before) ~= "table"
        or proposal.intent.kind ~= "job"
        or not count(proposal.intent.expectedCost)
        or proposal.intent.expectedCost < 1
        or type(proposal.intent.catalogKey) ~= "string"
        or #proposal.intent.catalogKey == 0
        or not matchingIdentity(proposal, before)
        or proposal.revision ~= before.revision then
        return nil, "Job proposal or baseline header mismatch"
    end
    local native = before.native
    local cost = selectedCost(before, proposal.intent.targetId)
    if type(before.catalogKey) ~= "string"
        or before.catalogKey ~= proposal.intent.catalogKey
        or not cost or cost ~= proposal.intent.expectedCost
        or type(proposal.resources) ~= "table"
        or proposal.resources.energy ~= cost
        or native.pools.energy < cost then
        return nil, "Current Job quote or resources changed"
    end
    local record = native.jobs[proposal.intent.targetId]
    if record ~= nil and type(record) ~= "table" then
        return nil, "Invalid Job baseline record"
    end
    local completions = record and record.completions or 0
    if not count(completions) then return nil, "Invalid Job completion baseline" end
    return {
        session = proposal.session, account = proposal.account,
        place = proposal.place, release = proposal.release,
        revision = proposal.revision, jobId = proposal.intent.targetId,
        completions = completions,
    }, nil
end

function JobsEvidence.evaluate(proposal, beforeHeader, after, reply, baseline)
    if type(proposal) ~= "table" or type(beforeHeader) ~= "table"
        or type(after) ~= "table" or type(baseline) ~= "table"
        or type(reply) ~= "table"
        or not matchingIdentity(proposal, beforeHeader)
        or not matchingIdentity(proposal, baseline)
        or not matchingIdentity(proposal, after)
        or baseline.revision ~= beforeHeader.revision
        or proposal.revision ~= baseline.revision
        or baseline.jobId ~= proposal.intent.targetId then
        return "pending"
    end
    local native = after.native
    if type(native) ~= "table" or native.fullSync ~= true
        or type(native.jobs) ~= "table" then return "pending" end
    local record = native.jobs[baseline.jobId]
    local completed = record and record.completions
    if completed ~= nil and not count(completed) then return "pending" end
    local advanced = count(completed) and completed > baseline.completions
    if reply.ok == false then
        return advanced and "pending" or "rejected"
    end
    if reply.ok == true and advanced and count(after.revision)
        and after.revision > baseline.revision then
        return "confirmed"
    end
    return "pending"
end

return JobsEvidence
