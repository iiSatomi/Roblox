-- Saved TerritoryView("district", id, generation, nil); no mutation route.
local DistrictQuery = {}
local Methods = {}
Methods.__index = Methods
local fields = { "session", "account", "place", "release", "revision", "capturedAt" }
local function integer(value, low, high)
    return type(value) == "number" and value == value
        and value >= low and value <= high and value % 1 == 0
end
function DistrictQuery.new()
    return setmetatable({ generation = 0, closed = false }, Methods)
end
function Methods:Prepare(id, snapshot)
    if self.closed or type(id) ~= "string" or #id == 0 or #id > 120
        or type(snapshot) ~= "table" or type(snapshot.native) ~= "table"
        or snapshot.native.fullSync ~= true or type(snapshot.native.family) ~= "table"
        or not integer(snapshot.revision, 0, 9007199254740991)
        or type(snapshot.capturedAt) ~= "number" or snapshot.capturedAt < 0
        or snapshot.capturedAt ~= snapshot.capturedAt or snapshot.capturedAt == math.huge then
        return nil, "Current district query snapshot required"
    end
    local header = {}
    for _, field in ipairs(fields) do header[field] = snapshot[field] end
    for _, field in ipairs({ "session", "account", "place", "release" }) do
        if type(header[field]) ~= "string" or #header[field] == 0 or #header[field] > 200 then
            return nil, "Invalid district query identity"
        end
    end
    self.generation = self.generation + 1
    local request = { remote = "TerritoryView", method = "InvokeServer", arity = 4,
        args = { "district", id, self.generation }, districtId = id,
        header = header, familyId = snapshot.native.family.id, token = self.generation }
    self.current = request
    return request, nil
end
function Methods:Accept(request, reply)
    local district = type(reply) == "table" and reply.district
    if self.closed or type(request) ~= "table" or request ~= self.current or type(reply) ~= "table"
        or reply.ok ~= true or reply.pending == true or type(district) ~= "table"
        or district.id ~= request.districtId
        or (district.mine ~= nil and type(district.mine) ~= "boolean")
        or (district.holderId ~= nil and not (type(district.holderId) == "string" and #district.holderId > 0
            or integer(district.holderId, 1, 9007199254740991)))
        or not integer(district.garrisonCount, 0, 1000000)
        or (district.garrisonCap ~= nil and not integer(district.garrisonCap, 1, 1000000))
        or (district.settling ~= nil and type(district.settling) ~= "boolean")
        or (district.shieldUntil ~= nil and (type(district.shieldUntil) ~= "number"
            or district.shieldUntil ~= district.shieldUntil or district.shieldUntil < 0
            or district.shieldUntil > 9007199254740991))
        or not integer(district.revision, 0, 9007199254740991) then
        return nil, "Current district ownership and garrison required"
    end
    local mine = district.mine == true
    if district.holderId ~= nil then
        mine = district.holderId == request.familyId
        if district.mine ~= nil and district.mine ~= mine then return nil, "Conflicting district holder" end
    end
    local copied = { id = district.id, mine = mine, holderId = district.holderId,
        garrisonCount = district.garrisonCount, garrisonCap = district.garrisonCap,
        revision = district.revision, settling = district.settling, shieldUntil = district.shieldUntil }
    self.current = nil
    return { header = request.header, familyId = request.familyId, district = copied }, nil
end
function Methods:Close()
    self.closed, self.current = true, nil
end
return DistrictQuery
