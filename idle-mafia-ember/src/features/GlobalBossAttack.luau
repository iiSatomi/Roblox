-- Ordinary attack with conservative health and per-run send bounds.
local GlobalBossAttack = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge and value % 1 == 0
end

function GlobalBossAttack.propose(view, settings, reservations)
    if type(view) ~= "table" or type(settings) ~= "table"
        or type(reservations) ~= "table" then
        return nil, "Missing Global Boss attack planning input"
    end
    if settings.enabled ~= true then
        return nil, "Global Boss attacks disabled"
    end
    if view.status ~= "known" or view.canAttack ~= true
        or view.phase ~= "live"
        or type(view.runKey) ~= "string" or #view.runKey == 0
        or #view.runKey > 120
        or not integer(view.serverNow, 0)
        or not integer(view.health, 0)
        or type(view.maxHealth) ~= "number"
        or view.maxHealth <= 0
        or not integer(view.stamina, 0)
        or view.staminaCost ~= 1
        or not integer(view.usageHits, 0)
        or not integer(view.lastServerNow, 0)
        or not integer(reservations.stamina or 0, 0)
        or not integer(reservations.uncertainStamina or 0, 0) then
        return nil, "Current live Global Boss resources required"
    end
    if view.usageHits >= 25 then
        return nil, "Global Boss run hit cap reached"
    end
    if view.usageHits > 0
        and view.serverNow < view.lastServerNow + 5 then
        return nil, "Global Boss hit spacing"
    end
    if view.health < view.maxHealth * 0.75
        or view.stamina - view.staminaCost
            - (reservations.stamina or 0)
            - (reservations.uncertainStamina or 0) < 1 then
        return nil, "Global Boss health or stamina reserve"
    end
    return { session = view.session, account = view.account,
        place = view.place, release = view.release,
        revision = view.revision, feature = "globalBossAttack",
        actionKey = "globalBossAttack:" .. view.runKey
            .. ":" .. view.usageHits,
        resources = { stamina = view.staminaCost },
        intent = { kind = "globalBossAttack",
            runKey = view.runKey, serverNow = view.serverNow,
            hitsBefore = view.usageHits,
            lastServerNowBefore = view.lastServerNow,
            mineHitsBefore = view.mineHits,
            mineDamageBefore = view.mineDamage,
            expectedStaminaCost = view.staminaCost } }, nil
end

return GlobalBossAttack
