-- Explicit local allowance review. Never resets automatically or sends gameplay.
local AllowanceReset = {}
local function clear(claims)
    return type(claims) == "table" and claims.allCrew == false and (claims.allItems == false or claims.allItems == nil)
        and type(claims.members) == "table" and next(claims.members) == nil
        and type(claims.items) == "table" and next(claims.items) == nil
        and type(claims.funds) == "table" and next(claims.funds) == nil
end
function AllowanceReset.new(deps)
    assert(type(deps) == "table" and type(deps.checkpoint) == "table"
        and type(deps.checkpoint.Allowance) == "function" and type(deps.checkpoint.ResetAllowance) == "function"
        and type(deps.checkpoint.Records) == "function"
        and type(deps.session) == "table" and type(deps.session.Status) == "function"
        and type(deps.clock) == "table" and type(deps.clock.Now) == "function"
        and type(deps.reservations) == "table" and type(deps.reservations.Held) == "function"
        and type(deps.currentSnapshot) == "function" and type(deps.requested) == "function"
        and type(deps.identity) == "table", "Missing allowance reset owners")
    local identity = {}
    for _, key in ipairs({"session", "account", "place", "release"}) do
        assert(type(deps.identity[key]) == "string" and #deps.identity[key] > 0, "Invalid allowance scope")
        identity[key] = deps.identity[key]
    end
    local closed, busy, staged = false, false, nil
    local function time()
        local ok, now = pcall(deps.clock.Now, deps.clock)
        if not ok or type(now) ~= "number" or now ~= now or now < 0 or now == math.huge then return nil end
        return now
    end
    local function paused()
        local status = deps.session:Status()
        if type(status) ~= "table" or status.state ~= "paused" or deps.requested() ~= false then
            return false, "Pause automation before reviewing an allowance"
        end
        if status.storageFault then return false, "Storage needs attention before reset" end
        if status.active ~= nil or status.uncertainCount ~= 0 or #deps.checkpoint:Records() ~= 0 then
            return false, "Finish or review pending actions before reset"
        end
        return true
    end
    local function guard()
        if closed or busy then return false, closed and "Allowance controls are closed" or "Allowance reset is already saving" end
        local allowed, reason = paused()
        if not allowed then return false, reason end
        local ok, raw = pcall(deps.currentSnapshot)
        if not ok or type(raw) ~= "table" or type(raw.native) ~= "table" or raw.native.fullSync ~= true then
            return false, "Current account information is unavailable"
        end
        for key, value in pairs(identity) do if raw[key] ~= value then return false, "Current account information changed" end end
        local read, claims = pcall(deps.reservations.Held, deps.reservations, raw)
        if not read or not clear(claims) then return false, "Saved transactions still hold assets or need review" end
        if closed then return false, "Allowance controls are closed" end
        return paused()
    end
    local result = {}
    function result:Preview(feature)
        staged = nil
        local allowed, reason = guard()
        if not allowed then return nil, reason end
        local expected, why = deps.checkpoint:Allowance(feature)
        if not expected then return nil, why end
        local now = time()
        if now == nil then return nil, "Allowance review timer unavailable" end
        local ticket = {}
        staged = {ticket = ticket, expected = expected, at = now}
        return {feature = feature, attempted = expected.attempted, spent = expected.spent, ticket = ticket}, nil
    end
    function result:Confirm(ticket)
        local preview = staged
        if not preview or ticket ~= preview.ticket then return false, "Preview this allowance before confirming" end
        staged = nil -- One explicit confirmation attempt; never a replay arm.
        local allowed, reason = guard()
        if not allowed then return false, reason end
        local now = time()
        if now == nil or now < preview.at or now - preview.at > 30 then return false, "Preview expired; review the allowance again" end
        busy = true
        local ok, saved, why = pcall(deps.checkpoint.ResetAllowance, deps.checkpoint, preview.expected)
        busy = false
        if not ok then return false, "Allowance reset could not be saved" end
        return saved == true, why, saved == true and preview.expected.feature or nil
    end
    function result:Invalidate() staged = nil end
    function result:IsBusy() return busy end
    function result:Close() closed, staged = true, nil end
    return result
end
return AllowanceReset
