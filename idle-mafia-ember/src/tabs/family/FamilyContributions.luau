-- Tab-owned ordinary contributions. Fresh personal counters and run usage required.
local FamilyContributions = {}
local specs = {
    cash = { feature = "familyCash", resource = "cash", balance = "cash",
        uncertain = "uncertainCash" },
    stamina = { feature = "familyStamina", resource = "stamina", balance = "stamina",
        uncertain = "uncertainStamina" },
    gold = { feature = "familyGold", resource = "gold_bar", balance = "gold",
        uncertain = "uncertainGold" },
}

local function number(value, minimum, maximum)
    return type(value) == "number" and value == value
        and value >= minimum and value <= maximum
end

local function integer(value, minimum, maximum)
    return number(value, minimum, maximum) and value % 1 == 0
end

local function text(value)
    return type(value) == "string" and #value > 0 and #value <= 200
end

local function assess(spec, view, settings, reservations)
    if type(view) ~= "table" or type(settings) ~= "table"
        or settings.enabled ~= true then return nil, "Family activity disabled" end
    for _, field in ipairs({ "session", "account", "place", "release" }) do
        if not text(view[field]) then return nil, "Current Family identity required" end
    end
    local usage = type(view.usage) == "table" and view.usage[spec.feature]
    local before = type(view.ledger) == "table" and view.ledger[spec.resource]
    if not (text(view.familyId) or integer(view.familyId, 1, 9007199254740991))
        or not integer(view.actorId, 1, 9007199254740991)
        or not integer(view.revision, 0, 9007199254740991)
        or not number(view.capturedAt, 0, 9007199254740991)
        or not number(view[spec.balance], 0, 9007199254740991)
        or not integer(before, 0, 9007199254740991)
        or not integer(settings.amount, 1, 1000000000000000)
        or not integer(settings.reserve, 0, 9007199254740991)
        or not integer(settings.runBudget, 0, 1000000000000000)
        or not integer(settings.maxAttempts, 0, 1000)
        or type(usage) ~= "table"
        or not integer(usage.attempted, 0, 1000)
        or not integer(usage.spent, 0, 1000000000000000) then
        return nil, "Current personal Family ledger and independent run limits required"
    end
    if usage.attempted >= settings.maxAttempts
        or usage.spent + settings.amount > settings.runBudget
        or before > 9007199254740991 - settings.amount then
        return nil, "Family run spend or attempt cap reached"
    end
    reservations = type(reservations) == "table" and reservations or {}
    local reserved = reservations[spec.resource]
    local uncertain = reservations[spec.uncertain]
    if reserved == nil then reserved = 0 end
    if uncertain == nil then uncertain = 0 end
    if not number(reserved, 0, 9007199254740991)
        or not number(uncertain, 0, 9007199254740991)
        or view[spec.balance] - reserved - uncertain - settings.amount < settings.reserve then
        return nil, "Family resource reserve or uncertain exposure blocks contribution"
    end
    local intent = { kind = "familyContribution", resource = spec.resource,
        familyId = view.familyId, actorId = view.actorId, amount = settings.amount,
        ledgerBefore = before, reserve = settings.reserve,
        runBudget = settings.runBudget, maxAttempts = settings.maxAttempts,
        spentBefore = usage.spent, attemptsBefore = usage.attempted }
    if spec.resource == "cash" then
        if not integer(view.donateMin, 1, 1000000000)
            or settings.amount < view.donateMin then
            return nil, "Family donation is below the native minimum"
        end
    elseif spec.resource == "gold_bar" then
        -- Origin order for mixed loose/bound donations is not established.
        if view.boundGold ~= 0 then return nil, "Mixed-origin Family Gold custody unverified" end
    else
        local perk = settings.selectedPerk
        local level = type(view.perks) == "table" and view.perks[perk]
        local progress = type(view.progress) == "table" and view.progress[perk]
        local cost = type(view.staminaCosts) == "table" and type(level) == "number"
            and view.staminaCosts[level + 1]
        if type(perk) ~= "string" or #perk > 80
            or type(view.staminaTracks) ~= "table" or view.staminaTracks[perk] ~= true
            or not integer(view.contributeMax, 1, 25)
            or (settings.amount ~= 1 and settings.amount ~= 5)
            or settings.amount > view.contributeMax
            or not integer(level, 0, 24)
            or not integer(cost, 1, 1000000000)
            or not integer(progress, 0, cost - 1)
            or progress + settings.amount > cost then
            return nil, "Selected native Stamina perk and exact batch quote required"
        end
        intent.perkId, intent.perkLevelBefore = perk, level
        intent.perkProgressBefore, intent.perkCost = progress, cost
    end
    return { session = view.session, account = view.account, place = view.place,
        release = view.release, revision = view.revision, feature = spec.feature,
        actionKey = spec.feature .. ":" .. tostring(view.familyId) .. ":"
            .. tostring(before) .. ":" .. tostring(settings.amount) .. ":" .. tostring(usage.attempted),
        resources = { [spec.resource] = settings.amount }, intent = intent }, nil
end

for name, spec in pairs(specs) do
    local selected = spec
    FamilyContributions[name] = { propose = function(view, settings, reservations)
        return assess(selected, view, settings, reservations)
    end }
end

return FamilyContributions
