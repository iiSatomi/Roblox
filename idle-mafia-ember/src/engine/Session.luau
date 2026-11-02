-- Effective execution lifecycle. Desired UI settings live elsewhere.
local Session = {}
local Methods = {}
Methods.__index = Methods
local running = {}

local function conflict(proposal, unresolved, reservations)
    if proposal.actionKey == unresolved.actionKey
        or proposal.feature == unresolved.feature then return true end
    if reservations ~= nil then return false end -- Quantities/origins belong to the trusted custody owner.
    if type(proposal.resources) ~= "table" then return false end
    for resource, amount in pairs(proposal.resources) do
        if type(amount) == "number" and amount > 0
            and (unresolved.resources[resource] or 0) > 0 then return true end
    end
    return false
end

function Session.new(broker, checkpoint, identity)
    assert(type(broker) == "table" and type(broker.Offer) == "function"
        and type(broker.Stop) == "function", "Missing lifecycle broker")
    assert(type(checkpoint) == "table" and type(checkpoint.Load) == "function"
        and type(checkpoint.Save) == "function", "Missing checkpoint")
    assert(type(identity) == "table", "Missing session identity")
    for _, field in ipairs({ "session", "account", "place", "release" }) do
        assert(identity[field] == broker.session[field], "Session identity mismatch")
    end
    local _, loadError = checkpoint:Load(identity.account, identity.place, identity.release)
    local key = checkpoint:ScopeKey()
    assert(key and not running[key], "Duplicate active session")
    local self = setmetatable({
        broker = broker, checkpoint = checkpoint, key = key,
        state = "running", storageFault = loadError,
    }, Methods)
    running[key] = self
    broker.policy.canOffer = function() return self.state == "running" and not self.storageFault end
    broker.policy.canSend = function() return self.state == "running" and not self.storageFault end
    broker.policy.beforeSend = function(proposal, before, baseline)
        local saved, reason = checkpoint:Save(proposal, before, baseline)
        if not saved then self.storageFault = reason end
        return saved, reason
    end
    if type(checkpoint.RecordUnsent) == "function" then
        broker.policy.abandonedUnsent = function(proposal, before, baseline)
            return checkpoint:RecordUnsent(proposal, before, baseline)
        end
    end
    broker.policy.afterResolve = function(proposal, outcome)
        local resolved, reason = checkpoint:Resolve(proposal.actionKey, outcome)
        if not resolved then self.storageFault = reason end
        return resolved
    end
    if checkpoint.pendingModule then
        broker.policy.recordReply = function(proposal, reply)
            local saved, reason = checkpoint:RecordReply(proposal.actionKey, reply)
            if not saved then self.storageFault = reason or "Result persistence failed" end
            return saved
        end
    end
    return self
end

function Methods:Offer(proposal, snapshot)
    if self.state ~= "running" then return "blocked", "Session " .. self.state end
    if self.storageFault then return "blocked", self.storageFault end
    if type(proposal) ~= "table" then return "blocked", "Missing proposal" end
    for _, unresolved in ipairs(self.checkpoint:Records()) do
        if conflict(proposal, unresolved, self.broker.policy.reservations) then
            return "blocked", "Unresolved action exposure"
        end
    end
    return self.broker:Offer(proposal, snapshot)
end

function Methods:Tick(snapshot)
    if self.state == "stopped" or self.state == "closed" then return "stopped" end
    if self.state == "paused" and (not self.broker.active
        or self.broker.active.sentAt == nil) then return "paused" end
    return self.broker:Tick(snapshot)
end

function Methods:Observe(snapshot)
    if self.state == "stopped" or self.state == "closed" then return "ignored" end
    return self.broker:Observe(snapshot)
end

function Methods:Pause()
    if self.state == "running" then self.state = "paused" end
end

function Methods:Resume()
    if self.state == "paused" then self.state = "running" end
end

function Methods:Stop()
    if self.state == "closed" then return end
    self.state = "stopped"
    self.broker:Stop()
    if running[self.key] == self then running[self.key] = nil end
end

function Methods:Close()
    self:Stop()
    self.state = "closed"
end

function Methods:Status()
    local broker = self.broker:Status()
    local unresolved = self.checkpoint:Records()
    return {
        state = self.state, storageFault = self.storageFault ~= nil,
        storageReason = self.storageFault, uncertainCount = #unresolved,
        active = broker.active, nextSendAt = broker.nextSendAt,
        cooldownUntil = broker.cooldownUntil,
    }
end

return Session
