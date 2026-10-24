-- Attack planning requires the read-only stage view and durable send proof.
local BossesState = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge and value % 1 == 0
end

function BossesState.read(raw, context)
    if type(raw) ~= "table" or type(context) ~= "table" then
        return nil, "Missing Boss planning input"
    end
    for _, field in ipairs({ "session", "account", "place", "release",
        "revision", "capturedAt" }) do
        if raw[field] ~= context[field] then
            return nil, "Boss snapshot header changed"
        end
    end
    local stages, usage = context.bossStages, raw.bossUsageProof
    if type(stages) ~= "table" or stages.status ~= "known"
        or type(usage) ~= "table"
        or usage.account ~= context.account
        or usage.capturedAt ~= context.capturedAt
        or usage.day ~= stages.dayStamp
        or not integer(usage.hits, 0)
        or not integer(usage.stamina, 0)
        or not integer(usage.lastServerNow, 0) then
        return nil, "Current Boss stage and daily attempt proof required"
    end
    local view = {}
    for key, value in pairs(stages) do view[key] = value end
    view.usageHits = usage.hits
    view.usageStamina = usage.stamina
    view.lastServerNow = usage.lastServerNow
    return view, nil
end

return BossesState
