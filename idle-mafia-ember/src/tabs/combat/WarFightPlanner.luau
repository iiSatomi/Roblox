-- War uses its own roster, opt-ins and durable Attack/Scout allowances.
-- The shared selector applies native scoring caps and fresh Scout requirements.
local Planner = {}
local function number(v) return type(v) == "number" and v == v and v >= 0 and v <= 9007199254740991 end
local function integer(v) return number(v) and v % 1 == 0 and v <= 1000000 end
local function usage(attempted, spent)
    return integer(attempted) and integer(spent) and spent >= attempted and spent <= attempted * 5
end
function Planner.new(selector)
    assert(type(selector) == "table" and type(selector.choose) == "function", "Missing War target policy")
    return {propose = function(view, settings, reservations)
        if type(view) ~= "table" or type(settings) ~= "table" or type(reservations) ~= "table"
            or not number(reservations.stamina) or not number(reservations.uncertainStamina)
            or not usage(view.attackAttempted, view.attackSpent) or not usage(view.scoutAttempted, view.scoutSpent)
            or not integer(settings.maxAttackSpend) or not integer(settings.maxScoutSpend)
            or not number(view.capturedAt) or not number(view.revision) or view.revision % 1 ~= 0
            or type(view.sourceKey) ~= "string" or #view.sourceKey ~= 64 or not view.sourceKey:match("^[%x]+$")
            or not integer(view.maxNativeStaminaCost) or view.maxNativeStaminaCost < 1 or view.maxNativeStaminaCost > 5 then
            return nil, "Owned War counters, maximum exposure and explicit resource holds required"
        end
        for _, key in ipairs({"session", "account", "place", "release"}) do
            if type(view[key]) ~= "string" or #view[key] < 1 or #view[key] > 200 or view[key]:find("[%c]") then
                return nil, "Current War scope required"
            end
        end
        local held = {stamina = reservations.stamina + reservations.uncertainStamina,
            health = reservations.health or 0, attackSpent = view.attackSpent, scoutSpent = view.scoutSpent}
        local selected, why = selector.choose(view, settings, held, "warCombat")
        if not selected then return nil, why end
        local scout = selected.kind == "scout"
        local attempted = scout and view.scoutAttempted or view.attackAttempted
        local spent = scout and view.scoutSpent or view.attackSpent
        local p = {feature = "warCombat", revision = view.revision, resources = {stamina = selected.exposure},
            actionKey = "warCombat:" .. selected.kind .. ":" .. selected.userId .. ":" .. attempted,
            intent = {kind = scout and "playerScout" or "playerAttack", target = selected.userId,
                targetName = selected.name, targetLevel = selected.level, familyId = selected.familyId,
                warFamilyId = selected.warFamilyId, ownFamilyId = view.ownFamilyId,
                warDay = math.floor(view.serverNow / 86400), warStatusServerNow = view.war.statusServerNow,
                expectedStaminaCost = selected.cost, maxStaminaExposure = selected.exposure,
                attackExposure = selected.attackExposure, attackQuote = selected.attackCost,
                sourceKey = view.sourceKey, serverNow = view.serverNow,
                attemptedBefore = attempted, spentBefore = spent, maxAttackSpend = settings.maxAttackSpend,
                maxScoutSpend = settings.maxScoutSpend, allowScout = settings.allowScout == true,
                staminaReserve = settings.staminaReserve, healthFloor = settings.healthFloor,
                uncertainStamina = held.stamina, scoutMaxAge = settings.scoutMaxAge,
                minWinChance = settings.minWinChance, minPowerRatio = settings.minPowerRatio, attack = view.attack,
                statsAt = selected.statsAt, defense = selected.defense}}
        for _, key in ipairs({"session", "account", "place", "release"}) do p[key] = view[key] end
        return p, nil
    end}
end
return Planner
