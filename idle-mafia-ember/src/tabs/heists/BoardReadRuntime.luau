-- Bounded read-only Heist board lane. Mutation sequences are not inferred.
local BoardReadRuntime = {}
local Methods = {}
Methods.__index = Methods

local function valid(header)
    if type(header) ~= "table" then return false end
    for _, field in ipairs({ "session", "account", "place",
        "release" }) do
        if type(header[field]) ~= "string" or #header[field] == 0 then
            return false
        end
    end
    local revision, capturedAt = header.revision, header.capturedAt
    return type(revision) == "number" and revision == revision
        and revision >= 0 and revision < math.huge
        and revision % 1 == 0
        and type(capturedAt) == "number"
        and capturedAt == capturedAt
        and capturedAt >= 0 and capturedAt < math.huge
end

local function same(header, raw)
    if not valid(header) or not valid(raw)
        or type(raw.native) ~= "table"
        or raw.native.fullSync ~= true then return false end
    for _, field in ipairs({ "session", "account", "place",
        "release", "revision", "capturedAt" }) do
        if header[field] ~= raw[field] then return false end
    end
    return true
end

local function header(snapshot)
    local result = {}
    for _, field in ipairs({ "session", "account", "place",
        "release", "revision", "capturedAt" }) do
        result[field] = snapshot[field]
    end
    return result
end

function BoardReadRuntime.new(budget, query, executor,
    currentSnapshot, onResult)
    assert(type(budget) == "table" and type(budget.Due) == "function"
        and type(budget.Finish) == "function"
        and type(budget.Owns) == "function"
        and type(budget.Close) == "function"
        and type(query) == "table"
        and type(query.Describe) == "function"
        and type(query.Stage) == "function"
        and type(executor) == "table"
        and type(executor.Schedule) == "function"
        and type(executor.Invoke) == "function"
        and type(currentSnapshot) == "function"
        and type(onResult) == "function",
        "Missing Heist board read capabilities")
    return setmetatable({ budget = budget, query = query,
        executor = executor, currentSnapshot = currentSnapshot,
        onResult = onResult, queued = nil, inFlight = nil,
        closed = false }, Methods)
end

function Methods:Current(bound)
    local ok, raw = pcall(self.currentSnapshot)
    if ok and same(bound, raw) then return raw end
    return nil
end

function Methods:Queue(snapshot)
    if self.closed then return false, "Heist board reader closed" end
    if not same(snapshot, snapshot) then
        return false, "Current full Sync required"
    end
    local ok, call = pcall(self.query.Describe, self.query)
    if not ok or type(call) ~= "table"
        or call.kind ~= "readOnly"
        or call.remote ~= "HeistAction"
        or call.method ~= "InvokeServer"
        or call.arity ~= 1
        or type(call.args) ~= "table"
        or call.args[1] ~= "board" then
        return false, "Unsupported Heist board read"
    end
    self.queued = { header = header(snapshot), call = call }
    return true, nil
end

function Methods:Step()
    if self.closed then return "closed" end
    if self.inFlight then
        if self.inFlight.phase == "invoking" then
            self.budget:Due({})
            return "Read invocation still running"
        end
        if self.budget:Owns(self.inFlight.token) then
            return "Read in flight"
        end
        self.budget:Due({})
        self.inFlight = nil
    end
    if not self.queued then return "idle" end
    local id, token = self.budget:Due({ heistBoard = true })
    if not id then return token == "No read due" and "idle" or token end
    if id ~= "heistBoard" then
        self.budget:Finish(token, false)
        return "unsupported_read_source"
    end
    local item = self.queued
    self.queued = nil
    local flight = { token = token, phase = "scheduled" }
    self.inFlight = flight
    local scheduled, accepted = pcall(self.executor.Schedule,
        self.executor, function()
            if self.closed or self.inFlight ~= flight
                or not self.budget:Owns(token) then return end
            if not self:Current(item.header) then
                self.budget:Finish(token, false)
                if self.inFlight == flight then self.inFlight = nil end
                return
            end
            flight.phase = "invoking"
            local call = item.call
            local ok, reply = pcall(self.executor.Invoke,
                self.executor, call.remote, call.method,
                table.unpack(call.args, 1, call.arity))
            local current = self:Current(item.header)
            local result, reason
            if ok and type(reply) == "table"
                and not self.closed and self.inFlight == flight
                and self.budget:Owns(token) and current then
                local parsed, staged, why = pcall(self.query.Stage,
                    self.query, current, reply)
                if parsed then result, reason = staged, why
                else reason = "Heist board parse failed" end
            else
                reason = "Heist board read interrupted or stale"
            end
            local finished = self.budget:Finish(token, result ~= nil)
            if self.inFlight == flight then self.inFlight = nil end
            if finished and current and not self.closed then
                pcall(self.onResult, result, reason)
            end
        end)
    if not scheduled or accepted == false then
        self.budget:Finish(token, false)
        if self.inFlight == flight then self.inFlight = nil end
        return "schedule_failed"
    end
    return "scheduled"
end

function Methods:Close()
    if self.closed then return end
    self.closed = true
    self.queued = nil
    self.inFlight = nil
    self.budget:Close()
end

return BoardReadRuntime
