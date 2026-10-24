-- One injected broker/session for all ordinary feature descriptors.
local AutomationRuntime = {}
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

local function withUsageProofs(raw, checkpoint)
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
    observed.bossShopUsageProof = nil
    observed.purchaseSavings = nil
    observed.collectionProtection = nil
    observed.shopQuoteProof = nil
    observed.weekendBuff = nil
    observed.groupMembership = nil
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
            return os.date("!%Y%j", bossNow)
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
        if type(family.famId) == "number"
            and family.famId == family.famId
            and family.famId >= 1
            and family.famId < math.huge
            and family.famId % 1 == 0
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
            and type(spec.evidence.evaluate) == "function",
            "Invalid or duplicate feature descriptor")
        features[spec.id] = spec
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
    local journal = m.Journal.new(100)
    local broker = m.Broker.new(deps.clock, deps.transport, journal, {
        contracts = m.Contracts, session = deps.identity,
        maxSnapshotAge = 2, minInterval = 1, cooldownSeconds = 45,
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
    local checkpoint = m.Checkpoint.new(deps.storage)
    local session = m.Session.new(broker, checkpoint, deps.identity)
    session:Pause()
    return setmetatable({
        clock = deps.clock, identity = deps.identity, features = features,
        snapshotAssembler = deps.snapshotAssembler,
        featurePages = deps.featurePages or {},
        modules = m,
        order = deps.features, checkpoint = checkpoint, session = session,
        journal = journal, context = m.Context.new(m.Contracts,
            m.EconomyContext, m.BuffContext, m.HeistBoardState,
            m.BossStageState, m.GlobalBossState,
            m.BossShopState, m.FamilyTakedownState),
        scheduler = m.Scheduler.new(), requested = false,
        outcomes = {}, reasons = {}, globalReason = "Paused",
    }, Methods)
end

function Methods:Pause()
    self.requested = false
    self.session:Pause()
    self.globalReason = "Paused"
end

function Methods:Resume()
    if self.session:Status().state == "paused" then
        self.requested = true
        self.globalReason = nil
    end
end

function Methods:Stop()
    self.requested = false
    self.session:Stop()
    self.globalReason = "Stopped"
end

function Methods:Close()
    self.requested = false
    self.session:Close()
    self.globalReason = "Closed"
end

function Methods:Status()
    local status = self.session:Status()
    status.recentActions = self.journal:PublicEvents(10)
    status.outcomes = copy(self.outcomes)
    status.reasons = copy(self.reasons)
    status.reason = self.globalReason
    local available = {}
    for id in pairs(self.features) do available[id] = true end
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

function Methods:Step(raw, settings)
    local tabReasons = {}
    if self.snapshotAssembler then
        local ok, enriched, reasons = pcall(self.snapshotAssembler.Enrich,
            self.snapshotAssembler, raw)
        if ok and type(enriched) == "table" then
            raw = enriched
            if type(reasons) == "table" then tabReasons = reasons end
        else
            tabReasons["*"] = "Tab snapshot assembly failed"
        end
    end
    raw = withUsageProofs(raw, self.checkpoint)
    local state = self.session:Status().state
    if state == "closed" or state == "stopped" then return self:Status() end
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
        uncertainCash = uncertain.cash or 0,
        uncertainSkillPoints = uncertain.skillPoints or 0,
        uncertainBossTokens = uncertain.bossTokens or 0,
    }
    local planningRaw = raw
    if type(self.modules.ShopQuoteProducer) == "table"
        and type(self.modules.ShopQuoteProducer.derive)
            == "function" then
        local ok, proof = pcall(self.modules.ShopQuoteProducer.derive,
            raw, context, self.modules.shopQuoteSource)
        if ok and type(proof) == "table" then
            planningRaw = copy(raw)
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
            raw, context, settings, self.features)
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
                    proposals[#proposals + 1] = proposal
                    self.reasons[spec.id] = nil
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
    local chosen, reason = self.scheduler:Choose(context, {
        proposals = proposals, enabled = enabled,
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
