-- Non-sending Gold and shop guard for one freshly reassessed flip candidate.
local MarketFlipPreflight = {}

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

local function listingId(value)
    return text(value, 160)
        or integer(value, 1, 9007199254740991)
end

local function same(raw, context)
    if type(raw) ~= "table" or type(context) ~= "table" then
        return false
    end
    for _, field in ipairs({ "session", "account", "place", "release" }) do
        if not text(raw[field], 200)
            or raw[field] ~= context[field] then return false end
    end
    return integer(raw.revision, 0, 9007199254740991)
        and raw.revision == context.revision
        and finite(raw.capturedAt, 0, math.huge)
        and raw.capturedAt == context.capturedAt
end

function MarketFlipPreflight.assess(quote, raw, context,
    terms, budget, spent, attempted, now)
    local native = type(raw) == "table" and raw.native
    local market = type(native) == "table" and native.market
    local derived = type(native) == "table" and native.derived
    if type(quote) ~= "table" or quote.hypothetical ~= true
        or not listingId(quote.listingId)
        or not text(quote.itemId, 120)
        or not text(quote.kind, 80)
        or not integer(quote.rarity, 1, 20)
        or not integer(quote.buy, 1, 9999999)
        or not integer(quote.ask, 2, 9999999)
        or not integer(quote.margin, 1, 9999999)
        or not finite(now, 0, math.huge)
        or not finite(quote.capturedAt, 0, now + 1)
        or now - quote.capturedAt > 15
        or not same(raw, context)
        or now - raw.capturedAt > 15
        or raw.capturedAt > now + 1
        or type(native) ~= "table" or native.fullSync ~= true
        or type(market) ~= "table"
        or type(market.listings) ~= "table"
        or type(derived) ~= "table"
        or type(derived.marketShop) ~= "boolean"
        or not integer(native.level, 0, 1000000)
        or not finite(native.serverNow, 0, 9007199254740991)
        or not integer(market.shopUntil, 0, 9007199254740991)
        or type(native.inventory) ~= "table"
        or type(native.inventoryBound) ~= "table"
        or not integer(native.inventory.gold_bar, 0, 1000000000)
        or not integer(native.inventoryBound.gold_bar or 0, 0, 1000000000)
        or type(terms) ~= "table"
        or terms.release ~= raw.release
        or not integer(terms.minLevel, 1, 1000000)
        or not integer(terms.maxSlots, 1, 20)
        or type(budget) ~= "table"
        or not integer(budget.maxBuy, 1, 9999999)
        or not integer(budget.sessionBudget, 1, 1000000000)
        or not integer(budget.goldReserve, 0, 1000000000)
        or not integer(budget.maxAttempts, 1, 20)
        or type(budget.transactionOpen) ~= "boolean"
        or type(budget.blockedItems) ~= "table"
        or type(budget.blockedKinds) ~= "table"
        or type(budget.blockedRarities) ~= "table"
        or not integer(spent, 0, 1000000000)
        or not integer(attempted, 0, 20) then
        return nil, "Current Market flip preflight required"
    end
    local listings = 0
    for id, row in pairs(market.listings) do
        listings = listings + 1
        if listings > 100 or not text(id, 160)
            or type(row) ~= "table" then
            return nil, "Owned Market listing slots invalid"
        end
    end
    if native.level < terms.minLevel
        or listings >= terms.maxSlots
        or (not derived.marketShop
            and market.shopUntil - native.serverNow < 120) then
        return nil, "Market shop locked, closed or full"
    end
    if budget.transactionOpen
        or attempted >= budget.maxAttempts then
        return nil, "Market flip transaction or attempt cap active"
    end
    if budget.blockedItems[quote.itemId] == true
        or budget.blockedKinds[quote.kind] == true
        or budget.blockedRarities[quote.rarity] == true
        or budget.blockedRarities[tostring(quote.rarity)] == true then
        return nil, "Market flip item excluded"
    end
    if quote.buy > budget.maxBuy
        or spent + quote.buy > budget.sessionBudget
        or native.inventory.gold_bar - quote.buy
            < budget.goldReserve then
        return nil, "Market flip Gold limit or reserve reached"
    end
    return { session = raw.session, account = raw.account,
        place = raw.place, release = raw.release,
        revision = raw.revision, capturedAt = raw.capturedAt,
        feature = "marketFlip", preflightOnly = true,
        intent = { kind = "marketBuy", listingId = quote.listingId,
            itemId = quote.itemId, quantity = 1,
            quotedPrice = quote.buy, expectedAsk = quote.ask,
            expectedMargin = quote.margin } }, nil
end

return MarketFlipPreflight
