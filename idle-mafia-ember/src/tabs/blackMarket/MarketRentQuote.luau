-- Non-sending one-period Market rent quote from a current full Sync.
local MarketRentQuote = {}

local function integer(value, low, high)
    return type(value) == "number" and value == value
        and value >= low and value <= high and value % 1 == 0
end

local function finite(value, low, high)
    return type(value) == "number" and value == value
        and value > -math.huge and value < math.huge
        and value >= low and value <= high
end

local function header(raw, context)
    if type(raw) ~= "table" or type(context) ~= "table" then
        return false
    end
    for _, field in ipairs({ "session", "account", "place", "release" }) do
        if type(raw[field]) ~= "string" or #raw[field] == 0
            or #raw[field] > 200 or raw[field] ~= context[field] then
            return false
        end
    end
    return integer(raw.revision, 0, 9007199254740991)
        and raw.revision == context.revision
        and finite(raw.capturedAt, 0, math.huge)
        and raw.capturedAt == context.capturedAt
end

function MarketRentQuote.assess(raw, context, terms, settings, attempted)
    if not header(raw, context)
        or type(raw.native) ~= "table"
        or raw.native.fullSync ~= true
        or type(raw.native.market) ~= "table"
        or type(raw.native.derived) ~= "table"
        or type(raw.native.inventory) ~= "table"
        or type(raw.native.inventoryBound) ~= "table"
        or not integer(raw.native.level, 0, 1000000)
        or not finite(raw.native.serverNow, 0, 9007199254740991)
        or not integer(raw.native.market.shopUntil,
            0, 9007199254740991)
        or (raw.native.inventory.gold_bar ~= nil and not integer(raw.native.inventory.gold_bar, 0, 1000000000))
        or (raw.native.inventoryBound.gold_bar ~= nil and not integer(raw.native.inventoryBound.gold_bar, 0, 1000000000))
        or type(raw.native.derived.marketShop) ~= "boolean"
        or type(terms) ~= "table"
        or terms.release ~= raw.release
        or not integer(terms.minLevel, 1, 1000000)
        or not integer(terms.rentPerPeriod, 1, 1000)
        or not integer(terms.rentPeriodHours, 1, 720)
        or not integer(terms.rentMaxDays, 1, 30)
        or type(settings) ~= "table"
        or not integer(settings.goldReserve, 0, 1000000000)
        or not integer(settings.maxAttempts, 0, 20)
        or not integer(settings.maxGoldSpend, 0, 1000)
        or not integer(attempted, 0, 20) then
        return nil, "Current Market rental state and terms required"
    end
    local native = raw.native
    local looseGold, boundGold = native.inventory.gold_bar or 0, native.inventoryBound.gold_bar or 0
    local cost = terms.rentPerPeriod
    local duration = terms.rentPeriodHours * 3600
    local now = native.serverNow
    local untilTime = native.market.shopUntil
    if native.level < terms.minLevel then
        return nil, "Black Market level locked"
    end
    if native.derived.marketShop
        or untilTime - now >= 120 then
        return nil, "Market shop does not need rental"
    end
    if attempted >= settings.maxAttempts then
        return nil, "Market rental attempt cap reached"
    end
    if cost > settings.maxGoldSpend
        or looseGold + boundGold < cost
        or looseGold + boundGold - cost
                < settings.goldReserve then
        return nil, "Market rental Gold limit or reserve reached"
    end
    if math.max(now, untilTime) + duration
        > now + terms.rentMaxDays * 86400 then
        return nil, "Market rental would exceed native time cap"
    end
    return { session = raw.session, account = raw.account,
        place = raw.place, release = raw.release,
        revision = raw.revision, capturedAt = raw.capturedAt,
        feature = "marketRent", intent = {
            kind = "marketRent", periods = 1, cost = cost,
            durationSeconds = duration } }, nil
end

return MarketRentQuote
