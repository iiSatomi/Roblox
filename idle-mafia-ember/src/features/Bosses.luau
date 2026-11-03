-- Ordinary staged Boss hits; native paid stageAuto remains untouched.
local Bosses = {}

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

local function safe(row, view, reservations, healthFloor, staminaReserve, minLevel, maxLevel, limitsEnabled, confirmedLimitsEnabled, maxConfirmedHits, maxConfirmedStamina)
    return row.unlocked == true and row.doneToday == false
        and integer(row.stage, 1) and integer(row.level, 1)
        and row.level <= 1000000
        and (not limitsEnabled or row.level >= minLevel and row.level <= maxLevel)
        and (not confirmedLimitsEnabled or integer(row.confirmedHits, 0)
            and integer(row.confirmedStamina, 0) and row.confirmedHits < maxConfirmedHits
            and row.confirmedStamina + view.staminaCost <= maxConfirmedStamina)
        and integer(row.remainingHp, 1)
        and integer(row.hitBackMax, 0)
        and view.health >= row.hitBackMax + view.maxHealth * healthFloor / 100
        and view.stamina >= view.staminaCost
            + (reservations.stamina or 0)
            + (reservations.uncertainStamina or 0) + staminaReserve
end

function Bosses.propose(view, settings, reservations)
    if type(view) ~= "table" or type(settings) ~= "table"
        or type(reservations) ~= "table" then
        return nil, "Missing Boss planning input"
    end
    if settings.enabled ~= true then return nil, "City Bosses disabled" end
    local limitsEnabled = settings.limitsEnabled
    if limitsEnabled == nil then limitsEnabled = false end
    local minLevel, maxLevel = settings.minLevel, settings.maxLevel
    if minLevel == nil then minLevel = 1 end
    if maxLevel == nil then maxLevel = 10000 end
    if type(limitsEnabled) ~= "boolean"
        or not integer(minLevel, 1) or minLevel > 1000000
        or not integer(maxLevel, 1) or maxLevel > 1000000
        or (limitsEnabled and minLevel > maxLevel) then
        return nil, "Invalid Boss level range"
    end
    local confirmedLimitsEnabled = settings.confirmedLimitsEnabled
    local confirmationDelayEnabled = settings.confirmationDelayEnabled
    if confirmedLimitsEnabled == nil then confirmedLimitsEnabled = false end
    if confirmationDelayEnabled == nil then confirmationDelayEnabled = false end
    local maxConfirmedHits = settings.maxConfirmedHits or 100
    local maxConfirmedStamina = settings.maxConfirmedStamina or 100
    local confirmationDelay = settings.confirmationDelay or 5
    if type(confirmedLimitsEnabled) ~= "boolean" or type(confirmationDelayEnabled) ~= "boolean"
        or not finite(maxConfirmedHits, 1) or maxConfirmedHits > 100000
        or not finite(maxConfirmedStamina, 1) or maxConfirmedStamina > 100000
        or not finite(confirmationDelay, 5) or confirmationDelay > 120 then
        return nil, "Invalid confirmed Boss encounter preferences"
    end
    if (confirmedLimitsEnabled or confirmationDelayEnabled) and view.encounterKnown ~= true then
        return nil, "Owned confirmed Boss encounter proof required"
    end
    if confirmationDelayEnabled and (not timestamp(view.confirmationReadyAt)
        or not timestamp(view.encounterNow) or view.encounterNow < view.confirmationReadyAt) then return nil, "Boss confirmation delay" end
    local healthFloor, staminaReserve = settings.healthFloor, settings.staminaReserve
    if healthFloor == nil then healthFloor = 50 end
    if staminaReserve == nil then staminaReserve = 1 end
    if not finite(healthFloor, 1) or healthFloor > 100
        or not finite(staminaReserve, 0) or staminaReserve > 1e12 then
        return nil, "Invalid Boss resource floors"
    end
    if view.status ~= "known" or not integer(view.dayStamp, 0)
        or not timestamp(view.serverNow)
        or not integer(view.best, 0)
        or not finite(view.health, 0)
        or not integer(view.maxHealth, 1)
        or not finite(view.stamina, 0)
        or not integer(view.staminaCost, 1)
        or not integer(view.usageHits, 0)
        or not integer(view.usageStamina, 0)
        or not timestamp(view.lastServerNow)
        or not finite(reservations.stamina or 0, 0)
        or not finite(reservations.uncertainStamina or 0, 0)
        or type(view.stages) ~= "table" then
        return nil, "Current Boss resources and attempt proof required"
    end
    if view.usageHits >= 100
        or view.usageStamina + view.staminaCost > 100 then
        return nil, "Boss daily send cap reached"
    end
    if view.usageHits > 0
        and view.serverNow < view.lastServerNow + 5 then
        return nil, "Boss hit spacing"
    end
    local mode = settings.selection or "Current progression"
    local modes = { ["Current progression"] = true, Smart = true, ["First undefeated"] = true,
        ["Highest level"] = true, ["Best chest"] = true, ["Cash reward"] = true, ["XP reward"] = true }
    if not modes[mode] then return nil, "Invalid Boss selection" end
    local complete = view.selectionContract == "boss-get-653-v1" and view.selectionComplete == true
    if mode ~= "Current progression" and not complete then
        return nil, "Reviewed build 653 complete Boss selection source required"
    end
    if complete then
        local captured = view.selectionSettings
        if type(captured) ~= "table" or captured.healthFloor ~= healthFloor
            or captured.minLevel ~= minLevel or captured.maxLevel ~= maxLevel
            or captured.limitsEnabled ~= limitsEnabled or captured.selection ~= mode
            or captured.confirmedLimitsEnabled ~= confirmedLimitsEnabled
            or captured.maxConfirmedHits ~= maxConfirmedHits
            or captured.maxConfirmedStamina ~= maxConfirmedStamina then return nil, "Boss selection preferences changed" end
    end
    local nextStage, repeatStage, top
    for _, row in ipairs(view.stages) do
        if type(row) == "table" and row.stage == math.min(view.best + 1, 100000) then top = row end
        if type(row) == "table" and row.stage == view.best + 1 then
            nextStage = row
        elseif type(row) == "table" and integer(row.stage, 1)
            and row.stage <= view.best
            and safe(row, view, reservations, healthFloor, staminaReserve, minLevel, maxLevel, limitsEnabled, confirmedLimitsEnabled, maxConfirmedHits, maxConfirmedStamina)
            and (not repeatStage or row.stage < repeatStage.stage) then
            repeatStage = row
        end
    end
    if not complete and view.best < 100000 and not nextStage then return nil, "Next Boss stage catalog unknown" end
    local preferred = complete and top or nextStage
    local chosen = preferred
        and safe(preferred, view, reservations, healthFloor, staminaReserve, minLevel, maxLevel, limitsEnabled, confirmedLimitsEnabled, maxConfirmedHits, maxConfirmedStamina) and preferred
        or repeatStage
    if complete and mode ~= "Current progression" and mode ~= "Smart" and mode ~= "First undefeated" then
        chosen = top and safe(top, view, reservations, healthFloor, staminaReserve, minLevel, maxLevel, limitsEnabled, confirmedLimitsEnabled, maxConfirmedHits, maxConfirmedStamina) and top or nil
        local function rank(row)
            if mode == "Highest level" then return row.level end
            if mode == "XP reward" then return row.xp end
            if mode == "Cash reward" then return row.stage > view.best and row.cash or 0 end
            return math.max(not row.mostWanted and row.crateRarity or 0,
                row.stage > view.best and row.firstClearRarity or 0)
        end
        for _, row in ipairs(view.stages) do
            if safe(row, view, reservations, healthFloor, staminaReserve, minLevel, maxLevel, limitsEnabled, confirmedLimitsEnabled, maxConfirmedHits, maxConfirmedStamina) then
                local value, previous = rank(row), chosen and rank(chosen)
                if not chosen or value > previous or value == previous and mode == "Highest level" and row.stage > chosen.stage then
                    chosen = row
                elseif value == previous and row.stage ~= (top and top.stage)
                    and chosen.stage ~= (top and top.stage) and mode ~= "Highest level" and row.stage < chosen.stage then
                    chosen = row
                end
            end
        end
    end
    if not chosen then return nil, view.selectionReason or "No safe available Boss stage" end
    local reward = complete and chosen or {}
    local encounter = view.encounterKnown and {enabled = confirmedLimitsEnabled,
        maxHits = maxConfirmedHits, maxStamina = maxConfirmedStamina,
        delayEnabled = confirmationDelayEnabled, delay = confirmationDelay,
        hits = chosen.confirmedHits, stamina = chosen.confirmedStamina,
        readyAt = view.confirmationReadyAt} or {}
    return { session = view.session, account = view.account,
        place = view.place, release = view.release,
        revision = view.revision, feature = "bosses",
        actionKey = "bosses:" .. view.dayStamp .. ":"
            .. chosen.stage .. ":" .. view.usageHits,
        resources = { stamina = view.staminaCost },
        intent = { kind = "bossStageAttack", stage = chosen.stage,
            healthFloor = healthFloor, staminaReserve = staminaReserve,
            confirmedLimitsEnabled = encounter.enabled, maxConfirmedHits = encounter.maxHits,
            maxConfirmedStamina = encounter.maxStamina,
            confirmationDelayEnabled = encounter.delayEnabled, confirmationDelay = encounter.delay,
            confirmedHitsBefore = encounter.hits, confirmedStaminaBefore = encounter.stamina,
            confirmationReadyAt = encounter.readyAt,
            selectionContract = complete and view.selectionContract or nil,
            selectionMode = complete and mode or nil,
            selectedCash = reward.cash, selectedXp = reward.xp,
            selectedCrate = reward.crate, selectedFirstClearCrate = reward.firstClearCrate,
            selectedCrateRarity = reward.crateRarity, selectedFirstClearRarity = reward.firstClearRarity,
            selectedMostWanted = reward.mostWanted,
            limitsEnabled = limitsEnabled, minLevel = minLevel,
            maxLevel = maxLevel, selectedLevel = chosen.level,
            dayStamp = view.dayStamp, serverNow = view.serverNow,
            bestBefore = view.best,
            remainingHpBefore = chosen.remainingHp,
            maxHp = chosen.maxHp,
            hitBackMax = chosen.hitBackMax,
            expectedStaminaCost = view.staminaCost,
            hitsBefore = view.usageHits,
            staminaBefore = view.usageStamina,
            lastServerNowBefore = view.lastServerNow } }, nil
end

return Bosses
