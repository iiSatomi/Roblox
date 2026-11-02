-- Attach accepted read-only replies only to their originating full Sync.
local ReadAttachment = {}

local function same(header, raw)
    if type(header) ~= "table" or type(raw) ~= "table" then
        return false
    end
    for _, field in ipairs({ "session", "account", "place",
        "release", "revision", "capturedAt" }) do
        if header[field] ~= raw[field] then return false end
    end
    for _, field in ipairs({ "session", "account", "place", "release" }) do
        if type(header[field]) ~= "string" or #header[field] == 0 or #header[field] > 200 then return false end
    end
    if type(header.revision) ~= "number" or header.revision % 1 ~= 0 or header.revision < 0
        or header.revision == math.huge or type(header.capturedAt) ~= "number"
        or header.capturedAt ~= header.capturedAt or header.capturedAt < 0
        or header.capturedAt == math.huge then return false end
    return true
end

function ReadAttachment.attach(raw, map, residency)
    local native = type(raw) == "table" and raw.native
    local capacity = type(map) == "table" and map.territoryCapacity
    local nativeCapacity = type(native) == "table"
        and native.territoryCapacity
    if type(native) ~= "table" or native.fullSync ~= true
        or type(map) ~= "table" or not same(map.header, raw)
        or type(map.cityId) ~= "string" or #map.cityId == 0
        or type(map.districts) ~= "table"
        or type(native.family) ~= "table"
        or (capacity ~= nil and (type(capacity) ~= "table"
            or capacity.familyId ~= native.family.id))
        or (nativeCapacity ~= nil and (type(nativeCapacity) ~= "table"
            or nativeCapacity.familyId ~= native.family.id))
        or (capacity == nil and nativeCapacity == nil) then
        return nil, "Territory read is not from this Sync"
    end
    if residency ~= nil then
        if type(residency) ~= "table"
            or not same(residency.header, raw)
            or type(residency.districtId) ~= "string" then
            return nil, "Residency read is not from this Sync"
        end
        local matched = false
        for _, district in ipairs(map.districts) do
            if type(district) == "table"
                and district.id == residency.districtId then
                matched = true
                break
            end
        end
        if not matched then
            return nil, "Residency district is outside this map"
        end
    end
    local result = {}
    for key, value in pairs(raw) do result[key] = value end
    result.territoryMap = map
    result.residencyView = residency
    return result, nil
end

function ReadAttachment.attachResidency(raw, residency)
    if type(raw) ~= "table" or type(raw.native) ~= "table" or raw.native.fullSync ~= true
        or type(residency) ~= "table" or not same(residency.header, raw)
        or type(residency.districtId) ~= "string" or #residency.districtId == 0 then
        return nil, "Residency view is not from this Sync"
    end
    local result = {}
    for key, value in pairs(raw) do result[key] = value end
    result.residencyView = residency
    return result, nil
end

return ReadAttachment
