-- Live event attack view with native resources and sent-hit proof.
local GlobalBossAttackState = {}

local function finite(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge
end

local function integer(value, minimum)
    return finite(value, minimum) and value % 1 == 0
end

function GlobalBossAttackState.read(raw, context)
    if type(raw) ~= "table" or type(context) ~= "table" then
        return nil, "Missing Global Boss attack input"
    end
    for _, field in ipairs({ "session", "account", "place", "release",
        "revision", "capturedAt" }) do
        if raw[field] ~= context[field] then
            return nil, "Global Boss attack snapshot changed"
        end
    end
    local boss, usage, native = context.globalBoss,
        raw.globalAttackUsageProof, raw.native
    if type(boss) ~= "table" or boss.status ~= "known"
        or type(boss.runKey) ~= "string"
        or type(usage) ~= "table"
        or usage.account ~= context.account
        or usage.capturedAt ~= context.capturedAt
        or usage.runKey ~= boss.runKey
        or not integer(usage.hits, 0)
        or not integer(usage.lastServerNow, 0)
        or type(native) ~= "table" or native.fullSync ~= true
        or type(native.stats) ~= "table"
        or not finite(native.stats.maxHealth, 1)
        or type(native.pools) ~= "table"
        or not finite(native.pools.health, 0)
        or native.pools.health > native.stats.maxHealth
        or not finite(native.pools.stamina, 0) then
        return nil, "Current Global Boss attack proof required"
    end
    local view = {}
    for key, value in pairs(boss) do view[key] = value end
    view.health = math.floor(native.pools.health)
    view.maxHealth = native.stats.maxHealth
    view.stamina = math.floor(native.pools.stamina)
    view.staminaCost = 1 -- Saved GlobalBossRules.STAMINA_COST.
    view.usageHits = usage.hits
    view.lastServerNow = usage.lastServerNow
    return view, nil
end

return GlobalBossAttackState
