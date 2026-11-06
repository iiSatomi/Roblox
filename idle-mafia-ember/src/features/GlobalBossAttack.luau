-- Ordinary attack with conservative health and per-run send bounds.
local GlobalBossAttack = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge and value % 1 == 0
end

local function timestamp(value)
    return type(value) == "number" and value == value
        and value >= 0 and value < math.huge
end

local function finite(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge
end

function GlobalBossAttack.propose(view, settings, reservations)
    if type(view) ~= "table" or type(settings) ~= "table"
        or type(reservations) ~= "table" then
        return nil, "Missing Global Boss attack planning input"
    end
    if settings.enabled ~= true then
        return nil, "Global Boss attacks disabled"
    end
    local staminaReserve = settings.staminaReserve
    if staminaReserve == nil then staminaReserve = 1 end
    if not finite(staminaReserve, 0) or staminaReserve > 1e12 then
        return nil, "Invalid Global Boss stamina reserve"
    end
    local healthFloor = settings.healthFloor == nil and 50 or settings.healthFloor
    local hitBuffer = settings.hitBufferPct == nil and 25 or settings.hitBufferPct
    local delay = settings.minimumDelay == nil and 5 or settings.minimumDelay
    local cap = settings.maxPerLoad == nil and 25 or settings.maxPerLoad
    local limited = settings.useLoadCap == true
    if not finite(healthFloor,1) or healthFloor>100 or not finite(hitBuffer,0) or hitBuffer>75
        or not finite(delay,2) or delay>120 or not finite(cap,0) or cap>10000
        or settings.useLoadCap ~= nil and type(settings.useLoadCap) ~= "boolean" then
        return nil,"Invalid Global Boss preferences"
    end
    if view.attackCooldownUnavailable == true then return nil,"Current native cooldown unavailable; Global attacks paused" end
    local cooldown = view.attackCooldown
    if cooldown ~= nil and (not finite(cooldown,0) or cooldown<=0 or cooldown>120) then return nil,"Invalid native cooldown proof" end
    if delay<5 and cooldown==nil then return nil,"Current native cooldown required for faster Global hits" end
    local effectiveDelay = math.max(delay,cooldown or 5)
    local load = view.loadUsage
    if (limited or delay~=5) and type(load)~="table" then return nil,"Current Global load usage required" end
    if type(load)=="table" then
        if not integer(load.attackAttempts,0) or not timestamp(load.now)
            or load.lastAttackAt~=nil and not timestamp(load.lastAttackAt) then return nil,"Invalid Global load usage" end
        if limited and load.attackAttempts>=cap then return nil,"Global Boss per-load send cap reached" end
        if load.lastAttackAt and load.now<load.lastAttackAt+effectiveDelay then return nil,"Global Boss per-load hit spacing" end
    end
    if view.status ~= "known" or view.canAttack ~= true
        or view.phase ~= "live"
        or type(view.runKey) ~= "string" or #view.runKey == 0
        or #view.runKey > 120
        or not timestamp(view.serverNow)
        or not finite(view.health, 0)
        or not finite(view.maxHealth, 1)
        or not finite(view.stamina, 0)
        or view.staminaCost ~= 1
        or not integer(view.usageHits, 0)
        or not timestamp(view.lastServerNow)
        or not finite(reservations.stamina or 0, 0)
        or not finite(reservations.uncertainStamina or 0, 0) then
        return nil, "Current live Global Boss resources required"
    end
    if view.usageHits >= 25 then
        return nil, "Global Boss run hit cap reached"
    end
    if view.usageHits > 0
        and view.serverNow < view.lastServerNow + effectiveDelay then
        return nil, "Global Boss hit spacing"
    end
    if view.health < view.maxHealth * (healthFloor + hitBuffer) / 100
        or view.stamina < view.staminaCost
            + (reservations.stamina or 0)
            + (reservations.uncertainStamina or 0) + staminaReserve then
        return nil, "Global Boss health or stamina reserve"
    end
    return { session = view.session, account = view.account,
        place = view.place, release = view.release,
        revision = view.revision, feature = "globalBossAttack",
        actionKey = "globalBossAttack:" .. view.runKey
            .. ":" .. view.usageHits,
        resources = { stamina = view.staminaCost },
        intent = { kind = "globalBossAttack",
            staminaReserve = staminaReserve, healthFloor = healthFloor, hitBufferPct = hitBuffer,
            minimumDelay = delay, nativeAttackCooldown = cooldown, effectiveDelay = effectiveDelay,
            useLoadCap = limited, maxPerLoad = cap,
            loadCountBefore = type(load)=="table" and load.attackAttempts or nil,
            loadLastAttackAt = type(load)=="table" and load.lastAttackAt or nil,
            runKey = view.runKey, serverNow = view.serverNow,
            hitsBefore = view.usageHits,
            lastServerNowBefore = view.lastServerNow,
            mineHitsBefore = view.mineHits,
            mineDamageBefore = view.mineDamage,
            expectedStaminaCost = view.staminaCost } }, nil
end

return GlobalBossAttack
