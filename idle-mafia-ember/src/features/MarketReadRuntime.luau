-- Injected, read-only Market query lane over the shared background budget.
local MarketReadRuntime = {}
local Methods = {}
Methods.__index = Methods

function MarketReadRuntime.new(budget, browse, prices, executor, onResult)
    assert(type(budget) == "table" and type(budget.Due) == "function"
        and type(budget.Finish) == "function"
        and type(budget.Owns) == "function", "Missing Market read budget")
    assert(type(browse) == "table" and type(browse.Prepare) == "function"
        and type(browse.Accept) == "function", "Missing Market browser")
    assert(type(prices) == "table" and type(prices.Prepare) == "function"
        and type(prices.Accept) == "function", "Missing Market prices")
    assert(type(executor) == "table"
        and type(executor.Schedule) == "function"
        and type(executor.Invoke) == "function"
        and type(onResult) == "function", "Missing Market read executor")
    return setmetatable({ budget = budget, browse = browse,
        prices = prices, executor = executor, onResult = onResult,
        queued = {}, inFlight = nil, closed = false }, Methods)
end

function Methods:QueueBrowse(scope)
    if self.closed then return false, "Market reader closed" end
    local request, reason = self.browse:Prepare(scope)
    if not request then return false, reason end
    self.queued.marketBrowse = request
    return true, nil
end

function Methods:QueuePrices(itemId)
    if self.closed then return false, "Market reader closed" end
    local request, reason = self.prices:Prepare(itemId)
    if not request then return false, reason end
    self.queued.marketPrices = request
    return true, nil
end

function Methods:Step()
    if self.closed then return "closed" end
    if self.inFlight then
        if self.inFlight.phase == "invoking" then
            -- A timed-out Invoke can still be running; keep the lane occupied.
            self.budget:Due({})
            return "Read invocation still running"
        end
        if self.budget:Owns(self.inFlight.token) then
            return "Read in flight"
        end
        -- The queued callback has not started. Expire its token and fence it.
        self.budget:Due({})
        self.inFlight = nil
    end
    local eligible = {}
    for id in pairs(self.queued) do eligible[id] = true end
    local id, token = self.budget:Due(eligible)
    if not id then return token == "No read due" and "idle" or token end
    local request = self.queued[id]
    if not request then
        self.budget:Finish(token, false)
        return "unsupported_read_source"
    end
    self.queued[id] = nil
    local reader = id == "marketBrowse" and self.browse or self.prices
    local flight = { token = token, phase = "scheduled" }
    self.inFlight = flight
    local scheduled, accepted = pcall(self.executor.Schedule, self.executor, function()
        if self.closed or self.inFlight ~= flight
            or not self.budget:Owns(token) then return end
        flight.phase = "invoking"
        local ok, reply = pcall(self.executor.Invoke,
            self.executor, request.remote, request.method,
            table.unpack(request.args, 1, request.arity))
        local result, reason
        if ok and type(reply) == "table"
            and not self.closed and self.inFlight == flight
            and self.budget:Owns(token) then
            local parsed, acceptedResult, acceptedReason = pcall(
                reader.Accept, reader, request, reply)
            if parsed then
                result, reason = acceptedResult, acceptedReason
            else
                reason = "Market read parse failed"
            end
        else
            reason = "Market read interrupted"
        end
        local accepted = self.budget:Finish(token, result ~= nil)
        if self.inFlight == flight then self.inFlight = nil end
        if accepted and not self.closed then
            pcall(self.onResult, id, result, reason)
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
    self.queued = {}
    self.inFlight = nil
    self.budget:Close()
    self.browse:Close()
    self.prices:Close()
end

return MarketReadRuntime
