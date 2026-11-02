-- Read-only city holdings from a map accepted for the same native snapshot.
local TerritoryState = {}

local function identity(value)
    return type(value) == "string" and #value > 0
        or type(value) == "number" and value > 0
            and value < math.huge and value % 1 == 0
end
local function count(value, minimum)
    return type(value) == "number" and value >= minimum and value <= 1000000 and value % 1 == 0
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
    local capacity, observed = nil, false
    for _, candidate in pairs({native = native.territoryCapacity, map = map.territoryCapacity}) do
        observed = true
        if type(candidate) ~= "table" or candidate.familyId ~= native.family.id then
            return nil, "Territory Family identity unconfirmed"
        end
        if candidate.held ~= nil or candidate.maximum ~= nil or candidate.checkedAt ~= nil then
            if not count(candidate.held, 0) or not count(candidate.maximum, 1)
                or type(candidate.checkedAt) ~= "number" or candidate.checkedAt ~= candidate.checkedAt
                or candidate.checkedAt < 0 or candidate.checkedAt > 9007199254740991
                or type(native.serverNow) ~= "number" or native.serverNow ~= native.serverNow
                or candidate.checkedAt > native.serverNow + 2 then return nil, "Observed Family capacity unavailable" end
            if not capacity or candidate.checkedAt > capacity.checkedAt then
                capacity = {held = candidate.held, maximum = candidate.maximum, checkedAt = candidate.checkedAt,
                    available = math.max(0, candidate.maximum - candidate.held)}
            elseif candidate.checkedAt == capacity.checkedAt
                and (candidate.held ~= capacity.held or candidate.maximum ~= capacity.maximum) then
                return nil, "Conflicting observed Family capacity"
            end
        end
    end
    if not observed then return nil, "Territory Family identity unconfirmed" end
    local held, districts, seen = 0, {}, {}
    for index, district in ipairs(map.districts) do
        if type(district) ~= "table" or not identity(district.id)
            or seen[district.id] or type(district.mine) ~= "boolean" then
            return nil, "Invalid Territory holdings"
        end
        seen[district.id] = true
        if district.mine then held = held + 1 end
        local shieldRemaining
        if district.shieldUntil ~= nil then
            if type(district.shieldUntil) ~= "number" or district.shieldUntil ~= district.shieldUntil
                or district.shieldUntil < 0 or district.shieldUntil == math.huge then
                return nil, "Invalid current Territory shield"
            end
            if type(native.serverNow) == "number" and native.serverNow == native.serverNow
                and native.serverNow >= 0 and native.serverNow < math.huge then
                shieldRemaining = math.max(0, district.shieldUntil - native.serverNow)
            end
        end
        districts[index] = { id = district.id, mine = district.mine,
            shieldUntil = district.shieldUntil, shieldRemaining = shieldRemaining }
    end
    if #districts ~= #map.districts then
        return nil, "Sparse Territory holdings"
    end
    local detail
    if raw.territoryDistrict ~= nil then
        local accepted = raw.territoryDistrict
        local district = type(accepted) == "table" and accepted.district
        if type(accepted) ~= "table" or type(accepted.header) ~= "table"
            or accepted.familyId ~= native.family.id or type(district) ~= "table"
            or not seen[district.id] or type(district.mine) ~= "boolean"
            or not count(district.garrisonCount, 0)
            or (district.garrisonCap ~= nil and not count(district.garrisonCap, 1)) then
            return nil, "Selected district detail is not from this Family and map"
        end
        for _, field in ipairs({"session", "account", "place", "release", "revision", "capturedAt"}) do
            if accepted.header[field] ~= context[field] then return nil, "Selected district detail belongs to another Sync" end
        end
        detail = {id = district.id, garrisonCount = district.garrisonCount, garrisonCap = district.garrisonCap}
    end
    return { session = context.session, account = context.account,
        place = context.place, release = context.release,
        revision = context.revision, capturedAt = context.capturedAt,
        familyId = native.family.id, cityId = map.cityId,
        familyCity = map.familyCity, held = held,
        totalDistricts = map.totalDistricts, familyCapacity = capacity,
        districts = districts, districtDetail = detail }, nil
end

return TerritoryState
