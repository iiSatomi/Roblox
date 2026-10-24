-- Free native Briefcase picks; Event Shop is explicitly unavailable.
local EventsTab = {}
local Methods = {}
Methods.__index = Methods

function EventsTab.BuildUI(section, feature, bind)
    assert(type(section) == "table" and type(feature) == "table"
        and feature.page == "events"
        and (feature.id == "briefcases" or feature.id == "eventShop")
        and type(bind) == "function", "Invalid Events UI feature")
    local group = section:Group({ Text = feature.label,
        Description = feature.description, Open = true })
    bind(group, "Toggle", feature.id .. ".enabled", {
        Text = "Allow " .. feature.label,
        Description = "Select this activity for the prototype.",
        Default = false, RevertOnClose = true, RevertTo = false,
    })
    local reason = feature.id == "eventShop"
        and "Current Event Shop offers, medal custody and native call unavailable" or nil
    if reason then group:Description({ Text = reason }) end
    return { feature = feature, tabOwned = true,
        blockedReason = reason,
        status = group:Status({ Text = "Activity",
            Default = reason and "Blocked — " .. reason
                or "Off — UI only" }) }
end

function EventsTab.new(deps)
    assert(type(deps) == "table"
        and type(deps.FreeBriefcasesState) == "table"
        and type(deps.FreeBriefcasesState.read) == "function"
        and type(deps.FreeBriefcases) == "table"
        and type(deps.FreeBriefcases.propose) == "function"
        and type(deps.FreeBriefcasesEvidence) == "table"
        and type(deps.FreeBriefcasesEvidence.capture) == "function"
        and type(deps.FreeBriefcasesEvidence.evaluate) == "function"
        and type(deps.EventShopBlocked) == "table"
        and type(deps.EventShopBlocked.read) == "function"
        and type(deps.EventShopBlocked.propose) == "function"
        and type(deps.EventShopBlocked.capture) == "function"
        and type(deps.EventShopBlocked.evaluate) == "function",
        "Missing Events tab modules")
    return setmetatable({ id = "events", deps = deps }, Methods)
end

function Methods:Descriptors()
    local d = self.deps
    return {
        { id = "briefcases", reader = d.FreeBriefcasesState,
            planner = d.FreeBriefcases,
            evidence = d.FreeBriefcasesEvidence },
        { id = "eventShop", reader = d.EventShopBlocked,
            planner = d.EventShopBlocked,
            evidence = d.EventShopBlocked },
    }
end

return EventsTab
