-- Separately configurable Combat controls own their sources, evidence and lifecycle.
local CombatTab = {}
local ownedProofs = { "playerFightProof", "playerFightHistoryProof", "hitListProof", "warRosterProof", "bossStageProof", "bossShopProof", "globalBossProof", "localUserIdProof", "familyAttackProof" }
local Methods = {}
Methods.__index = Methods

local rows = {
    { "bosses", "BossesState", "Bosses", "BossesEvidence" },
    { "globalBossAttack", "GlobalBossAttackState", "GlobalBossAttack", "GlobalBossAttackEvidence" },
    { "globalBossClaim", "GlobalBossClaimState", "GlobalBossClaim", "GlobalBossClaimEvidence" },
    { "familyBossAttacks", "FamilyBossAttackState", "FamilyBossAttacks", "FamilyBossAttacksEvidence" },
    { "familyBossClaims", "FamilyBossClaimState", "FamilyBossClaims", "FamilyBossClaimsEvidence" },
    { "bossShop", "BossShopBuyState", "BossShopBuy", "BossShopBuyEvidence" },
}

local known = { combat = true, warCombat = true }
for _, row in ipairs(rows) do known[row[1]] = true end

function CombatTab.BuildUI(section, feature, bind, numeric)
    assert(type(section) == "table" and type(feature) == "table"
        and feature.page == "combat" and known[feature.id]
        and type(bind) == "function" and type(numeric) == "table"
        and type(feature.custom) == "table"
        and type(feature.policies) == "table",
        "Invalid Combat UI feature")
    local group = section:Group({ Text = feature.label,
        Description = feature.description, Open = true })
    bind(group, "Toggle", feature.id .. ".enabled", {
        Text = "Allow " .. feature.label,
        Description = "Select this activity; the status below shows whether this entry can run it.",
        Default = false, RevertOnClose = true, RevertTo = false,
    })
    if #feature.policies > 0 then
        bind(group, "Dropdown", feature.id .. ".policy", {
            Text = "Goal", Options = feature.policies,
            Default = feature.policies[1],
        })
    end
    local reason
    local row = { feature = feature, tabOwned = true, blockedReason = reason,
        alwaysShowCustom = feature.id == "combat" or feature.id == "warCombat",
        status = group:Status({ Text = "Activity",
            Default = reason and ("Blocked — " .. reason) or "Off — UI only" }) }
    if feature.id == "combat" then
        row.memoryStatus = group:Status({Text = "High-value history", Default = "Unknown — current owned history required"})
        group:Description({Text = "High-only sources use confirmed Cash: promote at 1B; remove after 3 consecutive payouts below 100M. All other limits still apply."})
    end
    if feature.limits then group:Description({ Text = feature.limits }) end
    if #feature.custom > 0 then
        row.custom = group:Group({ Text = "Custom limits", Open = false })
        for _, field in ipairs(feature.custom) do
            local key = feature.id .. ".custom." .. field.id
            if field.type == "number" then
                numeric[key] = true
                bind(row.custom, "Input", key, {
                    Text = field.label, Default = tostring(field.value),
                    FireOnBlur = true,
                })
            elseif field.type == "boolean" then
                bind(row.custom, "Toggle", key, {Text = field.label, Default = field.value,
                    RevertOnClose = true, RevertTo = false})
            else
                bind(row.custom, "Dropdown", key, {
                    Text = field.label, Default = field.value,
                    Options = field.options,
                })
            end
        end
    end
    return row
end

