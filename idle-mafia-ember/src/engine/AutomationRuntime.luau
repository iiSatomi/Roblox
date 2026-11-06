-- One injected broker/session for all ordinary feature descriptors.
local AutomationRuntime = {}
local function familyId(value)
    return type(value) == "string" and #value > 0 and #value <= 120
        and not value:find("[%c]")
        or type(value) == "number" and value == value and value >= 1
            and value <= 9007199254740991 and value % 1 == 0
end
local Methods = {}
Methods.__index = Methods

local function exposure(checkpoint)
    local totals = {}
    for _, record in ipairs(checkpoint:Records()) do
        for resource, amount in pairs(record.resources) do
            if type(amount) == "number" and amount > 0 then
                totals[resource] = (totals[resource] or 0) + amount
            end
        end
    end
    return totals
end

local function copy(source)
    local result = {}
    for key, value in pairs(source) do result[key] = value end
    return result
end

local function withUsageProofs(raw, checkpoint, reservations, controller, readController, currentController, readEnabled)
    if type(raw) ~= "table" then return raw end
    local observed = copy(raw)
    -- The board supplies the native day; the local checkpoint supplies
    -- the sent-attempt count. Never accept a caller-provided count.
    observed.favorUsageProof = nil
    observed.sabotageUsageProof = nil
    observed.bossUsageProof = nil
    observed.globalClaimUsageProof = nil
    observed.globalAttackUsageProof = nil
    observed.familyClaimUsageProof = nil
    observed.familyClaimUsageProofs = nil
    observed.familyAttackUsageProof = nil
    observed.familyUsageProof = nil
    observed.eventShopUsageProof = nil
    observed.marketRentUsageProof = nil
    observed.crewHireUsageProof=nil
    observed.prestigeUsageProof = nil -- Caller reset budgets/clear flags are never authoritative.
    if type(checkpoint.PrestigeUsage) == "function" then
        local proof = checkpoint:PrestigeUsage(raw)
        if proof then
            proof.controllersClear = false
            if readEnabled and type(controller) == "table" and type(readController) == "function"
                and type(currentController) == "function" and controller.Read == readController and controller.Current == currentController then
                local currentOk, valid = pcall(currentController, controller)
                if currentOk and valid == true then
                    local readOk, value = pcall(readController, controller)
                    local afterOk, afterValid = pcall(currentController, controller)
                    if readOk and type(value) == "table" and afterOk and afterValid == true
                        and controller.Read == readController and controller.Current == currentController
                        and type(raw.native) == "table" and raw.native.fullSync == true
                        and value.rank == raw.native.prestige and value.level == raw.native.level and value.xp == raw.native.xp then
                        proof.controllersClear = value.controllersClear == true and value.ready == true
                    end
                end
            end
            observed.prestigeUsageProof = proof
        end
    end
    observed.residencyUsageProof = nil
    if type(checkpoint.ResidencyUsage) == "function" then
        local attempted = checkpoint:ResidencyUsage(raw)
        if attempted ~= nil then
            local proof = {attempted = attempted}
            for _, key in ipairs({"session", "account", "place", "release", "revision", "capturedAt"}) do proof[key] = raw[key] end
            observed.residencyUsageProof = proof
        end
    end
    observed.stationReservationProof = nil
    if type(checkpoint.StationUsage) == "function" and reservations then
        local attempted = checkpoint:StationUsage(raw)
        local held = reservations:Held(raw)
        if attempted ~= nil and held then
            local proof = {members = {}, attempted = attempted, pendingStation = {}, stationUnknown = false}
            for _, record in ipairs(checkpoint:Records()) do
                if record.feature == "station" then
                    local data = checkpoint:Recovery(record.actionKey)
                    local intent = data and data.proposal and data.proposal.intent
                    if type(intent) == "table" and (intent.kind == "territoryStation" or intent.kind == "territoryRecall")
                        and type(intent.memberKey) == "string" and #intent.memberKey <= 131
                        and intent.memberKey:match("^id:.+") then
                        if intent.kind == "territoryStation" then proof.pendingStation[intent.memberKey] = true end
                    else proof.stationUnknown = true end
                end
            end
            for _, key in ipairs({"session", "account", "place", "release", "revision", "capturedAt"}) do proof[key] = raw[key] end
            for slot, row in pairs(type(raw.native) == "table" and raw.native.crew or {}) do
                if type(row) == "table" and type(row.healId) == "string"
                    and (held.allCrew or held.members["slot:" .. slot] or held.members["id:" .. row.healId]) then
                    proof.members["id:" .. row.healId] = true
                end
            end
            observed.stationReservationProof = proof
        end
    end
    observed.bossShopUsageProof = nil
    observed.purchaseSavings = nil
    observed.collectionProtection = nil
    observed.shopQuoteProof = nil
    observed.crateLuckProof = nil
    observed.weekendBuff = nil
    observed.groupMembership = nil
    -- Funding is derived from enabled purchases below, never from a caller.
    observed.fundingRequest = nil
    if type(checkpoint.FamilyContributionUsage) == "function" then
        observed.familyUsageProof = checkpoint:FamilyContributionUsage(raw)
    end
    if type(checkpoint.EventShopUsage) == "function" then observed.eventShopUsageProof = checkpoint:EventShopUsage(raw) end
    if type(checkpoint.CrewHireUsage)=="function" then observed.crewHireUsageProof=checkpoint:CrewHireUsage(raw) end
    if type(checkpoint.PlayerFightUsage) == "function" then observed.playerFightUsageProof = checkpoint:PlayerFightUsage(raw) end
    if type(checkpoint.MarketRentUsage) == "function" then observed.marketRentUsageProof = checkpoint:MarketRentUsage(raw) end
    if type(checkpoint.BossShopUsage) == "function" then
        observed.bossShopUsageProof = checkpoint:BossShopUsage(
            raw.session, raw.capturedAt)
    end
    local proof = raw.heistBoardProof
    local board = type(proof) == "table" and proof.board
    local serverNow = type(board) == "table" and board.serverNow
    if type(serverNow) == "number" and serverNow == serverNow
        and serverNow >= 0 and serverNow < math.huge then
        local day = math.floor(serverNow / 86400)
        if type(checkpoint.FavorUsage) == "function" then
            observed.favorUsageProof = checkpoint:FavorUsage(
                day, raw.capturedAt)
        end
        if type(checkpoint.SabotageUsage) == "function" then
            observed.sabotageUsageProof = checkpoint:SabotageUsage(
                day, raw.capturedAt)
        end
    end
    local native = raw.native
    local bossNow = type(native) == "table" and native.serverNow
    if type(bossNow) == "number" and bossNow == bossNow
        and bossNow >= 0 and bossNow < math.huge
        and type(checkpoint.BossUsage) == "function" then
        local converted, textDay = pcall(function()
            return os.date("!%Y%j", math.floor(bossNow))
        end)
        local day = converted and tonumber(textDay)
        if day then
            observed.bossUsageProof = checkpoint:BossUsage(
                day, raw.capturedAt)
        end
    end
    local eventProof = raw.globalBossProof
    local event = type(eventProof) == "table" and eventProof.event
    if type(event) == "table" and type(event.id) == "string"
        and #event.id > 0 and type(event.startAt) == "number"
        and event.startAt == event.startAt
        and event.startAt >= 0 and event.startAt < math.huge
        and event.startAt % 1 == 0
        and type(checkpoint.GlobalClaimUsage) == "function" then
        local run = event.id .. "_" .. tostring(event.startAt)
        observed.globalClaimUsageProof = checkpoint:GlobalClaimUsage(
            run, raw.capturedAt)
        if type(checkpoint.GlobalAttackUsage) == "function" then
            observed.globalAttackUsageProof = checkpoint:GlobalAttackUsage(
                run, raw.capturedAt)
        end
    end
    local familyProof = raw.familyTakedownProof
    local family = type(familyProof) == "table"
        and familyProof.state
    if type(family) == "table"
        and type(family.week) == "number"
        and family.week == family.week
        and family.week >= 1 and family.week < math.huge
        and family.week % 1 == 0
        and type(checkpoint.FamilyClaimUsage) == "function" then
        local proofs, weeks = {}, { [family.week] = true }
        for _, counted in ipairs(checkpoint.familyClaimUsage or {}) do
            if counted.week <= family.week then weeks[counted.week] = true end
        end
        if type(family.claims) == "table" then
            local count = 0
            for _, claim in ipairs(family.claims) do
                count = count + 1
                if count > 32 then break end
                if type(claim) == "table"
                    and type(claim.week) == "number"
                    and claim.week == claim.week
                    and claim.week >= 1 and claim.week < math.huge
                    and claim.week % 1 == 0 then
                    weeks[claim.week] = true
                end
            end
        end
        for week in pairs(weeks) do
            local usage = checkpoint:FamilyClaimUsage(
                week, raw.capturedAt)
            if usage then proofs[tostring(week)] = usage end
        end
        observed.familyClaimUsageProofs = proofs
        observed.familyClaimUsageProof = proofs[tostring(family.week)]
        if familyId(family.famId)
            and type(checkpoint.FamilyAttackUsage)
                == "function" then
            observed.familyAttackUsageProof =
                checkpoint:FamilyAttackUsage(family.week,
                    family.famId, raw.capturedAt)
        end
    end
    return observed
