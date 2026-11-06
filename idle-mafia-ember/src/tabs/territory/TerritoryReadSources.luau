-- Tab-owned read specifications for the shared request coordinator.
local TerritoryReadSources = {}
local fields = {"session", "account", "place", "release", "revision", "capturedAt"}
local function text(value) return type(value) == "string" and #value > 0 and #value <= 120 end
local function options(settings, feature)
    local row = settings[feature]
    return type(row) == "table" and row.enabled == true and (row.custom or row) or nil
end
local function mapped(raw, id)
    if type(raw) ~= "table" then return false end
    local map = raw.territoryMap
    if type(map) ~= "table" or type(map.header) ~= "table" or type(map.districts) ~= "table" then return false end
    for _, field in ipairs(fields) do if map.header[field] ~= raw[field] then return false end end
    for _, row in ipairs(map.districts) do if row.id == id then return true end end
    return false
end
function TerritoryReadSources.new(deps)
    assert(type(deps.fingerprint) == "string" and #deps.fingerprint == 64
        and deps.fingerprint:match("^[%x]+$") and type(deps.release) == "string", "Missing Territory source identity")
    local key, release = deps.fingerprint:lower(), deps.release
    local queries = {territoryMap = deps.TerritoryMapQuery.new(), residencyView = deps.ResidencyQuery.new()}
    if type(deps.DistrictQuery) == "table" then queries.territoryDistrict = deps.DistrictQuery.new() end
    if type(deps.FortificationQuery) == "table" then queries.fortificationView = deps.FortificationQuery.new() end
    local state = {closed = false, settings = {}, selected = {}}
    local owner = {}
    function owner:Sources(reader)
        if type(reader) ~= "table" or type(reader.AttachTerritoryRead) ~= "function"
            or type(reader.ClearTerritoryRead) ~= "function" then return {} end
        local function target(field)
            local watch, station, residency = options(state.settings, "territoryWatch"),
                options(state.settings, "station"), options(state.settings, "residency")
            if field == "territoryMap" then
                if not watch and not station then return nil end
                local city = watch and watch.cityId
                if text(city) then return city end
                if station and text(station.districtId) then
                    local district = type(deps.gameData) == "table" and deps.gameData.DISTRICTS_BY_ID
                    district = type(district) == "table" and district[station.districtId]
                    if type(district) == "table" and text(district.city) then
                        local maps = deps.cityMaps
                        if type(maps) ~= "table" then return district.city end
                        local row = type(maps.BY_ID) == "table" and maps.BY_ID[district.city]
                            or type(maps.BY_NAME) == "table" and maps.BY_NAME[district.city]
                        return type(row) == "table" and text(row.id) and row.id or nil
                    end
                end
                return "" -- Native map default is an explicit nil second argument.
            elseif field == "territoryDistrict" then
                return station and text(station.districtId) and station.districtId
                    or watch and text(watch.districtId) and watch.districtId or nil
            elseif field == "residencyView" then
                return residency and text(residency.districtId) and residency.districtId or nil
            end
            return watch and watch.showFortifications == true and text(watch.districtId) and watch.districtId or nil
        end
        local sources = {}
        for _, fieldName in ipairs({"territoryMap", "territoryDistrict", "residencyView", "fortificationView"}) do
            local field, query = fieldName, queries[fieldName]
            if query then
                sources[#sources + 1] = {id = field, interval = (field == "territoryMap" or field == "fortificationView") and 15 or 5,
                    enabled = function(settings, _, raw)
                        state.settings = settings
                        local selected = not state.closed and target(field) or nil
                        if state.selected[field] ~= selected then reader:ClearTerritoryRead(field) end
                        state.selected[field] = selected
                        -- A missing prerequisite is not a failed native read.
                        -- In particular, every new Sync invalidates the old map;
                        -- charging district/fort preparation here creates backoff
                        -- before their next matching map can be attached.
                        if selected ~= nil and (field == "territoryDistrict" or field == "fortificationView")
                            and not mapped(raw, selected) then return false end
                        return selected ~= nil
                    end,
                    prepare = function(raw)
                        local selected = target(field)
                        if state.closed or raw.release ~= release or selected == nil then return nil, "Territory read disabled" end
                        if (field == "territoryDistrict" or field == "fortificationView") and not mapped(raw, selected) then
                            return nil, "Selected district needs the matching city map"
                        end
                        return query:Prepare(selected ~= "" and selected or nil, raw)
                    end,
                    accept = function(raw, request, reply)
                        local selected = target(field)
                        if state.closed or selected == nil or raw.release ~= release
                            or (field == "territoryMap" and request.cityId ~= (selected ~= "" and selected or nil))
                            or (field ~= "territoryMap" and request.districtId ~= selected) then return nil end
                        local accepted = query:Accept(request, reply)
                        if not accepted then return nil end
                        if field == "territoryMap" then
                            if not deps.ReadAttachment.attach(raw, accepted) then return nil end
                        elseif field == "residencyView" then
                            if not deps.ReadAttachment.attachResidency(raw, accepted) then return nil end
                        elseif not mapped(raw, selected) or accepted.familyId ~= raw.native.family.id then return nil end
                        local staged = {territoryRead = {sourceKey = key, field = field, value = accepted}, native = raw.native}
                        for _, name in ipairs(fields) do staged[name] = raw[name] end
                        return staged
                    end,
                    commit = function(staged)
                        return not state.closed and reader:AttachTerritoryRead(staged)
                    end,
                }
            end
        end
        return sources
    end
    function owner:Close()
        state.closed = true
        for _, query in pairs(queries) do query:Close() end
    end
    return owner
end
return TerritoryReadSources
