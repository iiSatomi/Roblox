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
    return true
end

function ReadAttachment.attach(raw, map, residency)
    local native = type(raw) == "table" and raw.native
    if type(native) ~= "table" or native.fullSync ~= true
        or type(map) ~= "table" or not same(map.header, raw)
        or type(map.cityId) ~= "string" or #map.cityId == 0
        or type(map.districts) ~= "table"
        or type(native.family) ~= "table"
        or type(map.territoryCapacity) ~= "table"
        or map.territoryCapacity.familyId ~= native.family.id then
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

return ReadAttachment
