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
        cityId = cityId, header = bound,
        familyId = type(snapshot) == "table" and type(snapshot.native) == "table"
            and type(snapshot.native.family) == "table" and snapshot.native.family.id or nil }
    self.current = request
    return request, nil
end

function Methods:Accept(request, reply)
    if self.closed or request ~= self.current then
        return nil, "Stale Territory map reply"
    end
    if type(reply) ~= "table" or reply.ok ~= true or reply.pending == true
        or reply.code == "rate_limited" or reply.code == "presence"
        or type(reply.city) ~= "string" or #reply.city == 0 or #reply.city > 120
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
    local length, count, districts, seen = #reply.districts, 0, {}, {}
    for key in pairs(reply.districts) do
        if not integer(key, 1) or key > length then
            return nil, "Sparse Territory map"
        end
        count = count + 1
    end
    if count ~= length then return nil, "Sparse Territory map" end
    for index, row in ipairs(reply.districts) do
        if type(row) ~= "table" or type(row.id) ~= "string"
            or #row.id == 0 or #row.id > 120 or seen[row.id] then
            return nil, "Invalid Territory district"
        end
        seen[row.id] = true
        if row.mine ~= nil and type(row.mine) ~= "boolean" then
            return nil, "Invalid Territory ownership"
        end
        if row.shieldUntil ~= nil and (type(row.shieldUntil) ~= "number"
            or row.shieldUntil ~= row.shieldUntil or row.shieldUntil < 0
            or row.shieldUntil == math.huge) then return nil, "Invalid Territory shield" end
        local mine = row.mine == true
        if row.holderId ~= nil then
            if not (type(row.holderId) == "string" and #row.holderId > 0 and #row.holderId <= 160
                or integer(row.holderId, 1)) then return nil, "Invalid Territory holder identity" end
            if request.familyId ~= nil then
                mine = row.holderId == request.familyId
                if row.mine ~= nil and row.mine ~= mine then return nil, "Conflicting Territory ownership" end
            elseif row.mine == nil then return nil, "Unbound Territory holder identity" end
        end
        districts[index] = { id = row.id, mine = mine, holderId = row.holderId,
            revision = integer(row.revision, 0) and row.revision or nil,
            shieldUntil = row.shieldUntil }
    end
    self.current = nil
    local capacity = reply.territoryCapacity
    if capacity ~= nil and (type(capacity) ~= "table"
        or (type(capacity.familyId) ~= "string"
            and not integer(capacity.familyId, 1))) then
        return nil, "Invalid Territory capacity identity"
    end
    local copiedCapacity
    if capacity then
        copiedCapacity = {familyId = capacity.familyId}
        if capacity.held ~= nil or capacity.maximum ~= nil or capacity.checkedAt ~= nil then
            if not integer(capacity.held, 0) or capacity.held > 1000000
                or not integer(capacity.maximum, 1) or capacity.maximum > 1000000
                or type(capacity.checkedAt) ~= "number" or capacity.checkedAt ~= capacity.checkedAt
                or capacity.checkedAt < 0 or capacity.checkedAt > 9007199254740991 then
                return nil, "Invalid observed Family capacity"
            end
            copiedCapacity.held, copiedCapacity.maximum, copiedCapacity.checkedAt = capacity.held, capacity.maximum, capacity.checkedAt
        end
    end
    return { cityId = reply.city, familyCity = reply.familyCity,
        header = request.header,
        territoryCapacity = copiedCapacity,
        totalDistricts = reply.totalDistricts or #districts,
        districts = districts }, nil
end

function Methods:Close()
    self.closed = true
    self.current = nil
end

return TerritoryMapQuery