end

function AutomationRuntime.new(deps)
    assert(type(deps) == "table" and type(deps.modules) == "table"
        and type(deps.features) == "table" and #deps.features > 0,
        "Missing automation runtime dependencies")
    local features = {}
    for _, spec in ipairs(deps.features) do
        assert(type(spec) == "table" and type(spec.id) == "string"
            and #spec.id > 0 and not features[spec.id]
            and type(spec.reader) == "table"
            and type(spec.reader.read) == "function"
            and type(spec.planner) == "table"
            and type(spec.planner.propose) == "function"
            and type(spec.evidence) == "table"
            and type(spec.evidence.capture) == "function"
            and type(spec.evidence.evaluate) == "function"
            and (spec.canDispatch == nil or type(spec.canDispatch) == "function"),
            "Invalid or duplicate feature descriptor")
        assert(spec.goals == nil or type(spec.goals) == "table" and type(spec.goals.derive) == "function"
            and type(spec.goals.observe) == "function", "Invalid goal request module")
        features[spec.id] = spec
        assert(spec.recoverSaved == nil or type(spec.recoverSaved) == "function", "Invalid saved-outcome reader")
        assert(spec.recordOutcome == nil or type(spec.recordOutcome) == "function", "Invalid durable-outcome writer")
        if spec.lifecycle ~= nil then
            assert(type(spec.lifecycle) == "table", "Invalid feature lifecycle")
            for _, key in ipairs({"prepare", "authorize", "returned", "resolve", "unsent"}) do
                assert(type(spec.lifecycle[key]) == "function", "Missing feature lifecycle hook: " .. key)
            end
            assert(spec.lifecycle.recover == nil or type(spec.lifecycle.recover) == "function", "Invalid feature recovery hook")
            assert(spec.lifecycle.recoveryFactory == nil or type(spec.lifecycle.recoveryFactory) == "function", "Invalid feature recovery factory")
        end
    end
    if deps.snapshotAssembler ~= nil then
        assert(type(deps.snapshotAssembler) == "table"
            and type(deps.snapshotAssembler.Enrich) == "function"
            and type(deps.featurePages) == "table",
            "Missing tab source composition")
        for id in pairs(features) do
            assert(type(deps.featurePages[id]) == "string"
                and #deps.featurePages[id] > 0,
                "Missing feature tab ownership: " .. id)
        end
    end
    local m = deps.modules
    local selection = {}
    local function readSelection(feature)
        if selection.read == nil then return false end
        local ok, choices = pcall(selection.read, feature)
        if not ok or type(choices) ~= "table" then return nil end
        local copied = {}
        for key, value in pairs(choices) do copied[key] = value end
        return copied
    end
    local journal = m.Journal.new(100)
    local checkpoint = m.Checkpoint.new(deps.storage, m.FamilyContributionUsage, m.ResourceReservations, m.PendingAction, m.EventShopUsage, m.MarketRentUsage,m.CrewHireUsage,m.PlayerFightUsage)
    local reservationOwner
    if m.ResourceReservations ~= nil then
        reservationOwner = m.ResourceReservations.new(deps.identity,
            function()
                if checkpoint.fault then error("Checkpoint custody unavailable") end
                return checkpoint:Records()
            end, deps.reservationSources)
    end
    local broker = m.Broker.new(deps.clock, deps.transport, journal, {
        contracts = m.Contracts, session = deps.identity,
        reservations = reservationOwner,
        maxSnapshotAge = 2, minInterval = 1, cooldownSeconds = 45,
        dispatchToken = function(proposal) return readSelection(proposal.feature) end,
        canDispatch = function(proposal, expected)
            local current = readSelection(proposal.feature)
            if current == false then
                if expected ~= false then return false end
            else
                if type(current) ~= "table" or type(expected) ~= "table" then return false end
                for key, value in pairs(current) do if expected[key] ~= value then return false end end
                for key, value in pairs(expected) do if current[key] ~= value then return false end end
            end
            local guard = features[proposal.feature].canDispatch
            return guard == nil or (type(guard) == "function" and guard(proposal) == true)
        end,
        captureBefore = function(proposal, raw)
            local spec = features[proposal.feature]
            if not spec then return nil, "Unknown feature" end
            return spec.evidence.capture(proposal, raw)
        end,
        confirm = function(proposal, before, after, reply, baseline)
            local spec = features[proposal.feature]
            if not spec then return "pending" end
            return spec.evidence.evaluate(proposal, before, after, reply, baseline)
        end,
    })
    if type(m.heistRuntime) == "table" and type(m.heistRuntime.BindAccounting) == "function" then
        assert(m.heistRuntime:BindAccounting(checkpoint) == true, "Heist accounting owner changed")
    end
    local session = m.Session.new(broker, checkpoint, deps.identity)
    local saveBefore, resolveAfter, saveReply = broker.policy.beforeSend, broker.policy.afterResolve, broker.policy.recordReply
    local abandonedUnsent = broker.policy.abandonedUnsent
    local function lifecycle(proposal) return features[proposal.feature].lifecycle end
    local function failed(reason)
        session.storageFault = reason or "Feature transaction persistence failed"
        return false, session.storageFault
    end
    broker.policy.beforeSend = function(proposal, raw, baseline)
        local owner = lifecycle(proposal)
        if owner then
            local ok, prepared, why = pcall(owner.prepare, proposal, raw, baseline, deps.clock:Now())
            if not ok or prepared ~= true then return failed(ok and why or "Feature preparation raised") end
            if session.state ~= "running" then return false, "Session changed during preparation" end
        end
        local saved, why = saveBefore(proposal, raw, baseline)
        if not saved and owner then pcall(owner.unsent, proposal) end
        return saved, why
    end
    broker.policy.requiresAuthorization = function(proposal) return lifecycle(proposal) ~= nil end
    broker.policy.authorize = function(proposal, raw)
        local owner = lifecycle(proposal)
        if owner then return owner.authorize(proposal, raw, deps.clock:Now()) end
        return nil
    end
    broker.policy.abandonedUnsent = function(proposal, before, baseline)
        local owner = lifecycle(proposal)
        if owner then return type(owner.abandonedUnsent) == "function" and owner.abandonedUnsent(proposal) == true end
        return abandonedUnsent and abandonedUnsent(proposal, before, baseline)
    end
    broker.policy.recordReply = function(proposal, reply)
        local owner = lifecycle(proposal)
        if owner then
            local ok, saved, why = pcall(owner.returned, proposal, reply)
            if not ok or saved ~= true then return failed(ok and why or "Feature result persistence raised") end
        end
        return not saveReply or saveReply(proposal, reply)
    end
    broker.policy.afterResolve = function(proposal, outcome, after)
        if session.state == "stopped" or session.state == "closed" then return false end
        local owner = lifecycle(proposal)
        if owner then
            local ok, saved, why
            if outcome == "schedule_failed" then ok, saved, why = pcall(owner.unsent, proposal)
            else ok, saved, why = pcall(owner.resolve, proposal, outcome, after, deps.clock:Now()) end
            if not ok or saved ~= true then return failed(ok and why or "Feature outcome persistence raised") end
        end
        local writer = features[proposal.feature].recordOutcome
        if writer and outcome == "confirmed" then
            local data = checkpoint:Recovery(proposal.actionKey)
            local ok, saved, why = pcall(writer, data, after, outcome)
            if not ok or saved ~= true then return failed(ok and why or "Confirmed outcome persistence raised") end
        end
        if session.state == "stopped" or session.state == "closed" then return false end
        return resolveAfter(proposal, outcome)
    end
    session:Pause()
    local self = setmetatable({
        clock = deps.clock, identity = deps.identity, features = features,
        selection = selection,
        snapshotAssembler = deps.snapshotAssembler,
        tabInstances = deps.tabInstances or {}, readCoordinator = deps.readCoordinator,
        readSources = deps.readSources or {}, closed = false,
        featurePages = deps.featurePages or {},
        modules = m,
        reservationOwner = reservationOwner,
        order = deps.features, checkpoint = checkpoint, session = session,
        journal = journal, context = m.Context.new(m.Contracts,
            m.EconomyContext, m.BuffContext, m.HeistBoardState,
            m.BossStageState, m.GlobalBossState,
            m.BossShopState, m.FamilyTakedownState),
        scheduler = m.Scheduler.new(), requested = false,
        goalStates = {}, goalObserved = {}, outcomes = {}, recoveries = {}, recoveryControls = {}, reasons = {}, globalReason = "Paused",
    }, Methods)
    self.nativePrestigeController = m.nativePrestigeController
    self.nativePrestigeRead = type(m.nativePrestigeController) == "table" and m.nativePrestigeController.Read or nil
    self.nativePrestigeCurrent = type(m.nativePrestigeController) == "table" and m.nativePrestigeController.Current or nil
    if type(m.PlayerInfoState) == "table" and type(m.PlayerInfoState.new) == "function" then
        self.playerInfo = m.PlayerInfoState.new(deps.identity)
        self.playerInfoSource = m.playerInfoSource
        self.playerInfoRead = type(m.playerInfoSource) == "table" and m.playerInfoSource.Read or nil
        self.playerInfoCurrent = type(m.playerInfoSource) == "table" and m.playerInfoSource.Current or nil
    end
    if type(m.AllowanceReset) == "table" and reservationOwner then
        self.allowanceReset = m.AllowanceReset.new({checkpoint = checkpoint, session = session,
            clock = deps.clock, identity = deps.identity, reservations = reservationOwner,
            requested = function() return self.requested end,
            currentSnapshot = function() return self.allowanceSnapshot end})
    end
    for _, spec in ipairs(deps.features) do
        local factory = spec.lifecycle and spec.lifecycle.recoveryFactory
        if factory then
            local ok, control = pcall(factory, {checkpoint = checkpoint, session = session,
                identity = deps.identity, clock = deps.clock,
                currentSnapshot = function() return self.allowanceSnapshot end,
                requested = function() return self.requested end,
                busy = function() return self.recovering == true or self:AllowanceResetBusy() or self:FeatureRecoveryBusy() end})
            local valid = ok and type(control) == "table"
            for _, key in ipairs({"Preview", "Confirm", "Invalidate", "IsBusy", "Close"}) do
                valid = valid and type(control[key]) == "function"
            end
            if not valid then self:Close(); error("Invalid feature recovery controls", 0) end
            self.recoveryControls[spec.id] = control
        end
    end
    return self
