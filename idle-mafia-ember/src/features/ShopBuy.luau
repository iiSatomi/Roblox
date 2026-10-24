-- One selected cash offer per rotation; Gold and native Auto Buy excluded.
local ShopBuy = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge and value % 1 == 0
end

function ShopBuy.propose(view, settings, reservations)
    if type(view) ~= "table" or type(settings) ~= "table"
        or type(reservations) ~= "table" then
        return nil, "Missing Shop planning input"
    end
    if settings.enabled ~= true then return nil, "Shop buying disabled" end
    if view.autoBuy then return nil, "Native Auto Buy owns the Shop" end
    local id = settings.itemId
    local row = type(view.offers) == "table" and view.offers[id]
    if type(id) ~= "string" or #id == 0 or type(row) ~= "table"
        or not integer(view.slot, 0) or not integer(view.level, 1)
        or not integer(view.cash, 0)
        or not integer(settings.cashReserve, 0)
        or not integer(settings.purchaseCap, 1)
        or not integer(reservations.cash or 0, 0)
        or not integer(reservations.uncertainCash or 0, 0)
        or not integer(row.cost, 1)
        or not integer(row.level, 1)
        or not integer(row.bought, 0)
        or not integer(row.owned, 0)
        or type(row.rotationBought) ~= "boolean"
        or type(view.catalogKey) ~= "string" then
        return nil, "Selected cash Shop quote unavailable"
    end
    if row.level > view.level or row.rotationBought
        or (row.limit ~= nil and row.bought >= row.limit) then
        return nil, "Selected Shop offer unavailable"
    end
    local available = view.cash - settings.cashReserve
        - (reservations.cash or 0) - (reservations.uncertainCash or 0)
    if row.cost > settings.purchaseCap or row.cost > available then
        return nil, "Shop purchase budget blocks offer"
    end
    return { session = view.session, account = view.account,
        place = view.place, release = view.release,
        revision = view.revision, feature = "shop",
        actionKey = "shop:" .. view.catalogKey .. ":" .. view.slot
            .. ":" .. id,
        resources = { cash = row.cost },
        intent = { kind = "shopCashBuy", itemId = id,
            slot = view.slot, expectedCost = row.cost,
            beforeOwned = row.owned, beforeBought = row.bought,
            cashReserve = settings.cashReserve,
            catalogKey = view.catalogKey } }, nil
end

return ShopBuy