function CombatTab.new(deps)
    assert(type(deps) == "table"
        and type(deps.HitListQuery) == "table"
        and type(deps.HitListQuery.new) == "function"
        and type(deps.PlayerTargetState) == "table"
        and type(deps.PlayerTargetState.read) == "function"
        and type(deps.BlockedFight) == "table"
        and type(deps.BlockedFight.new) == "function"
        and type(deps.combatRules) == "table",
        "Missing Combat tab modules")
    local descriptors = {}
    for index, row in ipairs(rows) do
        local reader, planner, evidence = deps[row[2]], deps[row[3]], deps[row[4]]
        assert(type(reader) == "table" and type(reader.read) == "function"
            and type(planner) == "table"
            and type(planner.propose) == "function"
            and type(evidence) == "table"
            and type(evidence.capture) == "function"
            and type(evidence.evaluate) == "function",
            "Missing Combat feature modules: " .. row[1])
        descriptors[index] = { id = row[1], reader = reader,
            planner = planner, evidence = evidence }
    end
    local player = deps.BlockedFight.new("combat")
    local war = deps.BlockedFight.new("warCombat")
    local playerEvidence, playerLedger, playerLedgerFault
    if type(deps.PlayerFightEvidence) == "table" and type(deps.PlayerFightLedger) == "table"
        and type(deps.FightReceipts) == "table" then
        playerEvidence = deps.PlayerFightEvidence.new(deps.FightReceipts)
        playerLedger, playerLedgerFault = deps.PlayerFightLedger.new(deps.storage, deps.identity, playerEvidence)
    end
    local hitListQuery = deps.HitListQuery.new(deps.identity, deps.fingerprint, deps.nativeReadSource)
    local warRosterQuery = deps.HitListQuery.new(deps.identity, deps.fingerprint, deps.nativeReadSource, "war")
    if warRosterQuery.sourceKey and type(deps.PlayerTargetState.readWar) == "function" then
        war.read = deps.PlayerTargetState.readWar
    end
    local playerProfiles, warProfiles
    if type(deps.PlayerProfileQuery) == "table" and type(deps.PlayerProfileQuery.new) == "function"
        and type(deps.nativeReadSource) == "table" and type(deps.fingerprint) == "string" then
        playerProfiles = deps.PlayerProfileQuery.new(deps.identity, deps.fingerprint, hitListQuery, deps.nativeReadSource, deps.PlayerScoutEvidence)
        warProfiles = deps.PlayerProfileQuery.new(deps.identity, deps.fingerprint, warRosterQuery, deps.nativeReadSource, deps.PlayerScoutEvidence)
    end
    local playerPlannerReady = false
    if playerEvidence and playerLedger and not playerLedgerFault and playerProfiles
        and type(deps.PlayerFightPlanner) == "table" and type(deps.PlayerFightPlanner.new) == "function"
        and type(deps.TargetSelection) == "table" and type(deps.PlayerTargetState.readSelection) == "function" then
        local planner = deps.PlayerFightPlanner.new(deps.TargetSelection)
        player = {read = deps.PlayerTargetState.readSelection, propose = planner.propose}
        playerPlannerReady = true
    end
    local warPlannerReady = playerPlannerReady and warProfiles ~= nil
        and type(deps.PlayerTargetState.readWarSelection) == "function"
    if warPlannerReady then
        war = {read = deps.PlayerTargetState.readWarSelection,
            propose = deps.PlayerFightPlanner.new(deps.TargetSelection, "warCombat").propose}
    end
    local bossCatalog
    if type(deps.NativeBossCatalog) == "table"
        and type(deps.NativeBossCatalog.new) == "function"
        and type(deps.bossStages) == "table" then
        bossCatalog = deps.NativeBossCatalog.new(deps.bossStages,
            deps.config, deps.fingerprint, deps.release)
    end
    return setmetatable({ id = "combat", ownedProofs = ownedProofs, descriptors = descriptors,
        blocked = { { id = "combat", reader = player,
            planner = player, evidence = player },
            { id = "warCombat", reader = war,
            planner = war, evidence = war } },
        hitListQuery = hitListQuery, warRosterQuery = warRosterQuery, playerProfiles = playerProfiles, warProfiles = warProfiles,
        nativeReadSource = deps.nativeReadSource,
        frameReader = type(deps.nativeReadSource) == "table" and deps.nativeReadSource.CombatFrame or nil,
        targetReader = deps.PlayerTargetState, playerPlannerReady = playerPlannerReady, warPlannerReady = warPlannerReady,
        historyStats = type(deps.TargetSelection) == "table" and deps.TargetSelection.history or nil,
        fightReceipts = deps.fightReceipts, playerEvidence = playerEvidence, scoutEvidence = deps.PlayerScoutEvidence,
        playerLedger = playerLedger, playerLedgerFault = playerLedgerFault,
        combatRules = deps.combatRules,
        globalBossSource = deps.globalBossSource,
        familyBossQuery = type(deps.FamilyBossQuery) == "table"
            and type(deps.FamilyBossQuery.new) == "function"
            and type(deps.FamilyTakedownState) == "table"
            and type(deps.fingerprint) == "string" and type(deps.release) == "string"
            and deps.FamilyBossQuery.new(deps.FamilyTakedownState, deps.fingerprint, deps.release) or nil,
        bossCatalog = bossCatalog }, Methods)
