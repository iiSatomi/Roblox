-- One ordinary settled-reward claim per exact event run.
local GlobalBossClaim = {}

function GlobalBossClaim.propose(view, settings)
    if type(view) ~= "table" or type(settings) ~= "table" then
        return nil, "Missing Global Boss claim planning input"
    end
    if settings.enabled ~= true then
        return nil, "Global Boss claim disabled"
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
            runKey = view.runKey, attemptsBefore = 0 } }, nil
end

return GlobalBossClaim
