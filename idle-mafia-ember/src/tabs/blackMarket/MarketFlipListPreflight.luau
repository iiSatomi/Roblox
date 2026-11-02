-- Non-sending relist guard after one confirmed Market flip purchase.
local MarketFlipListPreflight = {}

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
    return true
end

function MarketFlipListPreflight.assess(tx, custody,
    quote, listings, terms, settings, now)
    if not same(tx, custody) or not same(tx, quote)
        or not same(tx, listings)
        or tx.stage ~= "bought"
        or not text(tx.itemId, 120)
        or not (text(tx.sourceListingId, 160)
            or integer(tx.sourceListingId, 1, 9007199254740991))
        or not integer(tx.buyPrice, 1, 9999999)
        or not integer(tx.beforeLoose, 0, 1000000000)
        or not integer(tx.boundBefore, 0, 1000000000)
        or not integer(tx.confirmedRevision, 0, 9007199254740991)
        or not finite(tx.confirmedAt, -3600, math.huge)
        or not integer(tx.listAttempts, 0, 20)
        or not finite(now, 0, math.huge)
        or tx.confirmedAt > now + 1
        or now - tx.confirmedAt > 3600
        or not integer(custody.revision,
            tx.confirmedRevision, 9007199254740991)
        or custody.revision ~= quote.revision
        or custody.revision ~= listings.revision
        or not finite(custody.capturedAt, 0, now + 1)
        or custody.capturedAt ~= quote.capturedAt
        or custody.capturedAt ~= listings.capturedAt
        or now - custody.capturedAt > 15
        or custody.itemId ~= tx.itemId
        or not integer(custody.loose, 1, 1000000000)
        or custody.loose < tx.beforeLoose + 1
        or custody.bound ~= tx.boundBefore
        or not integer(custody.reservedLoose, 0,
            custody.loose)
        or custody.reservedLoose > tx.beforeLoose
        or custody.quantity ~= 1
        or custody.withdraw ~= 0
        or quote.itemId ~= tx.itemId
        or quote.quantity ~= 1
        or quote.withdraw ~= 0
        or not integer(quote.ask, 2, 9999999)
        or not integer(quote.fee, 1, 1000000)
        or not integer(quote.net, 1, 9999999)
        or type(terms) ~= "table"
        or terms.release ~= tx.release
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
        or not integer(settings.minMargin, 1, 1000000)
        or not integer(settings.maxListAttempts, 1, 20) then
        return nil, "Current purchased-item listing proof required"
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
    if tx.listAttempts >= settings.maxListAttempts
        or quote.net - tx.buyPrice < settings.minMargin then
        return nil, "Flip listing cap or margin failed"
    end
    return { session = tx.session, account = tx.account,
        place = tx.place, release = tx.release,
        revision = custody.revision,
        capturedAt = custody.capturedAt,
        feature = "marketFlip", preflightOnly = true,
        intent = { kind = "marketList", itemId = tx.itemId,
            quantity = 1, ask = quote.ask,
            sourceListingId = tx.sourceListingId,
            buyPrice = tx.buyPrice } }, nil
end

return MarketFlipListPreflight
