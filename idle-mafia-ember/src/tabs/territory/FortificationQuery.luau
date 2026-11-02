-- Saved FortifyPanel fortview only. No donation, repair, vault or sabotage route.
local FortificationQuery = {}
local Methods = {}
Methods.__index = Methods
local MAX = 9007199254740991
local fields = { "session", "account", "place", "release", "revision", "capturedAt" }
local keys = { barricade = true, guardposts = true, clinic = true, apartment = true }
local function number(value, low, high)
    return type(value) == "number" and value == value and value >= low and value <= high
end
local function integer(value, low, high)
    return number(value, low, high) and value % 1 == 0
end
local function text(value, length)
    return type(value) == "string" and #value > 0 and #value <= length
end
local function family(value)
    return text(value, 160) or integer(value, 1, MAX)
end
local function header(raw)
    if type(raw) ~= "table" or type(raw.native) ~= "table" or raw.native.fullSync ~= true
        or not integer(raw.revision, 0, MAX) or not number(raw.capturedAt, 0, MAX)
        or not number(raw.native.serverNow, 0, MAX) or type(raw.native.family) ~= "table"
        or not family(raw.native.family.id) then return nil end
    local result = {}
    for _, field in ipairs(fields) do result[field] = raw[field] end
    for _, field in ipairs({ "session", "account", "place", "release" }) do
        if not text(result[field], 200) then return nil end
    end
    return result
end
local function same(a, b)
    if type(a) ~= "table" or type(b) ~= "table" then return false end
    for _, field in ipairs(fields) do if a[field] ~= b[field] then return false end end
    return true
end
local function copyHeader(bound)
    local result = {}
    for _, field in ipairs(fields) do result[field] = bound[field] end
    return result
end
local function structures(rows)
    -- FortifyRules.view emits exactly its four KEYS, including level-zero rows.
    if type(rows) ~= "table" or #rows ~= 4 then return nil end
    local result, count, seen = {}, 0, {}
    for index, row in pairs(rows) do
        count = count + 1
        if count > 4 or not integer(index, 1, 4) or type(row) ~= "table"
            or not keys[row.key] or seen[row.key] or not integer(row.lv, 0, 5)
            or (row.hp ~= nil and not integer(row.hp, 0, 1000000000000))
            or (row.hpMax ~= nil and not integer(row.hpMax, 0, 1000000000000))
            or (row.hp ~= nil and row.hpMax ~= nil and row.hp > row.hpMax)
            or (row.rebuilding ~= nil and type(row.rebuilding) ~= "boolean") then return nil end
        seen[row.key] = true
        result[index] = { key = row.key, lv = row.lv, hp = row.hp,
            hpMax = row.hpMax, rebuilding = row.rebuilding }
    end
    return count == 4 and result or nil
end

function FortificationQuery.new()
    return setmetatable({ generation = 0, closed = false }, Methods)
end
function Methods:Prepare(id, snapshot)
    local bound = header(snapshot)
    if self.closed or not text(id, 120) or not bound or self.generation >= MAX then
        return nil, "Current full Family fortification snapshot required"
    end
    self.generation = self.generation + 1
    local request = { remote = "TerritoryAction", method = "InvokeServer", arity = 2,
        args = { "fortview", id }, districtId = id, token = self.generation,
        header = copyHeader(bound), familyId = snapshot.native.family.id }
    self.current = { request = request, header = bound, districtId = id,
        familyId = snapshot.native.family.id, serverNow = snapshot.native.serverNow,
        token = self.generation, snapshot = snapshot }
    return request, nil
end
function Methods:Accept(request, reply)
    local bound = self.current
    local fort = type(reply) == "table" and reply.fort
    if self.closed or not bound or request ~= bound.request
        or request.token ~= bound.token or request.districtId ~= bound.districtId
        or request.familyId ~= bound.familyId or not same(request.header, bound.header)
        or request.remote ~= "TerritoryAction" or request.method ~= "InvokeServer" or request.arity ~= 2
        or type(request.args) ~= "table" or request.args[1] ~= "fortview"
        or request.args[2] ~= bound.districtId or request.args[3] ~= nil
        or not same(header(bound.snapshot), bound.header)
        or bound.snapshot.native.family.id ~= bound.familyId
        or bound.snapshot.native.serverNow ~= bound.serverNow then
        return nil, "Stale fortification query identity"
    end
    if type(reply) ~= "table" or reply.ok ~= true or reply.pending == true
        or reply.code == "rate_limited" or type(fort) ~= "table"
        or (fort.districtId ~= nil and fort.districtId ~= bound.districtId)
        or (reply.districtId ~= nil and reply.districtId ~= bound.districtId)
        or (reply.familyId ~= nil and reply.familyId ~= bound.familyId) then
        return nil, "Fortification display unavailable"
    end
    local rows = structures(fort.structures)
    if not rows then return nil, "Complete bounded fortification structures required" end
    self.current = nil
    return { readOnly = true, header = copyHeader(bound.header), familyId = bound.familyId,
        districtId = bound.districtId, serverNow = bound.serverNow,
        count = 4, fort = { structures = rows } }, nil
end
function Methods:Close()
    self.closed, self.current = true, nil
end

-- The future shared reader may attach the accepted view only to its origin Sync.
function FortificationQuery.read(raw, context)
    local current = header(raw)
    local view = type(raw) == "table" and raw.fortificationView
    if not current or not same(current, context) or type(view) ~= "table"
        or view.readOnly ~= true or not same(view.header, current)
        or view.familyId ~= raw.native.family.id or not text(view.districtId, 120)
        or view.serverNow ~= raw.native.serverNow or view.count ~= 4
        or type(view.fort) ~= "table" then return nil, "Fortification view is not from this Sync" end
    local rows = structures(view.fort.structures)
    if not rows then return nil, "Invalid fortification display" end
    return { readOnly = true, header = copyHeader(current), familyId = view.familyId,
        districtId = view.districtId, serverNow = view.serverNow,
        count = 4, fort = { structures = rows } }, nil
end

return FortificationQuery
