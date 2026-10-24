-- Read-only copy boundary for the saved client's Sync and State changes.
-- The integrator must call ObserveSync only for the actual Sync event.
local NativeSnapshotReader = {}
local Methods = {}
Methods.__index = Methods

local identityKeys = { "session", "account", "place", "release" }

local function copy(value, seen, budget, depth)
    local kind = type(value)
    if kind == "table" then
        if seen[value] or depth > 32 then error("Invalid native state graph") end
        seen[value] = true
        local result = {}
        for key, item in pairs(value) do
            budget.count = budget.count + 1
            if budget.count > 100000
                or (type(key) ~= "string" and type(key) ~= "number") then
                error("Invalid native state size or key")
            end
            result[key] = copy(item, seen, budget, depth + 1)
        end
        seen[value] = nil
        return result
    end
    if kind == "string" or kind == "boolean" or kind == "nil" then
        return value
    end
    if kind == "number" and value == value
        and value > -math.huge and value < math.huge then
        return value
    end
    error("Unsupported native state value")
end

local function copied(raw)
    if type(raw) ~= "table" then return nil end
    local ok, result = pcall(copy, raw, {}, { count = 0 }, 0)
    if ok then return result end
    return nil
end

local function equal(a, b)
    if type(a) ~= type(b) then return false end
    if type(a) ~= "table" then return a == b end
    for key, value in pairs(a) do
        if not equal(value, b[key]) then return false end
    end
    for key in pairs(b) do
        if a[key] == nil then return false end
    end
    return true
end

function NativeSnapshotReader.new(identity, clock)
    assert(type(identity) == "table" and type(clock) == "table"
        and type(clock.Now) == "function", "Missing native reader inputs")
    local bound = {}
    for _, key in ipairs(identityKeys) do
        assert(type(identity[key]) == "string" and #identity[key] > 0,
            "Invalid native reader identity")
        bound[key] = identity[key]
    end
    return setmetatable({ identity = bound, clock = clock,
        revision = 0, data = nil, capturedAt = nil,
        fullSync = false, closed = false }, Methods)
end

local function record(self, raw, fullSync)
    if self.closed then return false end
    local data = copied(raw)
    if not data then return false end
    if not fullSync and self.data and equal(data, self.data) then
        return true
    end
    local capturedAt = self.clock:Now()
    if type(capturedAt) ~= "number" or capturedAt ~= capturedAt
        or capturedAt < 0 or capturedAt == math.huge then return false end
    self.revision = self.revision + 1
    self.data = data
    self.capturedAt = capturedAt
    self.fullSync = fullSync
    return true
end

function Methods:ObserveSync(raw)
    return record(self, raw, true)
end

function Methods:ObserveChanged(raw)
    if not self.data then return false end
    return record(self, raw, false)
end

function Methods:Capture()
    if self.closed then return nil, "Native reader closed" end
    if not self.data then return nil, "No observed full Sync" end
    local native = copied(self.data)
    native.fullSync = self.fullSync
    local view = { revision = self.revision,
        capturedAt = self.capturedAt, fullSync = self.fullSync,
        data = native, native = native }
    for _, key in ipairs(identityKeys) do
        view[key] = self.identity[key]
    end
    return view, nil
end

function Methods:Close()
    self.closed = true
    self.data = nil
    self.capturedAt = nil
    self.fullSync = false
end

return NativeSnapshotReader