end

-- Availability describes configured ownership, never current readiness or permission.
function Methods:SupportsPrestigeReset()
    local feature, source = self.features.prestige, self.nativePrestigeController
    return not self.closed and not self.closing and type(feature) == "table"
        and type(feature.canDispatch) == "function" and type(feature.recoverSaved) == "function"
        and type(self.checkpoint.PrestigeUsage) == "function" and type(source) == "table"
        and type(self.nativePrestigeRead) == "function" and type(self.nativePrestigeCurrent) == "function"
        and source.Read == self.nativePrestigeRead and source.Current == self.nativePrestigeCurrent
end

function Methods:SupportsHeistAction(feature)
    local supported = {heists = true, heistCollect = true, favors = true, sabotage = true}
    local spec = supported[feature] and self.features[feature]
    return not self.closed and not self.closing and type(spec) == "table"
        and type(spec.lifecycle) == "table" and type(spec.canDispatch) == "function"
        and type(spec.recoverSaved) == "function" and type(self.modules.heistRuntime) == "table"
end

function Methods:SupportsFeatureRecovery(feature) return not self.closed and self.recoveryControls[feature] ~= nil end
function Methods:FeatureRecoveryBusy()
    for _, control in pairs(self.recoveryControls) do if control:IsBusy() then return true end end
    return false
