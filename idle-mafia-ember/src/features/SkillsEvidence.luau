-- Confirm chosen stat and point balance together; a reply alone is pending.
local SkillsEvidence = {}

local stats = { "energy", "stamina", "health", "attack", "defense", "property" }
local known = {}
for _, stat in ipairs(stats) do known[stat] = true end

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge
        and value % 1 == 0
end

local function quote(raw, stat, from, count)
    local rule = type(raw.skillRules) == "table"
        and raw.skillRules[stat]
    if type(rule) ~= "table" or not integer(rule.baseCost, 1) then
        return nil
    end
    if stat == "property" then
        if not integer(rule.costMultiplier, 2)
            or rule.costEvery ~= nil then return nil end
    elseif not integer(rule.costEvery, 1)
        or rule.costMultiplier ~= nil then return nil end
    local total = 0
    for allocated = from, from + count - 1 do
        local cost
        if stat == "property" then
            cost = math.floor(rule.baseCost
                * rule.costMultiplier ^ allocated + 0.5)
        else
            cost = rule.baseCost
                + math.floor(allocated / rule.costEvery)
        end
        if not integer(cost, 1) then return nil end
        total = total + cost
    end
    return integer(total, 1) and total or nil
end

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
    if not known[stat] then return nil end
    for key in pairs(native.allocs) do
        if not known[key] then return nil end
    end
    local allocs = {}
    for _, name in ipairs(stats) do
        local value = native.allocs[name] or 0
        if not integer(value, 0) then return nil end
        allocs[name] = value
    end
    return allocs[stat], native.skillPoints, allocs
end

function SkillsEvidence.capture(proposal, before)
    local intent = type(proposal) == "table" and proposal.intent
    if type(proposal) ~= "table" or proposal.feature ~= "skills"
        or type(intent) ~= "table" or intent.kind ~= "skillAllocation"
        or not known[intent.stat] or not integer(intent.count, 1)
        or intent.count > 100 or not integer(intent.from, 0)
        or type(before) ~= "table"
        or type(intent.catalogKey) ~= "string"
        or intent.catalogKey ~= before.catalogKey
        or type(proposal.resources) ~= "table"
        or not integer(proposal.resources.skillPoints, 1)
        or not matching(proposal, before)
        or proposal.revision ~= before.revision then
        return nil, "Skills baseline mismatch"
    end
    local allocated, points, allocs = state(before, intent.stat)
    if not allocated or allocated ~= intent.from
        or points < proposal.resources.skillPoints
        or quote(before, intent.stat, allocated, intent.count)
            ~= proposal.resources.skillPoints then
        return nil, "Selected Skills state changed"
    end
    return { session = proposal.session, account = proposal.account,
        place = proposal.place, release = proposal.release,
        revision = proposal.revision, stat = intent.stat,
        count = intent.count, allocated = allocated,
        points = points, cost = proposal.resources.skillPoints,
        allocs = allocs }, nil
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
    local allocated, points, allocs = state(after, baseline.stat)
    if not allocated or type(baseline.allocs) ~= "table" then
        return "pending"
    end
    for _, stat in ipairs(stats) do
        if stat ~= baseline.stat
            and allocs[stat] ~= baseline.allocs[stat] then
            return "pending"
        end
    end
    local advanced = type(after.revision) == "number"
        and after.revision > baseline.revision
        and allocated == baseline.allocated + baseline.count
        and points == baseline.points - baseline.cost
    if reply.ok == false then return advanced and "pending" or "rejected" end
    if reply.ok == true and advanced then return "confirmed" end
    return "pending"
end

return SkillsEvidence
