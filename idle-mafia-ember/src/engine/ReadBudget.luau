-- Admission only; the caller performs native reads and supplies outcomes.
local ReadBudget = {}
local Methods = {}
Methods.__index = Methods

local function positive(value)
    return type(value) == "number" and value == value
        and value > 0 and value < math.huge
end

function ReadBudget.new(clock, specs, timeout, maxBackoff)
    assert(type(clock) == "table" and type(clock.Now) == "function",
        "Read budget needs monotonic clock")
    assert(type(specs) == "table" and #specs > 0
        and positive(timeout) and positive(maxBackoff),
        "Invalid read budget")
    local sources, seen = {}, {}
    for _, spec in ipairs(specs) do
        assert(type(spec) == "table" and type(spec.id) == "string"
            and #spec.id > 0 and not seen[spec.id]
            and positive(spec.interval), "Invalid read source")
        seen[spec.id] = true
        sources[#sources + 1] = { id = spec.id,
            interval = spec.interval, nextAt = 0, failures = 0 }
    end
    return setmetatable({ clock = clock, sources = sources,
        timeout = timeout, maxBackoff = maxBackoff,
        active = nil, cursor = 0, token = 0, closed = false }, Methods)
end

local function failed(self, source, now)
    source.failures = source.failures + 1
    local delay = math.min(self.maxBackoff,
        source.interval * 2 ^ math.min(source.failures, 20))
    source.nextAt = now + delay
end

function Methods:Due(eligible)
    if self.closed then return nil, "Read budget closed" end
    if eligible ~= nil and type(eligible) ~= "table" then
        return nil, "Invalid read filter"
    end
    local now = self.clock:Now()
    if self.active then
        if now < self.active.deadline then return nil, "Read in flight" end
        failed(self, self.sources[self.active.index], now)
        self.active = nil
    end
    for offset = 1, #self.sources do
        local index = (self.cursor + offset - 1) % #self.sources + 1
        local source = self.sources[index]
        if (eligible == nil or eligible[source.id] == true)
            and now >= source.nextAt then
            self.token = self.token + 1
            self.cursor = index
            self.active = { index = index, token = self.token,
                deadline = now + self.timeout }
            return source.id, self.token
        end
    end
    return nil, "No read due"
end

function Methods:Finish(token, succeeded)
    if self.closed or not self.active or token ~= self.active.token
        or type(succeeded) ~= "boolean" then return false end
    local now = self.clock:Now()
    local source = self.sources[self.active.index]
    if now >= self.active.deadline then
        failed(self, source, now)
        self.active = nil
        return false
    end
    self.active = nil
    if succeeded then
        source.failures = 0
        source.nextAt = now + source.interval
    else
        failed(self, source, now)
    end
    return true
end

function Methods:Owns(token)
    return not self.closed and self.active ~= nil
        and self.active.token == token
        and self.clock:Now() < self.active.deadline
end

function Methods:Close()
    self.closed = true
    self.active = nil
end

function Methods:Status()
    local status = { closed = self.closed }
    for _, source in ipairs(self.sources) do
        status[source.id] = { nextAt = source.nextAt,
            failures = source.failures,
            inFlight = self.active ~= nil
                and self.sources[self.active.index] == source }
    end
    return status
end

return ReadBudget
