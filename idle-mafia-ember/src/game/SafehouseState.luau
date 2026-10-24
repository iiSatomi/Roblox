-- Current next-tier Safehouse quote from complete native state/catalog.
local SafehouseState = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value < math.huge and value >= minimum and value % 1 == 0
end

local function catalog(value)
    if type(value) ~= "table" or #value ~= 18 then return false end
    local lastCost, lastLevel = -1, 0
    for key in pairs(value) do
        if not integer(key, 1) or key > 18 then return false end
    end
    for index = 1, 18 do
        local row = value[index]
        if type(row) ~= "table" or type(row.name) ~= "string"
            or #row.name == 0 or not integer(row.cost, 0)
            or not integer(row.level, 1)
            or row.cost <= lastCost or row.level <= lastLevel
            or (index == 1 and (row.cost ~= 0 or row.level ~= 1)) then
            return false
        end
        lastCost, lastLevel = row.cost, row.level
    end
    return true
end

function SafehouseState.read(raw, context)
    if type(raw) ~= "table" or type(context) ~= "table" then
        return nil, "Missing Safehouse state or context"
    end
    for _, field in ipairs({ "session", "account", "place", "release",
        "revision", "capturedAt" }) do
        if raw[field] ~= context[field] then
            return nil, "Safehouse snapshot header changed"
        end
    end
    local native = raw.native
    if type(native) ~= "table" or native.fullSync ~= true
        or not integer(native.safehouse, 1) or native.safehouse > 18
        or not integer(native.level, 1)
        or not integer(native.maxLevel, 1)
        or not integer(native.cash, 0)
        or not catalog(raw.safehouseCatalog)
        or type(raw.catalogKey) ~= "string" or #raw.catalogKey == 0 then
        return nil, "Complete Safehouse tier and catalog required"
    end
    local current = native.safehouse
    local nextTier = current + 1
    local quote = raw.safehouseCatalog[nextTier]
    return { session = context.session, account = context.account,
        place = context.place, release = context.release,
        revision = context.revision, capturedAt = context.capturedAt,
        catalogKey = raw.catalogKey, tier = current,
        nextTier = quote and nextTier or nil,
        nextCost = quote and quote.cost or nil,
        nextLevel = quote and quote.level or nil,
        highestLevel = math.max(native.level, native.maxLevel),
        cash = native.cash }, nil
end

return SafehouseState
