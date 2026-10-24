-- One chosen cash offer; Gold purchases and native Auto Buy stay separate.
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
        Description = "Select this activity for the prototype.",
        Default = false, RevertOnClose = true, RevertTo = false,
    })
    if feature.limits then group:Description({ Text = feature.limits }) end
    local row = { feature = feature, tabOwned = true,
        status = group:Status({ Text = "Activity",
            Default = "Off — UI only" }) }
    row.custom = group:Group({ Text = "Selected cash offer", Open = false })
    for _, field in ipairs(feature.custom) do
        local key = "shop.custom." .. field.id
        if field.type == "number" then
            numeric[key] = true
            bind(row.custom, "Input", key, {
                Text = field.label, Default = tostring(field.value),
                FireOnBlur = true,
            })
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
        deps.gameData, deps.fingerprint, deps.release)
    return setmetatable({ id = "shop", deps = deps,
        catalog = catalog }, Methods)
end

function Methods:Enrich(snapshot)
    return self.catalog:Enrich(snapshot)
end

function Methods:Descriptors()
    local d = self.deps
    return { { id = "shop", reader = d.ShopState,
        planner = d.ShopBuy, evidence = d.ShopBuyEvidence } }
end

return ShopTab
