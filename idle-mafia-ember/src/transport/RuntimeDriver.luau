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
    return setmetatable({ app = app, reader = reader, alive = true }, Methods)
end

function Methods:Tick()
    if not self.alive then return false, "Driver closed" end
    if self.app.alive == false then
        self:Close()
        return false, "App closed"
    end
    local raw, reason = self.reader:Capture()
    if not raw then return false, reason end
    return self.app:Step(raw)
end

function Methods:ObserveSync(payload)
    if not self.alive then return false, "Driver closed" end
    if not self.reader:ObserveSync(payload) then
        return false, "Invalid Sync payload"
    end
    return self:Tick()
end

function Methods:ObserveChanged(payload)
    if not self.alive then return false, "Driver closed" end
    if not self.reader:ObserveChanged(payload) then
        return false, "Invalid changed state"
    end
    return self:Tick()
end

function Methods:Close()
    if not self.alive then return false end
    self.alive = false
    self.reader:Close()
    self.app:Destroy()
    return true
end

return RuntimeDriver
