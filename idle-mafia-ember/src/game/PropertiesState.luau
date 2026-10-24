-- Read-only, next-copy Property quotes from complete native state.
local PropertiesState = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge and value % 1 == 0
end

local function quote(base, owned, discount)
    local grown = math.floor(base * 1.18 ^ owned + 0.5)
    if not integer(grown, 1) then return nil end
    if discount == 0 then return grown end
    return math.max(1, math.floor(grown * (1 - discount) + 0.5))
end

function PropertiesState.read(raw, context)
    if type(raw) ~= "table" or type(context) ~= "table" then
        return nil, "Missing Property state or context"
    end
    for _, field in ipairs({ "session", "account", "place", "release",
        "revision", "capturedAt" }) do
        if raw[field] ~= context[field] then
            return nil, "Property snapshot header changed"
        end
    end
    local native, proof, catalog = raw.native, raw.propertyProof,
        raw.propertyCatalog
    if type(native) ~= "table" or native.fullSync ~= true
        or not integer(native.level, 1) or not integer(native.cash, 0)
        or type(native.properties) ~= "table"
        or type(proof) ~= "table" or proof.account ~= context.account
        or proof.capturedAt ~= context.capturedAt
        or not integer(proof.occupied, 0)
        or not integer(proof.capacity, 1)
        or proof.occupied > proof.capacity
        or type(proof.buildDiscount) ~= "number"
        or proof.buildDiscount ~= proof.buildDiscount
        or proof.buildDiscount < 0 or proof.buildDiscount > 0.25
        or type(catalog) ~= "table" or #catalog == 0
        or type(raw.catalogKey) ~= "string" or #raw.catalogKey == 0 then
        return nil, "Complete current Property quote required"
    end
    local options, seen = {}, {}
    for _, row in ipairs(catalog) do
        if type(row) ~= "table" or type(row.id) ~= "string"
            or #row.id == 0 or seen[row.id]
            or not integer(row.level, 1)
            or not integer(row.baseCost, 1)
            or not integer(row.incomePerHour, 0) then
            return nil, "Invalid Property catalog"
        end
        seen[row.id] = true
        local record = native.properties[row.id]
        if record ~= nil and type(record) ~= "table" then
            return nil, "Invalid Property ownership record"
        end
        if record ~= nil and record.owned == nil then
            return nil, "Incomplete Property ownership record"
        end
        local owned = record and record.owned or 0
        if not integer(owned, 0) or owned > 10 then
            return nil, "Invalid Property ownership count"
        end
        local cost = quote(row.baseCost, owned, proof.buildDiscount)
        if not cost then return nil, "Invalid Property price" end
        options[#options + 1] = { id = row.id, level = row.level,
            owned = owned, cost = cost,
            incomePerHour = row.incomePerHour }
    end
    for id in pairs(native.properties) do
        if not seen[id] then return nil, "Unknown owned Property" end
    end
    return { session = context.session, account = context.account,
        place = context.place, release = context.release,
        revision = context.revision, capturedAt = context.capturedAt,
        catalogKey = raw.catalogKey, level = native.level,
        cash = native.cash, occupied = proof.occupied,
        capacity = proof.capacity, options = options }, nil
end

return PropertiesState
