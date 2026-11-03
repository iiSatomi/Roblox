-- Injected boundary only; the caller supplies a verified scheduler/invoker.
local NativeDispatchAdapter = {}
local Methods = {}
Methods.__index = Methods

function NativeDispatchAdapter.new(plan, executor, lane, clock, fightReceipts)
    assert(type(plan) == "table" and type(plan.describe) == "function",
        "Missing native call plan")
    assert(type(executor) == "table"
        and type(executor.Schedule) == "function"
        and type(executor.Invoke) == "function",
        "Missing injected native executor")
    assert(lane == nil or (type(lane) == "table" and type(lane.TryAcquire) == "function"
        and type(lane.Owns) == "function" and type(lane.Release) == "function"
        and type(lane.Status) == "function" and type(clock) == "table" and type(clock.Now) == "function"
        and type(executor.InvokeOwned) == "function"), "Missing owned native executor")
    assert(fightReceipts == nil or (lane ~= nil and type(fightReceipts) == "table"
        and type(fightReceipts.Begin) == "function" and type(fightReceipts.Bind) == "function"
        and type(fightReceipts.Release) == "function"), "Invalid fight receipt owner")
    return setmetatable({ plan = plan, executor = executor, fightReceipts = fightReceipts,
        lane = lane, clock = clock, lease = nil,
        invoking = nil }, Methods)
end

function Methods:InFlight()
    if self.lane then
        local status = self.lane:Status()
        return status.closed or status.now == nil or status.active ~= nil
    end
    return self.invoking ~= nil
        or (type(self.executor.InFlight) == "function"
            and self.executor:InFlight() == true)
end

function Methods:ReleaseExpired(proposal)
    -- Release only the local scheduling lock; the server call may still return.
    local released = self:ReleaseResolved(proposal, "expired_unconfirmed")
    if self.invoking and self.invoking.proposal == proposal then
        self.invoking = nil
        return true
    end
    return released
end

function Methods:ReleaseResolved(proposal, outcome)
    if self.lease and self.lease.proposal == proposal then
        if self.fightReceipts then self.fightReceipts:Release(self.lease.token) end
        self.lane:Release(self.lease.token, outcome or "resolved")
        self.lease = nil
        return true
    end
    return false
end

-- A confirmation read stays inside its exact mutation's logical ownership.
-- It cannot begin while the mutation's physical invocation is still running.
function Methods:ReadLease(feature)
    if self.lane and self.lease and self.lease.proposal.feature == feature
        and self.lease.returned == true and self.invoking == nil and self.lane:Owns(self.lease.token) then
        return self.lease.token
    end
    return nil
end

function Methods:Validate(proposal)
    self.validated = nil
    local ok, call, reason = pcall(self.plan.describe, proposal)
    if not ok or type(call) ~= "table"
        or type(call.remote) ~= "string"
        or call.method ~= "InvokeServer"
        or type(call.args) ~= "table"
        or type(call.arity) ~= "number"
        or call.arity < 0 or call.arity > 4
        or call.arity % 1 ~= 0 then
        return false, ok and (reason or "Invalid native call")
            or "Native call planning raised"
    end
    if call.remote == "Attack" and (not self.fightReceipts or not self.lane or call.arity ~= 1) then
        return false, "Current owned fight receipts unavailable"
    end
    if call.remote == "ScoutPlayer" and (not self.fightReceipts or not self.lane or call.arity ~= 1
        or type(self.fightReceipts.CheckScout) ~= "function") then
        return false, "Current owned Scout preflight unavailable"
    end
    local token = {}
    self.validated = { proposal = proposal, call = call, token = token }
    return true, nil, token
end

