-- Bounded action metadata. Never store payloads, raw replies or account data.
local Journal = {}
local Methods = {}
Methods.__index = Methods

function Journal.new(limit)
    local size = type(limit) == "number" and math.floor(limit) or 100
    assert(size >= 1 and size <= 1000, "Invalid journal size")
    return setmetatable({ limit = size, entries = {} }, Methods)
end

local function copy(entry)
    return {
        kind = entry.kind, at = entry.at, feature = entry.feature,
        actionKey = entry.actionKey, token = entry.token,
        reason = entry.reason, duplicateRisk = entry.duplicateRisk == true,
    }
end

function Methods:Record(entry)
    assert(type(entry) == "table" and type(entry.kind) == "string", "Invalid journal entry")
    local entries = self.entries
    entries[#entries + 1] = copy(entry)
    if #entries > self.limit then table.remove(entries, 1) end
end

function Methods:Events()
    local result = {}
    for i, entry in ipairs(self.entries) do result[i] = copy(entry) end
    return result
end

local function safeLabel(value)
    if type(value) ~= "string" or #value == 0 or #value > 48
        or not value:match("^[%w_]+$") then return "unknown" end
    return value
end

function Methods:PublicEvents(limit)
    local count = type(limit) == "number" and math.floor(limit) or 10
    count = math.max(1, math.min(20, count))
    local result = {}
    for i = math.max(1, #self.entries - count + 1), #self.entries do
        local entry = self.entries[i]
        result[#result + 1] = {
            kind = safeLabel(entry.kind), feature = safeLabel(entry.feature),
            at = type(entry.at) == "number" and entry.at or nil,
            duplicateRisk = entry.duplicateRisk == true,
        }
    end
    return result
end

return Journal
