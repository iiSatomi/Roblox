-- Source-ordered cash offers; Gold purchases and native Auto Buy stay separate.
local ShopTab = {}
local Methods = {}
Methods.__index = Methods

function ShopTab.BuildUI(section, feature, bind, numeric)
    assert(type(section) == "table" and type(feature) == "table"
        and feature.page == "shop" and feature.id == "shop"
        and type(bind) == "function" and type(numeric) == "table"
        and type(feature.custom) == "table",
        "Invalid Shop UI feature")
    local group = section:Group({ Text = feature.label,
        Description = feature.description, Open = true })
    bind(group, "Toggle", "shop.enabled", {
        Text = "Allow " .. feature.label,
        Description = "Select this activity; the status below shows whether this entry can run it.",
        Default = false, RevertOnClose = true, RevertTo = false,
    })
    if feature.limits then group:Description({ Text = feature.limits }) end
    local row = { feature = feature, tabOwned = true,
        status = group:Status({ Text = "Activity",
            Default = "Off — UI only" }) }
    row.custom = group:Group({ Text = "Cash selection and limits", Open = false })
    for _, field in ipairs(feature.custom) do
        local key = "shop.custom." .. field.id
        if field.type == "number" then
            numeric[key] = true
            bind(row.custom, "Input", key, {
                Text = field.label, Default = tostring(field.value),
                FireOnBlur = true,
            })
        elseif field.type == "boolean" then
            bind(row.custom, "Toggle", key, { Text = field.label, Default = field.value })
        elseif field.type == "select" then
            bind(row.custom, "Dropdown", key, { Text = field.label,
                Options = field.options, Default = field.value })
        else
            assert(field.type == "text", "Invalid Shop control")
            bind(row.custom, "Input", key, {
                Text = field.label, Default = field.value,
                FireOnBlur = true,
            })
        end
    end
    return row
end

function ShopTab.new(deps)
    assert(type(deps) == "table"
        and type(deps.NativeShopCatalog) == "table"
        and type(deps.NativeShopCatalog.new) == "function"
        and type(deps.ShopState) == "table"
        and type(deps.ShopState.read) == "function"
        and type(deps.ShopBuy) == "table"
        and type(deps.ShopBuy.propose) == "function"
        and type(deps.ShopBuyEvidence) == "table"
        and type(deps.ShopBuyEvidence.capture) == "function"
        and type(deps.ShopBuyEvidence.evaluate) == "function",
        "Missing Shop tab modules")
    local catalog = deps.NativeShopCatalog.new(
        deps.gameData, deps.fingerprint, deps.release, deps.config)
    return setmetatable({ id = "shop", deps = deps,
        catalog = catalog, clock = deps.clock, closed = false }, Methods)
end

function Methods:Enrich(snapshot)
    if self.closed then return nil, "Shop tab closed" end
    return self.catalog:Enrich(snapshot)
end

function Methods:Close() self.closed = true end

function Methods:Descriptors()
    local d = self.deps
    return { { id = "shop", reader = d.ShopState,
        planner = d.ShopBuy, evidence = d.ShopBuyEvidence,
        recoverSaved = d.ShopBuyEvidence.recoverSaved,
        canDispatch = function(proposal)
            local i = proposal.intent
            if self.closed or type(self.clock) ~= "table" or type(self.clock.Now) ~= "function"
                or type(i.quoteServerNow) ~= "number" or type(i.quoteCapturedAt) ~= "number"
                or type(i.quoteExpires) ~= "number" then return false end
            local elapsed = self.clock:Now() - i.quoteCapturedAt
            return elapsed >= 0 and elapsed <= 2 and i.quoteServerNow + elapsed <= i.quoteExpires - 5
        end } }
end

return ShopTab
