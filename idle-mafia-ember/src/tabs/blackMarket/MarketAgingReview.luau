-- Review only: identify old owned listings with current demand evidence.
local MarketAgingReview = {}

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

local function fresh(row, id, now)
    return type(row) == "table" and row.itemId == id
        and row.available == true
        and finite(row.capturedAt, 0, now + 1)
        and now - row.capturedAt <= 120
        and integer(row.sales, 0, 1000000000)
        and integer(row.quantity, 0, 1000000000)
        and finite(row.average, 2, 1000000000)
end

function MarketAgingReview.assess(listings, rapByItem,
    settings, now)
    if type(listings) ~= "table"
        or not text(listings.session, 200)
        or not text(listings.account, 200)
        or not text(listings.place, 200)
        or not text(listings.release, 200)
        or not integer(listings.revision, 0, 9007199254740991)
        or not finite(listings.capturedAt, 0, math.huge)
        or not finite(listings.serverNow, 0, 9007199254740991)
        or not integer(listings.listingCount, 0, 100)
        or type(listings.listings) ~= "table"
        or type(rapByItem) ~= "table"
        or not finite(now, 0, math.huge)
        or now - listings.capturedAt > 120
        or listings.capturedAt > now + 1
        or type(settings) ~= "table"
        or not integer(settings.minAgeHours, 1, 720)
        or not integer(settings.minSales, 1, 1000000)
        or not integer(settings.minSoldUnits, 1, 1000000000)
        or not integer(settings.demandMultiplier, 1, 5)
        or not integer(settings.maxReviews, 1, 20) then
        return nil, "Current owned Market listings required"
    end
    local candidates, count = {}, 0
    for listingId, row in pairs(listings.listings) do
        count = count + 1
        if count > 100 or not text(listingId, 160)
            or type(row) ~= "table"
            or not text(row.state, 40)
            or not text(row.item, 120)
            or not integer(row.price, 1, 9999999)
            or not integer(row.qty, 1, 1000000000)
            or not integer(row.left, 0, row.qty)
            or not integer(row.createdAt, 0,
                9007199254740991)
            or row.createdAt > listings.serverNow then
            return nil, "Invalid owned Market listing"
        end
        local age = listings.serverNow - row.createdAt
        local rap = rapByItem[row.item]
        if row.state == "live" and row.left > 0
            and age >= settings.minAgeHours * 3600
            and fresh(rap, row.item, now)
            and rap.sales >= settings.minSales
            and rap.quantity >= math.max(settings.minSoldUnits,
                row.left * settings.demandMultiplier)
            and row.price <= math.floor(rap.average * 1.1) then
            candidates[#candidates + 1] = {
                reviewOnly = true, listingId = listingId,
                itemId = row.item, remaining = row.left,
                ask = row.price, ageHours = math.floor(age / 3600),
                sales = rap.sales, soldUnits = rap.quantity,
                capturedAt = listings.capturedAt }
        end
    end
    if count ~= listings.listingCount then
        return nil, "Owned Market listing count changed"
    end
    table.sort(candidates, function(a, b)
        if a.ageHours ~= b.ageHours then
            return a.ageHours > b.ageHours
        end
        return a.listingId < b.listingId
    end)
    local result = {}
    for index = 1, math.min(#candidates,
        settings.maxReviews) do
        result[index] = candidates[index]
    end
    return result, nil
end

return MarketAgingReview