end

-- Independent current war observations can only remove ordinary permission.
-- Keep this check shared by planning and the final queued-call guard.
function Methods:CurrentHitList(snapshot, roster)
    local proof = self.hitListQuery:Read(snapshot)
    roster = roster or self.warRosterQuery:Read(snapshot)
    local ordinaryWar, war = proof and proof.war, roster and roster.war
    if not ordinaryWar or not war then return proof end
    if ordinaryWar.active ~= war.active or war.active and (war.enemyFamilyId == nil
        or ordinaryWar.enemyFamilyId ~= war.enemyFamilyId) then
        proof.war = nil
        return proof
    end
    if war.active then
        local members = {}
        for _, row in ipairs(roster.rows) do members[row.userId] = true end
        for _, row in ipairs(proof.rows) do
            if members[row.userId] and row.familyId ~= war.enemyFamilyId then
                proof.war = nil
                break
            end
        end
    end
    return proof
end

-- The roster proves enemy membership; a separate native search proves the quote.
-- Neither read confers ordinary attack permission or invents a Stamina price.
function Methods:CurrentWarTargets(snapshot)
    local roster = self.warRosterQuery:Read(snapshot)
    local quotes = self:CurrentHitList(snapshot, roster)
    if not roster then return nil end
    local sameWar = quotes and quotes.war and roster.war and roster.war.active == true
        and quotes.war.active == true and quotes.war.enemyFamilyId == roster.war.enemyFamilyId
    for _, row in ipairs(roster.rows) do
        row.stamina, row.shielded = nil, nil
        if sameWar then
            for _, quote in ipairs(quotes.rows) do
                if quote.userId == row.userId and quote.name == row.name and quote.level == row.level
                    and quote.familyId == row.familyId then row.stamina, row.shielded = quote.stamina, quote.shielded end
            end
        end
    end
    return roster
end

