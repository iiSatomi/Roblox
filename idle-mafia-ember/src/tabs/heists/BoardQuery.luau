-- Read-only native board call shape and bounded reply staging; no sender.
local BoardQuery = {}
local Methods = {}
Methods.__index = Methods

local function nonempty(value)
    return type(value) == "string" and #value > 0
end

local function finite(value)
    return type(value) == "number" and value == value
        and value >= 0 and value < math.huge
end

local function dense(rows)
    if type(rows) ~= "table" or #rows > 256 then return false end
    local count = 0
    for key in pairs(rows) do
        if type(key) ~= "number" or key % 1 ~= 0
            or key < 1 or key > #rows then return false end
        count = count + 1
    end
    return count == #rows
end

local function copied(value)
    local seen, count = {}, 0
    local function clone(item, depth)
        count = count + 1
        if count > 4096 or depth > 8 then error("Board reply too large") end
        local kind = type(item)
        if kind == "string" or kind == "boolean" or kind == "nil" then
            return item
        end
        if kind == "number" then
            if item ~= item or item == math.huge or item == -math.huge then
                error("Invalid board number")
            end
            return item
        end
        if kind ~= "table" or seen[item] then
            error("Invalid board value")
        end
        seen[item] = true
        local result = {}
        for key, child in pairs(item) do
            if (type(key) ~= "string" and type(key) ~= "number")
                or (type(key) == "number" and (key ~= key
                    or key == math.huge or key == -math.huge)) then
                error("Invalid board key")
            end
            result[key] = clone(child, depth + 1)
        end
        return result
    end
    return clone(value, 1)
end

function BoardQuery.new(identity)
    assert(type(identity) == "table" and nonempty(identity.account)
        and nonempty(identity.place) and nonempty(identity.release),
        "Missing Heist board identity")
    return setmetatable({ account = identity.account,
        place = identity.place, release = identity.release }, Methods)
end

function Methods:Describe()
    return { remote = "HeistAction", method = "InvokeServer",
        arity = 1, args = { "board" }, kind = "readOnly",
        source = "saved HeistsTab board call" }
end

function Methods:Stage(snapshot, reply)
    if type(snapshot) ~= "table"
        or snapshot.account ~= self.account
        or snapshot.place ~= self.place
        or snapshot.release ~= self.release
        or not finite(snapshot.capturedAt)
        or type(snapshot.native) ~= "table"
        or snapshot.native.fullSync ~= true
        or type(reply) ~= "table" or reply.ok ~= true
        or not dense(reply.rows) then
        return nil, "Current personal Heist board reply required"
    end
    local ok, board = pcall(copied, reply)
    if not ok then return nil, "Invalid personal Heist board reply" end
    local result = {}
    for key, value in pairs(snapshot) do result[key] = value end
    result.heistBoardProof = { account = self.account,
        capturedAt = snapshot.capturedAt, board = board }
    return result, nil
end

return BoardQuery
