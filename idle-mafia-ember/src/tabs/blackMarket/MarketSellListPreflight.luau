-- Non-sending owned-sale listing after a confirmed Collection transfer.
local MarketSellListPreflight = {}

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

function MarketSellListPreflight.assess(tx, custody,
    quote, listings, terms, settings, now)
    if not same(tx, custody) or not same(tx, quote)
        or not same(tx, listings)
        or tx.stage ~= "withdrawn"
        or not text(tx.itemId, 120)
        or not integer(tx.withdrawnQuantity, 1, 999)
        or not integer(tx.plannedQuantity,
            tx.withdrawnQuantity, 999)
        or not integer(tx.beforeLoose, 0, 1000000000)
        or not integer(tx.beforeBound, 0, 1000000000)
        or not integer(tx.beforeCollected,
            tx.withdrawnQuantity, 1000000000)
        or not integer(tx.checkpointFloor, 0, 1000000000)
        or not integer(tx.confirmedRevision, 0,
            9007199254740991)
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
        or not integer(custody.loose,
            tx.beforeLoose + tx.withdrawnQuantity,
            1000000000)
        or custody.bound ~= tx.beforeBound
        or custody.collected
            ~= tx.beforeCollected - tx.withdrawnQuantity
        or not integer(custody.collectedTotal,
            tx.checkpointFloor, 1000000000)
        or custody.quantity ~= tx.plannedQuantity
        or custody.withdraw ~= 0
        or quote.itemId ~= tx.itemId
        or quote.quantity ~= tx.plannedQuantity
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
        or not integer(settings.minNet, 1, 1000000000)
        or not integer(settings.maxListAttempts, 1, 20) then
        return nil, "Current withdrawn-item listing proof required"
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
        or quote.net < settings.minNet then
        return nil, "Owned sale listing limit or net failed"
    end
    return { session = tx.session, account = tx.account,
        place = tx.place, release = tx.release,
        revision = custody.revision,
        capturedAt = custody.capturedAt,
        feature = "marketSell", preflightOnly = true,
        intent = { kind = "marketList", itemId = tx.itemId,
            quantity = tx.plannedQuantity, ask = quote.ask,
            collectionWithdrawn = tx.withdrawnQuantity } }, nil
end

return MarketSellListPreflight
