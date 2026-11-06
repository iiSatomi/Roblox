-- Fair bounded reads use the same lease as writes. No independent remote loop.
local ReadCoordinator = {}
local fields = {"session", "account", "place", "release", "revision", "capturedAt"}
local arities = {HeistAction = {board = 1, status = 3}, FamilyAction = {info = 1},
    FamilyBossAction = {state = 2}, TerritoryView = {map = 2, district = 4},
    TerritoryAction = {fortview = 2}, TerritoryStatus = {recallstatus = 3}, ResidencyAction = {view = 3},
    MarketAction = {browse = 4, prices = 4, rap = 4}}
local function finite(value)
    return type(value) == "number" and value == value and value >= 0 and value < math.huge
end
local function header(raw, now)
    if type(raw) ~= "table" or type(raw.native) ~= "table" or raw.native.fullSync ~= true
        or not finite(raw.native.serverNow) or not finite(raw.capturedAt)
        or not finite(raw.revision) or raw.revision % 1 ~= 0
        or not finite(now) or raw.capturedAt > now or now - raw.capturedAt > 2 then return nil end
    local result = {serverNow = raw.native.serverNow}
    for _, field in ipairs(fields) do result[field] = raw[field] end
    for _, field in ipairs({"session", "account", "place", "release"}) do
        if type(result[field]) ~= "string" or #result[field] == 0 or #result[field] > 200 then return nil end
    end
    return result
end
local function same(a, b)
    if not a or not b then return false end
    for _, field in ipairs(fields) do if a[field] ~= b[field] then return false end end
    return a.serverNow == b.serverNow
end
local function argument(value, nested)
    local kind = type(value)
    if value == nil or kind == "boolean" then return value, true end
    if kind == "string" then return value, #value <= 512 end
    if kind == "number" then return value, finite(value) end
    if kind ~= "table" or nested or #value > 128 then return nil, false end
    local copied, count = {}, 0
    for key, item in pairs(value) do
        if not finite(key) or key % 1 ~= 0 or key < 1 or key > #value then return nil, false end
        local child, valid = argument(item, true)
        if not valid then return nil, false end
        copied[key], count = child, count + 1
    end
    return copied, count == #value
end
local function callCopy(call)
    if type(call) ~= "table" or call.method ~= "InvokeServer" or type(call.args) ~= "table" then return nil end
    local expected = (call.remote == "GetHitList" or call.remote == "SearchTarget" or call.remote == "PlayerProfile") and 1
        or arities[call.remote] and arities[call.remote][call.args[1]]
    if not expected or call.arity ~= expected then return nil end
    local statusOnly = call.remote == "HeistAction" and call.args[1] == "status"
        or call.remote == "TerritoryStatus" and call.args[1] == "recallstatus"
    if statusOnly and call.kind ~= "statusOnly" then return nil end
    if call.remote == "HeistAction" and statusOnly and (not finite(call.args[3])
        or call.args[3] < 1 or call.args[3] % 1 ~= 0 or call.args[3] > 9007199254740991) then return nil end
    if call.remote == "PlayerProfile" and (not finite(call.args[1]) or call.args[1] < 1
        or call.args[1] % 1 ~= 0 or call.args[1] > 9007199254740991) then return nil end
    local args = {}
    for key, value in pairs(call.args) do
        if not finite(key) or key % 1 ~= 0 or key < 1 or key > expected then return nil end
        local copied, valid = argument(value, false)
        if not valid then return nil end
        args[key] = copied
    end
    return {remote = call.remote, method = call.method, arity = expected, args = args, statusOnly = statusOnly}
