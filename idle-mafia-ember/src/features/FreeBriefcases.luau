-- Free-only Briefcase pick; no key use, buying or prize prediction.
local FreeBriefcases = {}

function FreeBriefcases.propose(view, settings)
    if type(view) ~= "table" or type(settings) ~= "table" then
        return nil, "Missing Briefcase pick input"
    end
    if settings.enabled ~= true then return nil, "Free Briefcases disabled" end
    if type(view.index) ~= "number" or view.index % 1 ~= 0
        or view.index < 1 or view.index > 12
        or type(view.free) ~= "number" or view.free < 1
        or type(view.season) ~= "number" or view.season < 1
        or type(view.board) ~= "number" or view.board < 1
        or type(view.endAt) ~= "number" or view.endAt < 1
        or type(view.catalogKey) ~= "string" or #view.catalogKey == 0 then
        return nil, "No replicated free Briefcase pick"
    end
    return { session = view.session, account = view.account,
        place = view.place, release = view.release,
        revision = view.revision, feature = "briefcases",
        actionKey = "briefcase-free:" .. view.season .. ":"
            .. view.board .. ":" .. view.index,
        resources = {},
        intent = { kind = "freeBriefcasePick", command = "open",
            index = view.index, season = view.season, board = view.board,
            free = view.free, endAt = view.endAt,
            catalogKey = view.catalogKey },
    }, nil
end

return FreeBriefcases
