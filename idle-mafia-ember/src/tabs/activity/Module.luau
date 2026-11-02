-- Local commands and bounded public broker metadata; no raw request/reply payloads.
local ActivityTab = {}
local Methods = {}
Methods.__index = Methods

function ActivityTab.new(section)
    assert(type(section) == "table", "Missing Activity section")
    local self = setmetatable({ tabOwned = true, recent = {}, limit = 20,
        gameplayEvents = {}, history = {},
        activity = section:Status({ Text = "Latest local command",
            Default = "Created inert UI" }),
        errorStatus = section:Status({ Text = "UI validation",
            Default = "No errors" }),
        runtimeHealth = section:Status({ Text = "Runtime health",
            Default = "Disconnected — UI only" }),
        brokerEvent = section:Status({ Text = "Latest broker event",
            Default = "No gameplay events" }),
    }, Methods)
    local history = section:Group({ Text = "Recent gameplay outcomes", Open = true })
    for index = 1, 5 do
        self.history[index] = history:Status({ Text = tostring(index), Default = "—" })
    end
    return self
end

local DETAILS = {
    admitted = "queued for preflight", sent = "sent; awaiting evidence",
    returned = "reply received; awaiting evidence", confirmed = "confirmed by replicated state",
    rejected = "rejected by response", skipped_unconfirmed = "unconfirmed; skipped after deadline",
    stale_preflight = "snapshot changed; no send", transport_blocked = "transport unavailable",
    baseline_failed = "outcome baseline unavailable; no send",
    checkpoint_failed = "checkpoint storage failed", late_return = "stale reply ignored",
    schedule_failed = "could not schedule request", transport_error = "send raised; inspect uncertainty",
    cancelled_unsent = "cancelled before sending; no native action",
    reservation_blocked = "crew, items or funds reserved; no send",
    reconciled_saved = "saved outcome observed; no request replayed",
    recovered_unsent = "saved unsent request released; no native action",
}

local function label(value)
    return type(value) == "string" and #value > 0 and #value <= 48
        and value:match("^[%w_]+$") and value or "unknown"
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
        event = label(latest.feature) .. " — " .. label(latest.kind)
        if latest.duplicateRisk then event = event .. " (duplicate risk)" end
    end
    self.brokerEvent:Set(event, true)
    self.gameplayEvents = {}
    if type(recent) == "table" then
        for index = math.max(1, #recent - 9), #recent do
            local row = recent[index]
            if type(row) == "table" then
                local kind, feature = label(row.kind), label(row.feature)
                self.gameplayEvents[#self.gameplayEvents + 1] = feature .. " — "
                    .. (DETAILS[kind] or kind)
                    .. (row.duplicateRisk == true and " (duplicate risk)" or "")
            end
        end
    end
    local first = math.max(1, #self.gameplayEvents - 4)
    for index, handle in ipairs(self.history) do
        handle:Set(self.gameplayEvents[first + index - 1] or "—", true)
    end
    self.errorStatus:Set(lastError or "No errors", true)
end

function Methods:Snapshot()
    local rows = {}
    for i, label in ipairs(self.recent) do rows[i] = label end
    local events = {}
    for i, value in ipairs(self.gameplayEvents) do events[i] = value end
    return { localCommands = rows, gameplayEvents = events, limit = self.limit }
end

return ActivityTab
