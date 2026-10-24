-- Scalar preferences only. No storage, Roblox services, timers or transport.
local Settings = {}
local Model = {}
Model.__index = Model

local function copy(values)
    local result = {}
    for key, value in pairs(values) do result[key] = value end
    return result
end

local function accepts(spec, value)
    if spec.kind == "boolean" then return type(value) == "boolean" end
    if spec.kind == "number" then
        return type(value) == "number" and value == value
            and value > -math.huge and value < math.huge
            and (spec.min == nil or value >= spec.min)
            and (spec.max == nil or value <= spec.max)
            and (not spec.integer or value % 1 == 0)
    end
    if spec.kind == "enum" then
        for _, option in ipairs(spec.options) do
            if value == option then return true end
        end
    end
    if spec.kind == "text" then
        return type(value) == "string" and #value > 0
            and #value <= (spec.maxLength or 120)
            and value:match("^[%w_%-]+$") ~= nil
    end
    return false
end

function Settings.new(catalog, runByDefault)
    local self = setmetatable({
        values = {}, specs = {}, groups = {},
        paused = runByDefault ~= true, stopped = false,
    }, Model)
    local function add(key, value, spec)
        assert(not self.specs[key], "Duplicate preference: " .. key)
        self.values[key], self.specs[key] = value, spec
    end
    for _, feature in ipairs(catalog.features) do
        local key = feature.id .. ".enabled"
        add(key, false, { kind = "boolean" })
        self.groups[key] = feature.exclusiveGroup
        if #feature.policies > 0 then
            add(feature.id .. ".policy", feature.policies[1],
                { kind = "enum", options = feature.policies })
        end
        for _, field in ipairs(feature.custom) do
            assert(type(field.id) == "string", "Custom preference needs a stable ID")
            add(feature.id .. ".custom." .. field.id, field.value, {
                kind = field.type == "select" and "enum"
                    or field.type == "text" and "text" or "number",
                options = field.options, min = field.min, max = field.max,
                integer = field.integer, maxLength = field.maxLength,
            })
        end
    end
    return self
end

function Model:Validate(profile)
    if type(profile) ~= "table" or profile.schema ~= 1 or type(profile.values) ~= "table" then
        return nil, "Unsupported profile schema"
    end
    for key in pairs(profile) do
        if key ~= "schema" and key ~= "values" then return nil, "Unknown profile field" end
    end
    local selected = {}
    for key, value in pairs(profile.values) do
        local spec = self.specs[key]
        if not spec then return nil, "Unknown preference: " .. tostring(key) end
        if not accepts(spec, value) then return nil, "Invalid preference: " .. key end
        local group = self.groups[key]
        if value == true and group then
            if selected[group] then return nil, "Conflicting owners for " .. group end
            selected[group] = key
        end
    end
    local nextValues = copy(self.values)
    for key, value in pairs(profile.values) do nextValues[key] = value end
    for group, owner in pairs(selected) do
        for peer, peerGroup in pairs(self.groups) do
            if peerGroup == group and peer ~= owner then nextValues[peer] = false end
        end
    end
    return nextValues, nil
end

function Model:Commit(values, pause)
    self.values = copy(values)
    if pause ~= false then self.paused = true end
end

function Model:Set(key, value)
    if not self.specs[key] or value == nil then return false, "Invalid preference: " .. tostring(key) end
    local prepared, reason = self:Validate({ schema = 1, values = { [key] = value } })
    if not prepared then return false, reason end
    self.values = prepared
    return true, nil
end

function Model:Snapshot() return { schema = 1, values = copy(self.values) } end
function Model:Pause() self.paused = true end
function Model:Resume() self.paused = false; self.stopped = false end
function Model:Stop()
    for key, spec in pairs(self.specs) do
        if spec.kind == "boolean" then self.values[key] = false end
    end
    self.stopped = true
    self.paused = true
end

return Settings
