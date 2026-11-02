-- Read account-owned Market listings only from a matching complete Sync.
local MarketListingsState = {}

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

local function header(raw, context)
    if type(raw) ~= "table" or type(context) ~= "table" then
        return false
    end
    for _, field in ipairs({ "session", "account", "place", "release" }) do
        if not text(raw[field], 200) or raw[field] ~= context[field] then
            return false
        end
    end
    return integer(raw.revision, 0, 9007199254740991)
        and raw.revision == context.revision
        and type(raw.capturedAt) == "number"
        and raw.capturedAt == raw.capturedAt
        and raw.capturedAt >= 0 and raw.capturedAt < math.huge
        and raw.capturedAt == context.capturedAt
end

function MarketListingsState.read(raw, context)
    if not header(raw, context) then
        return nil, "Market listing snapshot header changed"
    end
    local native = raw.native
    local market = type(native) == "table" and native.market
    local listings = type(market) == "table" and market.listings
    if type(native) ~= "table" or native.fullSync ~= true
        or type(market) ~= "table" or type(listings) ~= "table"
        or not finite(native.serverNow, 0, 9007199254740991)
        or not integer(market.shopUntil, 0, 9007199254740991) then
        return nil, "Complete Market listing Sync required"
    end
    local copy, count = {}, 0
    for id, row in pairs(listings) do
        count = count + 1
        local origin = type(row) == "table" and row.itemOrigin
        if count > 100 or not text(id, 160)
            or type(row) ~= "table"
            or not text(row.state, 40)
            or not text(row.item, 120)
            or not integer(row.indexed, 0, 1000000000)
            or not integer(row.price, 1, 1000000000)
            or not integer(row.qty, 1, 1000000000)
            or not integer(row.left, 0, row.qty)
            or not integer(row.createdAt, 0, 9007199254740991)
            or type(origin) ~= "table"
            or not integer(origin.total, 0, 1000000000)
            or not integer(origin.free, 0, origin.total) then
            return nil, "Invalid Market listing or custody"
        end
        copy[id] = { state = row.state, item = row.item,
            indexed = row.indexed, price = row.price,
            qty = row.qty, left = row.left,
            createdAt = row.createdAt,
            itemOrigin = { total = origin.total, free = origin.free } }
    end
    return { session = raw.session, account = raw.account,
        place = raw.place, release = raw.release,
        revision = raw.revision, capturedAt = raw.capturedAt,
        serverNow = native.serverNow, shopUntil = market.shopUntil,
        listingCount = count, listings = copy }, nil
end

return MarketListingsState
