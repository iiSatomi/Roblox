-- Heist start and sabotage are separate controls; sends remain protocol-gated.
local HeistsTab = {}
local Methods = {}
Methods.__index = Methods

local blocked = {
    heists = "Mutation sequence ownership unverified",
    heistCollect = "Result identity and sequence ownership unverified",
    sabotage = "Mutation sequence ownership unverified",
}

function HeistsTab.BuildUI(section, feature, bind)
    assert(type(section) == "table" and type(feature) == "table"
        and feature.page == "heists" and blocked[feature.id]
        and type(bind) == "function"
        and type(feature.custom) == "table" and #feature.custom == 0,
        "Invalid Heists UI feature")
    local group = section:Group({ Text = feature.label,
        Description = feature.description, Open = true })
    bind(group, "Toggle", feature.id .. ".enabled", {
        Text = "Allow " .. feature.label,
        Description = "Select this activity for the prototype.",
        Default = false, RevertOnClose = true, RevertTo = false,
    })
    if #feature.policies > 0 then
        bind(group, "Dropdown", feature.id .. ".policy", {
            Text = "Goal", Options = feature.policies,
            Default = feature.policies[1],
        })
    end
    local row = { feature = feature, tabOwned = true,
        blockedReason = blocked[feature.id],
        status = group:Status({ Text = "Activity",
            Default = "Blocked — " .. blocked[feature.id] }) }
    if feature.limits then group:Description({ Text = feature.limits }) end
    return row
end

function HeistsTab.new(deps)
    assert(type(deps) == "table"
        and type(deps.NativeHeistCatalog) == "table"
        and type(deps.NativeHeistCatalog.new) == "function"
        and type(deps.SequenceRecovery) == "table"
        and type(deps.SequenceRecovery.statusCall) == "function"
        and type(deps.SequenceRecovery.classify) == "function"
        and type(deps.BoardQuery) == "table"
        and type(deps.BoardQuery.new) == "function"
        and type(deps.HeistBoardState) == "table"
        and type(deps.HeistBoardState.read) == "function"
        and type(deps.HeistStart) == "table"
        and type(deps.HeistStart.propose) == "function"
        and type(deps.HeistStartEvidence) == "table"
        and type(deps.HeistStartEvidence.capture) == "function"
        and type(deps.HeistStartEvidence.evaluate) == "function"
        and type(deps.HeistCollect) == "table"
        and type(deps.HeistCollect.propose) == "function"
        and type(deps.HeistCollectEvidence) == "table"
        and type(deps.HeistCollectEvidence.capture) == "function"
        and type(deps.HeistCollectEvidence.evaluate) == "function"
        and type(deps.SabotageState) == "table"
        and type(deps.SabotageState.read) == "function"
        and type(deps.Sabotage) == "table"
        and type(deps.Sabotage.propose) == "function"
        and type(deps.SabotageEvidence) == "table"
        and type(deps.SabotageEvidence.capture) == "function"
        and type(deps.SabotageEvidence.evaluate) == "function",
        "Missing Heists tab modules")
    local catalog = deps.NativeHeistCatalog.new(deps.gameData,
        deps.fingerprint, deps.release)
    local boardQuery = deps.BoardQuery.new(deps.identity)
    return setmetatable({ id = "heists", deps = deps,
        catalog = catalog, recovery = deps.SequenceRecovery,
        boardQuery = boardQuery }, Methods)
end

function Methods:Enrich(snapshot)
    return self.catalog:Enrich(snapshot)
end

function Methods:StatusCall(record, identity)
    return self.recovery.statusCall(record, identity)
end

function Methods:BoardCall()
    return self.boardQuery:Describe()
end

function Methods:StageBoard(snapshot, reply)
    return self.boardQuery:Stage(snapshot, reply)
end

function Methods:Descriptors()
    local deps = self.deps
    return {
        { id = "heists", reader = deps.HeistBoardState,
            planner = deps.HeistStart,
            evidence = deps.HeistStartEvidence },
        { id = "heistCollect", reader = deps.HeistBoardState,
            planner = deps.HeistCollect,
            evidence = deps.HeistCollectEvidence },
        { id = "sabotage", reader = deps.SabotageState,
            planner = deps.Sabotage,
            evidence = deps.SabotageEvidence },
    }
end

return HeistsTab