end
function Methods:PreviewFeatureRecovery(feature)
    local control = self.recoveryControls[feature]
    if self.closed or not control then return nil, "Feature recovery is unavailable" end
    return control:Preview()
end
function Methods:ConfirmFeatureRecovery(feature, ticket)
    local control = self.recoveryControls[feature]
    if self.closed or not control then return false, "Feature recovery is unavailable" end
    local saved, reason = control:Confirm(ticket)
    if not saved and self.checkpoint.fault then self.session.storageFault = self.checkpoint.fault end
    return saved, reason
end
function Methods:CancelFeatureRecovery()
    for _, control in pairs(self.recoveryControls) do control:Invalidate() end
end

function Methods:SupportsAllowanceReset() return self.allowanceReset ~= nil and not self.closed end
function Methods:AllowanceResetBusy() return self.allowanceReset and self.allowanceReset:IsBusy() or false end
function Methods:PreviewAllowanceReset(feature)
    if not self.allowanceReset then return nil, "Allowance controls are unavailable" end
    return self.allowanceReset:Preview(feature)
end
function Methods:CancelAllowanceReset()
    if self.allowanceReset then self.allowanceReset:Invalidate() end
end
function Methods:ConfirmAllowanceReset(ticket)
    if not self.allowanceReset then return false, "Allowance controls are unavailable" end
    local saved, reason, feature = self.allowanceReset:Confirm(ticket)
    if not saved and self.checkpoint.fault then self.session.storageFault = self.checkpoint.fault end
    if saved and feature then self.session.broker:ClearCompletedFeatureKeys(feature) end
    return saved, reason
