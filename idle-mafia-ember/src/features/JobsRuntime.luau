-- Injected ordinary-Jobs composition. No Roblox service or executor access here.
local JobsRuntime = {}
local Methods = {}
Methods.__index = Methods

local function uncertainEnergy(checkpoint)
    local amount = 0
    for _, record in ipairs(checkpoint:Records()) do
        amount = amount + (record.resources.energy or 0)
    end
    return amount
end

function JobsRuntime.new(deps)
    assert(type(deps) == "table" and type(deps.modules) == "table",
        "Missing Jobs runtime dependencies")
    assert(deps.tab == nil or (type(deps.tab) == "table"
        and deps.tab.id == "jobs"
        and type(deps.tab.Enrich) == "function"),
        "Invalid Jobs tab module")
    local m = deps.modules
    local journal = m.Journal.new(100)
    local broker = m.Broker.new(deps.clock, deps.transport, journal, {
        contracts = m.Contracts, session = deps.identity,
        maxSnapshotAge = 2, minInterval = 1, cooldownSeconds = 45,
        captureBefore = m.JobsEvidence.capture,
        confirm = m.JobsEvidence.evaluate,
    })
    local checkpoint = m.Checkpoint.new(deps.storage)
    local session = m.Session.new(broker, checkpoint, deps.identity)
    session:Pause()
    return setmetatable({
        clock = deps.clock, identity = deps.identity, journal = journal,
        checkpoint = checkpoint, session = session,
        context = m.Context.new(m.Contracts), scheduler = m.Scheduler.new(),
        jobsState = m.JobsState, jobs = m.Jobs,
        tab = deps.tab,
        requested = false, lastOutcome = nil, reason = "Paused",
    }, Methods)
end

function Methods:Pause()
    self.requested = false
    self.session:Pause()
    self.reason = "Paused"
end

function Methods:Resume()
    if self.session:Status().state == "paused" then
        self.requested = true
        self.reason = nil
    end
end

function Methods:Stop()
    self.requested = false
    self.session:Stop()
    self.reason = "Stopped"
end

function Methods:Close()
    self.requested = false
    self.session:Close()
    self.reason = "Closed"
end

function Methods:Status()
    local status = self.session:Status()
    status.recentActions = self.journal:PublicEvents(10)
    status.lastOutcome = self.lastOutcome
    status.reason = self.reason
    return status
end

function Methods:Step(raw, settings)
    local state = self.session:Status().state
    if state == "closed" or state == "stopped" then return self:Status() end
    local sourceReason
    if self.tab then
        local ok, enriched, reason = pcall(self.tab.Enrich,
            self.tab, raw)
        if ok and type(enriched) == "table" then
            raw = enriched
        else
            sourceReason = ok and (reason or "Jobs catalog unavailable")
                or "Jobs tab source failed"
        end
    end
    if not self.requested or type(settings) ~= "table"
        or settings.enabled ~= true then
        self.session:Pause()
    else
        self.session:Resume()
    end

    -- Sent requests retain their owner while paused; only evidence or the
    -- immutable 45-second deadline can settle them.
    local observed = self.session:Observe(raw)
    if observed == "confirmed" or observed == "rejected"
        or observed == "skipped_unconfirmed" then
        self.lastOutcome = observed
    end
    local ticked = self.session:Tick(raw)
    if ticked == "skipped_unconfirmed" then self.lastOutcome = ticked end
    if self.session:Status().state ~= "running" then return self:Status() end
    if self.session:Status().active then return self:Status() end
    if sourceReason then self.reason = sourceReason; return self:Status() end

    local now = self.clock:Now()
    local context, reason = self.context:Read(raw, self.identity, now, 2)
    if not context then self.reason = reason; return self:Status() end
    local view
    view, reason = self.jobsState.read(raw, context)
    if not view then self.reason = reason; return self:Status() end
    local exposure = uncertainEnergy(self.checkpoint)
    local proposal
    proposal, reason = self.jobs.propose(view, settings,
        { energy = 0, uncertainEnergy = exposure })
    if not proposal then self.reason = reason; return self:Status() end
    local chosen
    chosen, reason = self.scheduler:Choose(context, {
        proposals = { proposal }, enabled = { jobs = true },
        reservations = { energy = 0 }, uncertain = { energy = exposure },
    }, self.session:Status(), now)
    if not chosen then self.reason = reason; return self:Status() end
    local admitted
    admitted, reason = self.session:Offer(chosen, raw)
    if admitted ~= "admitted" then self.reason = reason; return self:Status() end
    local sent = self.session:Tick(raw)
    if sent == "sent" then self.reason = nil else self.reason = sent end
    return self:Status()
end

return JobsRuntime
