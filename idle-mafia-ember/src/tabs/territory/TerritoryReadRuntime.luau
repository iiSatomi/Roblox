-- Bounded read-only map/residency lane, tied to one originating full Sync.
local TerritoryReadRuntime = {}
local Methods = {}
Methods.__index = Methods

local function same(header, raw)
    if type(header) ~= "table" or type(raw) ~= "table"
        or type(raw.native) ~= "table"
        or raw.native.fullSync ~= true then return false end
    for _, field in ipairs({ "session", "account", "place",
        "release", "revision", "capturedAt" }) do
        if header[field] ~= raw[field] then return false end
    end
    return true
end

function TerritoryReadRuntime.new(budget, mapQuery, residencyQuery,
    attachment, executor, currentSnapshot, onResult)
    assert(type(budget) == "table"
        and type(budget.Due) == "function"
        and type(budget.Finish) == "function"
        and type(budget.Owns) == "function"
        and type(mapQuery) == "table"
        and type(mapQuery.Prepare) == "function"
        and type(mapQuery.Accept) == "function"
        and type(residencyQuery) == "table"
        and type(residencyQuery.Prepare) == "function"
        and type(residencyQuery.Accept) == "function"
        and type(attachment) == "table"
        and type(attachment.attach) == "function"
        and type(executor) == "table"
        and type(executor.Schedule) == "function"
        and type(executor.Invoke) == "function"
        and type(currentSnapshot) == "function"
        and type(onResult) == "function",
        "Missing Territory read capabilities")
    return setmetatable({ budget = budget, mapQuery = mapQuery,
        residencyQuery = residencyQuery, attachment = attachment,
        executor = executor, currentSnapshot = currentSnapshot,
        onResult = onResult, queued = {}, map = nil,
        inFlight = nil, closed = false }, Methods)
end

function Methods:QueueMap(cityId, snapshot)
    if self.closed then return false, "Territory reader closed" end
    local request, reason = self.mapQuery:Prepare(cityId, snapshot)
    if not request or not same(request.header, snapshot) then
        return false, reason or "Current full Sync required"
    end
    self.map = nil
    self.queued.residencyView = nil
    self.queued.territoryMap = { request = request }
    return true, nil
end

function Methods:QueueResidency(districtId, snapshot)
    if self.closed then return false, "Territory reader closed" end
    if not self.map or not same(self.map.header, snapshot) then
        return false, "Matching Territory map required"
    end
    local found = false
    for _, row in ipairs(self.map.districts) do
        if row.id == districtId then found = true; break end
    end
    if not found then return false, "District outside current map" end
    local request, reason = self.residencyQuery:Prepare(
        districtId, snapshot)
    if not request or not same(request.header, snapshot) then
        return false, reason or "Current full Sync required"
    end
    self.queued.residencyView = { request = request }
    return true, nil
end

function Methods:Current(header)
    local ok, raw = pcall(self.currentSnapshot)
    if ok and same(header, raw) then return raw end
    return nil
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
    local eligible = {}
    for id in pairs(self.queued) do eligible[id] = true end
    local id, token = self.budget:Due(eligible)
    if not id then return token == "No read due" and "idle" or token end
    local item = self.queued[id]
    if not item then
        self.budget:Finish(token, false)
        return "unsupported_read_source"
    end
    self.queued[id] = nil
    local request = item.request
    local reader = id == "territoryMap"
        and self.mapQuery or self.residencyQuery
    local flight = { token = token, phase = "scheduled" }
    self.inFlight = flight
    local scheduled = pcall(self.executor.Schedule,
        self.executor, function()
            if self.closed or self.inFlight ~= flight
                or not self.budget:Owns(token)
                or not self:Current(request.header) then return end
            flight.phase = "invoking"
            local ok, reply = pcall(self.executor.Invoke,
                self.executor, request.remote, request.method,
                table.unpack(request.args, 1, request.arity))
            local result, reason
            local current = self:Current(request.header)
            if ok and type(reply) == "table"
                and not self.closed and self.inFlight == flight
                and self.budget:Owns(token)
                and current then
                result, reason = reader:Accept(request, reply)
                if result then
                    local map = id == "territoryMap" and result
                        or self.map
                    local residency = id == "residencyView"
                        and result or nil
                    local attached
                    attached, reason = self.attachment.attach(
                        current, map, residency)
                    if attached then
                        if id == "territoryMap" then self.map = result end
                        result = attached
                    else
                        result = nil
                    end
                end
            else
                reason = "Territory read interrupted or stale"
            end
            local accepted = self.budget:Finish(token,
                result ~= nil)
            if self.inFlight == flight then self.inFlight = nil end
            if accepted and not self.closed then
                pcall(self.onResult, id, result, reason)
            end
        end)
    if not scheduled then
        self.budget:Finish(token, false)
        if self.inFlight == flight then self.inFlight = nil end
        return "schedule_failed"
    end
    return "scheduled"
end

function Methods:Close()
    if self.closed then return end
    self.closed = true
    self.queued = {}
    self.map = nil
    self.inFlight = nil
    self.budget:Close()
    self.mapQuery:Close()
    self.residencyQuery:Close()
end

return TerritoryReadRuntime
