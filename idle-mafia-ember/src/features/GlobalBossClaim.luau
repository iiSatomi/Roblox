-- One ordinary settled-reward claim per exact event run.
local GlobalBossClaim = {}

function GlobalBossClaim.propose(view, settings)
    if type(view) ~= "table" or type(settings) ~= "table" then
        return nil, "Missing Global Boss claim planning input"
    end
    if settings.enabled ~= true then
        return nil, "Global Boss claim disabled"
    end
    local cap = settings.maxPerLoad == nil and 1 or settings.maxPerLoad
    local limited = settings.useLoadCap == true
    if type(cap)~="number" or cap~=cap or cap<0 or cap>10
        or settings.useLoadCap~=nil and type(settings.useLoadCap)~="boolean" then return nil,"Invalid Global claim load cap" end
    local load=view.loadUsage
    if limited and type(load)~="table" then return nil,"Current Global load usage required" end
    if type(load)=="table" then
        if type(load.claimAttempts)~="number" or load.claimAttempts~=load.claimAttempts
            or load.claimAttempts<0 or load.claimAttempts%1~=0 then return nil,"Invalid Global claim load usage" end
        if limited and load.claimAttempts>=cap then return nil,"Global Boss claim per-load send cap reached" end
    end
    if view.status ~= "known" or view.phase ~= "done"
        or view.claimable ~= true
        or type(view.runKey) ~= "string" or #view.runKey == 0
        or #view.runKey > 120
        or view.attempts ~= 0 then
        return nil, "No unclaimed participated Global Boss result"
    end
    return { session = view.session, account = view.account,
        place = view.place, release = view.release,
        revision = view.revision, feature = "globalBossClaim",
        actionKey = "globalBossClaim:" .. view.runKey,
        resources = {}, intent = { kind = "globalBossClaim",
            runKey = view.runKey, attemptsBefore = 0, useLoadCap=limited, maxPerLoad=cap,
            loadCountBefore=type(load)=="table" and load.claimAttempts or nil } }, nil
end

return GlobalBossClaim
