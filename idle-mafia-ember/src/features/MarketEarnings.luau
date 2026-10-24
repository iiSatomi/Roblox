-- Opt-in collection of already-sold Black Market earnings only.
local MarketEarnings = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge and value % 1 == 0
end

function MarketEarnings.propose(view, settings)
    if type(view) ~= "table" or type(settings) ~= "table" then
        return nil, "Missing Market earnings input"
    end
    if settings.enabled ~= true then
        return nil, "Market earnings collection disabled"
    end
    local minimum = settings.minEarnings or 1
    if not integer(minimum, 1)
        or not integer(view.earnings, 1)
        or not integer(view.gold, 0)
        or not integer(view.revision, 0)
        or view.earnings < minimum then
        return nil, "Market earnings below collection minimum"
    end
    return { session = view.session, account = view.account,
        place = view.place, release = view.release,
        revision = view.revision, feature = "marketManage",
        actionKey = "market-collect:" .. view.revision .. ":" .. view.earnings,
        resources = {}, intent = { kind = "marketCollectEarnings",
            earningsBefore = view.earnings, goldBefore = view.gold } }, nil
end

return MarketEarnings
