-- Injected boundary only; the caller supplies a verified scheduler/invoker.
local NativeDispatchAdapter = {}
local Methods = {}
Methods.__index = Methods

function NativeDispatchAdapter.new(plan, executor)
    assert(type(plan) == "table" and type(plan.describe) == "function",
        "Missing native call plan")
    assert(type(executor) == "table"
        and type(executor.Schedule) == "function"
        and type(executor.Invoke) == "function",
        "Missing injected native executor")
    return setmetatable({ plan = plan, executor = executor,
        invoking = nil }, Methods)
end

function Methods:InFlight()
    return self.invoking ~= nil
end

function Methods:ReleaseExpired(proposal)
    -- Release only the local scheduling lock; the server call may still return.
    if self.invoking and self.invoking.proposal == proposal then
        self.invoking = nil
        return true
    end
    return false
end

function Methods:Validate(proposal)
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
    return true, nil
end

function Methods:Send(proposal, onReturn, canDispatch)
    assert(type(onReturn) == "function", "Missing native return callback")
    assert(type(canDispatch) == "function", "Missing dispatch ownership check")
    local valid, reason = self:Validate(proposal)
    if not valid then error(reason or "Unsupported native call") end
    local call = self.plan.describe(proposal)
    self.executor:Schedule(function()
        local owned, allowed = pcall(canDispatch)
        if not owned or allowed ~= true or self.invoking then return end
        local invocation = { proposal = proposal }
        self.invoking = invocation
        local ok, reply = pcall(self.executor.Invoke,
            self.executor, call.remote, call.method,
            table.unpack(call.args, 1, call.arity))
        if self.invoking == invocation then self.invoking = nil end
        -- An interrupted/malformed response is ambiguous. Keep the broker's
        -- sent action pending until state proof or the 45-second deadline.
        if ok and type(reply) == "table" then
            onReturn(reply)
        end
    end)
end

return NativeDispatchAdapter
