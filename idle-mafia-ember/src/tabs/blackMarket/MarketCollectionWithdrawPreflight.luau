-- Non-sending Collection transfer for a custody-approved owned sale.
local MarketCollectionWithdrawPreflight = {}

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

function MarketCollectionWithdrawPreflight.assess(custody,
    quote, listings, terms, settings, attempted, now)
    if not same(custody, quote)
        or not same(custody, listings)
        or not finite(now, 0, math.huge)
        or now - custody.capturedAt > 15
        or custody.capturedAt > now + 1
        or not text(custody.itemId, 120)
        or custody.itemId ~= quote.itemId
        or not integer(custody.quantity, 1, 999)
        or custody.quantity ~= quote.quantity
        or not integer(custody.withdraw, 1,
            custody.quantity)
        or custody.withdraw ~= quote.withdraw
        or not integer(custody.loose, 0, 1000000000)
        or not integer(custody.bound, 0, 1000000000)
        or not integer(custody.collected, 0, 1000000000)
        or not integer(custody.collectedBound, 0, 1000000000)
        or not integer(custody.collectedTotal,
            custody.collected, 1000000000)
        or not integer(custody.collectionSurplus,
            custody.withdraw, 1000000000)
        or not integer(custody.checkpointFloor, 0,
            custody.collectedTotal)
        or custody.collected < custody.withdraw
        or custody.collectedTotal - custody.withdraw
            < custody.checkpointFloor
        or not integer(quote.ask, 2, 9999999)
        or not integer(quote.net, 1, 9999999)
        or type(terms) ~= "table"
        or terms.release ~= custody.release
        or type(terms.permanent) ~= "boolean"
        or not integer(terms.maxSlots, 1, 20)
        or not integer(listings.listingCount, 0, 100)
        or type(listings.listings) ~= "table"
        or not finite(listings.serverNow,
            0, 9007199254740991)
        or not integer(listings.shopUntil,
            0, 9007199254740991)
        or type(settings) ~= "table"
        or not integer(settings.maxWithdraw, 1, 999)
        or not integer(settings.maxAttempts, 1, 20)
        or not integer(attempted, 0, 20) then
        return nil, "Current Collection sale withdrawal required"
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
        return nil, "Market shop closed or full before withdrawal"
    end
    if custody.withdraw > settings.maxWithdraw
        or attempted >= settings.maxAttempts then
        return nil, "Collection withdrawal cap reached"
    end
    return { session = custody.session, account = custody.account,
        place = custody.place, release = custody.release,
        revision = custody.revision,
        capturedAt = custody.capturedAt,
        feature = "marketSell", preflightOnly = true,
        intent = { kind = "marketCollectionWithdraw",
            itemId = custody.itemId,
            quantity = custody.withdraw,
            plannedListingQuantity = custody.quantity,
            expectedAsk = quote.ask,
            checkpointFloor = custody.checkpointFloor,
            collectionBefore = custody.collected,
            looseBefore = custody.loose } }, nil
end

return MarketCollectionWithdrawPreflight
