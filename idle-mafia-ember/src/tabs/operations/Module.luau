-- Two independent Operations switches share one validated tab source.
local OperationsTab = {}
local Methods = {}
Methods.__index = Methods

function OperationsTab.BuildUI(section, feature, bind)
    assert(type(section) == "table" and type(feature) == "table"
        and feature.page == "operations"
        and (feature.id == "operations" or feature.id == "collect")
        and type(bind) == "function"
        and type(feature.custom) == "table" and #feature.custom == 0,
        "Invalid Operations UI feature")
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
    return { feature = feature, tabOwned = true,
        status = group:Status({ Text = "Activity", Default = "Off — UI only" }) }
end

function OperationsTab.new(deps)
    assert(type(deps) == "table"
        and type(deps.NativeOperationsCatalog) == "table"
        and type(deps.NativeOperationsCatalog.new) == "function"
        and type(deps.OperationsState) == "table"
        and type(deps.OperationsState.read) == "function"
        and type(deps.OperationsStart) == "table"
        and type(deps.OperationsStart.propose) == "function"
        and type(deps.OperationsCollect) == "table"
        and type(deps.OperationsCollect.propose) == "function"
        and type(deps.OperationsEvidence) == "table"
        and type(deps.OperationsEvidence.capture) == "function"
        and type(deps.OperationsEvidence.evaluate) == "function"
        and type(deps.OperationsCollectEvidence) == "table"
        and type(deps.OperationsCollectEvidence.capture) == "function"
        and type(deps.OperationsCollectEvidence.evaluate) == "function",
        "Missing Operations tab modules")
    local catalog = deps.NativeOperationsCatalog.new(deps.gameData,
        deps.fingerprint, deps.release)
    return setmetatable({ id = "operations", catalog = catalog,
        reader = deps.OperationsState,
        start = deps.OperationsStart,
        startEvidence = deps.OperationsEvidence,
        collect = deps.OperationsCollect,
        collectEvidence = deps.OperationsCollectEvidence }, Methods)
end

function Methods:Descriptors()
    return {
        { id = "operations", reader = self.reader,
            planner = self.start, evidence = self.startEvidence },
        { id = "collect", reader = self.reader,
            planner = self.collect, evidence = self.collectEvidence },
    }
end

function Methods:Enrich(snapshot)
    return self.catalog:Enrich(snapshot)
end

return OperationsTab