function Methods:Send(proposal, onReturn, canDispatch, preflightToken, onUnsent, authorize)
    assert(type(onReturn) == "function", "Missing native return callback")
    assert(type(canDispatch) == "function", "Missing dispatch ownership check")
    if preflightToken == nil then
        local valid, reason = self:Validate(proposal)
        if not valid then error(reason or "Unsupported native call") end
    elseif type(self.validated) ~= "table"
        or self.validated.proposal ~= proposal
        or self.validated.token ~= preflightToken then
        return false
    end
    local call = self.validated.call
    self.validated = nil
    local lease
    if self.lane then
        local token = self.lane:TryAcquire("mutation", proposal.actionKey, self.clock:Now() + 45)
        if not token then return false end
        lease = {token = token, proposal = proposal}
        self.lease = lease
    end
    local cancelled = false
    local ran = false
    local scheduled = self.executor:Schedule(function()
        if cancelled or ran or (lease and not self.lane:Owns(lease.token)) then return end
        ran = true
        local owned, allowed = pcall(canDispatch)
        if not owned or allowed ~= true or self.invoking or (lease and not self.lane:Owns(lease.token)) then
            self:ReleaseResolved(proposal, "dispatch_refused")
            if type(onUnsent) == "function" then onUnsent() end
            return
        end
        if authorize ~= nil then
            local authorized, exact = pcall(authorize)
            local same = authorized and type(exact) == "table" and exact.remote == call.remote
                and exact.method == call.method and exact.arity == call.arity and type(exact.args) == "table"
            if same then
                for index = 1, call.arity do if exact.args[index] ~= call.args[index] then same = false; break end end
            end
            -- Authorizing a durable stage can yield while writing. Recheck all
            -- runtime/selection/deadline/lease guards after that write.
            owned, allowed = pcall(canDispatch)
            if not same or not owned or allowed ~= true or self.invoking or (lease and not self.lane:Owns(lease.token)) then
                self:ReleaseResolved(proposal, "authorization_refused")
                if type(onUnsent) == "function" then onUnsent() end
                return
            end
        end
        if call.remote == "Attack" then
            local started, accepted = pcall(self.fightReceipts.Begin, self.fightReceipts,
                lease.token, proposal, call.args[1])
            owned, allowed = pcall(canDispatch)
            if not started or accepted ~= true or not owned or allowed ~= true or not self.lane:Owns(lease.token) then
                self:ReleaseResolved(proposal, "fight_receipt_refused")
                if type(onUnsent) == "function" then onUnsent() end
                return
            end
        end
        if call.remote == "ScoutPlayer" then
            local checked, accepted = pcall(self.fightReceipts.CheckScout, self.fightReceipts, lease.token, proposal, call.args[1])
            owned, allowed = pcall(canDispatch)
            if not checked or accepted ~= true or not owned or allowed ~= true or not self.lane:Owns(lease.token) then
                self:ReleaseResolved(proposal, "scout_preflight_refused")
                if type(onUnsent) == "function" then onUnsent() end
                return
            end
        end
        local invocation = { proposal = proposal }
        self.invoking = invocation
        local ok, reply
        if lease then
            ok, reply = pcall(self.executor.InvokeOwned, self.executor, lease.token,
                call.remote, call.method, table.unpack(call.args, 1, call.arity))
        else
            ok, reply = pcall(self.executor.Invoke, self.executor, call.remote, call.method,
                table.unpack(call.args, 1, call.arity))
        end
        if self.invoking == invocation then self.invoking = nil end
        if lease then lease.returned = true end
        -- An interrupted/malformed response is ambiguous. Keep the broker's
        -- sent action pending until state proof or the 45-second deadline.
        if ok and type(reply) == "table" and (not lease or self.lane:Owns(lease.token)) then
            if call.remote == "Attack" then pcall(self.fightReceipts.Bind, self.fightReceipts, lease.token, reply) end
            onReturn(reply)
            if call.remote == "Attack" and type(self.fightReceipts.Persist) == "function" then
                self.fightReceipts:Persist()
            end
        end
    end)
    if scheduled == false and not ran then
        -- A definite refusal cannot invoke the native call. Fence even an
        -- executor that queued the callback before returning false.
        cancelled = true
        self:ReleaseResolved(proposal, "schedule_failed")
        return false
    end
    return true
end

return NativeDispatchAdapter
