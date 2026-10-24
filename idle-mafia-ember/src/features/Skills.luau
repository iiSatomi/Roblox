-- One user-selected native skill batch, bounded by point cost and target.
local Skills = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value < math.huge and value >= minimum and value % 1 == 0
end

local function cost(rule, allocated)
    local value
    if rule.costMultiplier then
        value = math.floor(rule.baseCost * rule.costMultiplier ^ allocated + 0.5)
    else
        value = rule.baseCost + math.floor(allocated / rule.costEvery)
    end
    if not integer(value, 1) then return nil end
    return value
end

function Skills.propose(view, settings, reservations)
    if type(view) ~= "table" or type(settings) ~= "table" then
        return nil, "Missing Skills input"
    end
    if settings.enabled ~= true then return nil, "Skills disabled" end
    local stat, cap, batch = settings.stat, settings.maxAllocations, settings.batchSize
    local rule = type(view.rules) == "table" and view.rules[stat]
    local current = type(view.allocs) == "table" and view.allocs[stat]
    if type(stat) ~= "string" or not rule or not integer(current, 0)
        or not integer(cap, 1) or not integer(batch, 1) or batch > 100
        or not integer(view.skillPoints, 0)
        or type(view.catalogKey) ~= "string" or #view.catalogKey == 0 then
        return nil, "Invalid Skills selection or limit"
    end
    if current >= cap then return nil, "Skills allocation target reached" end
    local reserved = type(reservations) == "table"
        and (reservations.skillPoints or 0) or 0
    local uncertain = type(reservations) == "table"
        and (reservations.uncertainSkillPoints or 0) or 0
    if not integer(reserved, 0) or not integer(uncertain, 0) then
        return nil, "Invalid Skills reservation"
    end
    local available = view.skillPoints - reserved - uncertain
    local count, total = 0, 0
    for index = current, math.min(cap, current + batch) - 1 do
        local step = cost(rule, index)
        if not step or total + step > available then break end
        count, total = count + 1, total + step
    end
    if count == 0 then return nil, "Skill points unavailable" end
    local key = "skills:" .. #view.catalogKey .. ":" .. view.catalogKey
        .. ":" .. stat .. ":" .. current .. ":" .. count
    return {
        session = view.session, account = view.account,
        place = view.place, release = view.release,
        revision = view.revision, feature = "skills", actionKey = key,
        resources = { skillPoints = total },
        intent = { kind = "skillAllocation", stat = stat,
            count = count, from = current, catalogKey = view.catalogKey },
    }, nil
end

return Skills
