-- Non-sending listing guard for already loose owned-item surplus.
local MarketSellDirectPreflight = {}

local function integer(value, low, high)
    return type(value) == "number" and value == value
        and value >= low and value <= high and value % 1 == 0
end

local function finite(value, low, high)
    return type(value) == "number" and value == value
        and value > -math.huge and value < math.huge
        and value >= low and value <= high
end

local function text(value, maximum)
    return type(value) == "string" and #value > 0
        and #value <= maximum
end

local function same(a, b)
    if type(a) ~= "table" or type(b) ~= "table" then return false end
    for _, field in ipairs({ "session", "account", "place", "release" }) do
        if not text(a[field], 200) or a[field] ~= b[field] then
            return false
        end
    end
    return integer(a.revision, 0, 9007199254740991)
        and a.revision == b.revision
        and finite(a.capturedAt, 0, math.huge)
        and a.capturedAt == b.capturedAt
end

function MarketSellDirectPreflight.assess(custody, quote,
    listings, terms, settings, attempted, now)
    if not same(custody, quote)
        or not same(custody, listings)
        or not finite(now, 0, math.huge)
        or now - custody.capturedAt > 15
        or custody.capturedAt > now + 1
        or not text(custody.itemId, 120)
        or quote.itemId ~= custody.itemId
        or not integer(custody.quantity, 1, 999)
        or not integer(custody.loose, 0, 1000000000)
        or not integer(custody.reservedLoose,
            0, custody.loose)
        or custody.withdraw ~= 0
        or not integer(quote.quantity, 1,
            custody.quantity)
        or quote.withdraw ~= 0
        or custody.loose - custody.reservedLoose
            < quote.quantity
        or not integer(quote.ask, 2, 9999999)
        or not integer(quote.fee, 1, 1000000)
        or not integer(quote.net, 1, 9999999)
        or type(terms) ~= "table"
        or terms.release ~= custody.release
        or not integer(terms.minPrice, 2, 9999999)
        or not integer(terms.maxPrice,
            terms.minPrice, 9999999)
        or not integer(terms.maxSlots, 1, 20)
        or not integer(terms.rentAllowance, 0, 1000)
        or type(terms.permanent) ~= "boolean"
        or not integer(quote.ask,
            terms.minPrice, terms.maxPrice)
        or quote.ask - quote.fee
            - terms.rentAllowance ~= quote.net
        or not finite(listings.serverNow,
            0, 9007199254740991)
        or not integer(listings.shopUntil,
            0, 9007199254740991)
        or not integer(listings.listingCount, 0, 100)
        or type(listings.listings) ~= "table"
        or type(settings) ~= "table"
        or not integer(settings.minNet, 1, 1000000000)
        or not integer(settings.maxListings, 1, 20)
        or type(settings.transactionOpen) ~= "boolean"
        or not integer(attempted, 0, 20) then
        return nil, "Current loose owned-item sale proof required"
    end
    local count = 0
    for id, row in pairs(listings.listings) do
        count = count + 1
        if count > 100 or not text(id, 160)
            or type(row) ~= "table" then
            return nil, "Owned Market listing slots invalid"
        end
    end
    if count ~= listings.listingCount
        or count >= terms.maxSlots
        or (not terms.permanent
            and listings.shopUntil - listings.serverNow < 120) then
        return nil, "Market shop is closed or full"
    end
    if settings.transactionOpen
        or attempted >= settings.maxListings
        or quote.net < settings.minNet then
        return nil, "Owned sale limit or net failed"
    end
    return { session = custody.session, account = custody.account,
        place = custody.place, release = custody.release,
        revision = custody.revision,
        capturedAt = custody.capturedAt,
        feature = "marketSell", preflightOnly = true,
        intent = { kind = "marketList", itemId = custody.itemId,
            quantity = quote.quantity, ask = quote.ask } }, nil
end

return MarketSellDirectPreflight
