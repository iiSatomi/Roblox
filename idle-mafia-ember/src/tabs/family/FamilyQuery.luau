-- Bounded, read-only saved FamilyAction("info") staging.
local FamilyQuery = {}
local Methods = {}
Methods.__index = Methods

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge and value % 1 == 0
end

function FamilyQuery.new()
    return setmetatable({ current = nil, nextToken = 0,
        closed = false }, Methods)
end

function Methods:Prepare()
    if self.closed then return nil, "Family reader closed" end
    self.nextToken = self.nextToken + 1
    local request = { remote = "FamilyAction",
        method = "InvokeServer", arity = 1,
        args = { "info" }, token = self.nextToken }
    self.current = request
    return request, nil
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
