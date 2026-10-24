-- Current and historical claims plus per-week checkpointed attempt proof.
local FamilyBossClaimState = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge and value % 1 == 0
end

function FamilyBossClaimState.read(raw, context)
    if type(raw) ~= "table" or type(context) ~= "table" then
        return nil, "Missing Family claim input"
    end
    for _, field in ipairs({ "session", "account", "place", "release",
        "revision", "capturedAt" }) do
        if raw[field] ~= context[field] then
            return nil, "Family claim snapshot changed"
        end
    end
    local takedown = context.takedown
    local proofs = raw.familyClaimUsageProofs
    if type(proofs) ~= "table" then
        proofs = {}
        local legacy = raw.familyClaimUsageProof
        if type(legacy) == "table" then
            proofs[tostring(legacy.week)] = legacy
        end
    end
    if type(takedown) ~= "table" or takedown.status ~= "known"
        or type(proofs) ~= "table" then
        return nil, "Current Family claim and attempt proof required"
    end
    local attemptedByWeek, attemptCountByWeek = {}, {}
    for key, usage in pairs(proofs) do
        local week = type(usage) == "table" and usage.week
        if type(key) ~= "string" or not integer(week, 1)
            or key ~= tostring(week) or week > takedown.week
            or usage.account ~= context.account
            or usage.capturedAt ~= context.capturedAt
            or type(usage.stages) ~= "table"
            or #usage.stages > 32 then
            return nil, "Invalid Family claim usage proof"
        end
        local attempted, stages = {}, {}
        for _, stage in ipairs(usage.stages) do
            if not integer(stage, 0) or stage > 100 or attempted[stage] then
                return nil, "Invalid Family claim usage"
            end
            attempted[stage] = true
            stages[#stages + 1] = stage
        end
        for index in pairs(usage.stages) do
            if not integer(index, 1) or index > #stages then
                return nil, "Invalid Family claim usage shape"
            end
        end
        attemptedByWeek[week] = attempted
        attemptCountByWeek[week] = #stages
    end
    local view = {}
    for key, value in pairs(takedown) do view[key] = value end
    view.attemptedByWeek = attemptedByWeek
    view.attemptCountByWeek = attemptCountByWeek
    return view, nil
end

return FamilyBossClaimState
