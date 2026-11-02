-- Bounded, read-only saved FamilyAction("info") staging.
local FamilyQuery = {}
local Methods = {}
Methods.__index = Methods

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge and value % 1 == 0
end

function FamilyQuery.new(contributionState)
    assert(contributionState == nil or (type(contributionState) == "table"
        and type(contributionState.Stage) == "function"), "Invalid Family contribution source")
    return setmetatable({ current = nil, nextToken = 0,
        contributionState = contributionState, closed = false }, Methods)
end

function Methods:Prepare(snapshot)
    if self.closed then return nil, "Family reader closed" end
    self.nextToken = self.nextToken + 1
    local request = { remote = "FamilyAction",
        method = "InvokeServer", arity = 1,
        args = { "info" }, token = self.nextToken }
    if snapshot ~= nil then
        if type(snapshot) ~= "table" then return nil, "Invalid Family query snapshot" end
        request.header = {}
        for _, field in ipairs({ "session", "account", "place", "release", "revision", "capturedAt" }) do
            request.header[field] = snapshot[field]
        end
        request.familyId = type(snapshot.native) == "table"
            and type(snapshot.native.family) == "table" and snapshot.native.family.id
    end
    self.current = request
    return request, nil
end

function Methods:Stage(snapshot, request, reply)
    if self.closed or type(request) ~= "table" or request ~= self.current or not self.contributionState
        or type(request.header) ~= "table" or type(snapshot) ~= "table" then
        return nil, "Stale or unbound Family contribution query"
    end
    if type(snapshot.native) ~= "table" or type(snapshot.native.family) ~= "table"
        or snapshot.native.family.id ~= request.familyId then
        return nil, "Family membership changed while querying"
    end
    for _, field in ipairs({ "session", "account", "place", "release", "revision", "capturedAt" }) do
        if snapshot[field] ~= request.header[field] then
            return nil, "Family changed while querying"
        end
    end
    local staged, reason = self.contributionState:Stage(snapshot, reply)
    if staged then self.current = nil end
    return staged, reason
end

function Methods:Accept(request, reply)
    if self.closed or request ~= self.current then
        return nil, "Stale Family info reply"
    end
    if type(reply) ~= "table" or reply.ok ~= true
        or type(reply.family) ~= "table" then
        return nil, "Family info unavailable"
    end
    local family = reply.family
    if not (type(family.id) == "string" and #family.id > 0
        or integer(family.id, 1))
        or type(family.perks) ~= "table"
        or not integer(family.level, 1) then
        return nil, "Invalid Family info"
    end
    local perks, count = {}, 0
    for id, level in pairs(family.perks) do
        if type(id) ~= "string" or #id == 0
            or not integer(level, 0) or level > 25 then
            return nil, "Invalid Family perk"
        end
        perks[id] = level
        count = count + 1
        if count > 64 then return nil, "Family perk list too large" end
    end
    self.current = nil
    return { id = family.id, level = family.level,
        perks = perks }, nil
end

function Methods:Close()
    self.closed = true
    self.current = nil
end

return FamilyQuery
