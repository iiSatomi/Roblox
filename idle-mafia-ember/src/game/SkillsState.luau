-- Native skill allocation view from a complete Sync and current cost rules.
local SkillsState = {}

local stats = { "energy", "stamina", "health", "attack", "defense", "property" }
local known = {}
for _, stat in ipairs(stats) do known[stat] = true end

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value < math.huge and value >= minimum and value % 1 == 0
end

local function rules(source)
    if type(source) ~= "table" then return nil end
    for key in pairs(source) do if not known[key] then return nil end end
    local result = {}
    for _, stat in ipairs(stats) do
        local rule = source[stat]
        if type(rule) ~= "table" or not integer(rule.baseCost, 1) then
            return nil
        end
        if stat == "property" then
            if not integer(rule.costMultiplier, 2) or rule.costEvery ~= nil then
                return nil
            end
            result[stat] = { baseCost = rule.baseCost,
                costMultiplier = rule.costMultiplier }
        else
            if not integer(rule.costEvery, 1) or rule.costMultiplier ~= nil then
                return nil
            end
            result[stat] = { baseCost = rule.baseCost,
                costEvery = rule.costEvery }
        end
    end
    return result
end

function SkillsState.read(raw, context)
    if type(raw) ~= "table" or type(context) ~= "table" then
        return nil, "Missing Skills state or context"
    end
    for _, field in ipairs({ "session", "account", "place", "release",
        "revision", "capturedAt" }) do
        if raw[field] ~= context[field] then
            return nil, "Skills snapshot header changed"
        end
    end
    local native = raw.native
    if type(native) ~= "table" or native.fullSync ~= true then
        return nil, "Complete native Sync required"
    end
    local costRules = rules(raw.skillRules)
    if not integer(native.skillPoints, 0) or not context.resources
        or context.resources.skillPoints ~= native.skillPoints
        or type(native.allocs) ~= "table" or not costRules
        or type(raw.catalogKey) ~= "string" or #raw.catalogKey == 0 then
        return nil, "Skills points, allocations or rules incomplete"
    end
    for key in pairs(native.allocs) do if not known[key] then
        return nil, "Unknown Skills allocation"
    end end
    local allocations = {}
    for _, stat in ipairs(stats) do
        local count = native.allocs[stat] or 0
        if not integer(count, 0) then return nil, "Invalid Skills allocation" end
        allocations[stat] = count
    end
    return {
        session = context.session, account = context.account,
        place = context.place, release = context.release,
        revision = context.revision, capturedAt = context.capturedAt,
        catalogKey = raw.catalogKey, skillPoints = native.skillPoints,
        allocs = allocations, rules = costRules,
    }, nil
end

return SkillsState
