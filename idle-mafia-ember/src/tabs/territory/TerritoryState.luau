-- Read-only city holdings from a map accepted for the same native snapshot.
local TerritoryState = {}

local function identity(value)
    return type(value) == "string" and #value > 0
        or type(value) == "number" and value > 0
            and value < math.huge and value % 1 == 0
end

function TerritoryState.read(raw, context)
    if type(raw) ~= "table" or type(context) ~= "table" then
        return nil, "Missing Territory snapshot"
    end
    for _, field in ipairs({ "session", "account", "place", "release",
        "revision", "capturedAt" }) do
        if raw[field] ~= context[field] then
            return nil, "Territory snapshot changed"
        end
    end
    local native, map = raw.native, raw.territoryMap
    if type(native) ~= "table" or native.fullSync ~= true
        or type(native.family) ~= "table"
        or not identity(native.family.id)
        or type(map) ~= "table"
        or type(map.header) ~= "table"
        or type(map.districts) ~= "table"
        or type(map.totalDistricts) ~= "number"
        or map.totalDistricts < #map.districts
        or map.totalDistricts > 200
        or map.totalDistricts % 1 ~= 0 then
        return nil, "Current Family and Territory map required"
    end
    for _, field in ipairs({ "session", "account", "place",
        "release", "revision", "capturedAt" }) do
        if map.header[field] ~= context[field] then
            return nil, "Territory map belongs to another Sync"
        end
    end
    local capacity = native.territoryCapacity
        or (type(map) == "table" and map.territoryCapacity)
    if type(capacity) ~= "table"
        or capacity.familyId ~= native.family.id then
        return nil, "Territory Family identity unconfirmed"
    end
    local held, districts, seen = 0, {}, {}
    for index, district in ipairs(map.districts) do
        if type(district) ~= "table" or not identity(district.id)
            or seen[district.id] or type(district.mine) ~= "boolean" then
            return nil, "Invalid Territory holdings"
        end
        seen[district.id] = true
        if district.mine then held = held + 1 end
        districts[index] = { id = district.id, mine = district.mine }
    end
    if #districts ~= #map.districts then
        return nil, "Sparse Territory holdings"
    end
    return { session = context.session, account = context.account,
        place = context.place, release = context.release,
        revision = context.revision, capturedAt = context.capturedAt,
        familyId = native.family.id, cityId = map.cityId,
        familyCity = map.familyCity, held = held,
        totalDistricts = map.totalDistricts,
        districts = districts }, nil
end

return TerritoryState
