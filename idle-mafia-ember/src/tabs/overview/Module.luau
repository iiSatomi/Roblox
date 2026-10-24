-- Overview owns local session controls and read-only request health.
local OverviewTab = {}
local Methods = {}
Methods.__index = Methods

function OverviewTab.new(section, callbacks, userOrigin)
    assert(type(section) == "table" and type(callbacks) == "table"
        and type(callbacks.command) == "function"
        and type(userOrigin) == "function",
        "Missing Overview UI dependencies")
    section:Description({ Text = "Local UI preview. Feature choices do not start Jobs, fights or purchases." })
    local self = setmetatable({
        sessionStatus = section:Status({ Text = "Session", Default = "Paused — UI only" }),
        requestStatus = section:Status({ Text = "Request health", Default = "Unavailable — no gameplay adapter" }),
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
        elseif runtime.active then
            health = "Awaiting exact state — " .. tostring(runtime.active.phase)
        elseif (runtime.uncertainCount or 0) > 0 then
            health = "Unconfirmed — duplicate risk"
        else
            health = runtime.reason or "Ready for fresh state"
        end
    end
    self.sessionStatus:Set(session .. detail, true)
    self.requestStatus:Set(health, true)
    return true
end

return OverviewTab
