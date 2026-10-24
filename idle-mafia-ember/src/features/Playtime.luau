-- One earned native ladder index from complete replicated readiness.
local Playtime = {}

function Playtime.propose(view, settings)
    if type(view) ~= "table" or type(settings) ~= "table" then
        return nil, "Missing playtime claim input"
    end
    if settings.enabled ~= true then return nil, "Playtime claims disabled" end
    if type(view.ready) ~= "table" or type(view.catalogKey) ~= "string"
        or #view.catalogKey == 0 or type(view.today) ~= "number" then
        return nil, "Invalid playtime view"
    end
    local selected = view.ready[1]
    if type(selected) ~= "table" or type(selected.index) ~= "number"
        or selected.index % 1 ~= 0 or selected.index < 1
        or selected.index > 7 or type(selected.rewardKind) ~= "string" then
        return nil, "No replicated ready ladder reward"
    end
    return {
        session = view.session, account = view.account,
        place = view.place, release = view.release,
        revision = view.revision, feature = "playtime",
        actionKey = "playtime:" .. view.today .. ":" .. #view.catalogKey
            .. ":" .. view.catalogKey .. ":" .. selected.index,
        resources = {},
        intent = { kind = "playtimeClaim", index = selected.index,
            day = view.today, rewardKind = selected.rewardKind,
            catalogKey = view.catalogKey },
    }, nil
end

return Playtime
