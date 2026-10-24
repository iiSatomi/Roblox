-- Saved TerritoryView("map", city) read, staged without mutations.
local TerritoryMapQuery = {}
local Methods = {}
Methods.__index = Methods

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge and value % 1 == 0
end

function TerritoryMapQuery.new()
    return setmetatable({ current = nil, token = 0,
        closed = false }, Methods)
end

local function header(snapshot)
    local native = type(snapshot) == "table" and snapshot.native
    if type(native) ~= "table" or native.fullSync ~= true
        or not integer(snapshot.revision, 0)
        or type(snapshot.capturedAt) ~= "number"
        or snapshot.capturedAt ~= snapshot.capturedAt
        or snapshot.capturedAt < 0
        or snapshot.capturedAt == math.huge then return nil end
    local result = { revision = snapshot.revision,
        capturedAt = snapshot.capturedAt }
    for _, field in ipairs({ "session", "account", "place",
        "release" }) do
        if type(snapshot[field]) ~= "string"
            or #snapshot[field] == 0 then return nil end
        result[field] = snapshot[field]
    end
    return result
end

function Methods:Prepare(cityId, snapshot)
    if self.closed then return nil, "Territory map reader closed" end
    if cityId ~= nil and (type(cityId) ~= "string"
        or #cityId == 0 or #cityId > 120) then
        return nil, "Invalid Territory city"
    end
    self.token = self.token + 1
    local bound = header(snapshot)
    local request = { remote = "TerritoryView",
        method = "InvokeServer", arity = 2,
        args = { "map", cityId }, token = self.token,
        cityId = cityId, header = bound }
    self.current = request
    return request, nil
end

function Methods:Accept(request, reply)
    if self.closed or request ~= self.current then
        return nil, "Stale Territory map reply"
    end
    if type(reply) ~= "table" or reply.ok ~= true
        or type(reply.districts) ~= "table"
        or #reply.districts > 200 then
        return nil, "Territory map unavailable"
    end
    if request.cityId ~= nil and reply.city ~= request.cityId then
        return nil, "Territory city changed"
    end
    if reply.totalDistricts ~= nil
        and (not integer(reply.totalDistricts, 0)
            or reply.totalDistricts < #reply.districts
            or reply.totalDistricts > 200) then
        return nil, "Invalid Territory district total"
    end
    local length, count, districts = #reply.districts, 0, {}
    for key in pairs(reply.districts) do
        if not integer(key, 1) or key > length then
            return nil, "Sparse Territory map"
        end
        count = count + 1
    end
    if count ~= length then return nil, "Sparse Territory map" end
    for index, row in ipairs(reply.districts) do
        if type(row) ~= "table" or type(row.id) ~= "string"
            or #row.id == 0 then
            return nil, "Invalid Territory district"
        end
        if row.mine ~= nil and type(row.mine) ~= "boolean" then
            return nil, "Invalid Territory ownership"
        end
        districts[index] = { id = row.id, mine = row.mine == true,
            revision = integer(row.revision, 0) and row.revision or nil }
    end
    self.current = nil
    local capacity = reply.territoryCapacity
    if capacity ~= nil and (type(capacity) ~= "table"
        or (type(capacity.familyId) ~= "string"
            and not integer(capacity.familyId, 1))) then
        return nil, "Invalid Territory capacity identity"
    end
    return { cityId = request.cityId, familyCity = reply.familyCity,
        header = request.header,
        territoryCapacity = capacity and { familyId = capacity.familyId } or nil,
        totalDistricts = reply.totalDistricts or #districts,
        districts = districts }, nil
end

function Methods:Close()
    self.closed = true
    self.current = nil
end

return TerritoryMapQuery
