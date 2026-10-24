-- One explicitly selected native Boss Shop item; never auto-selects a reward.
local BossShopBuy = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge and value % 1 == 0
end

function BossShopBuy.propose(view, settings, reservations)
    if type(view) ~= "table" or type(settings) ~= "table"
        or type(reservations) ~= "table" then
        return nil, "Missing Boss Shop planning input"
    end
    if settings.enabled ~= true then return nil, "Boss Shop disabled" end
    if view.status ~= "known" or type(view.items) ~= "table"
        or type(view.catalogKey) ~= "string"
        or not integer(view.tokens, 0)
        or not integer(view.attempts, 0)
        or not integer(settings.tokenReserve, 0)
        or not integer(settings.maxSends, 1) or settings.maxSends > 20
        or not integer(settings.crateQuantity, 1)
        or (settings.crateQuantity ~= 1 and settings.crateQuantity ~= 10)
        or not integer(reservations.uncertainBossTokens or 0, 0) then
        return nil, "Invalid Boss Shop limits or state"
    end
    if view.attempts >= settings.maxSends then
        return nil, "Boss Shop session send cap reached"
    end
    local selected
    for _, row in ipairs(view.items) do
        if row.item == settings.itemId then selected = row; break end
    end
    if not selected or selected.unlocked ~= true
        or not integer(selected.price, 1)
        or not integer(selected.owned, 0) then
        return nil, "Selected Boss Shop item unavailable"
    end
    local quantity = selected.kind == "crate"
        and settings.crateQuantity or 1
    if selected.kind ~= "crate" and selected.kind ~= "gear" then
        return nil, "Unknown Boss Shop item kind"
    end
    local cost = selected.price * quantity
    if cost > view.tokens - settings.tokenReserve
        - (reservations.uncertainBossTokens or 0) then
        return nil, "Boss Tokens below quote and reserve"
    end
    return { session = view.session, account = view.account,
        place = view.place, release = view.release,
        revision = view.revision, feature = "bossShop",
        actionKey = "boss-shop:" .. view.session .. ":"
            .. tostring(view.attempts + 1),
        resources = { bossTokens = cost },
        intent = { kind = "bossShopBuy", item = selected.item,
            itemKind = selected.kind, quantity = quantity,
            unitPrice = selected.price, totalCost = cost,
            catalogKey = view.catalogKey,
            tokenReserve = settings.tokenReserve,
            attemptsBefore = view.attempts,
            maxSends = settings.maxSends } }, nil
end

return BossShopBuy
