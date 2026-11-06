-- Favors owns its own permission, reader and attempt evidence.
local FavorsTab = {}
local Methods = {}
Methods.__index = Methods

local sequenceReason = "Mutation sequence ownership unverified"

function FavorsTab.BuildUI(section, feature, bind, numeric, nativeAvailable)
    assert(type(section) == "table" and type(feature) == "table"
        and feature.id == "favors" and feature.page == "favors"
        and type(bind) == "function"
        and type(numeric) == "table"
        and type(feature.custom) == "table" and #feature.custom == 4,
        "Invalid Favors UI feature")
    local group = section:Group({ Text = feature.label,
        Description = feature.description, Open = true })
    bind(group, "Toggle", "favors.enabled", {
        Text = "Allow " .. feature.label,
        Description = "Select this activity; the status below shows whether this entry can run it.",
        Default = false, RevertOnClose = true, RevertTo = false,
    })
    bind(group, "Dropdown", "favors.policy", {
        Text = "Goal", Options = feature.policies,
        Default = feature.policies[1],
    })
    local custom = group:Group({ Text = "Help limits", Open = false })
    for _, field in ipairs(feature.custom) do
        local key = "favors.custom." .. field.id
        if field.type == "number" then
            numeric[key] = true
            bind(custom, "Input", key, {
                Text = field.label, Default = tostring(field.value),
                FireOnBlur = true,
            })
        else
            assert(field.type == "select"
                and type(field.options) == "table",
                "Invalid Favor custom control")
            bind(custom, "Dropdown", key, {
                Text = field.label, Default = field.value,
                Options = field.options,
            })
        end
    end
    if feature.limits then group:Description({ Text = feature.limits }) end
    local unavailable = nativeAvailable ~= true and sequenceReason or nil
    return { feature = feature, tabOwned = true,
        custom = custom,
        blockedReason = unavailable,
        status = group:Status({ Text = "Activity",
            Default = unavailable and ("Blocked — " .. unavailable) or "Off" }) }
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
        and type(deps.BoardQuery.new) == "function"
        and type(deps.BoardReadRuntime) == "table"
        and type(deps.BoardReadRuntime.new) == "function",
        "Missing Favors tab modules")
    return setmetatable({ id = "favors", deps = deps, runtime = deps.heistRuntime,
        boardQuery = deps.BoardQuery.new(deps.identity) }, Methods)
end

function Methods:BoardCall()
    return self.boardQuery:Describe()
end

function Methods:StageBoard(snapshot, reply)
    return self.boardQuery:Stage(snapshot, reply)
end

function Methods:NewBoardRead(budget, executor, currentSnapshot,
    onResult)
    return self.deps.BoardReadRuntime.new(budget, self.boardQuery,
        executor, currentSnapshot, onResult)
end

function Methods:Descriptors()
    local deps = self.deps
    local spec = { id = "favors", reader = deps.FavorsState,
        planner = deps.FavorHelp, evidence = deps.FavorHelpEvidence }
    return {self.runtime and self.runtime:Feature(spec) or spec}
end

function Methods:Close() if self.runtime then self.runtime:Close() end end

return FavorsTab
