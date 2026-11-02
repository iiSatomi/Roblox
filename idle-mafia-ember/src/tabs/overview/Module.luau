-- Overview owns local session controls and read-only request health.
local OverviewTab = {}
local Methods = {}
Methods.__index = Methods

function OverviewTab.new(section, callbacks, userOrigin)
    assert(type(section) == "table" and type(callbacks) == "table"
        and type(callbacks.command) == "function"
        and type(userOrigin) == "function",
        "Missing Overview UI dependencies")
    section:Description({ Text = callbacks.runtimeConnected
        and "Runtime connected. Feature switches start off; enabled actions run automatically."
        or "Local UI preview. Feature choices do not start Jobs, fights or purchases." })
    local self = setmetatable({
        sessionStatus = section:Status({ Text = "Session", Default = "Paused — UI only" }),
        requestStatus = section:Status({ Text = "Request health", Default = "Unavailable — no gameplay adapter" }),
        actionStatus = section:Status({ Text = "Active action", Default = "Disconnected" }),
        blockerStatus = section:Status({ Text = "Selected feature blockers", Default = "None selected" }),
        exposureStatus = section:Status({ Text = "Unconfirmed exposure", Default = "Unavailable" }),
        availabilityStatus = section:Status({ Text = "Runtime adapters", Default = "Disconnected" }),
    }, Methods)
    for _, row in ipairs({
        { "Pause", "pause" }, { "Resume", "resume" },
        { "Emergency Stop", "stop", true }, { "Unload", "unload", true },
    }) do
        section:Button({ Text = row[1], ButtonText = row[1], Danger = row[3],
            FireOnStart = false, Callback = function(_, _, origin)
                if userOrigin(origin) then callbacks.command(row[2]) end
            end })
    end
    return self
end

function Methods:Render(model)
    local session = model.stopped and "Stopped"
        or (model.paused and "Paused" or "Resumed")
    local detail, health = " — UI only; gameplay disconnected",
        "Unavailable — no gameplay adapter"
    local runtime = model.automationRuntime or model.jobsRuntime
    if model.automationRuntime then
        detail = " — shared broker adapter attached"
    elseif model.jobsRuntime then
        detail = " — Jobs adapter attached"
    end
    if runtime then
        if runtime.storageFault then
            health = "Blocked — checkpoint storage failed"
        elseif (runtime.uncertainCount or 0) > 0 then
            health = "Unconfirmed — duplicate risk"
        elseif runtime.active then
            health = "Awaiting exact state — " .. tostring(runtime.active.phase)
        else
            health = runtime.reason or "Ready for fresh state"
        end
    end
    self.sessionStatus:Set(session .. detail, true)
    self.requestStatus:Set(health, true)
    local action, blockers, exposure, availability = "Disconnected", {},
        "Unavailable — no gameplay adapter", "Disconnected"
    if runtime then
        local active = runtime.active
        action = active and (tostring(active.feature or "unknown") .. " — "
            .. tostring(active.phase or "awaiting evidence")) or "None"
        local available = 0
        for _, present in pairs(runtime.availableFeatures or {}) do
            if present == true then available = available + 1 end
        end
        availability = tostring(available) .. " registered; inspect each feature status"
        local selected = {}
        for key, enabled in pairs(model.values or {}) do
            if enabled == true and key:sub(-8) == ".enabled" then
                selected[#selected + 1] = key:sub(1, -9)
            end
        end
        table.sort(selected)
        for _, id in ipairs(selected) do
            local reason = runtime.reasons and runtime.reasons[id]
            if reason and #blockers < 3 then
                blockers[#blockers + 1] = id .. ": " .. tostring(reason):sub(1, 180)
            end
        end
        if #blockers == 0 and #selected > 0 then
            blockers[1] = runtime.reason or "Check each selected feature status"
        end
        local exposed = {}
        for id, count in pairs(runtime.uncertainByFeature or {}) do
            if type(id) == "string" and type(count) == "number" and count > 0 then
                exposed[#exposed + 1] = id .. " ×" .. tostring(count)
            end
        end
        table.sort(exposed)
        while #exposed > 5 do table.remove(exposed) end
        exposure = tostring(runtime.uncertainCount or 0) .. " unconfirmed"
            .. (#exposed > 0 and (" — " .. table.concat(exposed, ", ")) or "")
            .. ((runtime.uncertainCount or 0) > 0 and "; duplicate risk" or "")
    end
    self.actionStatus:Set(action, true)
    self.blockerStatus:Set(#blockers > 0 and table.concat(blockers, " • ")
        or "None selected", true)
    self.exposureStatus:Set(exposure, true)
    self.availabilityStatus:Set(availability, true)
    return true
end

return OverviewTab
