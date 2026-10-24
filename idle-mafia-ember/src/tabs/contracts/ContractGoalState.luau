-- Classify native Contract goals without enabling any other feature.
local ContractGoalState = {}

local ordinary = {
    banked = "bank", bosshits = "bosses", bosskills = "bosses",
    crates = "chests", deposits = "collectionDonate", energy = "jobs",
    heiststarts = "heists", hires = "crewHire", jobs = "jobs",
    ladder = "playtime", ops = "collect",
    properties = "properties", shopbuys = "shop",
}
local passive = { playtime = true }
local guarded = {
    donatecash = "familyCash", fightwins = "combat",
    heisthelps = "favors", heistsabos = "sabotage",
    stamina = "combat",
}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge and value % 1 == 0
end

local function rows(value, count, singleton)
    if singleton and type(value) == "table" and value.id ~= nil then
        value, count = { value }, 1
    end
    if type(value) ~= "table" or #value ~= count then return nil end
    local result = {}
    for key in pairs(value) do
        if not integer(key, 1) or key > count then return nil end
    end
    for index = 1, count do result[index] = value[index] end
    return result
end

function ContractGoalState.read(raw, context)
    if type(raw) ~= "table" or type(context) ~= "table" then
        return nil, "Missing Contract goal state"
    end
    for _, field in ipairs({ "session", "account", "place", "release",
        "revision", "capturedAt" }) do
        if raw[field] ~= context[field] then
            return nil, "Contract goal snapshot changed"
        end
    end
    local native, templates = raw.native, raw.contractTemplates
    if type(native) ~= "table" or native.fullSync ~= true
        or type(native.contracts) ~= "table"
        or type(templates) ~= "table" or #templates == 0
        or #templates > 100
        or type(raw.catalogKey) ~= "string" or #raw.catalogKey == 0 then
        return nil, "Current Contract template catalog required"
    end
    local byId = {}
    for key, template in pairs(templates) do
        if not integer(key, 1) or key > #templates
            or type(template) ~= "table"
            or type(template.id) ~= "string" or #template.id == 0
            or type(template.key) ~= "string" or #template.key == 0
            or byId[template.id] then
            return nil, "Invalid Contract template catalog"
        end
        byId[template.id] = template.key
    end
    local daily = rows(native.contracts.daily, 5, false)
    local weekly = rows(native.contracts.weekly, 5, true)
    if not daily or not weekly then
        return nil, "Current Contract rows required"
    end
    local result = {}
    for _, period in ipairs({ "daily", "weekly" }) do
        for index, row in ipairs(period == "daily" and daily or weekly) do
            if type(row) ~= "table" or type(row.id) ~= "string"
                or #row.id == 0 or type(row.done) ~= "boolean"
                or type(row.claimed) ~= "boolean" then
                return nil, "Invalid Contract goal row"
            end
            local key = byId[row.id]
            local status, reason, feature
            if row.claimed then status, reason = "claimed", "Reward claimed"
            elseif row.done then status, reason = "complete", "Ready for separate claim"
            elseif not key then status, reason = "unsupported", "Unknown template"
            elseif not integer(row.progress, 0)
                or not integer(row.goal, 1) then
                status, reason = "unsupported", "Progress or goal unavailable"
            elseif row.progress >= row.goal then
                status, reason = "waiting", "Awaiting native completion"
            elseif ordinary[key] then
                status, reason, feature = "mapped", "Ordinary planner mapping; eligibility unverified", ordinary[key]
            elseif passive[key] then
                status, reason = "waiting", "Advances with elapsed playtime"
            elseif guarded[key] then
                status, reason, feature = "blocked", "Separate permission required", guarded[key]
            else status, reason = "unsupported", "No verified planner" end
            result[#result + 1] = { period = period, index = index,
                id = row.id, key = key, status = status,
                reason = reason, feature = feature,
                progress = row.progress, goal = row.goal }
        end
    end
    return { session = context.session, account = context.account,
        place = context.place, release = context.release,
        revision = context.revision, capturedAt = context.capturedAt,
        catalogKey = raw.catalogKey, rows = result }, nil
end

return ContractGoalState
