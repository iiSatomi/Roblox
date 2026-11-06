-- Ordinary player proposals reuse the bounded selector and checkpoint-owned counters.
local Planner = {}
local function number(v) return type(v) == "number" and v == v and v >= 0 and v <= 9007199254740991 end
local function integer(v) return number(v) and v % 1 == 0 and v <= 1000000 end
function Planner.new(selector)
    assert(type(selector) == "table" and type(selector.choose) == "function", "Missing player target policy")
    return {propose = function(view, settings, reservations)
        if type(view) ~= "table" or type(settings) ~= "table" or type(reservations) ~= "table"
            or not number(reservations.stamina) or not number(reservations.uncertainStamina)
            or not integer(view.attackAttempted) or not integer(view.scoutAttempted)
            or not integer(view.attackSpent) or not integer(view.scoutSpent)
            or not integer(settings.maxAttackSpend) or not integer(settings.maxScoutSpend)
            or not number(view.capturedAt) or not number(view.revision) or view.revision % 1 ~= 0
            or type(view.sourceKey) ~= "string" or #view.sourceKey ~= 64 or not view.sourceKey:match("^[%x]+$")
            or not integer(view.maxNativeStaminaCost) or view.maxNativeStaminaCost < 1 or view.maxNativeStaminaCost > 5 then
            return nil, "Owned player counters, maximum exposure and explicit resource holds required"
        end
        for _, k in ipairs({"session", "account", "place", "release"}) do
            if type(view[k]) ~= "string" or #view[k] < 1 or #view[k] > 200 or view[k]:find("[%c]") then
                return nil, "Current player scope required"
            end
        end
        local promote = settings.highPromoteCash == nil and 1000000000 or settings.highPromoteCash
        local below = settings.highDemoteBelow == nil and 100000000 or settings.highDemoteBelow
        local hits = settings.highDemoteHits == nil and 3 or settings.highDemoteHits
        if not number(promote) or promote < 1 or promote > 1000000000000000 or promote % 1 ~= 0
            or not number(below) or below > 1000000000000000 or below % 1 ~= 0
            or not integer(hits) or hits < 1 or hits > 100 then return nil, "Explicit bounded high-value rules required" end
        local held = {stamina = reservations.stamina + reservations.uncertainStamina,
            health = reservations.health or 0, attackSpent = view.attackSpent, scoutSpent = view.scoutSpent}
        local selected, why = selector.choose(view, settings, held, "combat")
        if not selected then return nil, why end
        local scout = selected.kind == "scout"
        local attempted = scout and view.scoutAttempted or view.attackAttempted
        local spent = scout and view.scoutSpent or view.attackSpent
        local p = {feature = "combat", revision = view.revision, resources = {stamina = selected.exposure},
            actionKey = "combat:" .. selected.kind .. ":" .. selected.userId .. ":" .. attempted,
            intent = {kind = scout and "playerScout" or "playerAttack", target = selected.userId,
                targetName = selected.name, targetLevel = selected.level, familyId = selected.familyId,
                excludedWarFamilyId = view.war and view.war.active == true and view.war.enemyFamilyId or nil,
                expectedStaminaCost = selected.cost, maxStaminaExposure = selected.exposure,
                attackExposure = selected.attackExposure, attackQuote = selected.attackCost, sourceKey = view.sourceKey, serverNow = view.serverNow,
                attemptedBefore = attempted, spentBefore = spent, maxAttackSpend = settings.maxAttackSpend,
                maxScoutSpend = settings.maxScoutSpend, allowScout = settings.allowScout == true,
                dailyOnly = settings.dailyOnly == true,
                highValueOnly = (settings.targetSource == "High value only" or settings.targetSource == "High value only + lookup"
                    or settings.preferHighValue == true and selected.highValue == true) and true or nil,
                staminaReserve = settings.staminaReserve, healthFloor = settings.healthFloor,
                uncertainStamina = held.stamina, scoutMaxAge = settings.scoutMaxAge, statsAt = selected.statsAt, defense = selected.defense}}
        if not scout and (promote ~= 1000000000 or below ~= 100000000 or hits ~= 3) then
            p.intent.highPromoteCash, p.intent.highDemoteBelow, p.intent.highDemoteHits = promote, below, hits
        end
        for _, k in ipairs({"session", "account", "place", "release"}) do p[k] = view[k] end
        return p, nil
    end}
end
return Planner
