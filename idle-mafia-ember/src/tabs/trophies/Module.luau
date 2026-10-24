-- Earned native claims and a separate read-only goal inspector.
local TrophiesTab = {}
local Methods = {}
Methods.__index = Methods

function TrophiesTab.BuildUI(section, feature, bind)
    assert(type(section) == "table" and type(feature) == "table"
        and feature.page == "trophies"
        and (feature.id == "trophies" or feature.id == "trophyFocus")
        and type(bind) == "function", "Invalid Trophies UI feature")
    local group = section:Group({ Text = feature.label,
        Description = feature.description, Open = true })
    bind(group, "Toggle", feature.id .. ".enabled", {
        Text = "Allow " .. feature.label,
        Description = "Select this activity; the status below shows whether this entry can run it.",
        Default = false, RevertOnClose = true, RevertTo = false,
    })
    local reason
    if feature.id == "trophyFocus" then
        local field = feature.custom[1]
        assert(type(field) == "table" and field.id == "goalId"
            and field.type == "text", "Missing Trophy goal selector")
        bind(group, "Input", "trophyFocus.custom.goalId", {
            Text = field.label, Default = field.value,
            FireOnBlur = true,
        })
        reason = "Goal routes need separate action opt-ins and progress proof"
        group:Description({ Text = reason })
    end
    return { feature = feature, tabOwned = true,
        blockedReason = reason,
        status = group:Status({ Text = "Activity",
            Default = reason and "Blocked — " .. reason
                or "Off — UI only" }) }
end

function TrophiesTab.new(deps)
    assert(type(deps) == "table"
        and type(deps.NativeTrophyCatalog) == "table"
        and type(deps.NativeTrophyCatalog.new) == "function"
        and type(deps.EarnedTrophiesState) == "table"
        and type(deps.EarnedTrophiesState.read) == "function"
        and type(deps.EarnedTrophies) == "table"
        and type(deps.EarnedTrophies.propose) == "function"
        and type(deps.EarnedTrophiesEvidence) == "table"
        and type(deps.EarnedTrophiesEvidence.capture) == "function"
        and type(deps.EarnedTrophiesEvidence.evaluate) == "function"
        and type(deps.TrophyFocusState) == "table"
        and type(deps.TrophyFocusState.read) == "function"
        and type(deps.TrophyFocusBlocked) == "table"
        and type(deps.TrophyFocusBlocked.inspect) == "function"
        and type(deps.TrophyFocusBlocked.propose) == "function"
        and type(deps.TrophyFocusBlocked.capture) == "function"
        and type(deps.TrophyFocusBlocked.evaluate) == "function",
        "Missing Trophies tab modules")
    local catalog = deps.NativeTrophyCatalog.new(deps.gameData,
        deps.fingerprint, deps.release)
    return setmetatable({ id = "trophies", deps = deps,
        catalog = catalog }, Methods)
end

function Methods:Enrich(snapshot)
    return self.catalog:Enrich(snapshot)
end

function Methods:InspectGoal(view, settings)
    return self.deps.TrophyFocusBlocked.inspect(view, settings)
end

function Methods:Descriptors()
    local d = self.deps
    return {
        { id = "trophies", reader = d.EarnedTrophiesState,
            planner = d.EarnedTrophies,
            evidence = d.EarnedTrophiesEvidence },
        { id = "trophyFocus", reader = d.TrophyFocusState,
            planner = d.TrophyFocusBlocked,
            evidence = d.TrophyFocusBlocked },
    }
end

return TrophiesTab
