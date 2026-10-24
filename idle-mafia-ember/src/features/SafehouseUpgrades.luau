-- One next-tier native upgrade under explicit cap and cash reserve.
local SafehouseUpgrades = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value < math.huge and value >= minimum and value % 1 == 0
end

function SafehouseUpgrades.propose(view, settings, reservations)
    if type(view) ~= "table" or type(settings) ~= "table"
        or type(reservations) ~= "table" then
        return nil, "Missing Safehouse planning input"
    end
    if settings.enabled ~= true then return nil, "Safehouse upgrades disabled" end
    if not integer(view.tier, 1) or not integer(view.nextTier, 2)
        or view.nextTier ~= view.tier + 1
        or not integer(view.nextCost, 1)
        or not integer(view.nextLevel, 1)
        or not integer(view.highestLevel, 1)
        or not integer(view.cash, 0)
        or not integer(settings.maxTier, 1) or settings.maxTier > 18
        or not integer(settings.maxCost, 0)
        or not integer(settings.cashReserve, 0)
        or not integer(reservations.cash or 0, 0)
        or not integer(reservations.uncertainCash or 0, 0)
        or type(view.catalogKey) ~= "string" or #view.catalogKey == 0 then
        return nil, "Invalid Safehouse tier or limits"
    end
    if view.nextTier > settings.maxTier then
        return nil, "Safehouse tier cap reached"
    end
    if view.nextLevel > view.highestLevel then
        return nil, "Safehouse level requirement not met"
    end
    if view.nextCost > settings.maxCost then
        return nil, "Safehouse cost cap reached"
    end
    local available = view.cash - settings.cashReserve
        - (reservations.cash or 0) - (reservations.uncertainCash or 0)
    if view.nextCost > available then
        return nil, "Safehouse cash reserve blocks upgrade"
    end
    return { session = view.session, account = view.account,
        place = view.place, release = view.release,
        revision = view.revision, feature = "safehouse",
        actionKey = "safehouse:" .. #view.catalogKey .. ":"
            .. view.catalogKey .. ":" .. view.nextTier,
        resources = { cash = view.nextCost },
        intent = { kind = "safehouseUpgrade",
            fromTier = view.tier, nextTier = view.nextTier,
            expectedCost = view.nextCost,
            cashReserve = settings.cashReserve,
            catalogKey = view.catalogKey },
    }, nil
end

return SafehouseUpgrades
