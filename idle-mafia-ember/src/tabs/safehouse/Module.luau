-- Next-tier Safehouse upgrades only; no auto spending outside its switch.
local SafehouseTab = {}
local Methods = {}
Methods.__index = Methods

function SafehouseTab.BuildUI(section, feature, bind, numeric)
    assert(type(section) == "table" and type(feature) == "table"
        and feature.page == "safehouse" and feature.id == "safehouse"
        and type(bind) == "function" and type(numeric) == "table"
        and type(feature.custom) == "table",
        "Invalid Safehouse UI feature")
    local group = section:Group({ Text = feature.label,
        Description = feature.description, Open = true })
    bind(group, "Toggle", "safehouse.enabled", {
        Text = "Allow " .. feature.label,
        Description = "Select this activity; the status below shows whether this entry can run it.",
        Default = false, RevertOnClose = true, RevertTo = false,
    })
    if feature.limits then group:Description({ Text = feature.limits }) end
    local row = { feature = feature, tabOwned = true,
        status = group:Status({ Text = "Activity",
            Default = "Off — UI only" }) }
    row.custom = group:Group({ Text = "Upgrade limits", Open = false })
    for _, field in ipairs(feature.custom) do
        assert(field.type == "number", "Invalid Safehouse limit")
        local key = "safehouse.custom." .. field.id
        numeric[key] = true
        bind(row.custom, "Input", key, {
            Text = field.label, Default = tostring(field.value),
            FireOnBlur = true,
        })
    end
    return row
end

function SafehouseTab.new(deps)
    assert(type(deps) == "table"
        and type(deps.SafehouseState) == "table"
        and type(deps.SafehouseState.read) == "function"
        and type(deps.SafehouseUpgrades) == "table"
        and type(deps.SafehouseUpgrades.propose) == "function"
        and type(deps.SafehouseUpgradesEvidence) == "table"
        and type(deps.SafehouseUpgradesEvidence.capture) == "function"
        and type(deps.SafehouseUpgradesEvidence.evaluate) == "function"
        and type(deps.NativeSafehouseCatalog) == "table"
        and type(deps.NativeSafehouseCatalog.new) == "function",
        "Missing Safehouse tab modules")
    local catalog = deps.NativeSafehouseCatalog.new(
        deps.config, deps.fingerprint, deps.release)
    return setmetatable({ id = "safehouse", deps = deps,
        catalog = catalog }, Methods)
end

function Methods:Enrich(snapshot)
    return self.catalog:Enrich(snapshot)
end

function Methods:Descriptors()
    local d = self.deps
    return { { id = "safehouse", reader = d.SafehouseState,
        planner = d.SafehouseUpgrades,
        evidence = d.SafehouseUpgradesEvidence } }
end

return SafehouseTab