end

function Methods:SetSelectionGuard(callback)
    assert(type(callback) == "function", "Missing feature selection guard")
    self.selection.read = callback
end

function Methods:Pause()
    self:CancelFeatureRecovery()
    self:CancelAllowanceReset()
    self.requested = false
    self.session:Pause()
    self.globalReason = "Paused"
end

function Methods:Resume()
    if self:FeatureRecoveryBusy() then return false, "Feature recovery is saving; wait before resuming" end
    self:CancelFeatureRecovery()
    if self:AllowanceResetBusy() then return false, "Allowance reset is saving; wait before resuming" end
    self:CancelAllowanceReset()
    if self.session:Status().state == "paused" then
        self.requested = true
        self.globalReason = nil
    end
end

function Methods:Stop()
    for _, control in pairs(self.recoveryControls) do control:Close() end
    if self.allowanceReset then self.allowanceReset:Close() end
    self.requested = false
    self.session:Stop()
    if self.readCoordinator then self.readCoordinator:Close() end
    self.globalReason = "Stopped"
end

function Methods:CanReplace()
    if self.checkpoint.writing or self.recovering or self:FeatureRecoveryBusy() or self:AllowanceResetBusy() then
        return false,"Current runtime storage/recovery is busy"
    end
    local active=self.session.broker.active
    if active then
        if active.sentAt==nil and active.preparing then return false,"Current action is preparing durable custody" end
        if active.sentAt~=nil and self.clock:Now()<active.sentAt+45 then
            return false,"Current action still owns its first-send 45-second gate"
        end
    end
    return true
end

function Methods:Close()
    if self.closed or self.closing then return end
    self.closing = true
    self.requested = false
    self.session:Pause()
    for _, tab in ipairs(self.tabInstances) do
        if type(tab.FlushBeforeClose) == "function" then
            local ok, saved, why = pcall(tab.FlushBeforeClose, tab, self.checkpoint, self.latestOutcomeSnapshot)
            if not ok or saved ~= true then
                self.session.storageFault = ok and why or "Close receipt persistence failed"
            end
        end
    end
    self.closed = true
    self.latestOutcomeSnapshot = nil
    self.playerInfoSnapshot = nil
    if self.playerInfo then self.playerInfo:Close() end
    for _, control in pairs(self.recoveryControls) do control:Close() end
    if self.allowanceReset then self.allowanceReset:Close() end
    self.allowanceSnapshot = nil
    self.goalStates, self.goalObserved = {}, {}
    self.requested = false
    self.session:Close()
    if self.readCoordinator then self.readCoordinator:Close() end
    for _, tab in ipairs(self.tabInstances) do
        if type(tab.Close) == "function" then pcall(tab.Close, tab) end
    end
    self.globalReason = "Closed"
end

function Methods:Status()
    local status = self.session:Status()
    status.recentActions = self.journal:PublicEvents(10)
    status.goals = {}
    for id, state in pairs(self.goalStates) do status.goals[id] = copy(state) end
    status.outcomes = copy(self.outcomes)
    status.recoveries = copy(self.recoveries)
    status.reasons = copy(self.reasons)
    status.reason = self.globalReason
    local available = {}
    for id in pairs(self.features) do available[id] = true end
    if self.playerInfo and not self.closed then
        local now, raw = self.clock:Now(), self.playerInfoSnapshot
        if raw and (self.playerInfoObservedAt ~= now or self.playerInfoObservedRevision ~= raw.revision) then
            local facts, summary
            local source = self.playerInfoSource
            if type(source) == "table" and source.Read == self.playerInfoRead and source.Current == self.playerInfoCurrent
                and type(self.playerInfoRead) == "function" and type(self.playerInfoCurrent) == "function" then
                local ok, valid = pcall(self.playerInfoCurrent, source)
                if ok and valid == true then
                    local read, value = pcall(self.playerInfoRead, source, raw.native)
                    local checked, current = pcall(self.playerInfoCurrent, source)
                    if read and checked and current == true and source.Read == self.playerInfoRead
                        and source.Current == self.playerInfoCurrent then facts = value end
                end
            end
            for _, tab in ipairs(self.tabInstances) do
                if tab.id == "combat" and tab.playerLedger and type(tab.playerLedger.InfoSummary) == "function" then
                    local ok, value = pcall(tab.playerLedger.InfoSummary, tab.playerLedger)
                    if ok then summary = value end
                end
            end
            self.playerInfo:Observe(raw, now, facts, summary)
            self.playerInfoObservedAt, self.playerInfoObservedRevision = now, raw.revision
        end
        status.playerInfo = self.playerInfo:Read(now)
    end
    if not self.closed then
        for _, tab in ipairs(self.tabInstances) do
            if tab.id == "combat" and tab.playerLedger and type(tab.playerLedger.HighValueStatus) == "function" then
                local ok, value = pcall(tab.playerLedger.HighValueStatus, tab.playerLedger, self.allowanceSnapshot)
                if ok then status.combatMemory = value end
            end
        end
    end
    status.availableFeatures = available
    local byFeature = {}
    for _, record in ipairs(self.checkpoint:Records()) do
        byFeature[record.feature] = (byFeature[record.feature] or 0) + 1
    end
    status.uncertainByFeature = byFeature
    return status
end

local function outcome(result)
    return result == "confirmed" or result == "rejected"
        or result == "skipped_unconfirmed"
end

