-- Read-only Market research and earned payout, with Gold trades blocked.
local BlackMarketTab = {}
local Methods = {}
Methods.__index = Methods

local blocked = {
    marketWatch = "Read-only research needs the current-client query scheduler",
    marketSell = "Listing moves inventory into a sale; separate custody consent required",
    marketFlip = "Buying and reselling spends Gold; separate budget consent required",
    marketRent = "Rent spends Gold over time; separate budget consent required",
}
local known = { marketWatch = true, marketSell = true,
    marketFlip = true, marketRent = true, marketManage = true }

function BlackMarketTab.BuildUI(section, feature, bind)
    assert(type(section) == "table" and type(feature) == "table"
        and feature.page == "blackMarket" and known[feature.id]
        and type(bind) == "function",
        "Invalid Black Market UI feature")
    local group = section:Group({ Text = feature.label,
        Description = feature.description, Open = true })
    bind(group, "Toggle", feature.id .. ".enabled", {
        Text = "Allow " .. feature.label,
        Description = "Select this activity for the prototype.",
        Default = false, RevertOnClose = true, RevertTo = false,
    })
    local reason = blocked[feature.id]
    if reason then group:Description({ Text = reason }) end
    return { feature = feature, tabOwned = true,
        blockedReason = reason,
        status = group:Status({ Text = "Activity",
            Default = reason and "Blocked — " .. reason
                or "Off — UI only" }) }
end

function BlackMarketTab.new(deps)
    assert(type(deps) == "table"
        and type(deps.MarketEarningsState) == "table"
        and type(deps.MarketEarningsState.read) == "function"
        and type(deps.MarketEarnings) == "table"
        and type(deps.MarketEarnings.propose) == "function"
        and type(deps.MarketEarningsEvidence) == "table"
        and type(deps.MarketEarningsEvidence.capture) == "function"
        and type(deps.MarketEarningsEvidence.evaluate) == "function"
        and type(deps.MarketBrowse) == "table"
        and type(deps.MarketBrowse.new) == "function"
        and type(deps.MarketPrices) == "table"
        and type(deps.MarketPrices.new) == "function"
        and type(deps.MarketReadRuntime) == "table"
        and type(deps.MarketReadRuntime.new) == "function"
        and type(deps.MarketBlocked) == "table"
        and type(deps.MarketBlocked.watch) == "table"
        and type(deps.MarketBlocked.trade) == "table",
        "Missing Black Market tab modules")
    return setmetatable({ id = "blackMarket", deps = deps }, Methods)
end

function Methods:NewResearch(budget, executor, clock, onResult)
    local d = self.deps
    return d.MarketReadRuntime.new(budget,
        d.MarketBrowse.new(5), d.MarketPrices.new(clock),
        executor, onResult)
end

function Methods:Descriptors()
    local d = self.deps
    return {
        { id = "marketWatch", reader = d.MarketBlocked.watch,
            planner = d.MarketBlocked.watch, evidence = d.MarketBlocked.watch },
        { id = "marketSell", reader = d.MarketBlocked.trade,
            planner = d.MarketBlocked.trade, evidence = d.MarketBlocked.trade },
        { id = "marketFlip", reader = d.MarketBlocked.trade,
            planner = d.MarketBlocked.trade, evidence = d.MarketBlocked.trade },
        { id = "marketRent", reader = d.MarketBlocked.trade,
            planner = d.MarketBlocked.trade, evidence = d.MarketBlocked.trade },
        { id = "marketManage", reader = d.MarketEarningsState,
        planner = d.MarketEarnings,
        evidence = d.MarketEarningsEvidence },
    }
end

return BlackMarketTab
