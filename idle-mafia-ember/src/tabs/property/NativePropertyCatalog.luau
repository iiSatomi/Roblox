-- Reviewed GameData/Config Property constants and current full-Sync proof.
local NativePropertyCatalog = {}
local Methods = {}
Methods.__index = Methods

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge and value % 1 == 0
end

function NativePropertyCatalog.new(gameData, config, fingerprint, release)
    assert(type(gameData) == "table" and type(gameData.PROPERTIES) == "table"
        and type(config) == "table" and type(config.PROPERTY) == "table"
        and config.PROPERTY.costGrowth == 1.18
        and integer(config.PROPERTY.maxOwned, 1)
        and type(fingerprint) == "string" and #fingerprint == 64
        and fingerprint:match("^[%x]+$")
        and type(release) == "string" and #release > 0,
        "Missing reviewed Property source")
    local rows, seen = {}, {}
    for _, source in ipairs(gameData.PROPERTIES) do
        assert(type(source) == "table" and type(source.id) == "string"
            and #source.id > 0 and not seen[source.id]
            and integer(source.level, 1) and integer(source.baseCost, 1)
            and (integer(source.incomePerHour, 0)
                or integer(source.goldPerDay, 1)),
            "Invalid saved Property definition")
        seen[source.id] = true
        rows[#rows + 1] = { id = source.id, level = source.level,
            baseCost = source.baseCost,
            incomePerHour = source.incomePerHour or 0,
            goldPerDay = source.goldPerDay }
    end
    assert(#rows > 0 and #rows <= 128, "Invalid Property catalog size")
    return setmetatable({ rows = rows, defaultCap = config.PROPERTY.maxOwned,
        key = fingerprint:lower(), release = release }, Methods)
end

function Methods:Enrich(snapshot)
    if type(snapshot) ~= "table" or snapshot.release ~= self.release
        or type(snapshot.native) ~= "table"
        or snapshot.native.fullSync ~= true then
        return nil, "Property needs a matching full Sync"
    end
    local native = snapshot.native
    if type(native.properties) ~= "table"
        or not integer(native.cash, 0) or not integer(native.level, 1)
        or (native.propertyCap ~= nil
            and not integer(native.propertyCap, 1)) then
        return nil, "Incomplete Property Sync"
    end
    local cap = native.propertyCap or self.defaultCap
    if cap > 1000 then return nil, "Invalid Property capacity" end
    local occupied, rows, seen = 0, {}, {}
    for index, source in ipairs(self.rows) do
        local record = native.properties[source.id]
        if record ~= nil and (type(record) ~= "table"
            or not integer(record.owned, 0)) then
            return nil, "Invalid Property ownership"
        end
        local owned = record and record.owned or 0
        if owned > 1000 then return nil, "Invalid Property count" end
        occupied = occupied + owned
        rows[index] = { id = source.id, level = source.level,
            baseCost = source.baseCost,
            incomePerHour = source.incomePerHour,
            goldPerDay = source.goldPerDay }
        seen[source.id] = true
    end
    for id in pairs(native.properties) do
        if not seen[id] then return nil, "Unknown owned Property" end
    end
    local derived = native.derived
    if type(derived) ~= "table"
        or type(derived.territoryBonuses) ~= "table" then
        return nil, "Current Property discount proof required"
    end
    local bonus = derived.territoryBonuses
    local discount = type(bonus) == "table"
        and bonus.buildDiscount or 0
    if type(discount) ~= "number" or discount ~= discount
        or discount < 0 or discount > 0.25 then
        return nil, "Invalid Property build discount"
    end
    local result = {}
    for key, value in pairs(snapshot) do result[key] = value end
    result.catalogKey = self.key
    result.propertyCatalog = rows
    result.propertyProof = { account = snapshot.account,
        capturedAt = snapshot.capturedAt,
        occupied = math.min(occupied, cap), capacity = cap,
        buildDiscount = discount }
    return result, nil
end

return NativePropertyCatalog
