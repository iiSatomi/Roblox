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
        seenFeatures = {},
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

function Methods:Reserve(proposal, raw, checkOnly)
    local owner = self.policy.reservations
    if owner == nil then return true end
    local ok, claims, reason = pcall(owner.Check, owner, proposal, raw)
    if not ok or type(claims) ~= "table" then
        return false, ok and (reason or "Reservation refused") or "Reservation owner raised"
    end
    if checkOnly then
        local expected = proposal.custody
        if type(expected) ~= "table" or expected.allCrew ~= claims.allCrew
            or expected.allItems ~= claims.allItems then return false, "Reserved identity changed" end
        for _, field in ipairs({"members", "items", "funds"}) do
            for key, value in pairs(claims[field]) do
                if expected[field][key] ~= value then return false, "Reserved identity changed" end
            end
            for key, value in pairs(expected[field]) do
                if claims[field][key] ~= value then return false, "Reserved identity changed" end
            end
        end
    else
        proposal.custody = claims
    end
    return true
end

function Methods:Expire(active, now)
    if not self.active or self.active.token ~= active.token then return end
    self:Record("skipped_unconfirmed", active, now,
        "No action-specific confirmation by first send + 45s", true)
    if type(self.transport.ReleaseExpired) == "function" then
        pcall(self.transport.ReleaseExpired, self.transport, active.proposal)
    end
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
    local reserved, reservationReason = self:Reserve(proposal, rawSnapshot)
    if not reserved then return "blocked", reservationReason end
    if self.seen[proposal.actionKey] then return "blocked", "Action key already sent" end
    if now < (self.cooldownUntil[proposal.feature] or 0) then
        return "blocked", "Feature cooling down"
    end
    local dispatchToken
    if type(self.policy.dispatchToken) == "function" then
        local ok, value = pcall(self.policy.dispatchToken, proposal)
        if not ok or value == nil then return "blocked", "Feature choices unavailable" end
        dispatchToken = value
    end
    self.serial = self.serial + 1
    self.active = {
        token = self.serial, proposal = proposal, before = snapshot,
        phase = "admitted", sentAt = nil, reply = nil,
        dispatchToken = dispatchToken,
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
    if active.preparing then return "preparing" end

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
    active.preparing = true -- Includes yielding feature/checkpoint write-ahead.
    local nativeCallToken
    if type(self.transport.Validate) == "function" then
        local checked, valid, transportReason, token = pcall(
            self.transport.Validate, self.transport, active.proposal)
        if not checked or valid ~= true then
            self:Record("transport_blocked", active, now,
                checked and (transportReason or "Unsupported call")
                    or "Transport validation raised")
            self.active = nil
            return "transport_blocked"
        end
        nativeCallToken = token
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

    if self.stopped or self.active ~= active then return "stopped" end

    local reserved, reservationReason = self:Reserve(active.proposal, rawSnapshot, true)
    if not reserved then
        self:Record("reservation_blocked", active, now, reservationReason)
        self.active = nil
        return "reservation_blocked"
    end
    if self.stopped or self.active ~= active then return "stopped" end
    if type(self.policy.beforeSend) == "function" then
        local ok, saved, saveReason = pcall(self.policy.beforeSend, active.proposal, rawSnapshot, active.beforeEvidence)
        if not ok or saved ~= true then
            if type(self.policy.abandonedUnsent) == "function" then
                pcall(self.policy.abandonedUnsent, active.proposal, rawSnapshot, active.beforeEvidence)
            end
            self:Record("checkpoint_failed", active, now,
                ok and (saveReason or "Checkpoint rejected") or "Checkpoint raised")
            if self.active == active then self.active = nil end
            return "checkpoint_failed"
        end
    end
    if self.stopped or self.active ~= active then
        if type(self.policy.abandonedUnsent) == "function" then
            pcall(self.policy.abandonedUnsent, active.proposal, rawSnapshot, active.beforeEvidence)
        end
        return "stopped"
    end

    active.sentAt = now -- Immutable first-send time, even if transport raises.
    active.phase = "sent"
    active.latestObservedRevision = snapshot.revision
    local token = active.token
    local function canDispatch()
        local function current()
            local sending = type(self.policy.canSend) ~= "function" or self.policy.canSend()
            local dispatchAt = self.clock:Now()
            return sending and not self.stopped and self.active == active and active.phase == "sent"
                and dispatchAt - active.sentAt < 45 and dispatchAt >= snapshot.capturedAt
                and dispatchAt - snapshot.capturedAt <= self.freshness
                and active.latestObservedRevision == snapshot.revision
        end
        if not current() then return false end
        local selectionAllowed = true
        if type(self.policy.canDispatch) == "function" then
            local ok, allowed = pcall(self.policy.canDispatch, active.proposal, active.dispatchToken)
            selectionAllowed = ok and allowed == true
        end
        return selectionAllowed
            and self:Reserve(active.proposal, rawSnapshot, true) == true
            and current()
    end
    local sendOk, scheduled = pcall(self.transport.Send, self.transport, active.proposal, function(reply)
        local current = self.active
        local callbackAt = self.clock:Now()
        if self.stopped or not current or current.token ~= token then
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
        if type(self.policy.recordReply) == "function" then
            local persisted, saved = pcall(self.policy.recordReply, current.proposal, reply)
            if not persisted or saved ~= true then
                self:Record("checkpoint_failed", current, callbackAt, "Returned result was not persisted")
            end
        end
        self:Record("returned", current, callbackAt)
    end, canDispatch, nativeCallToken, function()
        if active.phase ~= "sent" then return end -- A returned invocation cannot become unsent.
        if type(self.policy.abandonedUnsent) == "function" then
            pcall(self.policy.abandonedUnsent, active.proposal, rawSnapshot, active.beforeEvidence)
        end
        if self.stopped or self.active ~= active then
            -- Old owners may append exact unsent facts, never rewrite the main checkpoint.
            return
        end
        local cleared, resolved = true, true
        if type(self.policy.afterResolve) == "function" then
            cleared, resolved = pcall(self.policy.afterResolve, active.proposal, "schedule_failed")
        end
        if self.active == active then self.active = nil end
        self.seen[active.proposal.actionKey] = nil
        self.seenFeatures[active.proposal.actionKey] = nil
        self:Record(cleared and resolved == true and "cancelled_unsent" or "checkpoint_failed",
            active, self.clock:Now(), "Native invocation did not begin")
    end, self.policy.authorize and (not self.policy.requiresAuthorization or self.policy.requiresAuthorization(active.proposal)) and function()
        return self.policy.authorize(active.proposal, rawSnapshot, active.beforeEvidence)
    end or nil)
    if sendOk and scheduled == false and type(self.policy.abandonedUnsent) == "function" then
        pcall(self.policy.abandonedUnsent, active.proposal, rawSnapshot, active.beforeEvidence)
    end
    if self.stopped then return "stopped" end
    if self.active ~= active then return "cancelled_unsent" end
    if sendOk and scheduled == false then
        -- The transport explicitly refused scheduling and fenced its callback.
        -- No native invocation occurred, so clear the write-ahead record.
        local cleared, resolved = true, true
        if type(self.policy.afterResolve) == "function" then
            cleared, resolved = pcall(self.policy.afterResolve,
                active.proposal, "schedule_failed")
        end
        self.active = nil
        if not cleared or resolved ~= true then
            self:Record("checkpoint_failed", active, self.clock:Now(),
                "Unsent checkpoint clear failed")
            return "checkpoint_failed"
        end
        self:Record("schedule_failed", active, self.clock:Now(),
            "Native scheduling refused")
        return "schedule_failed"
    end
    self.lastSendAt = now
    self.seen[active.proposal.actionKey] = true
    self.seenFeatures[active.proposal.actionKey] = active.proposal.feature
    self:Record("sent", active, now)
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
    if type(self.transport.ReleaseResolved) == "function" then
        pcall(self.transport.ReleaseResolved, self.transport, active.proposal, result)
    end
    if type(self.policy.afterResolve) == "function" then
        local resolveOk, resolved = pcall(self.policy.afterResolve, active.proposal, result, rawSnapshot)
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

function Methods:ClearCompletedFeatureKeys(feature)
    if self.active or self.stopped then return false end
    for key, owner in pairs(self.seenFeatures) do
        if owner == feature then self.seen[key], self.seenFeatures[key] = nil, nil end
    end
    -- Server retry cooldown and global send spacing remain in force.
    return true
end

function Methods:Status()
    local nextSendAt = self.lastSendAt and self.lastSendAt + self.spacing or 0
    local cooldowns = {}
    for feature, untilTime in pairs(self.cooldownUntil) do cooldowns[feature] = untilTime end
    return { active = activeView(self.active), nextSendAt = nextSendAt,
        cooldownUntil = cooldowns }
end

return Broker
