-- Saved ResidencyAction("view", districtId, page) read; never requests a move.
local ResidencyQuery = {}
local Methods = {}
Methods.__index = Methods

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge and value % 1 == 0
end

local function bounded(value, maximum)
    return type(value) == "number" and value == value
        and value >= 0 and value <= maximum
end

function ResidencyQuery.new()
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

function Methods:Prepare(districtId, snapshot)
    if self.closed then return nil, "Residency reader closed" end
    if type(districtId) ~= "string" or #districtId == 0
        or #districtId > 120 then
        return nil, "Invalid Residency district"
    end
    self.token = self.token + 1
    local bound = header(snapshot)
    local request = { remote = "ResidencyAction",
        method = "InvokeServer", arity = 3,
        args = { "view", districtId, 1 },
        districtId = districtId, token = self.token,
        header = bound }
    self.current = request
    return request, nil
end

function Methods:Accept(request, reply)
    if self.closed or request ~= self.current then
        return nil, "Stale Residency reply"
    end
    if type(reply) ~= "table" or reply.ok ~= true
        or reply.districtId ~= request.districtId
        or (reply.status ~= nil and reply.status ~= "resident"
            and reply.status ~= "pending")
        or type(reply.admission) ~= "string"
        or not ({ open = true, closed = true,
            request = true })[reply.admission]
        or type(reply.kind) ~= "string" or #reply.kind == 0
        or not bounded(reply.rent or 0, 10)
        or (reply.share ~= nil and not bounded(reply.share, 1))
        or (reply.myRent ~= nil and not bounded(reply.myRent, 10))
        or (reply.count ~= nil and not integer(reply.count, 0))
        or (reply.capacity ~= nil and not integer(reply.capacity, 1))
        or (reply.minLevel ~= nil
            and not integer(reply.minLevel, 0)) then
        return nil, "Residency view unavailable"
    end
    self.current = nil
    return { districtId = reply.districtId,
        header = request.header,
        status = reply.status or "none", admission = reply.admission,
        kind = reply.kind, rent = reply.rent or 0,
        myRent = reply.myRent, share = reply.share,
        count = reply.count, capacity = reply.capacity,
        minLevel = reply.minLevel, elsewhere = reply.elsewhere }, nil
end

function Methods:Close()
    self.closed = true
    self.current = nil
end

return ResidencyQuery
