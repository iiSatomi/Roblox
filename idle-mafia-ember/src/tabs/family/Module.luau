-- Distinct Family spending controls; only read-only info is staged.
local FamilyTab = {}
local Methods = {}
Methods.__index = Methods

local blocked = {
    familyCash = "Cash donation transfers to shared Family vault; separate consent required",
    familyStamina = "Stamina contribution upgrades a shared perk; separate consent required",
    familyGold = "Gold donation transfers to shared Family vault; separate consent required",
}

function FamilyTab.BuildUI(section, feature, bind)
    assert(type(section) == "table" and type(feature) == "table"
        and feature.page == "family" and blocked[feature.id]
        and type(bind) == "function", "Invalid Family UI feature")
    local group = section:Group({ Text = feature.label,
        Description = feature.description, Open = true })
    bind(group, "Toggle", feature.id .. ".enabled", {
        Text = "Allow " .. feature.label,
        Description = "Select this activity; the status below shows whether this entry can run it.",
        Default = false, RevertOnClose = true, RevertTo = false,
    })
    group:Description({ Text = blocked[feature.id] })
    return { feature = feature, tabOwned = true,
        blockedReason = blocked[feature.id],
        status = group:Status({ Text = "Activity",
            Default = "Blocked — " .. blocked[feature.id] }) }
end

function FamilyTab.new(deps)
    assert(type(deps) == "table"
        and type(deps.FamilyQuery) == "table"
        and type(deps.FamilyQuery.new) == "function"
        and type(deps.FamilyState) == "table"
        and type(deps.FamilyState.read) == "function"
        and type(deps.FamilyBlocked) == "table"
        and type(deps.FamilyBlocked.propose) == "function"
        and type(deps.FamilyBlocked.capture) == "function"
        and type(deps.FamilyBlocked.evaluate) == "function",
        "Missing Family info module")
    return setmetatable({ id = "family", deps = deps }, Methods)
end

function Methods:NewInfoQuery()
    return self.deps.FamilyQuery.new()
end

function Methods:Descriptors()
    local d = self.deps
    return {
        { id = "familyCash", reader = d.FamilyState,
            planner = d.FamilyBlocked, evidence = d.FamilyBlocked },
        { id = "familyStamina", reader = d.FamilyState,
            planner = d.FamilyBlocked, evidence = d.FamilyBlocked },
        { id = "familyGold", reader = d.FamilyState,
            planner = d.FamilyBlocked, evidence = d.FamilyBlocked },
    }
end

return FamilyTab
