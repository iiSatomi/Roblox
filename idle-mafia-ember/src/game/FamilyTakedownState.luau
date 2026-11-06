-- Read-only weekly Family Takedown view and regenerated free charges.
local FamilyTakedownState = {}
local function familyId(value)
    return type(value) == "string" and #value > 0 and #value <= 120
        and not value:find("[%c]")
        or type(value) == "number" and value == value and value >= 1
            and value <= 9007199254740991 and value % 1 == 0
end

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge and value % 1 == 0
end

local function timestamp(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge
end

function FamilyTakedownState.read(raw, context)
    if type(raw) ~= "table" or type(context) ~= "table" then
        return nil, "Missing Family Takedown input"
    end
    for _, field in ipairs({ "session", "account", "place", "release",
        "revision", "capturedAt" }) do
        if raw[field] ~= context[field] then
            return nil, "Family Takedown snapshot changed"
        end
    end
    local native, proof = raw.native, raw.familyTakedownProof
    local state = type(proof) == "table" and proof.state
    if type(native) ~= "table" or native.fullSync ~= true
        or not timestamp(native.serverNow, 0)
        or context.serverNow ~= native.serverNow
        or type(proof) ~= "table"
        or proof.account ~= context.account
        or proof.capturedAt ~= context.capturedAt
        or type(state) ~= "table"
        or not integer(state.week, 1)
        or (not familyId(state.famId) and not (state.famId == nil
            and state.inFamily == false and native.family == nil))
        or type(state.inFamily) ~= "boolean"
        or (state.claims ~= nil and type(state.claims) ~= "table")
        or (state.claimedStages ~= nil
            and type(state.claimedStages) ~= "table")
        or (state.nextFreeAt ~= nil
            and not timestamp(state.nextFreeAt, 0)) then
        return nil, "Current weekly Family Takedown state required"
    end
    -- Native historical claim buttons do not use membership or combat resources.
    -- A Family-less reply can therefore be a claim-only view; unknown attack
    -- fields stay absent, and no former Family ID or synthetic run key is used.
    local historicalOnly = state.famId == nil
    if historicalOnly then
        if type(state.claims) ~= "table" then
            return nil, "Explicit historical Family claim list required"
        end
    elseif not integer(state.stage, 1) or state.stage > 6
        or not timestamp(state.resetAt, native.serverNow + 1)
        or not integer(state.freeMax, 0) or state.freeMax > 100
        or not integer(state.freeUsed, 0) or state.freeUsed > state.freeMax
        or not integer(state.freeRegen, 1)
        or not integer(state.tickets, 0) or not integer(state.myDmg, 0) then
        return nil, "Current weekly Family Takedown combat state required"
    end
    local free, nextFreeAt
    if not historicalOnly then
        free = math.max(0, state.freeMax - state.freeUsed)
        nextFreeAt = free < state.freeMax and state.nextFreeAt or nil
    end
    if nextFreeAt and nextFreeAt <= native.serverNow then
        local gained = math.floor(
            (native.serverNow - nextFreeAt) / state.freeRegen) + 1
        free = math.min(state.freeMax, free + gained)
        nextFreeAt = free < state.freeMax
            and nextFreeAt + gained * state.freeRegen or nil
    end
    local claims, seen = {}, {}
    if state.claims then
        if #state.claims > 32 then
            return nil, "Too many Family Takedown claims"
        end
        for _, row in ipairs(state.claims) do
            if type(row) ~= "table"
                or not integer(row.week, 1)
                or row.week > state.week
                or not integer(row.stage, 0)
                or row.stage > 100
                or (row.expiresAt ~= nil
                    and not timestamp(row.expiresAt, 0)) then
                return nil, "Invalid Family Takedown claim"
            end
            local key = tostring(row.week) .. ":"
                .. tostring(row.stage)
            if seen[key] then
                return nil, "Duplicate Family Takedown claim"
            end
            seen[key] = true
            if row.expiresAt ~= nil
                and row.expiresAt > native.serverNow then
                claims[#claims + 1] = { week = row.week, stage = row.stage, expiresAt = row.expiresAt,
                    cash = row.cash, gold = row.gold, crates = row.crates,
                    crateId = row.crateId, medal = row.medal, border = row.border }
            end
        end
        for key in pairs(state.claims) do
            if type(key) ~= "number" or key % 1 ~= 0
                or key < 1 or key > #state.claims then
                return nil, "Invalid Family Takedown claim list"
            end
        end
    end
    local claimedStages = (not historicalOnly or state.claimedStages ~= nil) and {} or nil
    local claimedSeen = {}
    if state.claimedStages then
        if #state.claimedStages > 5 then
            return nil, "Too many claimed Family stages"
        end
        for _, stage in ipairs(state.claimedStages) do
            if not integer(stage, 1) or stage > 5
                or claimedSeen[stage] then
                return nil, "Invalid claimed Family stage"
            end
            claimedSeen[stage] = true
            claimedStages[#claimedStages + 1] = stage
        end
        for key in pairs(state.claimedStages) do
            if not integer(key, 1) or key > #claimedStages then
                return nil, "Invalid claimed Family stage list"
            end
        end
    end
    return { status = "known", session = context.session,
        account = context.account, place = context.place,
        release = context.release, revision = context.revision,
        capturedAt = context.capturedAt,
        serverNow = native.serverNow, week = state.week,
        famId = state.famId, runKey = not historicalOnly and (tostring(state.week)
            .. ":" .. tostring(state.famId)) or nil,
        inFamily = state.inFamily, stage = state.stage,
        resetAt = state.resetAt, free = free,
        freeMax = state.freeMax, nextFreeAt = nextFreeAt,
        tickets = state.tickets, myDmg = state.myDmg,
        claims = claims, claimedStages = claimedStages }, nil
end

return FamilyTakedownState
