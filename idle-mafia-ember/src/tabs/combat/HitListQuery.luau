-- Saved FightTab read-only GetHitList contract; never proposes an attack.
local HitListQuery = {}
local Methods = {}
Methods.__index = Methods

local function nonempty(value)
    return type(value) == "string" and #value > 0
end

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value < math.huge and value >= minimum and value % 1 == 0
end

local function finite(value)
    return type(value) == "number" and value == value
        and value > -math.huge and value < math.huge
end

local function dense(rows)
    if type(rows) ~= "table" or #rows > 128 then return false end
    local count = 0
    for key in pairs(rows) do
        if not integer(key, 1) or key > #rows then return false end
        count = count + 1
    end
    return count == #rows
end

function HitListQuery.new(identity)
    assert(type(identity) == "table" and nonempty(identity.account)
        and nonempty(identity.place) and nonempty(identity.release),
        "Missing Combat hit-list identity")
    return setmetatable({ account = identity.account,
        place = identity.place, release = identity.release }, Methods)
end

function Methods:Describe(refresh)
    assert(type(refresh) == "boolean", "Hit-list refresh must be boolean")
    return { remote = "GetHitList", method = "InvokeServer",
        arity = 1, args = { refresh }, kind = "readOnly",
        source = "saved FightTab refreshHitList" }
end

function Methods:DescribeSearch(term)
    if type(term) ~= "string" then return nil, "Invalid target search" end
    local query = term:match("^%s*(.-)%s*$")
    if #query == 0 or #query > 64
        or query:find("[%c]") then
        return nil, "Invalid target search"
    end
    return { remote = "SearchTarget", method = "InvokeServer",
        arity = 1, args = { query }, kind = "readOnly",
        source = "saved FightTab search target call" }, nil
end

function Methods:Stage(snapshot, reply)
    if type(snapshot) ~= "table" or snapshot.account ~= self.account
        or snapshot.place ~= self.place or snapshot.release ~= self.release
        or not finite(snapshot.capturedAt)
        or type(snapshot.native) ~= "table"
        or snapshot.native.fullSync ~= true
        or type(reply) ~= "table" or reply.ok ~= true
        or not dense(reply.list)
        or (reply.cooldown ~= nil and type(reply.cooldown) ~= "boolean")
        or (reply.search ~= nil and type(reply.search) ~= "string") then
        return nil, "Current Combat hit list required"
    end
    local rows, seen = {}, {}
    for index, item in ipairs(reply.list) do
        if type(item) ~= "table" or not integer(item.userId, 1)
            or seen[item.userId] or not nonempty(item.name)
            or not integer(item.level, 1)
            or (item.online ~= nil and type(item.online) ~= "boolean")
            or (item.stamina ~= nil and not integer(item.stamina, 0))
            or (item.shielded ~= nil and not finite(item.shielded)) then
            return nil, "Invalid Combat hit-list row"
        end
        seen[item.userId] = true
        rows[index] = { userId = item.userId, name = item.name,
            level = item.level, online = item.online == true,
            stamina = item.stamina, shielded = item.shielded }
    end
    local result = {}
    for key, value in pairs(snapshot) do result[key] = value end
    result.hitListProof = { account = self.account,
        capturedAt = snapshot.capturedAt, rows = rows,
        cooldown = reply.cooldown == true, search = reply.search }
    return result, nil
end

function Methods:StageSearch(snapshot, reply, term)
    local call, reason = self:DescribeSearch(term)
    if not call then return nil, reason end
    if type(reply) ~= "table" or reply.search ~= call.args[1] then
        return nil, "Target search reply does not match query"
    end
    return self:Stage(snapshot, reply)
end

return HitListQuery