function Methods:RecoverSaved(raw)
    local now = self.clock:Now()
    if self.closed or self.recovering or self.session.storageFault or not self.session.broker:Fresh(raw, now)
        or type(raw.native) ~= "table" or raw.native.fullSync ~= true then return end
    local state = self.session:Status()
    if state.state == "closed" or state.state == "stopped" then return end
    local key = tostring(raw.session) .. ":" .. tostring(raw.revision) .. ":" .. tostring(raw.capturedAt)
    if self.recoverySeen == key then return end
    self.recoverySeen = key
    self.recovering = true
    local completed = pcall(function()
    for _, record in ipairs(self.checkpoint:Records()) do
        local spec = self.features[record.feature]
        local owner = spec and spec.lifecycle
        local recover = spec and spec.recoverSaved or owner and owner.recover
        if (type(recover) == "function" or (not owner and type(self.checkpoint.KnownUnsent) == "function"))
            and (not state.active or state.active.actionKey ~= record.actionKey) then
            local data = self.checkpoint:Recovery(record.actionKey)
            if data then
                local ok, observed = true, nil
                if not owner and type(self.checkpoint.KnownUnsent) == "function"
                    and self.checkpoint:KnownUnsent(record) then observed = "known_unsent"
                elseif type(recover) == "function" then ok, observed = pcall(recover, data, raw, now) end
                local currentState = self.session:Status().state
                if self.closed or currentState == "stopped" or currentState == "closed"
                    or not self.session.broker:Fresh(raw, self.clock:Now()) then return end
                if ok and (observed == "confirmed" or observed == "rejected" or observed == "known_unsent") then
                    if observed == "confirmed" and spec and spec.recordOutcome then
                        local stored, saved, why = pcall(spec.recordOutcome, data, raw, observed)
                        if not stored or saved ~= true then self.session.storageFault = why or "Saved outcome ledger failed"; return end
                        currentState = self.session:Status().state
                        if self.closed or currentState == "stopped" or currentState == "closed"
                            or not self.session.broker:Fresh(raw, self.clock:Now()) then return end
                    end
                    local saved, why = self.checkpoint:Resolve(record.actionKey, observed == "known_unsent" and "schedule_failed" or observed)
                    if not saved then self.session.storageFault = why or "Saved outcome cleanup failed"; return end
                    if self.closed or self.session:Status().state == "stopped" then return end
                    self.recoveries[record.feature] = observed
                    self.journal:Record({kind = observed == "known_unsent" and "recovered_unsent" or "reconciled_saved", at = self.clock:Now(), feature = record.feature,
                        actionKey = record.actionKey, reason = "Saved exact feature outcome observed; no replay"})
                end
            end
        end
    end
    end)
    self.recovering = false
    if not completed and not self.closed then self.session.storageFault = "Saved outcome recovery raised" end
end

-- Goals only arbitrate proposals already allowed by each ordinary feature switch.
local function goalSelection(settings)
    local result = {}
    for key, value in pairs(settings or {}) do
        if type(value) == "boolean" or type(value) == "string" or type(value) == "number" then result[key] = value end
    end
    return result
end
local function sameGoalSelection(a, b)
    for key, value in pairs(a) do if b[key] ~= value then return false end end
    for key, value in pairs(b) do if a[key] ~= value then return false end end
    return true
