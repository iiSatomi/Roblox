-- Pure injected broker. The transport is supplied later by a verified adapter.
local Broker = {}
local Methods = {}
Methods.__index = Methods

local function boundedCooldown(value)
    if type(value) ~= "number" or value ~= value then return 45 end
    return math.max(45, math.min(300, value))
end

local function activeView(active)
    if not active then return nil end
    return {
        token = active.token, feature = active.proposal.feature,
        actionKey = active.proposal.actionKey, phase = active.phase,
        sentAt = active.sentAt,
    }
end

function Broker.new(clock, transport, journal, policy)
    assert(type(clock) == "table" and type(clock.Now) == "function", "Missing clock")
    assert(type(transport) == "table" and type(transport.Send) == "function", "Missing transport")
    assert(type(journal) == "table" and type(journal.Record) == "function", "Missing journal")
    assert(type(policy) == "table" and type(policy.contracts) == "table"
        and type(policy.session) == "table", "Missing broker policy")
    local spacing = type(policy.minInterval) == "number" and policy.minInterval or 1
    local freshness = type(policy.maxSnapshotAge) == "number" and policy.maxSnapshotAge or 2
    assert(spacing == spacing and spacing >= 1 and spacing < math.huge, "Invalid send spacing")
    assert(freshness == freshness and freshness > 0 and freshness < math.huge,
        "Invalid snapshot age")
    local session = {}
    for _, key in ipairs({ "session", "account", "place", "release" }) do
        assert(type(policy.session[key]) == "string" and #policy.session[key] > 0,
            "Invalid broker session identity")
        session[key] = policy.session[key]
    end
    return setmetatable({
        clock = clock, transport = transport, journal = journal, policy = policy,
        session = session,
        spacing = spacing, freshness = freshness,
        cooldown = boundedCooldown(policy.cooldownSeconds),
        active = nil, lastSendAt = nil, serial = 0, seen = {}, cooldownUntil = {},
        stopped = false,
    }, Methods)
end

function Methods:Record(kind, active, at, reason, duplicateRisk)
    self.journal:Record({
        kind = kind, at = at, feature = active.proposal.feature,
        actionKey = active.proposal.actionKey, token = active.token,
        reason = reason, duplicateRisk = duplicateRisk,
    })
end

function Methods:Fresh(raw, now)
    local snapshot, reason = self.policy.contracts.validateSnapshot(raw, self.session)
    if not snapshot then return nil, reason end
    if snapshot.capturedAt > now or now - snapshot.capturedAt > self.freshness then
        return nil, "Snapshot is stale"
    end
    return snapshot, nil
end

function Methods:Expire(active, now)
    if not self.active or self.active.token ~= active.token then return end
    self:Record("skipped_unconfirmed", active, now,
        "No action-specific confirmation by first send + 45s", true)
    self.cooldownUntil[active.proposal.feature] = now + self.cooldown
    self.active = nil
end

function Methods:Offer(rawProposal, rawSnapshot)
    local now = self.clock:Now()
    if self.stopped then return "blocked", "Broker stopped" end
    if type(self.policy.canOffer) == "function" and not self.policy.canOffer() then
        return "blocked", "Session unavailable"
    end
    if type(self.transport.InFlight) == "function"
        and self.transport:InFlight() then
        return "wait", "Transport invocation still running"
    end
    if self.active then return "wait", "Another request owns the broker" end
    local snapshot, reason = self:Fresh(rawSnapshot, now)
    if not snapshot then return "blocked", reason end
    local proposal, proposalReason = self.policy.contracts.validateProposal(rawProposal, snapshot)
    if not proposal then return "blocked", proposalReason end
    if self.seen[proposal.actionKey] then return "blocked", "Action key already sent" end
    if now < (self.cooldownUntil[proposal.feature] or 0) then
        return "blocked", "Feature cooling down"
    end
    self.serial = self.serial + 1
    self.active = {
        token = self.serial, proposal = proposal, before = snapshot,
        phase = "admitted", sentAt = nil, reply = nil,
    }
    self:Record("admitted", self.active, now)
    return "admitted", nil
end

