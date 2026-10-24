-- One nondestructive native Property build under explicit cash limits.
local Properties = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge and value % 1 == 0
end

local function better(candidate, chosen, policy)
    if not chosen then return true end
    if policy == "Next tier" then
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
        and policy ~= "Next tier"
        or not integer(settings.cashReserve, 0)
        or not integer(settings.purchaseCap, 0)
        or not integer(settings.ownedLimit, 1)
        or settings.ownedLimit > 10
        or not integer(view.level, 1)
        or not integer(view.cash, 0)
        or not integer(view.occupied, 0)
        or not integer(view.capacity, 1)
        or type(view.options) ~= "table"
        or not integer(reservations.cash or 0, 0)
        or not integer(reservations.uncertainCash or 0, 0) then
        return nil, "Invalid Property limits or state"
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
