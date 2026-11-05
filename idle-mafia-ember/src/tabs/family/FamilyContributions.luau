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
        familyId = view.familyId, actorId = view.actorId, actorAccount = view.account, amount = settings.amount,
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
        local choices, seen = {}, {}
        local selection = settings.selectedPerks
        if selection == nil or type(selection) == "string" and selection:match("^%s*$") then
            choices[1] = settings.selectedPerk
        elseif type(selection) == "string" and #selection <= 240 then
            for raw in (selection .. ","):gmatch("(.-),") do
                local perk = raw:match("^%s*(.-)%s*$")
                if #choices >= 10 or seen[perk] or not perk:match("^[%w_%-]+$") then
                    return nil, "Invalid selected Family Stamina perks"
                end
                seen[perk], choices[#choices + 1] = true, perk
            end
        else return nil, "Invalid selected Family Stamina perks" end
        if #choices == 0 or type(view.staminaTracks) ~= "table"
            or not integer(view.contributeMax, 1, 25)
            or (settings.amount ~= 1 and settings.amount ~= 5)
            or settings.amount > view.contributeMax then
            return nil, "Selected native Stamina perk and exact batch quote required"
        end
        for _, perk in ipairs(choices) do
            if type(perk) ~= "string" or #perk > 80 or view.staminaTracks[perk] ~= true then
                return nil, "Selected native Stamina perk required"
            end
        end
        local order = type(view.staminaTrackOrder) == "table" and view.staminaTrackOrder or {}
        table.sort(choices, function(a, b)
            local left = number(order[a], -1000000000, 1000000000) and order[a] or 1000
            local right = number(order[b], -1000000000, 1000000000) and order[b] or 1000
            return left == right and a < b or left < right
        end)
        local first = 1
        for index, perk in ipairs(choices) do
            if perk == view.lastStaminaPerk then first = index % #choices + 1; break end
        end
        for offset = 0, #choices - 1 do
            local perk = choices[(first + offset - 1) % #choices + 1]
            local level = type(view.perks) == "table" and view.perks[perk]
            local progress = type(view.progress) == "table" and view.progress[perk]
            local cost = type(view.staminaCosts) == "table" and type(level) == "number"
                and view.staminaCosts[level + 1]
            if integer(level, 0, 24) and integer(cost, 1, 1000000000)
                and integer(progress, 0, cost - 1) and progress + settings.amount <= cost then
                intent.perkId, intent.perkLevelBefore = perk, level
                intent.perkProgressBefore, intent.perkCost = progress, cost
                break
            end
        end
        if not intent.perkId then return nil, "Selected Stamina perks are maxed or exact batch does not fit" end
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
