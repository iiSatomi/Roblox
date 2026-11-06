-- Event/tick seam. Native subscriptions and timing are injected by the host.
local RuntimeDriver = {}
local Methods = {}
Methods.__index = Methods

function RuntimeDriver.new(app, reader)
    assert(type(app) == "table" and type(app.Step) == "function"
        and type(app.Destroy) == "function"
        and type(reader) == "table"
        and type(reader.ObserveSync) == "function"
        and type(reader.ObserveChanged) == "function"
        and type(reader.Capture) == "function"
        and type(reader.Close) == "function",
        "Missing runtime driver dependencies")
    return setmetatable({ app = app, reader = reader, alive = true, pending = {} }, Methods)
end

function Methods:Tick()
    if not self.alive then return false, "Driver closed" end
    if self.app.alive == false then
        self:Close()
        return false, "App closed"
    end
    if self.fault then
        local reason = self.fault
        self:Close()
        return false, reason
    end
    if self.ticking then return false, "Driver tick already in progress" end
    self.ticking = true
    local pending = self.pending
    self.pending = {}
    local ok, accepted, reason = pcall(function()
        -- Preserve intermediate terminal Sync evidence without planning from an
        -- older revision. Only the latest reader snapshot may select new work.
        if #pending == 0 then
            local raw, why = self.reader:Capture()
            if not raw then return false, why end
            pending[1] = raw
        end
        local index, result, failure = 1, true, nil
        while index <= #pending do
            if self.fault then self:Close(); return false, self.fault end
            -- Events may arrive during a yielding evidence/storage operation.
            -- Append them rather than replacing the queued terminal snapshot.
            for _, raw in ipairs(self.pending) do pending[#pending + 1] = raw end
            self.pending = {}
            if #pending > 64 then
                self.fault = "Native event drain capacity exceeded"
                self:Close()
                return false, self.fault
            end
            if not self.alive or self.app.alive == false then return false, "Driver closed" end
            local raw = pending[index]
            if index == #pending then
                local latest, why = self.reader:Capture()
                if not latest then return false, why end
                if latest.revision == raw.revision then raw = latest
                else pending[#pending + 1] = latest end
            end
            result, failure = self.app:Step(raw, index < #pending)
            if result == false then return result, failure end
            index = index + 1
        end
        return result, failure
    end)
    self.ticking = false
    if not ok then error(accepted, 0) end
    return accepted, reason
end

local function queueSnapshot(self)
    local raw, reason = self.reader:Capture()
    if not raw then return false, reason end
    local last = self.pending[#self.pending]
    if last and last.revision == raw.revision then return true end
    if #self.pending >= 32 then
        self.fault = "Native event queue capacity exceeded"
        return false, self.fault
    end
    self.pending[#self.pending + 1] = raw
    return true
end

function Methods:ObserveSync(payload)
    if not self.alive or self.fault then return false, self.fault or "Driver closed" end
    if not self.reader:ObserveSync(payload) then
        return false, "Invalid Sync payload"
    end
    -- Native/remote callback coroutines need not retain Ember GUI capabilities.
    -- The pre-existing RuntimeLoop timer owns all application/UI processing.
    return queueSnapshot(self)
end

function Methods:ObserveChanged(payload)
    if not self.alive or self.fault then return false, self.fault or "Driver closed" end
    if not self.reader:ObserveChanged(payload) then
        return false, "Invalid changed state"
    end
    return queueSnapshot(self)
end

function Methods:Close()
    if not self.alive then return false end
    self.alive = false
    self.pending = {}
    self.reader:Close()
    self.app:Destroy()
    return true
end

return RuntimeDriver
