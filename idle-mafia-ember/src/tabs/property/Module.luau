-- Ordinary no-slot Property builds; replacement is a later separate function.
local PropertyTab = {}
local Methods = {}
Methods.__index = Methods

function PropertyTab.BuildUI(section, feature, bind, numeric)
    assert(type(section) == "table" and type(feature) == "table"
        and feature.page == "property" and feature.id == "properties"
        and type(bind) == "function" and type(numeric) == "table"
        and type(feature.policies) == "table"
        and type(feature.custom) == "table",
        "Invalid Property UI feature")
    local group = section:Group({ Text = feature.label,
        Description = feature.description, Open = true })
    bind(group, "Toggle", "properties.enabled", {
        Text = "Allow " .. feature.label,
        Description = "Select this activity; the status below shows whether this entry can run it.",
        Default = false, RevertOnClose = true, RevertTo = false,
    })
    bind(group, "Dropdown", "properties.policy", {
        Text = "Goal", Options = feature.policies,
        Default = feature.policies[1],
    })
    if feature.limits then group:Description({ Text = feature.limits }) end
    local row = { feature = feature, tabOwned = true,
        status = group:Status({ Text = "Activity",
            Default = "Off — UI only" }) }
    row.custom = group:Group({ Text = "Build limits", Open = false })
    for _, field in ipairs(feature.custom) do
        assert(field.type == "number", "Invalid Property limit")
        local key = "properties.custom." .. field.id
        numeric[key] = true
        bind(row.custom, "Input", key, {
            Text = field.label, Default = tostring(field.value),
            FireOnBlur = true,
        })
    end
    return row
end

function PropertyTab.new(deps)
    assert(type(deps) == "table"
        and type(deps.PropertiesState) == "table"
        and type(deps.PropertiesState.read) == "function"
        and type(deps.Properties) == "table"
        and type(deps.Properties.propose) == "function"
        and type(deps.PropertiesEvidence) == "table"
        and type(deps.PropertiesEvidence.capture) == "function"
        and type(deps.PropertiesEvidence.evaluate) == "function"
        and type(deps.NativePropertyCatalog) == "table"
        and type(deps.NativePropertyCatalog.new) == "function",
        "Missing Property tab modules")
    local catalog = deps.NativePropertyCatalog.new(
        deps.gameData, deps.config, deps.fingerprint, deps.release)
    return setmetatable({ id = "property", deps = deps,
        catalog = catalog }, Methods)
end

function Methods:Enrich(snapshot)
    return self.catalog:Enrich(snapshot)
end

function Methods:Descriptors()
    local d = self.deps
    return { { id = "properties", reader = d.PropertiesState,
        planner = d.Properties, evidence = d.PropertiesEvidence } }
end

return PropertyTab
