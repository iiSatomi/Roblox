-- Only catalog-proven non-consuming earned rewards are supported.
local EarnedTrophies = {}

function EarnedTrophies.propose(view, settings)
    if type(view) ~= "table" or type(settings) ~= "table" then
        return nil, "Missing earned Trophy input"
    end
    if settings.enabled ~= true then return nil, "Earned Trophies disabled" end
    if type(view.eligible) ~= "table" or type(view.catalogKey) ~= "string"
        or #view.catalogKey == 0 then return nil, "Invalid Trophy view" end
    local id = view.eligible[1]
    if type(id) ~= "string" or #id == 0 then
        return nil, "No proven earned Trophy ready"
    end
    return {
        session = view.session, account = view.account,
        place = view.place, release = view.release,
        revision = view.revision, feature = "trophies",
        actionKey = "earnedTrophy:" .. #view.catalogKey .. ":"
            .. view.catalogKey .. ":" .. id,
        resources = {},
        intent = { kind = "earnedTrophyClaim", targetId = id,
            catalogKey = view.catalogKey },
    }, nil
end

return EarnedTrophies
