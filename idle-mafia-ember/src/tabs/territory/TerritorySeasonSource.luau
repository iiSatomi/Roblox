-- Inject the decoded MW SeasonLive attribute and native SeasonRules.status.
-- No calendar algorithm, Roblox services, JSON decoder, local clock or timer.
local TerritorySeasonSource = {}
local Methods = {}
Methods.__index = Methods
local MAX = 9007199254740991
local fields = { "session", "account", "place", "release", "revision", "capturedAt" }
local function number(value, low, high)
    return type(value) == "number" and value == value and value >= low and value <= high
end
local function integer(value, low, high)
    return number(value, low, high) and value % 1 == 0
end
local function text(value, limit)
    return type(value) == "string" and #value > 0 and #value <= limit
end
local function header(raw, release)
    if type(raw) ~= "table" or raw.release ~= release
        or type(raw.native) ~= "table" or raw.native.fullSync ~= true
        or not integer(raw.revision, 0, MAX) or not number(raw.capturedAt, 0, MAX)
        or not number(raw.native.serverNow, 0, MAX) then return nil end
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
local function copy(value)
    if type(value) ~= "table" then return value end
    local result = {}
    for key, child in pairs(value) do result[key] = copy(child) end
    return result
end
local function equal(a, b)
    if type(a) ~= type(b) then return false end
    if type(a) ~= "table" then return a == b end
    for key, value in pairs(a) do if not equal(value, b[key]) then return false end end
    for key in pairs(b) do if a[key] == nil then return false end end
    return true
end
local function liveFacts(live)
    if type(live) ~= "table" or not integer(live.season, 0, 1000000)
        or (live.closed ~= nil and type(live.closed) ~= "boolean")
        or (live.startsAt ~= nil and not number(live.startsAt, 0, MAX))
        or (live.endsAt ~= nil and not number(live.endsAt, 0, MAX))
        or (live.startsAt ~= nil and live.endsAt ~= nil and live.endsAt < live.startsAt) then
        return nil
    end
    -- The native status function reads only these fields. Do not copy rankings.
    return { season = live.season, closed = live.closed,
        startsAt = live.startsAt, endsAt = live.endsAt }
end
local function statusFacts(status, serverNow)
    if type(status) ~= "table" or not integer(status.n, 1, 1000000) then return nil end
    local result = { phase = status.phase, n = status.n }
    if status.phase == "running" then
        if not number(status.startsAt, 0, MAX) or not number(status.endsAt, 0, MAX)
            or status.endsAt <= status.startsAt then return nil end
        result.startsAt, result.endsAt = status.startsAt, status.endsAt
        result.remaining = math.max(0, status.endsAt - serverNow)
    elseif status.phase == "upcoming" then
        if not number(status.startsAt, serverNow, MAX) or status.endsAt ~= nil then return nil end
        result.startsAt, result.remaining = status.startsAt, status.startsAt - serverNow
    elseif status.phase == "pre" then
        if status.startsAt ~= nil or status.endsAt ~= nil then return nil end
    else
        return nil
    end
    return result
end
function TerritorySeasonSource.new(readLiveCallback, statusCallback, fingerprint, release)
    if type(readLiveCallback) ~= "function" or type(statusCallback) ~= "function"
        or not text(release, 200) or type(fingerprint) ~= "string"
        or #fingerprint ~= 64 or not fingerprint:match("^[%x]+$") then
        return nil, "Reviewed native SeasonLive and SeasonRules callbacks required"
    end
    return setmetatable({ readLive = readLiveCallback, status = statusCallback,
        sourceKey = fingerprint:lower(), release = release, generation = 0, closed = false }, Methods), nil
end
function Methods:Enrich(snapshot)
    local bound = header(snapshot, self.release)
    if self.closed or not bound then return nil, "Current full season Sync required" end
    self.generation = self.generation + 1
    self.latest = nil
    local generation, serverNow = self.generation, snapshot.native.serverNow
    local ok, live = pcall(self.readLive)
    if not ok then return nil, "Native SeasonLive callback unavailable" end
    local fallback = live == nil
    if not fallback then
        live = liveFacts(live)
        if not live then return nil, "Native SeasonLive is invalid" end
    end
    local reported, status = pcall(self.status, live, serverNow)
    local view = reported and statusFacts(status, serverNow) or nil
    if not view then return nil, "Native season status unavailable" end
    if self.closed or self.generation ~= generation
        or not same(header(snapshot, self.release), bound)
        or snapshot.native.serverNow ~= serverNow then return nil, "Season source changed during capture" end
    view.header, view.serverNow, view.sourceKey = bound, serverNow, self.sourceKey
    view.release, view.readOnly = self.release, true
    view.calendarFallback = fallback
    view.sourceGeneration = generation
    self.latest = copy(view)
    local result = {}
    for key, value in pairs(snapshot) do result[key] = value end
    result.territorySeason = view
    return result, nil
end
function Methods:Read(raw, context)
    local bound = header(raw, self.release)
    local stamped = type(raw) == "table" and raw.territorySeason
    if self.closed or not bound or not same(bound, context) or type(stamped) ~= "table"
        or stamped.readOnly ~= true or stamped.sourceKey ~= self.sourceKey
        or stamped.sourceGeneration ~= self.generation
        or type(stamped.calendarFallback) ~= "boolean"
        or stamped.release ~= self.release or not same(stamped.header, bound)
        or stamped.serverNow ~= raw.native.serverNow or not equal(stamped, self.latest) then
        return nil, "Season status is not from this native source and Sync"
    end
    local view = statusFacts(stamped, stamped.serverNow)
    if not view or view.remaining ~= stamped.remaining then return nil, "Invalid season display facts" end
    view.header, view.serverNow, view.sourceKey = bound, stamped.serverNow, self.sourceKey
    view.release, view.readOnly = self.release, true
    view.calendarFallback = stamped.calendarFallback
    view.sourceGeneration = stamped.sourceGeneration
    return view, nil
end
function Methods:Close()
    self.closed = true
    self.latest = nil
    self.generation = self.generation + 1
end

return TerritorySeasonSource
