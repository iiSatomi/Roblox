-- Goal explanation is available; borrowing another tab remains blocked.
local TrophyFocusBlocked = {}

local ordinary = { level = "jobs", mastery = "jobs",
    property = "properties", operations = "operations",
    banking = "bank", heist = "heists" }

function TrophyFocusBlocked.inspect(view, settings)
    if type(view) ~= "table" or type(view.byId) ~= "table"
        or type(settings) ~= "table" then
        return { status = "waiting", reason = "Current Trophy state required" }
    end
    local id = settings.goalId
    if type(id) ~= "string" or #id == 0 or id == "none" then
        return { status = "waiting", reason = "Choose a Trophy goal" }
    end
    local row = view.byId[id]
    if type(row) ~= "table" then
        return { status = "blocked", reason = "Goal absent from current catalog" }
    end
    if row.status == "owned" then
        return { status = "owned", reason = "Trophy already owned" }
    end
    if row.status == "manualTradeIn" then
        return { status = "blocked",
            reason = "Item-consuming trade-in is manual" }
    end
    if row.status == "ready" then
        return { status = "ready", feature = "trophies",
            reason = "Native reward ready; separate Trophy claim switch required" }
    end
    local feature = ordinary[row.route]
    if feature then
        return { status = "mapped", feature = feature,
            reason = "Possible ordinary route; separate opt-in and progress proof required" }
    end
    if row.route == "combat" or row.route == "favor"
        or row.route == "takedownLoot" then
        return { status = "blocked",
            reason = "This route needs a separate action permission and outcome proof" }
    end
    return { status = "blocked",
        reason = "No verified personal automation for this Trophy" }
end

function TrophyFocusBlocked.propose()
    return nil, "Trophy goal borrowing requires shared opt-in and progress proof"
end

function TrophyFocusBlocked.capture()
    return nil, "Trophy goal controller does not send a remote"
end

function TrophyFocusBlocked.evaluate()
    return "pending"
end

return TrophyFocusBlocked