end
function ReadCoordinator.new(deps)
    assert(type(deps) == "table" and type(deps.clock) == "table" and type(deps.clock.Now) == "function"
        and type(deps.lane) == "table" and type(deps.lane.TryAcquire) == "function"
        and type(deps.lane.Owns) == "function" and type(deps.lane.Release) == "function"
        and type(deps.lane.Status) == "function" and type(deps.budget) == "table"
        and type(deps.budget.Due) == "function" and type(deps.budget.Finish) == "function"
        and type(deps.budget.Owns) == "function" and type(deps.budget.Close) == "function"
        and finite(deps.budget.timeout) and deps.budget.timeout > 0 and deps.budget.timeout <= 45
        and type(deps.executor) == "table" and type(deps.executor.Schedule) == "function"
        and type(deps.executor.InvokeOwned) == "function" and type(deps.currentSnapshot) == "function"
        and type(deps.sources) == "table" and #deps.sources > 0 and #deps.sources <= 32,
        "Missing shared read capabilities")
    local sources = {}
    local sourceCount = 0
    for key in pairs(deps.sources) do
        assert(finite(key) and key % 1 == 0 and key >= 1 and key <= #deps.sources, "Sparse read sources")
        sourceCount = sourceCount + 1
    end
    assert(sourceCount == #deps.sources, "Sparse read sources")
    for _, spec in ipairs(deps.sources) do
        assert(type(spec) == "table" and type(spec.id) == "string" and #spec.id > 0 and #spec.id <= 80
            and not sources[spec.id] and type(spec.prepare) == "function"
            and type(spec.accept) == "function" and type(spec.commit) == "function", "Invalid read source")
        local confirmFeatures, count = {}, 0
        assert(spec.confirmFeatures == nil or type(spec.confirmFeatures) == "table", "Invalid confirmation read scope")
        for feature, allowed in pairs(spec.confirmFeatures or {}) do
            assert(type(feature) == "string" and #feature > 0 and #feature <= 80 and allowed == true,
                "Invalid confirmation feature")
            confirmFeatures[feature], count = true, count + 1
            assert(count <= 8, "Too many confirmation features")
        end
        sources[spec.id] = {id = spec.id, prepare = spec.prepare, accept = spec.accept,
            commit = spec.commit, confirmFeatures = confirmFeatures}
    end
    local closed, active, enabled, reasons = false, nil, {}, {}
    local lane, budget, clock, executor = deps.lane, deps.budget, deps.clock, deps.executor
    local function nativeBusy()
        if type(executor.InFlight) ~= "function" then return false end
        local ok, busy = pcall(executor.InFlight, executor)
        return not ok or busy ~= false
    end
    local function owns(job)
        return not closed and active == job and enabled[job.id] == true
            and budget:Owns(job.budgetToken) and lane:Owns(job.lease)
    end
    local function current(job)
        if not owns(job) then return nil end
        local ok, raw = pcall(deps.currentSnapshot)
        if ok and same(header(raw, clock:Now()), job.header) then return raw end
        return nil
    end
    local function finish(job, success, reason)
        if active ~= job then return end
        budget:Finish(job.budgetToken, success)
        if not job.borrowed then lane:Release(job.lease, success and "read_committed" or "read_unavailable") end
        reasons[job.id] = reason
        active = nil
    end
    local result = {}
    function result:Step(snapshot, eligible)
        if closed then return "closed" end
        enabled = {}
        if type(eligible) == "table" then
            for id in pairs(sources) do enabled[id] = eligible[id] == true end
        end
        if active then
            local job = active
            if not budget:Owns(job.budgetToken) then
                budget:Due({}) -- Expire the old source and apply its own backoff.
                if not job.borrowed then lane:Release(job.lease, "read_expired") end
                reasons[job.id], active = "Read deadline expired", nil
            elseif not current(job) then
                finish(job, false, "Read disabled or source snapshot changed")
            else return "in_flight" end
        end
        if nativeBusy() then return "busy" end
        local bound = header(snapshot, clock:Now())
        if not bound then return "blocked" end
        local status = lane:Status()
        if status.closed or status.now == nil then return "busy" end
        local effective, borrowed = {}, {}
        if status.active then
            if status.active.kind ~= "mutation" or type(deps.borrowLease) ~= "function" then return "busy" end
            for id, spec in pairs(sources) do
                if enabled[id] then
                    for feature in pairs(spec.confirmFeatures) do
                        local ok, token = pcall(deps.borrowLease, feature)
                        if ok and token ~= nil and lane:Owns(token) then
                            effective[id], borrowed[id] = true, token
                            break
                        end
                    end
                end
            end
            if next(effective) == nil then return "busy" end
        else effective = enabled end
        local id, budgetToken = budget:Due(effective)
        if not id then return "idle" end
        local source = sources[id]
        if not source then budget:Finish(budgetToken, false); return "blocked" end
        local prepared, request, reason = pcall(source.prepare, snapshot)
        local call = prepared and callCopy(request) or nil
        if closed or not budget:Owns(budgetToken) or not same(header(snapshot, clock:Now()), bound) then
            budget:Finish(budgetToken, false)
            return "blocked"
        end
        if not call then
            budget:Finish(budgetToken, false)
            reasons[id] = prepared and (reason or "Unsupported read call") or "Read preparation raised"
            return "blocked"
        end
        local lease = borrowed[id] or lane:TryAcquire("read", "read:" .. id, clock:Now() + budget.timeout)
        if not lease then budget:Finish(budgetToken, false); return "busy" end
        local job = {id = id, budgetToken = budgetToken, lease = lease, header = bound,
            borrowed = borrowed[id] ~= nil}
        active = job
        local scheduled, accepted = pcall(executor.Schedule, executor, function()
            local raw = current(job)
            if not raw then finish(job, false, "Read dispatch owner changed"); return end
            if nativeBusy() then finish(job, false, "Native worker still owns physical invocation"); return end
            local ok, reply = pcall(executor.InvokeOwned, executor, lease, call.remote, call.method,
                table.unpack(call.args, 1, call.arity))
            raw = current(job)
            if not raw then finish(job, false, "Read result owner changed"); return end
            if not ok or type(reply) ~= "table" or (reply.ok ~= true and not (call.statusOnly and reply.ok == false)) or reply.pending == true
                or reply.code == "rate_limited" or reply.code == "busy" then
                finish(job, false, "Read reply unavailable"); return
            end
            local staged, value = pcall(source.accept, raw, request, reply)
            if not current(job) then finish(job, false, "Read staging owner changed"); return end
            if not staged or type(value) ~= "table" then finish(job, false, "Read source refused reply"); return end
            local committed, applied = pcall(source.commit, value)
            local failure
            if not committed or applied ~= true then failure = "Read attachment refused" end
            finish(job, committed and applied == true, failure)
        end)
        if not scheduled or accepted == false then finish(job, false, "Read scheduling refused"); return "blocked" end
        return "queued"
    end
    function result:Status()
        local copied = {closed = closed, active = active and active.id or nil, reasons = {}}
        for id, reason in pairs(reasons) do copied.reasons[id] = reason end
        return copied
    end
    function result:Close()
        if active then finish(active, false, "Read coordinator closed") end
        closed, enabled = true, {}
        budget:Close()
    end
    return result
end
return ReadCoordinator
