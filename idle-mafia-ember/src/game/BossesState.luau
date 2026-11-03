-- Attack planning requires the read-only stage view and durable send proof.
local BossesState = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge and value % 1 == 0
end

local function timestamp(value)
    return type(value) == "number" and value == value
        and value >= 0 and value < math.huge
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
        or not timestamp(usage.lastServerNow) then
        return nil, "Current Boss stage and daily attempt proof required"
    end
    local view = {}
    for key, value in pairs(stages) do view[key] = value end
    view.usageHits = usage.hits
    view.usageStamina = usage.stamina
    view.lastServerNow = usage.lastServerNow
    local encounters = raw.bossEncounterProof
    if type(encounters) == "table" and encounters.account == raw.account
        and encounters.session == raw.session and encounters.capturedAt == raw.capturedAt
        and encounters.day == stages.dayStamp and encounters.best == stages.best
        and timestamp(encounters.readyAt) and type(encounters.counts) == "table" then
        view.encounterKnown, view.confirmationReadyAt = true, encounters.readyAt
        view.encounterNow = encounters.now
        for _, row in ipairs(view.stages) do
            local record = encounters.counts[tostring(row.stage)]
            if record == nil then row.confirmedHits, row.confirmedStamina = 0, 0
            elseif type(record) == "table" and integer(record.hits, 0) and integer(record.stamina, 0) then
                row.confirmedHits, row.confirmedStamina = record.hits, record.stamina
            else return nil, "Invalid Boss encounter counters" end
        end
    end
    return view, nil
end

return BossesState