function Methods:Tick(rawSnapshot)
    local now = self.clock:Now()
    local active = self.active
    if not active then return "idle" end
    if active.sentAt ~= nil then
        if now - active.sentAt >= 45 then
            self:Expire(active, now)
            return "skipped_unconfirmed"
        end
        return active.phase
    end

    if self.stopped then
        self.active = nil
        return "stopped"
    end
    if type(self.policy.canSend) == "function" and not self.policy.canSend() then
        return "paused"
    end
    if type(self.transport.InFlight) == "function"
        and self.transport:InFlight() then return "transport_in_flight" end

    local nextSendAt = self.lastSendAt and self.lastSendAt + self.spacing or 0
    if now < nextSendAt then return "spacing" end
    local snapshot, reason = self:Fresh(rawSnapshot, now)
    if not snapshot or snapshot.revision ~= active.proposal.revision then
        self:Record("stale_preflight", active, now, reason or "Snapshot changed")
        self.active = nil
        return "stale_preflight"
    end

    -- An injected transport may reject an unsupported native call before
    -- the checkpoint records an attempt. Generic fake transports need not.
    if type(self.transport.Validate) == "function" then
        local checked, valid, transportReason = pcall(
            self.transport.Validate, self.transport, active.proposal)
        if not checked or valid ~= true then
            self:Record("transport_blocked", active, now,
                checked and (transportReason or "Unsupported call")
                    or "Transport validation raised")
            self.active = nil
            return "transport_blocked"
        end
    end

    if type(self.policy.captureBefore) == "function" then
        local captured, baseline, baselineReason = pcall(
            self.policy.captureBefore, active.proposal, rawSnapshot)
        if not captured or type(baseline) ~= "table" then
            self:Record("baseline_failed", active, now,
                captured and (baselineReason or "Baseline missing") or "Baseline raised")
            self.active = nil
            return "baseline_failed"
        end
        active.beforeEvidence = baseline
    end

    if type(self.policy.beforeSend) == "function" then
        local ok, saved, saveReason = pcall(self.policy.beforeSend, active.proposal)
        if not ok or saved ~= true then
            self:Record("checkpoint_failed", active, now,
                ok and (saveReason or "Checkpoint rejected") or "Checkpoint raised")
            self.active = nil
            return "checkpoint_failed"
        end
    end

    active.sentAt = now -- Immutable first-send time, even if transport raises.
    active.phase = "sent"
    active.latestObservedRevision = snapshot.revision
    self.lastSendAt = now
    self.seen[active.proposal.actionKey] = true
    self:Record("sent", active, now)
    local token = active.token
    local function canDispatch()
        local dispatchAt = self.clock:Now()
        return not self.stopped and self.active == active
            and active.phase == "sent"
            and dispatchAt - active.sentAt < 45
            and dispatchAt >= snapshot.capturedAt
            and dispatchAt - snapshot.capturedAt <= self.freshness
            and active.latestObservedRevision == snapshot.revision
            and (type(self.policy.canSend) ~= "function"
                or self.policy.canSend())
    end
    local sendOk = pcall(self.transport.Send, self.transport, active.proposal, function(reply)
        local current = self.active
        local callbackAt = self.clock:Now()
        if not current or current.token ~= token then
            self:Record("late_return", active, callbackAt, "Owner changed")
            return
        end
        if callbackAt - current.sentAt >= 45 then
            self:Expire(current, callbackAt)
            self:Record("late_return", active, callbackAt, "Deadline passed")
            return
        end
        if current.phase == "returned" then return end
        current.reply = reply
        current.phase = "returned"
        self:Record("returned", current, callbackAt)
    end, canDispatch)
    if not sendOk then self:Record("transport_error", active, self.clock:Now(), "Send raised") end
    return "sent"
end

function Methods:Observe(rawSnapshot)
    local active = self.active
    if not active or active.sentAt == nil then return "ignored" end
    local now = self.clock:Now()
    if now - active.sentAt >= 45 then
        self:Tick(rawSnapshot)
        return "skipped_unconfirmed"
    end
    local snapshot = self:Fresh(rawSnapshot, now)
    if not snapshot or snapshot.revision < active.before.revision then return "pending" end
    active.latestObservedRevision = math.max(
        active.latestObservedRevision or active.before.revision,
        snapshot.revision)
    local confirm = self.policy.confirm
    if type(confirm) ~= "function" then return "pending" end
    local ok, result = pcall(confirm, active.proposal, active.before,
        rawSnapshot, active.reply, active.beforeEvidence)
    if not ok or (result ~= "confirmed" and result ~= "rejected") then return "pending" end
    if result == "confirmed" and snapshot.revision <= active.before.revision then
        return "pending"
    end
    if result == "rejected" and type(active.reply) == "table"
        and active.reply.ok == false
        and active.reply.code == "rate_limited" then
        local retry = tonumber(active.reply.retryIn)
        if type(retry) ~= "number" or retry ~= retry
            or retry <= 0 or retry == math.huge then
            retry = 1
        end
        retry = math.max(1, math.min(86400, retry))
        local feature = active.proposal.feature
        self.cooldownUntil[feature] = math.max(
            self.cooldownUntil[feature] or 0, now + retry)
    end
    self:Record(result, active, now)
    if type(self.policy.afterResolve) == "function" then
        local resolveOk, resolved = pcall(self.policy.afterResolve, active.proposal, result)
        if not resolveOk or resolved ~= true then
            self:Record("checkpoint_failed", active, now, "Checkpoint clear failed")
        end
    end
    self.active = nil
    return result
end

function Methods:Stop()
    self.stopped = true
    if self.active and self.active.sentAt == nil then self.active = nil end
end

function Methods:Status()
    local nextSendAt = self.lastSendAt and self.lastSendAt + self.spacing or 0
    local cooldowns = {}
    for feature, untilTime in pairs(self.cooldownUntil) do cooldowns[feature] = untilTime end
    return { active = activeView(self.active), nextSendAt = nextSendAt,
        cooldownUntil = cooldowns }
end

return Broker
