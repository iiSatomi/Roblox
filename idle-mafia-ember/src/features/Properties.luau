-- One nondestructive native Property build under explicit cash limits.
local Properties = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge and value % 1 == 0
end

local function balance(value)
    return type(value) == "number" and value == value
        and value >= 0 and value < math.huge
end

local function better(candidate, chosen, policy)
    if not chosen then return true end
    if policy == "Highest tier" then
        if candidate.level ~= chosen.level then return candidate.level > chosen.level end
        if candidate.incomePerHour ~= chosen.incomePerHour then return candidate.incomePerHour > chosen.incomePerHour end
    elseif policy == "Next tier" then
        if candidate.level ~= chosen.level then
            return candidate.level < chosen.level end
    elseif policy == "Most income" then
        if candidate.incomePerHour ~= chosen.incomePerHour then
            return candidate.incomePerHour > chosen.incomePerHour end
    else
        local left = candidate.incomePerHour * chosen.cost
        local right = chosen.incomePerHour * candidate.cost
        if left ~= right then return left > right end
    end
    if candidate.cost ~= chosen.cost then return candidate.cost < chosen.cost end
    return candidate.id < chosen.id
end

function Properties.propose(view, settings, reservations)
    if type(view) ~= "table" or type(settings) ~= "table"
        or type(reservations) ~= "table" then
        return nil, "Missing Property planning input"
    end
    if settings.enabled ~= true then return nil, "Property builds disabled" end
    local policy = settings.policy
    if policy ~= "Best value" and policy ~= "Most income"
        and policy ~= "Next tier" and policy ~= "Highest tier"
        or not integer(settings.cashReserve, 0)
        or not integer(settings.purchaseCap, 0)
        or not integer(settings.ownedLimit, 1)
        or settings.ownedLimit > 10
        or not integer(view.level, 1)
        or not balance(view.cash)
        or not integer(view.occupied, 0)
        or not integer(view.capacity, 1)
        or type(view.options) ~= "table"
        or not integer(reservations.cash or 0, 0)
        or not integer(reservations.uncertainCash or 0, 0) then
        return nil, "Invalid Property limits or state"
    end
    if settings.limitsEnabled ~= nil and type(settings.limitsEnabled) ~= "boolean" then return nil, "Invalid Property bounds" end
    local limited = settings.limitsEnabled == true
    local minLevel, maxLevel = settings.minLevel or 1, settings.maxLevel or 10000
    if limited and (not integer(minLevel, 1) or not integer(maxLevel, 1) or minLevel > maxLevel) then
        return nil, "Invalid or inverted Property level bounds"
    end
    local selection = settings.selection or "Automatic"
    if selection ~= "Automatic" and selection ~= "Only selected" then return nil, "Invalid Property selection" end
    local selected
    if selection == "Only selected" then
        if type(settings.selectedIds) ~= "string" or #settings.selectedIds > 4096 then return nil, "Select property IDs" end
        selected = {}
        local known, count = {}, 0
        for _, row in ipairs(view.options) do known[row.id] = true end
        for token in (settings.selectedIds .. ","):gmatch("(.-),") do
            local id = token:match("^%s*(.-)%s*$")
            count = count + 1
            if count > 64 or #id > 120 or not id:match("^[%w_%-]+$") or not known[id] then
                return nil, "Selected property ID is empty, invalid or unavailable"
            end
            selected[id] = true
        end
        if count == 0 then return nil, "Select property IDs" end
    end
    if view.occupied >= view.capacity then
        return nil, "Property block is full"
    end
    local available = view.cash - settings.cashReserve
        - (reservations.cash or 0) - (reservations.uncertainCash or 0)
    local chosen
    for _, row in ipairs(view.options) do
        if type(row) == "table" and integer(row.level, 1)
            and integer(row.owned, 0) and integer(row.cost, 1)
            and integer(row.incomePerHour, 1)
            and type(row.id) == "string" and #row.id > 0
            and row.level <= view.level
            and (not limited or row.level >= minLevel and row.level <= maxLevel)
            and (not selected or selected[row.id] == true)
            and row.owned < settings.ownedLimit
            and row.cost <= settings.purchaseCap
            and row.cost <= available
            and better(row, chosen, policy) then chosen = row end
    end
    if not chosen then return nil, "No eligible Property build" end
    return { session = view.session, account = view.account,
        place = view.place, release = view.release,
        revision = view.revision, feature = "properties",
        actionKey = "properties:" .. #view.catalogKey .. ":"
            .. view.catalogKey .. ":" .. chosen.id .. ":"
            .. chosen.owned + 1,
        resources = { cash = chosen.cost },
        intent = { kind = "propertyBuild", propId = chosen.id,
            beforeOwned = chosen.owned, expectedCost = chosen.cost,
            cashReserve = settings.cashReserve,
            catalogKey = view.catalogKey, optionalSlot = nil } }, nil
end

return Properties
