-- Local UI activity only. The shared broker owns gameplay request journals.
local ActivityTab = {}
local Methods = {}
Methods.__index = Methods

function ActivityTab.new(section)
    assert(type(section) == "table", "Missing Activity section")
    return setmetatable({ tabOwned = true, recent = {}, limit = 20,
        activity = section:Status({ Text = "Latest local command",
            Default = "Created inert UI" }),
        errorStatus = section:Status({ Text = "UI validation",
            Default = "No errors" }),
        runtimeHealth = section:Status({ Text = "Runtime health",
            Default = "Disconnected — UI only" }),
        brokerEvent = section:Status({ Text = "Latest broker event",
            Default = "No gameplay events" }),
    }, Methods)
end

function Methods:Record(command)
    assert(type(command) == "string" and #command > 0,
        "Invalid local command")
    -- Only caller-authored UI command labels enter this bounded journal.
    local label = string.sub(command, 1, 120)
    self.activity:Set(label, true)
    self.recent[#self.recent + 1] = label
    if #self.recent > self.limit then table.remove(self.recent, 1) end
end

function Methods:Render(model, lastError)
    local runtime = model.automationRuntime or model.jobsRuntime
    local health = "Disconnected — UI only"
    if runtime then
        if runtime.storageFault then
            health = "Blocked — checkpoint storage failed"
        elseif (runtime.uncertainCount or 0) > 0 then
            health = "Unconfirmed requests — duplicate risk"
        elseif runtime.active then
            health = "Awaiting exact state"
        else
            health = "Adapter attached — current source unverified"
        end
    end
    self.runtimeHealth:Set(health, true)
    local recent = runtime and runtime.recentActions
    local latest = type(recent) == "table" and recent[#recent]
    local event = "No gameplay events"
    if type(latest) == "table" and type(latest.kind) == "string"
        and type(latest.feature) == "string" then
        event = latest.feature .. " — " .. latest.kind
        if latest.duplicateRisk then event = event .. " (duplicate risk)" end
    end
    self.brokerEvent:Set(event, true)
    self.errorStatus:Set(lastError or "No errors", true)
end

function Methods:Snapshot()
    local rows = {}
    for i, label in ipairs(self.recent) do rows[i] = label end
    return { localCommands = rows, limit = self.limit }
end

return ActivityTab