end
local function goalRoutes(self, raw, context, settings, proposals, enabled, tabReasons, reservations)
    local preferred, candidates, seen = {}, {}, {}
    for _, proposal in ipairs(proposals) do candidates[proposal.feature],seen[proposal.actionKey] = true,true end
    for _, spec in ipairs(self.order) do
        local goals = spec.goals
        if goals then
            local choices = type(settings) == "table" and settings[spec.id] or nil
            local selected = goalSelection(choices)
            local page = self.featurePages[spec.id]
            local previous = self.goalObserved[spec.id]
            if not enabled[spec.id] then
                self.goalObserved[spec.id], self.goalStates[spec.id] = nil, nil
            elseif type(goals.derive) ~= "function" or type(goals.observe) ~= "function" or tabReasons[page] then
                self.goalObserved[spec.id] = nil
                self.reasons[spec.id] = "Current goal source unavailable"
                self.goalStates[spec.id] = {state = "unavailable"}
            else
                local read, view, reason = pcall(spec.reader.read, raw, context)
                local derived, requests
                if read and view then derived, requests, reason = pcall(goals.derive, view, choices) end
                if not derived or type(requests) ~= "table" or type(requests.requests) ~= "table" or #requests.requests > 16 then
                    self.goalObserved[spec.id] = nil
                    self.goalStates[spec.id] = {state = "unavailable"}
                    self.reasons[spec.id] = reason or "Current goal information unavailable"
                else
                    local observed
                    if previous and sameGoalSelection(previous.settings, selected)
                        and type(raw.native.serverNow) == "number" and raw.native.serverNow >= previous.serverNow then
                        local ok, value = pcall(goals.observe, previous.view, view, previous.request)
                        if ok and (value == "progressed" or value == "complete" or value == "ready" or value == "owned") then observed = value end
                    end
                    local request, routed
                    for _, row in ipairs(requests.requests) do
                        local allowed = type(row.routes) == "table" and #row.routes > 0 and #row.routes <= 4
                        local available, keys = false, {}
                        for _, route in ipairs(type(row.routes) == "table" and row.routes or {}) do
                            if not self.features[route] or enabled[route] ~= true then allowed = false end
                            if enabled[route] and self.features[route] and not tabReasons[self.featurePages[route]]
                                and type(goals.propose)=="function" then
                                local ok, proposal = pcall(goals.propose,raw,context,row,self.features[route],settings[route],reservations)
                                if ok and type(proposal)=="table" and proposal.feature==route and not seen[proposal.actionKey] then
                                    local permitted=true
                                    if self.reservationOwner then
                                        local checked,claims=pcall(self.reservationOwner.Check,self.reservationOwner,proposal,raw)
                                        permitted=checked and type(claims)=="table"
                                    end
                                    if permitted then
                                        proposals[#proposals+1]=proposal
                                        candidates[route],seen[proposal.actionKey]=true,true
                                    end
                                end
                            end
                            if candidates[route] then
                                for _, proposal in ipairs(proposals) do
                                    if proposal.feature == route then
                                        local usable = goals.canUseProposal == nil
                                        if goals.canUseProposal then
                                            local ok, value = pcall(goals.canUseProposal, raw, row, proposal)
                                            usable = ok and value == true
                                        end
                                        if usable then available = true;keys[proposal.actionKey]=true end
                                    end
                                end
                            end
                        end
                        if allowed then
                            request = request or row
                            if available and not routed then
                                routed, request = true, row
                                for key in pairs(keys) do preferred[key] = true end
                                break
                            end
                        end
                    end
                    self.goalObserved[spec.id] = request and {view = view, request = request, settings = selected, serverNow = raw.native.serverNow}
                        or ((observed == "complete" or observed == "owned" or observed == "ready") and previous or nil)
                    local terminal = requests.status == "ready" or requests.status == "owned" or requests.status == "manualTradeIn"
                    local state = terminal and requests.status or observed or "waiting"
                    if not request and previous and sameGoalSelection(previous.settings, selected)
                        and observed == "complete" then state = "complete" end
                    self.goalStates[spec.id] = {state = state, routed = routed == true,
                        target = request and (request.contractId or request.targetId) or requests.targetId}
                    self.reasons[spec.id] = state == "owned" and "Selected Trophy ownership observed; goal routing stopped"
                        or state == "ready" and "Native Trophy ready; separate enabled Trophy claims are required"
                        or state == "manualTradeIn" and "Selected Trophy requires a manual item-consuming route"
                        or state == "complete" and "Native objective complete; ordinary switches keep their own settings"
                        or state == "progressed" and "Native objective progress observed"
                        or routed and "Goal route selected; ordinary availability and limits still apply"
                        or (type(requests.excluded) == "table" and type(requests.excluded[1]) == "table"
                            and type(requests.excluded[1].reason) == "string" and requests.excluded[1].reason)
                        or "No eligible explicitly borrowed ordinary proposal; verify switches, limits and current objective"
                end
            end
        end
    end
    return preferred
end

function Methods:Step(raw, settings)
    if self.closed or self.closing then return self:Status() end
    if self.readCoordinator and not self.closed then
        local eligible, active = {}, self.session:Status().active
        for _, source in ipairs(self.readSources) do
            local ok, enabled = pcall(source.enabled, self.requested and (settings or {}) or {}, active, raw)
            eligible[source.id] = ok and enabled == true
        end
        self.readCoordinator:Step(raw, eligible)
    end
    local tabReasons = {}
    if self.snapshotAssembler then
        local ok, enriched, reasons = pcall(self.snapshotAssembler.Enrich,
            self.snapshotAssembler, raw, settings)
        if ok and type(enriched) == "table" then
            raw = enriched
            if type(reasons) == "table" then tabReasons = reasons end
        else
            tabReasons["*"] = "Tab snapshot assembly failed"
        end
    end
    local readPrestige = self.requested and type(settings) == "table" and type(settings.prestige) == "table"
        and settings.prestige.enabled == true
    raw = withUsageProofs(raw, self.checkpoint, self.reservationOwner, self.nativePrestigeController,
        self.nativePrestigeRead, self.nativePrestigeCurrent, readPrestige)
    if self.closed or self.closing then return self:Status() end
    self.latestOutcomeSnapshot = raw
    self.playerInfoSnapshot = raw
    self.allowanceSnapshot = nil
    if not self.closed and type(raw) == "table" and type(raw.native) == "table" and raw.native.fullSync == true then
        local matched = true
        for _, key in ipairs({"session", "account", "place", "release"}) do if raw[key] ~= self.identity[key] then matched = false end end
        if matched then self.allowanceSnapshot = raw end
    end
    local state = self.session:Status().state
    if state == "closed" or state == "stopped" then return self:Status() end
    if self.recovering or self:FeatureRecoveryBusy() then return self:Status() end
    self:RecoverSaved(raw)
    local enabled = {}
    local anyEnabled = false
    if type(settings) == "table" then
        for id in pairs(self.features) do
            enabled[id] = type(settings[id]) == "table"
                and settings[id].enabled == true
            if enabled[id] then anyEnabled = true end
        end
    end
    if self.requested and anyEnabled then self.session:Resume()
    else self.session:Pause() end

    -- Observation and expiry continue while paused; no new proposal does.
    local active = self.session:Status().active
    local observed = self.session:Observe(raw)
    if active and outcome(observed) then
        self.outcomes[active.feature] = observed
    end
    active = self.session:Status().active
    local ticked = self.session:Tick(raw)
    if active and outcome(ticked) then
        self.outcomes[active.feature] = ticked
    end
    if self.session:Status().state ~= "running"
        or self.session:Status().active then return self:Status() end
    if tabReasons["*"] then
        self.globalReason = tabReasons["*"]
        return self:Status()
    end

    local now = self.clock:Now()
    local context, contextReason = self.context:Read(raw, self.identity, now, 2)
    if not context then
        self.globalReason = contextReason
        return self:Status()
    end
    local uncertain = exposure(self.checkpoint)
    local reservations = {
        energy = 0, stamina = 0, cash = 0, skillPoints = 0,
        uncertainEnergy = uncertain.energy or 0,
        uncertainStamina = uncertain.stamina or 0,
        uncertainGold = uncertain.gold_bar or 0,
        uncertainCash = uncertain.cash or 0,
        uncertainSkillPoints = uncertain.skillPoints or 0,
        uncertainBossTokens = uncertain.bossTokens or 0,
    }
    local planningRaw = raw
    if type(self.modules.CrateLuckProducer) == "table"
        and type(self.modules.CrateLuckProducer.derive)
            == "function" then
        local ok, proof = pcall(self.modules.CrateLuckProducer.derive,
            raw, context, self.modules.crateLuckSource)
        if ok and type(proof) == "table" then
            planningRaw = copy(raw)
            planningRaw.crateLuckProof = proof
        end
    end
    if type(self.modules.ShopQuoteProducer) == "table"
        and type(self.modules.ShopQuoteProducer.derive)
            == "function" then
        local ok, proof = pcall(self.modules.ShopQuoteProducer.derive,
            raw, context, self.modules.shopQuoteSource)
        if ok and type(proof) == "table" then
            if planningRaw == raw then planningRaw = copy(raw) end
            planningRaw.shopQuoteProof = proof
        end
    end
    if type(self.modules.PurchaseSavings) == "table"
        and type(self.modules.PurchaseSavings.derive) == "function" then
        local ok, savings = pcall(self.modules.PurchaseSavings.derive,
            planningRaw, context, settings, self.features,
            reservations)
        if ok and type(savings) == "table" then
            if planningRaw == raw then planningRaw = copy(raw) end
            planningRaw.purchaseSavings = savings
        end
    end
    if type(self.modules.CollectionProtection) == "table"
        and type(self.modules.CollectionProtection.derive)
            == "function" then
        local ok, proof = pcall(self.modules.CollectionProtection.derive,
            raw, context, settings, self.features, self.reservationOwner)
        if ok and type(proof) == "table" then
            if planningRaw == raw then planningRaw = copy(raw) end
            planningRaw.collectionProtection = proof
            context.collectionProtection = proof
        end
    end
    if type(self.modules.RewardsProofProducer) == "table"
        and type(self.modules.RewardsProofProducer.derive)
            == "function" then
        local ok, proofs = pcall(self.modules.RewardsProofProducer.derive,
            raw, context, self.modules.rewardsSource)
        if ok and type(proofs) == "table" then
            if planningRaw == raw then planningRaw = copy(raw) end
            planningRaw.weekendBuff = proofs.weekendBuff
            planningRaw.groupMembership = proofs.groupMembership
        end
    end
    if type(planningRaw) == "table" and planningRaw.fundingRequest == nil
        and type(self.modules.FundingCoordinator) == "table"
        and type(self.modules.FundingCoordinator.derive) == "function" then
        local ok, request = pcall(self.modules.FundingCoordinator.derive,
            planningRaw, context, settings, reservations, self.modules)
        if ok and type(request) == "table" then
            planningRaw = copy(planningRaw)
            planningRaw.fundingRequest = request
        end
    end
    local proposals = {}
    for _, spec in ipairs(self.order) do
        local page = self.featurePages[spec.id]
        local tabReason = self.snapshotAssembler and not page
            and "Missing feature tab ownership" or tabReasons[page]
        if enabled[spec.id] and tabReason then
            self.reasons[spec.id] = tabReason
        elseif enabled[spec.id] and spec.goals then
            self.reasons[spec.id] = "Awaiting current goal arbitration"
        elseif enabled[spec.id] then
            local readOk, view, readReason = pcall(spec.reader.read,
                planningRaw, context)
            if not readOk or not view then
                self.reasons[spec.id] = readOk and readReason or "Reader failed"
            else
                local planOk, proposal, planReason = pcall(
                    spec.planner.propose, view, settings[spec.id], reservations)
                if planOk and type(proposal) == "table"
                    and proposal.feature == spec.id then
                    local allowed, reservationReason = true, nil
                    if self.reservationOwner then
                        local checked, claims, why = pcall(self.reservationOwner.Check,
                            self.reservationOwner, proposal, planningRaw)
                        allowed, reservationReason = checked and type(claims) == "table", why
                    end
                    if allowed then
                        proposals[#proposals + 1] = proposal
                        self.reasons[spec.id] = nil
                    else
                        self.reasons[spec.id] = reservationReason or "Resource custody unavailable"
                    end
                else
                    if not planOk then
                        self.reasons[spec.id] = "Planner failed"
                    elseif proposal and (type(proposal) ~= "table"
                        or proposal.feature ~= spec.id) then
                        self.reasons[spec.id] = "Planner feature mismatch"
                    else
                        self.reasons[spec.id] = planReason or "No proposal"
                    end
                end
            end
        else
            self.reasons[spec.id] = "Disabled"
        end
    end
    local preferred = goalRoutes(self, planningRaw, context, settings, proposals, enabled, tabReasons, reservations)
    local chosen, reason = self.scheduler:Choose(context, {
        proposals = proposals, enabled = enabled, goalKeys = preferred,
        reservations = { energy = 0, stamina = 0,
            cash = 0, skillPoints = 0 },
        uncertain = uncertain,
    }, self.session:Status(), now)
    if not chosen then
        self.globalReason = reason
        return self:Status()
    end
    local admitted
    admitted, reason = self.session:Offer(chosen, planningRaw)
    if admitted ~= "admitted" then
        self.reasons[chosen.feature] = reason
        self.globalReason = reason
        return self:Status()
    end
    local sent = self.session:Tick(planningRaw)
    if sent == "sent" then
        self.globalReason = nil
    else
        self.reasons[chosen.feature] = sent
        self.globalReason = sent
    end
    return self:Status()
end

return AutomationRuntime
