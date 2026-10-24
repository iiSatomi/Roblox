-- Territory owns a read-only holdings lane and visibly blocked mutations.
local TerritoryTab = {}
local Methods = {}
Methods.__index = Methods

local known = { territoryWatch = true, station = true,
    residency = true }
local blocked = {
    station = "Stationing needs current own-member, city capacity and defense custody proof",
    residency = "Moving residence may end the previous lease; rent and rollback proof required",
}

function TerritoryTab.BuildUI(section, feature, bind)
    assert(type(section) == "table" and type(feature) == "table"
        and feature.page == "territory" and known[feature.id]
        and type(bind) == "function", "Invalid Territory UI feature")
    local group = section:Group({ Text = feature.label,
        Description = feature.description, Open = true })
    bind(group, "Toggle", feature.id .. ".enabled", {
        Text = "Allow " .. feature.label,
        Description = "Select this activity; the status below shows whether this entry can run it.",
        Default = false, RevertOnClose = true, RevertTo = false,
    })
    local reason = blocked[feature.id]
    if reason then group:Description({ Text = reason }) end
    if feature.id == "residency" then
        bind(group, "Dropdown", "residency.policy", {
            Text = "Goal", Options = feature.policies,
            Default = feature.policies[1],
        })
    end
    return { feature = feature, tabOwned = true,
        blockedReason = reason,
        status = group:Status({ Text = "Activity",
            Default = reason and "Blocked — " .. reason
                or "Off — read-only map requires current client" }) }
end

function TerritoryTab.new(deps)
    assert(type(deps) == "table"
        and type(deps.TerritoryMapQuery) == "table"
        and type(deps.TerritoryMapQuery.new) == "function"
        and type(deps.ResidencyQuery) == "table"
        and type(deps.ResidencyQuery.new) == "function"
        and type(deps.TerritoryState) == "table"
        and type(deps.TerritoryState.read) == "function"
        and type(deps.ReadAttachment) == "table"
        and type(deps.ReadAttachment.attach) == "function"
        and type(deps.TerritoryBlocked) == "table"
        and type(deps.TerritoryBlocked.propose) == "function"
        and type(deps.TerritoryBlocked.capture) == "function"
        and type(deps.TerritoryBlocked.evaluate) == "function",
        "Missing Territory tab modules")
    return setmetatable({ id = "territory", deps = deps }, Methods)
end

function Methods:NewMapQuery()
    return self.deps.TerritoryMapQuery.new()
end

function Methods:NewResidencyQuery()
    return self.deps.ResidencyQuery.new()
end

function Methods:AttachReads(snapshot, map, residency)
    return self.deps.ReadAttachment.attach(snapshot, map, residency)
end

function Methods:NewReadRuntime(budget, executor,
    currentSnapshot, onResult)
    local module = self.deps.TerritoryReadRuntime
    if type(module) ~= "table"
        or type(module.new) ~= "function" then
        return nil, "Territory read scheduler unavailable"
    end
    local ok, runtime = pcall(module.new, budget,
        self:NewMapQuery(), self:NewResidencyQuery(),
        self.deps.ReadAttachment, executor,
        currentSnapshot, onResult)
    if not ok or type(runtime) ~= "table" then
        return nil, "Territory read scheduler unavailable"
    end
    return runtime, nil
end

function Methods:Descriptors()
    local d = self.deps
    return {
        { id = "territoryWatch", reader = d.TerritoryState,
            planner = d.TerritoryBlocked, evidence = d.TerritoryBlocked },
        { id = "station", reader = d.TerritoryState,
            planner = d.TerritoryBlocked, evidence = d.TerritoryBlocked },
        { id = "residency", reader = d.TerritoryState,
            planner = d.TerritoryBlocked, evidence = d.TerritoryBlocked },
    }
end

return TerritoryTab
