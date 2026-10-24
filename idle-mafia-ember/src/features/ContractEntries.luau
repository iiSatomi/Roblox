-- One earned daily/weekly Contract row; bonus claims are separate.
local ContractEntries = {}

function ContractEntries.propose(view, settings)
    if type(view) ~= "table" or type(settings) ~= "table" then
        return nil, "Missing Contract claim input"
    end
    if settings.enabled ~= true then return nil, "Contract claims disabled" end
    local row = type(view.ready) == "table" and view.ready[1]
    if type(row) ~= "table" or (row.period ~= "daily"
        and row.period ~= "weekly")
        or type(row.index) ~= "number" or row.index % 1 ~= 0
        or row.index < 1 or row.index > 5
        or type(row.rowId) ~= "string" or #row.rowId == 0
        or type(view.catalogKey) ~= "string" or #view.catalogKey == 0 then
        return nil, "No replicated ready Contract entry"
    end
    local reset = row.period == "daily" and view.dayReset or view.weekReset
    if type(reset) ~= "number" then return nil, "Missing Contract reset" end
    return {
        session = view.session, account = view.account,
        place = view.place, release = view.release,
        revision = view.revision, feature = "contracts",
        actionKey = "contract:" .. row.period .. ":" .. reset .. ":"
            .. row.index .. ":" .. #row.rowId .. ":" .. row.rowId,
        resources = {},
        intent = { kind = "contractEntryClaim", period = row.period,
            command = row.period == "daily" and "claim" or "claimweekly",
            index = row.index, rowId = row.rowId, reset = reset,
            catalogKey = view.catalogKey },
    }, nil
end

return ContractEntries
