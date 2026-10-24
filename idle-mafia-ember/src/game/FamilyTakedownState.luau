-- Read-only weekly Family Takedown view and regenerated free charges.
local FamilyTakedownState = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge and value % 1 == 0
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
        or not integer(native.serverNow, 0)
        or context.serverNow ~= native.serverNow
        or type(proof) ~= "table"
        or proof.account ~= context.account
        or proof.capturedAt ~= context.capturedAt
        or type(state) ~= "table"
        or not integer(state.week, 1)
        or not integer(state.famId, 1)
        or type(state.inFamily) ~= "boolean"
        or not integer(state.stage, 1) or state.stage > 6
        or not integer(state.resetAt, native.serverNow + 1)
        or not integer(state.freeMax, 0) or state.freeMax > 100
        or not integer(state.freeUsed, 0)
        or state.freeUsed > state.freeMax
        or not integer(state.freeRegen, 1)
        or not integer(state.tickets, 0)
        or not integer(state.myDmg, 0)
        or (state.claims ~= nil and type(state.claims) ~= "table")
        or (state.claimedStages ~= nil
            and type(state.claimedStages) ~= "table")
        or (state.nextFreeAt ~= nil
            and not integer(state.nextFreeAt, 0)) then
        return nil, "Current weekly Family Takedown state required"
    end
    local free = math.max(0, state.freeMax - state.freeUsed)
    local nextFreeAt = free < state.freeMax
        and state.nextFreeAt or nil
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
                    and not integer(row.expiresAt, 0)) then
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
                claims[#claims + 1] = { week = row.week,
                    stage = row.stage,
                    expiresAt = row.expiresAt }
            end
        end
        for key in pairs(state.claims) do
            if type(key) ~= "number" or key % 1 ~= 0
                or key < 1 or key > #state.claims then
                return nil, "Invalid Family Takedown claim list"
            end
        end
    end
    local claimedStages, claimedSeen = {}, {}
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
        famId = state.famId, runKey = tostring(state.week)
            .. ":" .. tostring(state.famId),
        inFamily = state.inFamily, stage = state.stage,
        resetAt = state.resetAt, free = free,
        freeMax = state.freeMax, nextFreeAt = nextFreeAt,
        tickets = state.tickets, myDmg = state.myDmg,
        claims = claims, claimedStages = claimedStages }, nil
end

return FamilyTakedownState
