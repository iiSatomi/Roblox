-- Readiness and explicit reset boundary; no automatic Prestige send.
local PrestigeTab = {}
local Methods = {}
Methods.__index = Methods

local blocked = "Reset removes current level and EXP; separate consent required"

function PrestigeTab.BuildUI(section, feature, bind)
    assert(type(section) == "table" and type(feature) == "table"
        and feature.page == "prestige" and feature.id == "prestige"
        and type(bind) == "function", "Invalid Prestige UI feature")
    local group = section:Group({ Text = feature.label,
        Description = feature.description, Open = true })
    bind(group, "Toggle", "prestige.enabled", {
        Text = "Allow " .. feature.label,
        Description = "Select this activity; the status below shows whether this entry can run it.",
        Default = false, RevertOnClose = true, RevertTo = false,
    })
    group:Description({ Text = blocked })
    return { feature = feature, tabOwned = true,
        blockedReason = blocked,
        status = group:Status({ Text = "Activity",
            Default = "Blocked — " .. blocked }) }
end

function PrestigeTab.new(deps)
    assert(type(deps) == "table"
        and type(deps.PrestigeState) == "table"
        and type(deps.PrestigeState.new) == "function"
        and type(deps.PrestigeState.read) == "function"
        and type(deps.PrestigeBlocked) == "table"
        and type(deps.PrestigeBlocked.propose) == "function"
        and type(deps.PrestigeBlocked.capture) == "function"
        and type(deps.PrestigeBlocked.evaluate) == "function",
        "Missing Prestige tab module")
    local state = deps.PrestigeState.new(
        deps.config, deps.fingerprint, deps.release)
    return setmetatable({ id = "prestige", state = state,
        blocked = deps.PrestigeBlocked }, Methods)
end

function Methods:Enrich(snapshot)
    return self.state:Enrich(snapshot)
end

function Methods:Descriptors()
    return { { id = "prestige", reader = self.state,
        planner = self.blocked, evidence = self.blocked } }
end

return PrestigeTab
