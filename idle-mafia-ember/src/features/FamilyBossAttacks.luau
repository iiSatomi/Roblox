-- One free Takedown hit; held Tickets always block this automation.
local FamilyBossAttacks = {}
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

function FamilyBossAttacks.propose(view, settings, reservations)
    if type(view) ~= "table" or type(settings) ~= "table"
        or type(reservations) ~= "table" then
        return nil, "Missing Family attack planning input"
    end
    if settings.enabled ~= true then
        return nil, "Free Family attacks disabled"
    end
    local unknown = view.hitBackKnown == false
    if unknown and (settings.allowUncalculatedHitBack ~= true or view.nativePreflight ~= true
        or view.health ~= view.maxHealth or view.usageHits ~= 0 or not integer(view.hospitalHealth, 1)
        or view.health < view.hospitalHealth) then
        return nil, "Unknown Takedown damage needs explicit permission, full health and an unused weekly attempt"
    end
    if view.status ~= "known" or view.inFamily ~= true
        or not integer(view.week, 1)
        or not familyId(view.famId)
        or not integer(view.stage, 1) or view.stage > 6
        or not timestamp(view.serverNow, 0)
        or not timestamp(view.resetAt, view.serverNow + 1)
        or not integer(view.free, 1)
        or view.tickets ~= 0
        or not integer(view.freeUsed, 0)
        or not integer(view.myDmg, 0)
        or not integer(view.health, 0)
        or not integer(view.maxHealth, 1)
        or not integer(view.stamina, 0)
        or not integer(view.staminaCost, 1)
        or not unknown and not integer(view.hitBackMax, 1)
        or not integer(view.usageHits, 0)
        or not timestamp(view.lastServerNow, 0)
        or not integer(reservations.stamina or 0, 0)
        or not integer(reservations.uncertainStamina or 0, 0) then
        return nil, "Current free Family resources required"
    end
    if view.usageHits >= 25 then
        return nil, "Family week hit cap reached"
    end
    if view.usageHits > 0
        and view.serverNow < view.lastServerNow + 5 then
        return nil, "Family hit spacing"
    end
    if (not unknown and view.health - view.hitBackMax
            < math.max(20, view.maxHealth * 0.5)
        )
        or view.stamina - view.staminaCost
            - (reservations.stamina or 0)
            - (reservations.uncertainStamina or 0) < 1 then
        return nil, "Family health or stamina reserve"
    end
    local proposal = { session = view.session, account = view.account,
        place = view.place, release = view.release,
        revision = view.revision, feature = "familyBossAttacks",
        actionKey = "familyBossAttacks:" .. tostring(view.week)
            .. ":" .. tostring(view.famId)
            .. ":" .. tostring(view.usageHits),
        resources = { stamina = view.staminaCost },
        intent = { kind = "familyBossAttack",
            week = view.week, famId = view.famId,
            stage = view.stage, serverNow = view.serverNow,
            hitsBefore = view.usageHits,
            lastServerNowBefore = view.lastServerNow,
            mineDamageBefore = view.myDmg,
            freeUsedBefore = view.freeUsed,
            expectedStaminaCost = view.staminaCost,
            expectedHitBackMax = not unknown and view.hitBackMax or nil } }
    if unknown then
        proposal.intent.uncalculatedHitBack = true
        proposal.intent.allowUncalculatedHitBack = true
        proposal.intent.attackSourceKey = view.attackSourceKey
    end
    return proposal, nil
end

return FamilyBossAttacks
