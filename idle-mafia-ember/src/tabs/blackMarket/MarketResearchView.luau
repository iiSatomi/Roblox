-- Bounded, read-only explanation; incomplete native replies never yield quotes.
local MarketResearchView = {}

local function finite(value)
    return type(value) == "number" and value == value
        and value >= 0 and value < math.huge
end

function MarketResearchView.assess(browse, rapByItem,
    historyByItem, itemsById, termsByItem, settings, now, watch)
    if type(browse) ~= "table"
        or not (browse.kind == "all" and browse.arg == nil
            or browse.kind == "item" and type(browse.arg) == "string" and #browse.arg > 0 and #browse.arg <= 120)
        or type(browse.more) ~= "boolean"
        or (browse.stale ~= nil and type(browse.stale) ~= "boolean")
        or (browse.small ~= nil and type(browse.small) ~= "boolean")
        or type(browse.rows) ~= "table" or #browse.rows > 500
        or not finite(browse.capturedAt)
        or not finite(now) or browse.capturedAt > now + 1
        or now - browse.capturedAt > 15
        or type(rapByItem) ~= "table"
        or type(historyByItem) ~= "table"
        or type(itemsById) ~= "table"
        or type(termsByItem) ~= "table"
        or type(settings) ~= "table"
        or type(watch) ~= "table"
        or type(watch.assess) ~= "function" then
        return nil, "Complete fresh Market research required"
    end
    local count = 0
    for key in pairs(browse.rows) do
        if type(key) ~= "number" or key % 1 ~= 0
            or key < 1 or key > #browse.rows then
            return nil, "Sparse Market research rows"
        end
        count = count + 1
    end
    if count ~= #browse.rows then
        return nil, "Sparse Market research rows"
    end
    local accepted, rejected, seen = {}, {}, {}
    local complete = browse.more == false and browse.stale ~= true and browse.small ~= true
    local evaluated = math.min(#browse.rows, 100)
    for index = 1, evaluated do
        local row = browse.rows[index]
        if type(row) ~= "table"
            or type(row.item) ~= "string"
            or #row.item == 0 or #row.item > 120
            or (browse.kind == "item" and row.item ~= browse.arg)
            or row.id == nil or seen[tostring(row.id)] then
            return nil, "Invalid Market research listing"
        end
        seen[tostring(row.id)] = true
        local id = row.item
        local quote, reason
        if complete then
            quote, reason = watch.assess(browse, row.id,
                rapByItem[id], historyByItem[id], itemsById[id],
                termsByItem[id], settings, now)
        else reason = "Market browse is incomplete; quotes withheld" end
        if quote then
            accepted[#accepted + 1] = {
                listingId = quote.listingId, itemId = quote.itemId,
                buy = quote.buy, ask = quote.ask,
                margin = quote.margin, capturedAt = quote.capturedAt }
        else
            rejected[#rejected + 1] = { listingId = row.id,
                itemId = id, reason = reason or "Unknown research result" }
        end
    end
    table.sort(accepted, function(a, b)
        if a.margin ~= b.margin then return a.margin > b.margin end
        return tostring(a.listingId) < tostring(b.listingId)
    end)
    -- Presentation remains bounded even if a page contains many candidates.
    local shown, refused = {}, {}
    for index = 1, math.min(#accepted, 50) do
        shown[index] = accepted[index]
    end
    for index = 1, math.min(#rejected, 50) do
        refused[index] = rejected[index]
    end
    return { readOnly = true, paginationComplete = complete,
        capturedAt = browse.capturedAt,
        totalRows = #browse.rows, evaluated = evaluated,
        truncated = not complete or #browse.rows > evaluated
            or #accepted > #shown or #rejected > #refused,
        opportunities = shown, rejected = refused,
        opportunityCount = #accepted,
        rejectedCount = #rejected }, nil
end

return MarketResearchView
