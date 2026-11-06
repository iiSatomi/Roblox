-- Free-only Family Takedown attack view with native resource bounds.
local FamilyBossAttackState = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge and value % 1 == 0
end

local function finite(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge
end

function FamilyBossAttackState.read(raw, context)
    if type(raw) ~= "table" or type(context) ~= "table" then
        return nil, "Missing Family attack input"
    end
    for _, field in ipairs({ "session", "account", "place", "release",
        "revision", "capturedAt" }) do
        if raw[field] ~= context[field] then
            return nil, "Family attack snapshot changed"
        end
    end
    local takedown, proof, usage, native = context.takedown,
        raw.familyAttackProof, raw.familyAttackUsageProof,
        raw.native
    local state = type(raw.familyTakedownProof) == "table"
        and raw.familyTakedownProof.state
    local unknown = type(proof) == "table" and proof.hitBackKnown == false
    local nativePreflight = unknown and proof.nativePreflight == true and proof.controllersClear == true
        and integer(proof.hospitalHealth, 1) and type(proof.sourceKey) == "string"
        and #proof.sourceKey == 64 and proof.sourceKey:match("^[%x]+$") ~= nil and type(proof.header) == "table"
    if nativePreflight then
        for _, field in ipairs({"session", "account", "place", "release", "revision", "capturedAt"}) do
            if proof.header[field] ~= raw[field] then nativePreflight = false end
        end
    end
    if type(takedown) ~= "table" or takedown.status ~= "known"
        or type(proof) ~= "table"
        or proof.account ~= context.account
        or proof.capturedAt ~= context.capturedAt
        or proof.week ~= takedown.week
        or proof.famId ~= takedown.famId
        or proof.stage ~= takedown.stage
        or not integer(proof.staminaCost, 1)
        or (unknown and not nativePreflight or not unknown and not integer(proof.hitBackMax, 0))
        or type(usage) ~= "table"
        or usage.account ~= context.account
        or usage.capturedAt ~= context.capturedAt
        or usage.week ~= takedown.week
        or usage.famId ~= takedown.famId
        or not integer(usage.hits, 0)
        or not finite(usage.lastServerNow, 0)
        or type(native) ~= "table" or native.fullSync ~= true
        or type(native.stats) ~= "table"
        or not integer(native.stats.maxHealth, 1)
        or type(native.pools) ~= "table"
        or not finite(native.pools.health, 0)
        or native.pools.health > native.stats.maxHealth
        or not finite(native.pools.stamina, 0)
        or type(state) ~= "table"
        or not integer(state.freeUsed, 0) then
        return nil, "Current free Family attack proof required"
    end
    local view = {}
    for key, value in pairs(takedown) do view[key] = value end
    view.health = math.floor(native.pools.health)
    view.maxHealth = native.stats.maxHealth
    view.stamina = math.floor(native.pools.stamina)
    view.staminaCost = proof.staminaCost
    view.hitBackMax = proof.hitBackMax
    view.hitBackKnown = not unknown
    view.nativePreflight = nativePreflight == true
    view.attackSourceKey = proof.sourceKey
    view.hospitalHealth = proof.hospitalHealth
    view.freeUsed = state.freeUsed
    view.usageHits = usage.hits
    view.lastServerNow = usage.lastServerNow
    return view, nil
end

return FamilyBossAttackState
