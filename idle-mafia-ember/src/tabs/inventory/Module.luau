-- Inventory owns its three independent, inert controls and feature descriptors.
local InventoryTab = {}
local Methods = {}
Methods.__index = Methods

local known = { restoratives = true, chests = true,
    cosmetics = true }
local blocked = {
}

function InventoryTab.BuildUI(section, feature, bind, numeric)
    assert(type(section) == "table" and type(feature) == "table"
        and feature.page == "inventory" and known[feature.id]
        and type(bind) == "function" and type(numeric) == "table"
        and type(feature.policies) == "table"
        and type(feature.custom) == "table", "Invalid Inventory UI feature")
    local group = section:Group({ Text = feature.label,
        Description = feature.description, Open = true })
    bind(group, "Toggle", feature.id .. ".enabled", {
        Text = "Allow " .. feature.label,
        Description = "Select this activity; the status below shows whether this entry can run it.",
        Default = false, RevertOnClose = true, RevertTo = false,
    })
    if #feature.policies > 0 then
        bind(group, "Dropdown", feature.id .. ".policy", {
            Text = "Goal", Options = feature.policies,
            Default = feature.policies[1],
        })
    end
    if feature.limits then group:Description({ Text = feature.limits }) end
    local reason = blocked[feature.id]
    local row = { feature = feature, tabOwned = true,
        blockedReason = reason and ("Unavailable: " .. reason) or nil,
        status = group:Status({ Text = "Activity",
            Default = reason and ("Blocked — " .. reason)
                or "Off — UI only" }) }
    if #feature.custom > 0 then
        row.custom = group:Group({ Text = "Custom limits", Open = false })
        for _, field in ipairs(feature.custom) do
            local key = feature.id .. ".custom." .. field.id
            if field.type == "number" then
                numeric[key] = true
                bind(row.custom, "Input", key, {
                    Text = field.label, Default = tostring(field.value),
                    FireOnBlur = true,
                })
            else
                assert(field.type == "select" and type(field.options) == "table",
                    "Invalid Inventory custom field")
                bind(row.custom, "Dropdown", key, {
                    Text = field.label, Default = field.value,
                    Options = field.options,
                })
            end
        end
    end
    return row
end

function InventoryTab.new(deps)
    assert(type(deps) == "table" and type(deps.Restoratives) == "table"
        and type(deps.Restoratives.read) == "function"
        and type(deps.Restoratives.propose) == "function"
        and type(deps.Restoratives.capture) == "function"
        and type(deps.Restoratives.evaluate) == "function"
        and type(deps.NativeRestorativeCatalog) == "table"
        and type(deps.NativeRestorativeCatalog.new) == "function"
        and type(deps.Chests) == "table"
        and type(deps.Chests.read) == "function"
        and type(deps.Chests.propose) == "function"
        and type(deps.Chests.capture) == "function"
        and type(deps.Chests.evaluate) == "function"
        and type(deps.NativeCrateCatalog) == "table"
        and type(deps.NativeCrateCatalog.new) == "function"
        and type(deps.Cosmetics) == "table"
        and type(deps.Cosmetics.new) == "function",
        "Missing Inventory restorative module")
    local catalog = deps.NativeRestorativeCatalog.new(
        deps.gameData, deps.config, deps.fingerprint, deps.release)
    local crates = deps.NativeCrateCatalog.new(
        deps.gameData, deps.config, deps.fingerprint, deps.release)
    local cosmetics = deps.Cosmetics.new(
        deps.gameData, deps.fingerprint, deps.release)
    return setmetatable({ id = "inventory",
        restoratives = deps.Restoratives,
        chests = deps.Chests,
        cosmetics = cosmetics,
        restorativeCatalog = catalog,
        crateCatalog = crates }, Methods)
end

function Methods:Enrich(snapshot)
    local restored, reason = self.restorativeCatalog:Enrich(snapshot)
    if not restored then return nil, reason end
    local crated, crateReason = self.crateCatalog:Enrich(restored)
    if not crated then return nil, crateReason end
    local result = {}
    for key, value in pairs(crated) do result[key] = value end
    result.cosmeticSourceKey = self.cosmetics.sourceKey
    return result, nil
end

function Methods:Descriptors()
    return { { id = "restoratives", reader = self.restoratives,
        planner = self.restoratives, evidence = self.restoratives },
        { id = "chests", reader = self.chests,
            planner = self.chests, evidence = self.chests },
        { id = "cosmetics", reader = self.cosmetics,
            planner = self.cosmetics, evidence = self.cosmetics } }
end

return InventoryTab
