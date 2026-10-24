-- Favors owns its own permission, reader and attempt evidence.
local FavorsTab = {}
local Methods = {}
Methods.__index = Methods

local sequenceReason = "Mutation sequence ownership unverified"

function FavorsTab.BuildUI(section, feature, bind)
    assert(type(section) == "table" and type(feature) == "table"
        and feature.id == "favors" and feature.page == "favors"
        and type(bind) == "function"
        and type(feature.custom) == "table" and #feature.custom == 0,
        "Invalid Favors UI feature")
    local group = section:Group({ Text = feature.label,
        Description = feature.description, Open = true })
    bind(group, "Toggle", "favors.enabled", {
        Text = "Allow " .. feature.label,
        Description = "Select this activity for the prototype.",
        Default = false, RevertOnClose = true, RevertTo = false,
    })
    bind(group, "Dropdown", "favors.policy", {
        Text = "Goal", Options = feature.policies,
        Default = feature.policies[1],
    })
    if feature.limits then group:Description({ Text = feature.limits }) end
    return { feature = feature, tabOwned = true,
        blockedReason = sequenceReason,
        status = group:Status({ Text = "Activity",
            Default = "Blocked — " .. sequenceReason }) }
end

function FavorsTab.new(deps)
    assert(type(deps) == "table"
        and type(deps.FavorsState) == "table"
        and type(deps.FavorsState.read) == "function"
        and type(deps.FavorHelp) == "table"
        and type(deps.FavorHelp.propose) == "function"
        and type(deps.FavorHelpEvidence) == "table"
        and type(deps.FavorHelpEvidence.capture) == "function"
        and type(deps.FavorHelpEvidence.evaluate) == "function"
        and type(deps.BoardQuery) == "table"
        and type(deps.BoardQuery.new) == "function",
        "Missing Favors tab modules")
    return setmetatable({ id = "favors", deps = deps,
        boardQuery = deps.BoardQuery.new(deps.identity) }, Methods)
end

function Methods:BoardCall()
    return self.boardQuery:Describe()
end

function Methods:StageBoard(snapshot, reply)
    return self.boardQuery:Stage(snapshot, reply)
end

function Methods:Descriptors()
    local deps = self.deps
    return { { id = "favors", reader = deps.FavorsState,
        planner = deps.FavorHelp, evidence = deps.FavorHelpEvidence } }
end

return FavorsTab