function Methods:WarQuoteTarget(snapshot)
    if self.closed or not self.warPlannerReady then return nil end
    local roster = self:CurrentWarTargets(snapshot)
    local war = roster and roster.war
    if not war or war.active ~= true or war.canScore ~= true or war.enemyFamilyId == nil
        or not self.hitListQuery:Read(snapshot) then return nil end
    local candidates = {}
    for _, row in ipairs(roster.rows) do
        local allowance = row.warStatus
        if row.stamina == nil and row.familyId == war.enemyFamilyId and type(allowance) == "table"
            and allowance.canScore == true and allowance.remaining > 0 and allowance.attacksRemaining > 0
            and allowance.pairRemaining > 0 then candidates[#candidates + 1] = row end
    end
    return self.hitListQuery:PickSavedSearch(snapshot, candidates, 32)
end

function Methods:Enrich(snapshot, settings)
    local result = {}
    for key, value in pairs(snapshot) do result[key] = value end
    for _, field in ipairs(ownedProofs) do result[field] = nil end
    self.latestBossSnapshot = result
    if self.bossCatalog then
        -- Missing city state must not suppress independent Global/Family rows.
        result = self.bossCatalog:Enrich(result) or result
    end
    if self.globalBossSource then
        local enriched = self.globalBossSource:Enrich(result)
        if enriched then result = enriched else
            local copied = {}
            for key, value in pairs(result) do copied[key] = value end
            copied.globalBossProof, copied.localUserIdProof = nil, nil
            result = copied
        end
    end
    if self.fightReceipts and not self.closed then
        result.playerFightProof = self.fightReceipts:Read(result)
    end
    if not self.closed then
        result.warRosterProof = self:CurrentWarTargets(result)
        if result.warRosterProof and self.warProfiles then
            result.warRosterProof.profiles = self.warProfiles:Read(result) or {}
        end
        result.hitListProof = self:CurrentHitList(result, result.warRosterProof)
        if result.hitListProof and self.playerProfiles then
            result.hitListProof.profiles = self.playerProfiles:Read(result) or {}
        end
        for _, feature in ipairs({"combat", "warCombat"}) do
            local proof = result[feature == "combat" and "hitListProof" or "warRosterProof"]
            if proof and type(settings) == "table" and type(settings[feature]) == "table"
                and settings[feature].enabled == true and type(self.frameReader) == "function"
                and self.nativeReadSource.CombatFrame == self.frameReader then
                local ok, frame = pcall(self.frameReader, self.nativeReadSource, result.native, proof.rows)
                if ok and type(frame) == "table" then
                    local bound = {}
                    for key, value in pairs(frame) do bound[key] = value end
                    bound.header = {serverNow = result.native.serverNow}
                    for _, key in ipairs({"session", "account", "place", "release", "revision", "capturedAt"}) do
                        bound.header[key] = result[key]
                    end
                    bound.sourceKey = proof.sourceKey
                    proof.nativeFrame = bound
                end
            end
        end
    end
    if self.playerLedger and not self.closed then
        local combat = type(settings) == "table" and settings.combat
        local source = type(combat) == "table" and combat.enabled == true and combat.targetSource
        result.playerFightHistoryProof = self.playerLedger:Proof(result, source == "High value only" or source == "High value only + lookup")
    end
    self.latestPlayerSnapshot = result
    return result, nil
end

function Methods:PrepareFamilyBossRead(snapshot)
    if not self.familyBossQuery then return nil, "Current Family Boss reader unavailable" end
    return self.familyBossQuery:Prepare(snapshot)
end

function Methods:AcceptFamilyBossRead(snapshot, request, reply)
    if not self.familyBossQuery then return nil, "Current Family Boss reader unavailable" end
    return self.familyBossQuery:Accept(snapshot, request, reply)
end

function Methods:FlushBeforeClose(checkpoint, snapshot)
    if self.closed or self.playerLedgerFault or not self.playerLedger or not self.playerEvidence
        or not self.fightReceipts or type(snapshot) ~= "table" or type(checkpoint) ~= "table"
        or type(checkpoint.Recovery) ~= "function" then return true end
    local proof = self.fightReceipts:Read(snapshot)
    if type(proof) ~= "table" or type(proof.attempts) ~= "table" or #proof.attempts ~= 1
        or proof.attempts[1].status ~= "settled" then return true end
    local attempt = proof.attempts[1]
    local data = checkpoint:Recovery(attempt.actionKey)
    if not data or type(data.proposal.intent) ~= "table" or data.proposal.intent.kind ~= "playerAttack" then return true end
    local after = {}
    for k, v in pairs(snapshot) do after[k] = v end
    after.playerFightProof = proof
    after.playerFightHistoryProof = self.playerLedger:Proof(snapshot)
    if not self.playerEvidence.outcome(data, after) then return true end
    -- Freeze this owned terminal observation before a storage write can yield.
    -- This closes only our listener; it never changes native game flags/state.
    self.fightReceipts:Close()
    return self.playerLedger:Record(data, after)
end

function Methods:Close()
    self.latestBossSnapshot, self.latestPlayerSnapshot = nil, nil
    self.closed = true
    if self.fightReceipts then self.fightReceipts:Close() end
    if self.playerLedger then self.playerLedger:Close() end
    self.hitListQuery:Close()
    self.warRosterQuery:Close()
    if self.playerProfiles then self.playerProfiles:Close() end
    if self.warProfiles then self.warProfiles:Close() end
    if self.familyBossQuery then self.familyBossQuery:Close() end
    if self.globalBossSource then self.globalBossSource:Close() end
end

function Methods:SavedSearchTarget(snapshot, settings)
    if self.closed or not self.playerPlannerReady or type(settings) ~= "table" or settings.enabled ~= true
        or (settings.targetSource ~= "Saved only + lookup" and settings.targetSource ~= "Saved and new + lookup" and settings.targetSource ~= "High value only + lookup") or not self.playerLedger or self.playerLedgerFault
        or type(self.playerLedger.SavedTargets) ~= "function" or type(self.historyStats) ~= "function" then return nil end
    local list = self:CurrentHitList(snapshot)
    local native = type(snapshot) == "table" and snapshot.native
    local daily = type(native) == "table" and native.attackDaily
    if not list or #list.rows >= 128 or type(list.war) ~= "table" or type(list.war.active) ~= "boolean"
        or list.war.active and list.war.enemyFamilyId == nil
        or type(daily) ~= "table" or daily.day ~= math.floor(native.serverNow / 86400) or type(daily.counts) ~= "table"
        or type(settings.minSamples) ~= "number" or settings.minSamples < 0
        or type(settings.minimumPayout) ~= "number" or settings.minimumPayout < 0
        or type(settings.minWinRate) ~= "number" or settings.minWinRate < 0 or settings.minWinRate > 100 then return nil end
    local highOnly = settings.targetSource == "High value only + lookup"
    local targets = highOnly and self.playerLedger:HighValueTargets(snapshot) or nil
    if not highOnly then targets = self.playerLedger:SavedTargets(snapshot) end
    if not targets then return nil end
    local present, eligible = {}, {}
    for _, row in ipairs(list.rows) do present[row.userId] = true end
    local minimum = math.max(settings.minWinRate, settings.policy == "Cautious" and 90 or 0)
    for _, target in ipairs(targets) do
        local stats = self.historyStats(target.history, native.serverNow)
        local count = daily.counts[tostring(target.userId)]
        local used = count ~= nil and count ~= 0
        if settings.dailyOnly == true then
            for _, row in ipairs(target.history) do
                if math.floor(row.at / 86400) == daily.day then used = true end
            end
        end
        local enemy = list.war.active == true and type(list.war.enemyTargets) == "table" and list.war.enemyTargets[tostring(target.userId)] == true
        if not present[target.userId] and not enemy and target.userId ~= native.userId and stats and stats.samples >= math.max(highOnly and 0 or 1, settings.minSamples)
            and stats.payout >= settings.minimumPayout and (stats.samples == 0 or stats.winRate >= minimum)
            and (settings.dailyOnly ~= true or not used) then eligible[#eligible + 1] = target end
    end
    return self.hitListQuery:PickSavedSearch(snapshot, eligible, highOnly and 128 or 32)
end

function Methods:ReadSources(reader)
    local sources = {}
    if self.hitListQuery.sourceKey then
        sources[#sources + 1] = {id = "combatHitList", interval = 1,
            enabled = function(settings, _, snapshot)
                local current = snapshot or self.latestBossSnapshot
                return not self.closed and (type(settings.combat) == "table" and settings.combat.enabled == true
                    or type(settings.warCombat) == "table" and settings.warCombat.enabled == true)
                    and (not current or self.hitListQuery:NeedsRead(current))
            end,
            prepare = function(snapshot) return self.hitListQuery:Prepare(snapshot) end,
            accept = function(snapshot, request, reply) return self.hitListQuery:Accept(snapshot, request, reply) end,
            commit = function(staged) return self.hitListQuery:Commit(staged) end}
    end
    if self.warPlannerReady then
        local target, enemy
        sources[#sources + 1] = {id = "combatWarQuote", interval = 60,
            enabled = function(settings, _, snapshot)
                return not self.closed and type(settings.warCombat) == "table" and settings.warCombat.enabled == true
                    and self:WarQuoteTarget(snapshot or self.latestBossSnapshot) ~= nil
            end,
            prepare = function(snapshot)
                target = self:WarQuoteTarget(snapshot)
                local roster = target and self.warRosterQuery:Read(snapshot)
                enemy = roster and roster.war and roster.war.enemyFamilyId
                if not target or not enemy then return nil, "Current enemy quote identity required" end
                return self.hitListQuery:PrepareSavedSearch(snapshot, target)
            end,
            accept = function(snapshot, request, reply)
                local roster = self.warRosterQuery:Read(snapshot)
                local found = false
                if roster and roster.war and roster.war.enemyFamilyId == enemy and target then
                    for _, row in ipairs(roster.rows) do
                        if row.userId == target.userId and row.name == target.name and row.familyId == enemy then found = true end
                    end
                end
                if not found then return nil, "Enemy roster changed during quote lookup" end
                return self.hitListQuery:AcceptSavedSearch(snapshot, request, reply)
            end,
            commit = function(staged) return self.hitListQuery:CommitSavedSearch(staged) end}
    end
    if self.playerPlannerReady and self.playerLedger and type(self.playerLedger.SavedTargets) == "function"
        and type(self.historyStats) == "function" then
        sources[#sources + 1] = {id = "combatSavedSearch", interval = 60,
            enabled = function(settings, _, snapshot)
                self.savedSearchSettings = type(settings.combat) == "table" and settings.combat or nil
                local configured = self.savedSearchSettings
                if type(configured) ~= "table" or configured.enabled ~= true or self.closed or self.playerLedgerFault then return false end
                if configured.targetSource == "High value only + lookup" then
                    local status = self.playerLedger:HighValueStatus(snapshot or self.latestBossSnapshot)
                    return status.known and status.count > 0
                end
                return self:SavedSearchTarget(snapshot or self.latestBossSnapshot, configured) ~= nil
            end,
            prepare = function(snapshot)
                local target = self:SavedSearchTarget(snapshot, self.savedSearchSettings)
                return self.hitListQuery:PrepareSavedSearch(snapshot, target)
            end,
            accept = function(snapshot, request, reply) return self.hitListQuery:AcceptSavedSearch(snapshot, request, reply) end,
            commit = function(staged) return self.hitListQuery:CommitSavedSearch(staged) end}
    end
    if self.warRosterQuery.sourceKey then
        sources[#sources + 1] = {id = "combatWarRoster", interval = 1,
            enabled = function(settings, _, snapshot)
                local current = snapshot or self.latestBossSnapshot
                return not self.closed and type(settings.warCombat) == "table" and settings.warCombat.enabled == true
                    and (not current or self.warRosterQuery:NeedsRead(current))
            end,
            prepare = function(snapshot) return self.warRosterQuery:Prepare(snapshot) end,
            accept = function(snapshot, request, reply) return self.warRosterQuery:Accept(snapshot, request, reply) end,
            commit = function(staged) return self.warRosterQuery:Commit(staged) end}
    end
    if self.playerProfiles then
        local publicAge = 30
        sources[#sources + 1] = {id = "combatProfile", interval = 1,
            enabled = function(settings, _, snapshot)
                local configured = type(settings.combat) == "table" and settings.combat.scoutMaxAge
                publicAge = type(configured) == "number" and configured == configured and configured >= 1
                    and configured <= 1800 and math.min(30, configured) or 30
                return not self.closed and type(settings.combat) == "table" and settings.combat.enabled == true
                    and (snapshot or self.latestBossSnapshot) ~= nil
                    and self.playerProfiles:NeedsRead(snapshot or self.latestBossSnapshot, publicAge)
            end,
            prepare = function(snapshot) return self.playerProfiles:Prepare(snapshot, publicAge) end,
            accept = function(snapshot, request, reply) return self.playerProfiles:Accept(snapshot, request, reply) end,
            commit = function(staged) return self.playerProfiles:Commit(staged) end}
    end
    if self.warProfiles then
        local publicAge = 30
        sources[#sources + 1] = {id = "combatWarProfile", interval = 1,
            enabled = function(settings, _, snapshot)
                local configured = type(settings.warCombat) == "table" and settings.warCombat.scoutMaxAge
                publicAge = type(configured) == "number" and configured == configured and configured >= 1
                    and configured <= 1800 and math.min(30, configured) or 30
                return not self.closed and type(settings.warCombat) == "table" and settings.warCombat.enabled == true
                    and (snapshot or self.latestBossSnapshot) ~= nil
                    and self.warProfiles:NeedsRead(snapshot or self.latestBossSnapshot, publicAge)
            end,
            prepare = function(snapshot) return self.warProfiles:Prepare(snapshot, publicAge) end,
            accept = function(snapshot, request, reply) return self.warProfiles:Accept(snapshot, request, reply) end,
            commit = function(staged) return self.warProfiles:Commit(staged) end}
    end
    if not self.familyBossQuery or type(reader) ~= "table"
        or type(reader.AttachFamilyBoss) ~= "function" then return sources end
    sources[#sources + 1] = {id = "familyBoss", interval = 3,
        confirmFeatures = {familyBossClaims = true, familyBossAttacks = true},
        enabled = function(settings, active)
            return (type(active) == "table"
                and (active.feature == "familyBossClaims" or active.feature == "familyBossAttacks"))
                or (type(settings.familyBossClaims) == "table" and settings.familyBossClaims.enabled == true)
                or (type(settings.familyBossAttacks) == "table" and settings.familyBossAttacks.enabled == true)
        end,
        prepare = function(snapshot) return self:PrepareFamilyBossRead(snapshot) end,
        accept = function(snapshot, request, reply) return self:AcceptFamilyBossRead(snapshot, request, reply) end,
        commit = function(staged) return reader:AttachFamilyBoss(staged) end,
    }
    return sources
end

function Methods:HitListCall(refresh)
    return self.hitListQuery:Describe(refresh)
end

function Methods:StageHitList(snapshot, reply)
    return self.hitListQuery:Stage(snapshot, reply)
end

function Methods:SearchCall(term)
    return self.hitListQuery:DescribeSearch(term)
end

function Methods:StageSearch(snapshot, reply, term)
    return self.hitListQuery:StageSearch(snapshot, reply, term)
end

function Methods:ReadSelection(raw, context)
    if type(self.targetReader.readSelection) ~= "function" then return nil, "Current player target reader unavailable" end
    return self.targetReader.readSelection(raw, context)
end

function Methods:ReadTargets(raw, context)
    return self.targetReader.read(raw, context, self.combatRules)
end

function Methods:CanDispatchPlayer(p)
    local raw, i = self.latestPlayerSnapshot, type(p) == "table" and p.intent
    local feature = type(p) == "table" and p.feature
    local warMode = feature == "warCombat"
    local profilesOwner = warMode and self.warProfiles or self.playerProfiles
    if self.closed or not self.playerPlannerReady or warMode and not self.warPlannerReady
        or type(raw) ~= "table" or type(i) ~= "table"
        or (feature ~= "combat" and not warMode) or not profilesOwner then return false end
    for _, key in ipairs({"session", "account", "place", "release", "revision"}) do if p[key] ~= raw[key] then return false end end
    local proof
    if warMode then proof = self:CurrentWarTargets(raw) else proof = self:CurrentHitList(raw) end
    local profiles = profilesOwner:Read(raw)
    local profile = profiles and profiles[tostring(i.target)]
    if not proof or proof.sourceKey ~= i.sourceKey or type(proof.war) ~= "table"
        or type(proof.war.active) ~= "boolean"
        or not warMode and proof.war.active and (proof.war.enemyFamilyId == nil or i.excludedWarFamilyId ~= proof.war.enemyFamilyId
            or i.familyId == proof.war.enemyFamilyId)
        or not warMode and not proof.war.active and i.excludedWarFamilyId ~= nil
        or not profile or profile.userId ~= i.target or profile.name ~= i.targetName or profile.level ~= i.targetLevel
        or profile.familyId ~= i.familyId or profile.friend ~= false or profile.friendshipStatus ~= "reported"
        or profile.shieldUntil ~= nil and (type(profile.shieldUntil) ~= "number" or profile.shieldUntil ~= profile.shieldUntil
            or profile.shieldUntil > raw.native.serverNow) then return false end
    local target
    for _, row in ipairs(proof.rows) do if row.userId == i.target then target = row end end
    if not target or target.name ~= i.targetName or target.level ~= i.targetLevel or target.familyId ~= i.familyId
        or target.shielded ~= false or target.stamina ~= i.attackQuote or type(i.scoutMaxAge) ~= "number" or i.scoutMaxAge < 1 or i.scoutMaxAge > 1800 then return false end
    if warMode then
        local war, allowance = proof.war, target.warStatus
        if war.active ~= true or war.canScore ~= true or war.enemyFamilyId ~= i.warEnemyFamilyId
            or i.familyId ~= i.warEnemyFamilyId or type(raw.native.family) ~= "table"
            or raw.native.family.id ~= i.warOwnFamilyId or i.warDay ~= math.floor(raw.native.serverNow / 86400)
            or i.warStatusServerNow ~= war.statusServerNow or type(allowance) ~= "table"
            or allowance.canScore ~= true or allowance.day ~= i.warDay or allowance.remaining < 1
            or allowance.attacksRemaining < 1 or allowance.pairRemaining < 1 then return false end
    end
    if i.dailyOnly ~= nil and type(i.dailyOnly) ~= "boolean" or i.highValueOnly ~= nil and type(i.highValueOnly) ~= "boolean" then return false end
    if i.dailyOnly == true then
        if type(self.frameReader) ~= "function" or self.nativeReadSource.CombatFrame ~= self.frameReader then return false end
        local ok, frame = pcall(self.frameReader, self.nativeReadSource, raw.native, {target})
        local facts = ok and type(frame) == "table" and type(frame.targets) == "table" and frame.targets[tostring(i.target)]
        local cap = ok and type(frame) == "table" and frame.dailyTargetCap
        local daily = type(raw.native) == "table" and raw.native.attackDaily
        local count = type(daily) == "table" and type(daily.counts) == "table" and daily.counts[tostring(i.target)]
        if self.closed or self.nativeReadSource.CombatFrame ~= self.frameReader or not ok or type(frame) ~= "table" or frame.busy ~= false or frame.shielded ~= false
            or frame.globalCooldown ~= 0 or type(cap) ~= "number" or cap ~= cap or cap < 1 or cap % 1 ~= 0 or cap == math.huge
            or type(facts) ~= "table" or facts.remainingDaily ~= cap or facts.manualWarning ~= false or facts.sameFamily ~= false
            or type(daily) ~= "table" or daily.day ~= math.floor(raw.native.serverNow / 86400)
            or count ~= nil and count ~= 0 then return false end
    end
    if i.highValueOnly == true and (not self.playerLedger or self.playerLedger:IsHighValue(raw, i.target) ~= true) then return false end
    local stats = not warMode and profile.statsHidden == false and {at = profile.observedServerNow, defense = profile.defense} or nil
    if type(profile.scout) == "table" and (not stats or profile.scout.at > stats.at) then stats = profile.scout end
    local fresh = stats and type(stats.at) == "number" and stats.at <= raw.native.serverNow
        and raw.native.serverNow - stats.at <= i.scoutMaxAge
    if i.kind == "playerScout" then
        return i.allowScout == true and profile.scoutCost == i.expectedStaminaCost
            and (warMode or profile.statsHidden == true) and not fresh
    end
    return i.kind == "playerAttack" and target.stamina == i.expectedStaminaCost
        and fresh == true and i.statsAt == stats.at and i.defense == stats.defense
end

function Methods:Descriptors()
    local result = {}
    for index, descriptor in ipairs(self.blocked) do
        local function owner(p)
            if type(p) == "table" and type(p.intent) == "table" and p.intent.kind == "playerScout" then return self.scoutEvidence end
            return self.playerEvidence
        end
        local evidence = self.playerEvidence and {
            capture = function(p, before)
                local e = owner(p)
                if not e then return nil, "Player outcome evidence unavailable" end
                return e.capture(p, before)
            end,
            evaluate = function(p, before, after, reply, baseline)
                local e = owner(p)
                return e and e.evaluate(p, before, after, reply, baseline) or "pending"
            end,
        } or descriptor.evidence
        result[index] = { id = descriptor.id, reader = descriptor.reader, planner = descriptor.planner,
            evidence = evidence,
            canDispatch = (descriptor.id == "combat" or descriptor.id == "warCombat") and self.playerPlannerReady and function(p) return self:CanDispatchPlayer(p) end or nil,
            recoverSaved = self.playerEvidence and function(data, after)
                local e = type(data) == "table" and owner(data.proposal)
                return e and e.recoverSaved(data, after) or nil
            end,
            recordOutcome = self.playerEvidence and function(data, after)
                if self.closed then return false, "Player outcome owner closed" end
                local p = type(data) == "table" and data.proposal
                if type(p) == "table" and type(p.intent) == "table" and p.intent.kind == "playerScout" then
                    local profiles = p.feature == "warCombat" and self.warProfiles or self.playerProfiles
                    if not profiles then return false, "Owned Scout cache unavailable" end
                    return profiles:RecordScout(data, after)
                end
                if not self.playerLedger or self.playerLedgerFault then
                    return false, self.playerLedgerFault or "Durable player history unavailable"
                end
                return self.playerLedger:Record(data, after)
            end or nil }
    end
    for index, descriptor in ipairs(self.descriptors) do
        result[index + #self.blocked] = { id = descriptor.id, reader = descriptor.reader,
            planner = descriptor.planner, evidence = descriptor.evidence,
            recoverSaved = descriptor.evidence.recoverSaved,
            canDispatch = (descriptor.id == "globalBossAttack" or descriptor.id == "globalBossClaim") and function(proposal)
                if self.closed or not self.globalBossSource or not self.latestBossSnapshot then return false end
                local latest = self.globalBossSource:Enrich(self.latestBossSnapshot)
                return latest ~= nil and descriptor.evidence.canDispatch(proposal, latest)
            end or descriptor.id == "familyBossClaims" and function(proposal)
                return not self.closed and self.latestBossSnapshot ~= nil
                    and descriptor.evidence.canDispatch(proposal, self.latestBossSnapshot)
            end or (descriptor.id == "bosses" or descriptor.id == "bossShop") and function(proposal)
                if self.closed or not self.bossCatalog or not self.latestBossSnapshot then return false end
                local latest = self.bossCatalog:Enrich(self.latestBossSnapshot)
                return latest ~= nil and descriptor.evidence.canDispatch(proposal, latest)
            end or nil }
    end
    return result
end

return CombatTab
