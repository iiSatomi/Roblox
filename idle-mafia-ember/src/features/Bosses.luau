-- Ordinary staged Boss hits; native paid stageAuto remains untouched.
local Bosses = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge and value % 1 == 0
end

local function safe(row, view, reservations)
    return row.unlocked == true and row.doneToday == false
        and integer(row.stage, 1) and integer(row.level, 1)
        and integer(row.remainingHp, 1)
        and integer(row.hitBackMax, 0)
        and view.health - row.hitBackMax
            >= view.maxHealth * 0.5
        and view.stamina - view.staminaCost
            - (reservations.stamina or 0)
            - (reservations.uncertainStamina or 0) >= 1
end

function Bosses.propose(view, settings, reservations)
    if type(view) ~= "table" or type(settings) ~= "table"
        or type(reservations) ~= "table" then
        return nil, "Missing Boss planning input"
    end
    if settings.enabled ~= true then return nil, "City Bosses disabled" end
    if view.status ~= "known" or not integer(view.dayStamp, 0)
        or not integer(view.serverNow, 0)
        or not integer(view.best, 0)
        or not integer(view.health, 0)
        or not integer(view.maxHealth, 1)
        or not integer(view.stamina, 0)
        or not integer(view.staminaCost, 1)
        or not integer(view.usageHits, 0)
        or not integer(view.usageStamina, 0)
        or not integer(view.lastServerNow, 0)
        or not integer(reservations.stamina or 0, 0)
        or not integer(reservations.uncertainStamina or 0, 0)
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
    local nextStage, repeatStage
    for _, row in ipairs(view.stages) do
        if type(row) == "table" and row.stage == view.best + 1 then
            nextStage = row
        elseif type(row) == "table" and integer(row.stage, 1)
            and row.stage <= view.best
            and safe(row, view, reservations)
            and (not repeatStage or row.stage < repeatStage.stage) then
            repeatStage = row
        end
    end
    if view.best < 100000 and not nextStage then
        return nil, "Next Boss stage catalog unknown"
    end
    local chosen = nextStage
        and safe(nextStage, view, reservations) and nextStage
        or repeatStage
    if not chosen then return nil, "No safe available Boss stage" end
    return { session = view.session, account = view.account,
        place = view.place, release = view.release,
        revision = view.revision, feature = "bosses",
        actionKey = "bosses:" .. view.dayStamp .. ":"
            .. chosen.stage .. ":" .. view.usageHits,
        resources = { stamina = view.staminaCost },
        intent = { kind = "bossStageAttack", stage = chosen.stage,
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
