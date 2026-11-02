-- Logical scheduling custody. Expiry cannot cancel an already invoked server call.
local RequestLane = {}
local kinds = {mutation = true, read = true, status = true, membership = true}
local function finite(value)
    return type(value) == "number" and value == value and value >= 0 and value < math.huge
end
function RequestLane.new(clock)
    assert(type(clock) == "table" and type(clock.Now) == "function", "Request lane needs monotonic clock")
    local closed, active, serial, lastNow = false, nil, 0, 0
    local function now()
        local ok, value = pcall(clock.Now, clock)
        if not ok or not finite(value) or value < lastNow then return nil end
        lastNow = value
        if active and value >= active.deadline then active = nil end
        return value
    end
    local result = {}
    function result:TryAcquire(kind, actionKey, deadline)
        local current = now()
        if closed or not current then return nil, "Request lane unavailable" end
        if not kinds[kind] or type(actionKey) ~= "string" or #actionKey == 0 or #actionKey > 512
            or not finite(deadline) or deadline <= current or deadline > current + 45 then
            return nil, "Invalid request lease"
        end
        if active then return nil, "Another request owns the lane" end
        serial = serial + 1
        local token = {}
        active = {token = token, serial = serial, kind = kind, actionKey = actionKey,
            acquiredAt = current, deadline = deadline}
        return token, nil
    end
    function result:Owns(token)
        local current = now()
        return not closed and current ~= nil and active ~= nil and active.token == token
    end
    function result:Release(token, outcome)
        if not self:Owns(token) or type(outcome) ~= "string" or #outcome == 0 or #outcome > 80 then return false end
        active = nil
        return true
    end
    function result:Status()
        local current = now()
        local view = {closed = closed, now = current}
        if not closed and current ~= nil and active then
            view.active = {serial = active.serial, kind = active.kind, actionKey = active.actionKey,
                acquiredAt = active.acquiredAt, deadline = active.deadline}
        end
        return view
    end
    function result:Close() closed, active = true, nil end
    return result
end
return RequestLane
