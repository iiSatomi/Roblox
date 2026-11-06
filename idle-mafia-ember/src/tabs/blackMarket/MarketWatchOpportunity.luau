-- Read-only hypothetical margin for one complete, fresh Market listing.
local MarketWatchOpportunity = {}

local function integer(value, low, high)
    return type(value) == "number" and value == value
        and value >= low and value <= high and value % 1 == 0
end

local function finite(value, low, high)
    return type(value) == "number" and value == value
        and value > -math.huge and value < math.huge
        and value >= low and value <= high
end

local function fresh(value, now, age)
    return type(value) == "table"
        and finite(value.capturedAt, 0, now + 1)
        and now - value.capturedAt <= age
end

local function id(value)
    return type(value) == "string" and #value > 0
        and #value <= 160
        or integer(value, 1, 9007199254740991)
end

local function median(history)
    local rows = type(history) == "table" and history.recent
    if type(rows) ~= "table" or #rows < 3
        or #rows > 20 then return nil end
    local prices, count = {}, 0
    for index, row in ipairs(rows) do
        if type(row) ~= "table"
            or not integer(row.price, 1, 9999999) then
            return nil
        end
        count = index
        prices[index] = row.price
    end
    if count ~= #rows then return nil end
    for key in pairs(rows) do
        if not integer(key, 1, count) then return nil end
    end
    table.sort(prices)
    return prices[math.ceil(#prices / 2)]
end

local function visible(browse, listingId, itemId)
    local rows = browse.rows
    if type(rows) ~= "table" or #rows < 1
        or #rows > 500 then return nil end
    local target, cheapest, supply, count, seen = nil, nil, 0, 0, {}
    for index, row in ipairs(rows) do
        if type(row) ~= "table" or not id(row.id)
            or type(row.item) ~= "string" or #row.item == 0
            or #row.item > 120 or not (row.item:match("^[%w_%-]+$") or row.item:match("^[%w_%-]+@[1-9]%d?$"))
            or not integer(row.qty, 1, 1000000000)
            or not integer(row.price, 1, 9999999)
            or type(row.mine) ~= "boolean"
            or seen[tostring(row.id)] then return nil end
        count = index
        seen[tostring(row.id)] = true
        if tostring(row.id) == tostring(listingId) then
            if target then return nil end
            target = row
        elseif row.item == itemId then
            cheapest = math.min(cheapest or row.price, row.price)
            supply = supply + row.qty
            if supply > 1000000000 then return nil end
        end
    end
    if count ~= #rows then return nil end
    for key in pairs(rows) do
        if not integer(key, 1, count) then return nil end
    end
    if not target or target.item ~= itemId
        or target.mine or target.qty ~= 1 then return nil end
    return target, cheapest, supply
end

function MarketWatchOpportunity.assess(browse, listingId, rap,
    history, item, terms, settings, now)
    if not id(listingId)
        or not finite(now, 0, 9007199254740991)
        or not fresh(browse, now, 15)
        or not (browse.kind == "all" and browse.arg == nil
            or browse.kind == "item" and type(item) == "table" and type(item.id) == "string"
                and browse.arg == (item.id:match("^([%w_%-]+)@[1-9]%d?$") or item.id))
        or browse.more ~= false
        or browse.stale == true or browse.small == true
        or not fresh(rap, now, 120)
        or not fresh(history, now, 120)
        or type(item) ~= "table"
        or type(item.id) ~= "string" or #item.id == 0
        or #item.id > 120 or not (item.id:match("^[%w_%-]+$") or item.id:match("^[%w_%-]+@[1-9]%d?$")) or item.tradable ~= true
        or item.kind == "gold"
        or not integer(item.rarity, 1, 20)
        or rap.itemId ~= item.id
        or history.itemId ~= item.id
        or rap.available ~= true
        or not integer(rap.sales, 0, 1000000000)
        or not integer(rap.quantity, 0, 1000000000)
        or rap.average ~= nil and not finite(rap.average, 2, 1000000000)
        or type(terms) ~= "table"
        or type(terms.release) ~= "string"
        or #terms.release == 0
        or not integer(terms.minPrice, 2, 9999999)
        or not integer(terms.maxPrice, terms.minPrice, 9999999)
        or not integer(terms.minFee, 1, 1000)
        or not finite(terms.feeRate, 0, 0.5)
        or not integer(terms.rentAllowance, 0, 1000)
        or type(settings) ~= "table"
        or not integer(settings.minSales, 3, 1000000)
        or not integer(settings.minUnits, 3, 1000000000)
        or not integer(settings.minMargin, 1, 1000000)
        or not integer(settings.minMarginPct, 0, 100)
        or not integer(settings.undercutGold, 0, 3)
        or not integer(settings.floorPct, 90, 100)
        or type(settings.requireCoverage) ~= "boolean" then
        return nil, "Current Market watch research required"
    end
    if rap.sales < settings.minSales
        or rap.quantity < settings.minUnits then
        return nil, "Market sales below watch threshold"
    end
    local average = rap.average
    if type(average) ~= "number" or not finite(average, 2, 1000000000) then
        return nil, "Exact-item Market price history unavailable"
    end
    local row, cheapest, supply = visible(browse, listingId,
        item.id)
    local typical = median(history)
    if not row or type(typical) ~= "number" then
        return nil, "Complete Market listing and price evidence required"
    end
    local ask = cheapest and cheapest - settings.undercutGold
        or math.floor(math.min(typical, average) * 0.98)
    if not integer(ask, terms.minPrice, terms.maxPrice)
        or ask < math.ceil(average * settings.floorPct / 100)
        or ask > math.floor(average * 1.1) then
        return nil, "Conservative resale ask unavailable"
    end
    if settings.requireCoverage
        and rap.quantity < math.ceil((supply + 1) * 1.5) then
        return nil, "Visible supply exceeds recent Market demand"
    end
    local fee = math.max(terms.minFee,
        math.floor(ask * terms.feeRate))
    local margin = ask - fee - terms.rentAllowance - row.price
    if margin < math.max(settings.minMargin,
        math.ceil(row.price * settings.minMarginPct / 100)) then
        return nil, "Hypothetical Market margin below minimum"
    end
    return { hypothetical = true, listingId = row.id,
        itemId = item.id, kind = item.kind,
        rarity = item.rarity,
        buy = row.price, ask = ask, fee = fee,
        rentAllowance = terms.rentAllowance,
        margin = margin, sales = rap.sales,
        soldUnits = rap.quantity,
        competingUnits = supply,
        capturedAt = browse.capturedAt }, nil
end

return MarketWatchOpportunity
