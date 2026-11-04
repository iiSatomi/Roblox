-- Read-only selected Trophy goal request for the shared Task 24 arbiter.
local TrophyGoalRequests = {}

local borrow = {
    level = { setting = "borrowJobs", route = "jobs" },
    mastery = { setting = "borrowJobs", route = "jobs" },
    property = { setting = "borrowProperties", route = "properties" },
    operations = { setting = "borrowOperations", route = "operations" },
    banking = { setting = "borrowBanking", route = "bank" },
    heist = { setting = "borrowHeists", route = "heists" },
}

local function identity(view)
    if type(view) ~= "table" or type(view.byId) ~= "table"
        or type(view.revision) ~= "number" or view.revision < 0
        or view.revision % 1 ~= 0 then return false end
    for _, key in ipairs({ "session", "account", "place", "release",
        "catalogKey" }) do
        if type(view[key]) ~= "string" or #view[key] == 0 then return false end
    end
    return true
end

local function same(a, b)
    for _, key in ipairs({ "session", "account", "place", "release",
        "catalogKey" }) do
        if a[key] ~= b[key] then return false end
    end
    return true
end

function TrophyGoalRequests.derive(view, settings)
    if not identity(view) or type(settings) ~= "table" then
        return nil, "Current Trophy goal snapshot required"
    end
    local result = { requests = {}, excluded = {} }
    if settings.enabled ~= true then return result, nil end
    local id = settings.goalId
    if type(id) ~= "string" or #id == 0 or #id > 120 then
        return nil, "Select a current Trophy ID"
    end
    local row = view.byId[id]
    if type(row) ~= "table" or row.id ~= id then
        return nil, "Selected Trophy absent from current catalog"
    end
    result.status, result.targetId = row.status, id
    if row.status == "ready" then
        result.requests[1] = {session = view.session, account = view.account, place = view.place,
            release = view.release, revision = view.revision, catalogKey = view.catalogKey,
            origin = "trophyFocus", targetId = id, status = "ready", routes = {"trophies"}}
        return result, nil
    end
    if row.status ~= "notReady" then
        result.excluded[1] = { id = id, reason = row.status }
        return result, nil
    end
    if (row.route == "mastery" or row.route == "property") and type(row.goal) ~= "table" then
        result.excluded[1] = {id = id, reason = "Target-specific reviewed Job/property catalog unavailable"}
        return result, nil
    end
    local path = borrow[row.route]
    if not path or settings[path.setting] ~= true then
        result.excluded[1] = { id = id,
            reason = "No explicit ordinary route borrowing" }
        return result, nil
    end
    result.requests[1] = {
        session = view.session, account = view.account,
        place = view.place, release = view.release,
        revision = view.revision, catalogKey = view.catalogKey,
        origin = "trophyFocus", targetId = id,
        status = row.status, goal = row.goal,
        routes = row.route == "operations" and {"operations", "collect"}
            or row.route == "heist" and {"heists", "heistCollect"} or { path.route },
    }
    return result, nil
end

function TrophyGoalRequests.observe(before, after, request)
    if not identity(before) or not identity(after)
        or type(request) ~= "table" or not same(before, after)
        or not same(before, request)
        or request.origin ~= "trophyFocus"
        or request.revision ~= before.revision
        or after.revision <= before.revision then return "pending" end
    local prior = before.byId[request.targetId]
    local current = after.byId[request.targetId]
    if type(prior) ~= "table" or type(current) ~= "table"
        or prior.id ~= request.targetId
        or current.id ~= request.targetId
        or (prior.status ~= "notReady" and prior.status ~= "ready") then return "pending" end
    if current.status == "owned" then return "owned" end
    if current.status == "ready" then return "ready" end
    return "pending"
end

local function includes(goal, id)
    if type(goal)~="table" or type(goal.ids)~="table" or #goal.ids==0 or #goal.ids>256 then return false end
    for _, key in ipairs(goal.ids) do if key==id then return true end end
    return false
end
local function remaining(raw, request, feature, id)
    local goal=request.goal
    if not includes(goal,id) then return false end
    if feature=="jobs" and goal.kind=="mastery" then
        local row=type(raw.native.jobs)=="table" and raw.native.jobs[id]
        local tier=type(row)=="table" and row.masteryTier or 0
        return type(goal.goldTier)=="number" and type(tier)=="number" and tier%1==0 and tier>=0 and tier<goal.goldTier
    elseif feature=="properties" then
        local row=type(raw.native.properties)=="table" and raw.native.properties[id]
        local count=type(row)=="table" and row.owned or 0
        if type(count)~="number" or count%1~=0 or count<0 then return false end
        if goal.kind=="property" then return count==0 end
        if goal.kind=="propertyCount" then
            local total=0
            for _, propId in ipairs(goal.ids) do
                local prop=raw.native.properties[propId]
                local owned=prop and prop.owned or 0
                if type(owned)~="number" or owned%1~=0 or owned<0 then return false end
                total=total+owned
            end
            return total<10
        end
    end
    return false
end
-- Ask the existing ordinary planner to choose within the exact remaining target set.
function TrophyGoalRequests.propose(raw, context, request, spec, settings, reservations)
    if spec.id~="trophies" and (type(request.goal)~="table" or (spec.id~="jobs" and spec.id~="properties")) then return nil end
    local view=spec.reader.read(raw,context)
    if not view then return nil end
    local field=spec.id=="trophies" and "eligible" or spec.id=="jobs" and "jobs" or "options"
    local filtered={}
    for key,value in pairs(view) do filtered[key]=value end
    filtered[field]={}
    for _,row in ipairs(view[field] or {}) do
        if spec.id=="trophies" and row==request.targetId or spec.id~="trophies" and remaining(raw,request,spec.id,row.id) then
            filtered[field][#filtered[field]+1]=row
        end
    end
    return spec.planner.propose(filtered,settings,reservations)
end
function TrophyGoalRequests.canUseProposal(raw, request, proposal)
    if proposal.feature == "trophies" then return proposal.intent.targetId == request.targetId end
    if request.goal then
        return remaining(raw,request,proposal.feature,proposal.intent.targetId or proposal.intent.propId)
    end
    if proposal.feature ~= "jobs" then return true end
    for _, row in ipairs(type(raw.jobCatalog) == "table" and raw.jobCatalog or {}) do
        if row.id == proposal.intent.targetId then
            return type(row.xp) == "number" and row.xp > 0 and row.xp < math.huge
        end
    end
    return false
end
return TrophyGoalRequests
