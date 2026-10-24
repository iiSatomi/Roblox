-- Pure earned Operation collection choice; current native array index only.
local OperationsCollect = {}

local function nonempty(value)
    return type(value) == "string" and #value > 0
end

function OperationsCollect.propose(view, settings)
    if type(view) ~= "table" or type(settings) ~= "table" then
        return nil, "Missing Operation collection input"
    end
    if settings.enabled ~= true then return nil, "Operation collection disabled" end
    for _, field in ipairs({ "session", "account", "place", "release",
        "catalogKey" }) do
        if not nonempty(view[field]) then return nil, "Invalid Operation identity" end
    end
    if type(view.revision) ~= "number" or view.revision < 0
        or view.revision % 1 ~= 0 or type(view.active) ~= "table" then
        return nil, "Invalid Operation collection view"
    end
    for index, entry in ipairs(view.active) do
        if type(entry) ~= "table" or not nonempty(entry.opId)
            or type(entry.remaining) ~= "number" then
            return nil, "Invalid active Operation"
        end
        if entry.remaining <= 0 then
            local key = "collect:" .. #view.catalogKey .. ":" .. view.catalogKey
                .. ":" .. index .. ":" .. #entry.opId .. ":" .. entry.opId
                .. ":" .. view.revision
            return {
                session = view.session, account = view.account,
                place = view.place, release = view.release,
                revision = view.revision, feature = "collect", actionKey = key,
                resources = {}, intent = { kind = "operationCollect",
                    index = index, targetId = entry.opId,
                    catalogKey = view.catalogKey },
            }, nil
        end
    end
    return nil, "No replicated ready Operation"
end

return OperationsCollect
