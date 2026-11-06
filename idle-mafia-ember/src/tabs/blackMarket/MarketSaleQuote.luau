-- Non-sending price and demand check for one custody-approved owned item.
local MarketSaleQuote = {}

local function integer(value, low, high)
    return type(value) == "number" and value == value
        and value >= low and value <= high and value % 1 == 0
end

local function finite(value, low, high)
    return type(value) == "number" and value == value
        and value > -math.huge and value < math.huge
        and value >= low and value <= high
end

local function identity(custody, listings)
    if type(custody) ~= "table" or type(listings) ~= "table" then
        return false
    end
    for _, field in ipairs({ "session", "account", "place", "release",
        "revision", "capturedAt" }) do
        if custody[field] == nil
            or custody[field] ~= listings[field] then return false end
    end
    return type(custody.itemId) == "string" and #custody.itemId > 0
        and integer(custody.quantity, 1, 999)
        and integer(custody.withdraw, 0, custody.quantity)
end

local function fresh(value, now)
    return type(value) == "table"
        and finite(value.capturedAt, 0, now + 1)
        and now - value.capturedAt <= 120
end

local function recentPrices(history)
    local recent = history.recent
    if type(recent) ~= "table" or #recent < 3
        or #recent > 20 then return nil end
    local prices, count = {}, 0
    for index, row in ipairs(recent) do
        if type(row) ~= "table"
            or not integer(row.price, 1, 9999999) then return nil end
        count = index
        prices[index] = row.price
    end
    if count ~= #recent then return nil end
    for key in pairs(recent) do
        if not integer(key, 1, count) then return nil end
    end
    table.sort(prices)
    return prices[math.ceil(#prices / 2)]
end

local function supply(browse, listings, itemId)
    local rows = browse.rows
    if type(rows) ~= "table" or #rows > 500
        or type(listings.listings) ~= "table" then return nil end
    local depth, cheapest, count = 0, nil, 0
    for index, row in ipairs(rows) do
        if type(row) ~= "table" or type(row.item) ~= "string"
            or not integer(row.qty, 1, 1000000000)
            or not integer(row.price, 1, 9999999)
            or type(row.mine) ~= "boolean" then return nil end
        count = index
        if not row.mine then
            depth = depth + row.qty
            if row.item == itemId then
                cheapest = math.min(cheapest or row.price, row.price)
            end
        end
    end
    if count ~= #rows then return nil end
    for key in pairs(rows) do
        if not integer(key, 1, count) then return nil end
    end
    local owned = 0
    for id, row in pairs(listings.listings) do
        if type(id) ~= "string" or type(row) ~= "table"
            or type(row.item) ~= "string"
            or not integer(row.left, 0, 1000000000) then return nil end
        owned = owned + 1
        if row.item == itemId then depth = depth + row.left end
    end
    if owned ~= listings.listingCount then return nil end
    return depth, cheapest
end

function MarketSaleQuote.assess(custody, rap, history, browse,
    listings, terms, settings, now)
    if not identity(custody, listings)
        or not finite(now, 0, math.huge)
        or not fresh(rap, now)
        or not fresh(history, now)
        or not fresh(browse, now)
        or rap.itemId ~= custody.itemId
        or rap.available ~= true
        or not integer(rap.sales, 0, 1000000000)
        or not integer(rap.quantity, 0, 1000000000)
        or not finite(rap.average, 2, 1000000000)
        or history.itemId ~= custody.itemId
        or browse.kind ~= "item" or browse.arg ~= custody.itemId
        or browse.more ~= false
        or browse.stale == true or browse.small == true
        or type(terms) ~= "table"
        or terms.release ~= custody.release
        or not integer(terms.minPrice, 2, 9999999)
        or not integer(terms.maxPrice, terms.minPrice, 9999999)
        or not integer(terms.minFee, 1, 1000)
        or not integer(terms.maxQuantity, 1, 999)
        or not finite(terms.feeRate, 0, 0.5)
        or not integer(terms.rentAllowance, 0, 100)
        or type(terms.permanent) ~= "boolean"
        or not integer(terms.maxSlots, 1, 20)
        or not integer(listings.listingCount, 0, 100)
        or not finite(listings.serverNow, 0, 9007199254740991)
        or not integer(listings.shopUntil, 0, 9007199254740991)
        or type(settings) ~= "table"
        or not integer(settings.minSales, 3, 1000000)
        or not integer(settings.minUnits, 3, 1000000000)
        or not integer(settings.minNet, 1, 1000000000)
        or type(settings.likelyOnly) ~= "boolean"
        or not integer(settings.undercutGold, 0, 3)
        or not integer(settings.floorPct, 90, 100) then
        return nil, "Current Market sale quote inputs required"
    end
    if listings.listingCount >= terms.maxSlots
        or (not terms.permanent
            and listings.shopUntil - listings.serverNow < 120) then
        return nil, "Market shop is closed or full"
    end
    if rap.sales < settings.minSales
        or rap.quantity < settings.minUnits then
        return nil, "Market item has insufficient recent demand"
    end
    local median = recentPrices(history)
    local depth, cheapest = supply(browse, listings, custody.itemId)
    if not median or not depth then
        return nil, "Complete item prices and supply required"
    end
    local ask = cheapest and cheapest - settings.undercutGold
        or math.floor(math.min(median, rap.average) * 0.98)
    if not integer(ask, terms.minPrice, terms.maxPrice)
        or ask < math.ceil(rap.average * settings.floorPct / 100)
        or ask > math.floor(rap.average * 1.1) then
        return nil, "Conservative Market ask unavailable"
    end
    local fee = math.max(terms.minFee,
        math.floor(ask * terms.feeRate))
    local net = ask - fee - terms.rentAllowance
    if net < settings.minNet then
        return nil, "Market net Gold below minimum"
    end
    local quantity = math.min(custody.quantity, terms.maxQuantity)
    if settings.likelyOnly then
        if rap.sales < 10 or rap.quantity < 14 then
            return nil, "Market demand threshold not met"
        end
        local demandCap = math.floor(rap.quantity / 1.5 - depth)
        if demandCap < 1 then
            return nil, "Visible supply exceeds Market demand"
        end
        quantity = math.min(quantity, demandCap)
    end
    local turnover = rap.quantity / math.max(1, depth + quantity)
    if settings.likelyOnly and turnover < 1.5 then
        return nil, "Market demand coverage below minimum"
    end
    local looseAvailable = custody.quantity - custody.withdraw
    return { session = custody.session, account = custody.account,
        place = custody.place, release = custody.release,
        revision = custody.revision, capturedAt = custody.capturedAt,
        itemId = custody.itemId, quantity = quantity,
        withdraw = math.max(0, quantity - looseAvailable),
        ask = ask, fee = fee, net = net,
        competingUnits = depth, sales = rap.sales,
        soldUnits = rap.quantity, turnover = turnover }, nil
end

return MarketSaleQuote
