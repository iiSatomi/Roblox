-- Collection owns surplus deposit UI, catalog and offline action proof.
local CollectionTab = {}
local Methods = {}
Methods.__index = Methods

function CollectionTab.BuildUI(section, feature, bind, numeric)
    assert(type(section) == "table" and type(feature) == "table"
        and feature.page == "collection"
        and feature.id == "collectionDonate"
        and type(bind) == "function" and type(numeric) == "table"
        and type(feature.policies) == "table"
        and type(feature.custom) == "table",
        "Invalid Collection UI feature")
    local group = section:Group({ Text = feature.label,
        Description = feature.description, Open = true })
    bind(group, "Toggle", feature.id .. ".enabled", {
        Text = "Allow " .. feature.label,
        Description = "Select this activity for the prototype.",
        Default = false, RevertOnClose = true, RevertTo = false,
    })
    if feature.limits then group:Description({ Text = feature.limits }) end
    local row = { feature = feature, tabOwned = true,
        status = group:Status({ Text = "Activity",
            Default = "Off — UI only" }) }
    row.custom = group:Group({ Text = "Deposit limits", Open = false })
    for _, field in ipairs(feature.custom) do
        assert(field.type == "number",
            "Invalid Collection custom control")
        local key = feature.id .. ".custom." .. field.id
        numeric[key] = true
        bind(row.custom, "Input", key, {
            Text = field.label, Default = tostring(field.value),
            FireOnBlur = true,
        })
    end
    return row
end

function CollectionTab.new(deps)
    assert(type(deps) == "table"
        and type(deps.NativeCollectionCatalog) == "table"
        and type(deps.NativeCollectionCatalog.new) == "function"
        and type(deps.CollectionDonate) == "table"
        and type(deps.CollectionDonate.read) == "function"
        and type(deps.CollectionDonate.propose) == "function"
        and type(deps.CollectionDonate.capture) == "function"
        and type(deps.CollectionDonate.evaluate) == "function",
        "Missing Collection modules")
    local catalog = deps.NativeCollectionCatalog.new(
        deps.gameData, deps.config, deps.fingerprint, deps.release)
    return setmetatable({ id = "collection", catalog = catalog,
        donate = deps.CollectionDonate }, Methods)
end

function Methods:Enrich(snapshot)
    return self.catalog:Enrich(snapshot)
end

function Methods:Descriptors()
    return { { id = "collectionDonate", reader = self.donate,
        planner = self.donate, evidence = self.donate } }
end

return CollectionTab
