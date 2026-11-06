-- Read-only requests for the shared Task 24 goal arbiter; never a sender.
local ContractGoalRequests = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge and value % 1 == 0
end

local function identity(view)
    if type(view) ~= "table" then return false end
    for _, key in ipairs({ "session", "account", "place", "release",
        "catalogKey" }) do
        if type(view[key]) ~= "string" or #view[key] == 0 then return false end
    end
    return integer(view.revision, 0)
        and integer(view.dayReset, 1)
        and integer(view.weekReset, 1)
        and type(view.rows) == "table"
end

local function same(a, b)
    for _, key in ipairs({ "session", "account", "place", "release",
        "catalogKey" }) do
        if a[key] ~= b[key] then return false end
    end
    return true
end

local function find(view, request)
    if type(view.rows) ~= "table" then return nil end
    for _, row in ipairs(view.rows) do
        if row.period == request.period and row.index == request.index
            and row.id == request.contractId and row.key == request.key then
            return row
        end
    end
    return nil
end

function ContractGoalRequests.derive(view, settings)
    if not identity(view) or type(settings) ~= "table" then
        return nil, "Current Contract goal snapshot required"
    end
    if settings.enabled ~= true then
        return { requests = {}, excluded = {} }, nil
    end
    local result = { requests = {}, excluded = {} }
    for _, row in ipairs(view.rows) do
        if type(row) ~= "table" or (row.period ~= "daily"
            and row.period ~= "weekly")
            or not integer(row.index, 1) or row.index > 5
            or type(row.id) ~= "string" or #row.id == 0
            or type(row.status) ~= "string" then
            return nil, "Invalid Contract goal row"
        end
        if row.status == "mapped" then
            local reset = row.period == "daily" and view.dayReset
                or view.weekReset
            local route, metric
            if (row.key == "jobs" or row.key == "energy")
                and settings.borrowJobs == true then
                route = { "jobs" }
                metric = row.key == "jobs" and "completedJobs"
                    or "jobEnergySpent"
            elseif row.key == "ops" and settings.borrowOperations == true
                and settings.borrowCollect == true then
                route = { "operations", "collect" }
                metric = "collectedOperations"
            elseif row.key == "hires" and settings.borrowHires == true then
                route = { "crewHire" }
                metric = "completedHires"
            elseif row.key == "heiststarts" and settings.borrowHeists == true then
                route = { "heists" }
                metric = "startedHeists"
            end
            if route and integer(row.progress, 0)
                and integer(row.goal, 1) and row.progress < row.goal then
                result.requests[#result.requests + 1] = {
                    session = view.session, account = view.account,
                    place = view.place, release = view.release,
                    revision = view.revision, catalogKey = view.catalogKey,
                    origin = "autoContracts", period = row.period,
                    index = row.index, contractId = row.id,
                    key = row.key, reset = reset, metric = metric,
                    progress = row.progress, goal = row.goal,
                    remaining = row.goal - row.progress,
                    routes = route,
                }
            else
                result.excluded[#result.excluded + 1] = {
                    period = row.period, index = row.index, id = row.id,
                    key = row.key, reason = route and "Invalid progress"
                        or "No explicit borrowing route" }
            end
        elseif row.status == "blocked" or row.status == "unsupported" then
            result.excluded[#result.excluded + 1] = {
                period = row.period, index = row.index, id = row.id,
                key = row.key, reason = row.reason }
        end
    end
    return result, nil
end

function ContractGoalRequests.observe(before, after, request)
    if not identity(before) or not identity(after)
        or type(request) ~= "table" or not same(before, after)
        or not same(before, request)
        or after.revision <= before.revision
        or request.revision ~= before.revision
        or request.origin ~= "autoContracts"
        or request.reset ~= (request.period == "daily"
            and before.dayReset or before.weekReset)
        or request.reset ~= (request.period == "daily"
            and after.dayReset or after.weekReset) then
        return "pending"
    end
    local prior, current = find(before, request), find(after, request)
    if not prior or not current or not integer(prior.progress, 0)
        or not integer(current.progress, 0)
        or prior.progress ~= request.progress then return "pending" end
    if current.status == "complete" and current.progress >= request.goal then
        return "complete"
    end
    if current.progress > prior.progress
        and current.progress <= request.goal then return "progressed" end
    return "pending"
end

return ContractGoalRequests
