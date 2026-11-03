-- Separately configurable Combat controls own their sources, evidence and lifecycle.
local CombatTab = {}
local ownedProofs = { "bossEncounterProof", "playerFightProof", "playerFightHistoryProof", "hitListProof", "warRosterProof", "bossStageProof", "bossShopProof", "globalBossProof", "localUserIdProof", "familyAttackProof" }
local lookupHeaders = {"session", "account", "place", "release", "revision", "capturedAt"}
local lookupChoices = {"targetSource", "preferHighValue", "policy", "minimumPayout", "minSamples", "minWinRate", "dailyOnly"}
local function lookupScope(snapshot, settings)
    if type(snapshot) ~= "table" or type(snapshot.native) ~= "table" then return nil end
    local result = {serverNow = snapshot.native.serverNow}
    for _, key in ipairs(lookupHeaders) do result[key] = snapshot[key] end
    for _, key in ipairs(lookupChoices) do result[key] = settings[key] end
    return result
end
local function sameLookupScope(a, b)
    if type(a) ~= "table" or type(b) ~= "table" then return false end
    for key, value in pairs(a) do if b[key] ~= value then return false end end
    for key, value in pairs(b) do if a[key] ~= value then return false end end
    return true
end
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
    local reason = feature.id == "warCombat"
        and "Unavailable: verified active-war enemy contract not implemented" or nil
    local row = { feature = feature, tabOwned = true, blockedReason = reason,
        alwaysShowCustom = feature.id == "combat" or feature.id == "warCombat",
        status = group:Status({ Text = "Activity",
            Default = reason and ("Blocked — " .. reason) or "Off — UI only" }) }
    if feature.id == "combat" then
        row.memoryStatus = group:Status({Text = "High-value history", Default = "Unknown — current owned history required"})
        row.memoryRules = group:Group({Text = "High-value rules", Open = false})
        row.memoryRules:Description({Text = "Rules apply to future owned fights, including a pending attack's saved rules. Changing rules does not replay old history or clear existing tags. Set the low threshold to 0 to disable demotion. All target and spending limits still apply."})
        for _, field in ipairs(feature.memoryRules or {}) do
            local key = "combat.memory." .. field.id
            if field.type == "boolean" then
                bind(row.memoryRules, "Toggle", key, {Text = field.label, Default = field.value, RevertOnClose = true, RevertTo = false})
            else
                numeric[key] = true
                bind(row.memoryRules, "Input", key, {Text = field.label, Default = tostring(field.value), FireOnBlur = true})
            end
        end
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
        warProfiles = deps.PlayerProfileQuery.new(deps.identity, deps.fingerprint, warRosterQuery, deps.nativeReadSource)
    end
    local playerPlannerReady = false
    if playerEvidence and playerLedger and not playerLedgerFault and playerProfiles
        and type(deps.PlayerFightPlanner) == "table" and type(deps.PlayerFightPlanner.new) == "function"
        and type(deps.TargetSelection) == "table" and type(deps.PlayerTargetState.readSelection) == "function" then
        local planner = deps.PlayerFightPlanner.new(deps.TargetSelection)
        player = {read = deps.PlayerTargetState.readSelection, propose = planner.propose}
        playerPlannerReady = true
    end
    local bossCatalog
    if type(deps.NativeBossCatalog) == "table"
        and type(deps.NativeBossCatalog.new) == "function"
        and type(deps.bossStages) == "table" then
        bossCatalog = deps.NativeBossCatalog.new(deps.bossStages,
            deps.config, deps.fingerprint, deps.release, deps.gameData, deps.clientGame)
    end
    return setmetatable({ id = "combat", ownedProofs = ownedProofs, descriptors = descriptors,
        blocked = { { id = "combat", reader = player,
            planner = player, evidence = player },
            { id = "warCombat", reader = war,
            planner = war, evidence = war } },
        hitListQuery = hitListQuery, warRosterQuery = warRosterQuery, playerProfiles = playerProfiles, warProfiles = warProfiles,
        familyDirectory = type(deps.FamilyDirectoryQuery) == "table" and deps.FamilyDirectoryQuery.new(deps.nativeReadSource) or nil,
        nativeReadSource = deps.nativeReadSource,
        frameReader = type(deps.nativeReadSource) == "table" and deps.nativeReadSource.CombatFrame or nil,
        targetReader = deps.PlayerTargetState, playerPlannerReady = playerPlannerReady,
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
        bossCatalog = bossCatalog, bossEncounters = {}, bossConfirmSeen = {}, bossReadyAt = 0, bossClock = deps.clock,
        bossNow = type(deps.clock) == "table" and deps.clock.Now }, Methods)
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

local function bossNumber(value, minimum, maximum)
    return type(value) == "number" and value == value and value >= minimum and value <= maximum
end
local function bossInteger(value, minimum, maximum)
    return bossNumber(value, minimum, maximum) and value % 1 == 0
end
function Methods:BossLocalNow()
    if self.closed or type(self.bossClock) ~= "table" or type(self.bossNow) ~= "function"
        or self.bossClock.Now ~= self.bossNow then return nil end
    local ok, value = pcall(self.bossNow, self.bossClock)
    return ok and bossNumber(value, 0, 9007199254740991) and value or nil
end
function Methods:BossEncounterProof(raw)
    local native = type(raw) == "table" and raw.native
    local state = type(native) == "table" and native.bossStage
    if self.closed or type(state) ~= "table" or not bossInteger(state.best, 0, 100000)
        or not bossNumber(native.serverNow, 0, 9007199254740991) then return nil end
    local day = tonumber(os.date("!%Y%j", math.floor(native.serverNow)))
    if not day then return nil end
    local counts = {}
    for stage, record in pairs(self.bossEncounters) do
        if record.day == day and record.best == state.best then
            counts[stage] = {hits = record.hits, stamina = record.stamina}
        end
    end
    return {account = raw.account, session = raw.session, capturedAt = raw.capturedAt,
        day = day, best = state.best, counts = counts, readyAt = self.bossReadyAt, now = self:BossLocalNow()}
end
function Methods:BossExcluded(proof, settings)
    local result = {}
    if type(settings) ~= "table" or settings.confirmedLimitsEnabled ~= true then return result end
    local hits, stamina = settings.maxConfirmedHits or 100, settings.maxConfirmedStamina or 100
    if not proof or not bossNumber(hits, 1, 100000) or not bossNumber(stamina, 1, 100000) then return nil end
    local cost = self.bossCatalog and self.bossCatalog.staminaCost
    if not bossInteger(cost, 1, 10000) then return nil end
    for stage, record in pairs(proof.counts) do
        if record.hits >= hits or record.stamina + cost > stamina then result[stage] = true end
    end
    return result
end
function Methods:RecordBossOutcome(data, after, evidence)
    if self.closed or type(data) ~= "table" or type(data.proposal) ~= "table"
        or type(data.proposal.intent) ~= "table" then return false, "Boss encounter owner unavailable" end
    local p, intent = data.proposal, data.proposal.intent
    if (p.requestId ~= nil and not bossInteger(p.requestId, 1, 9007199254740991)) or type(p.session) ~= "string"
        or type(p.actionKey) ~= "string" then return false, "Boss confirmation identity unavailable" end
    local enriched = self.bossCatalog and self.bossCatalog:Enrich(after, intent, intent.stage)
    if self.closed or not enriched or evidence.recoverSaved(data, enriched) ~= "confirmed" then
        return false, "Exact Boss confirmation required for encounter accounting"
    end
    local function part(value)
        local kind = type(value)
        local text = kind == "number" and string.format("%.17g", value) or tostring(value)
        return kind .. tostring(#text) .. ":" .. text
    end
    local parts = {}
    for _, field in ipairs({"session", "account", "place", "release", "actionKey"}) do
        parts[#parts + 1] = part(p[field])
    end
    if p.requestId ~= nil then
        parts[#parts + 1] = "numbered" .. part(p.requestId)
    else
        -- Checkpoint supports historical unnumbered custody. Bind its original
        -- logical request, never invent a new request ID for reconciliation.
        parts[#parts + 1] = "legacy" .. part(p.revision) .. part(data.before.capturedAt)
        local keys = {}
        for key in pairs(intent) do keys[#keys + 1] = key end
        table.sort(keys)
        for _, key in ipairs(keys) do parts[#parts + 1] = part(key) .. part(intent[key]) end
    end
    local identity = table.concat(parts)
    if self.bossConfirmSeen[identity] then return true end
    local key = tostring(intent.stage)
    local record = self.bossEncounters[key]
    if not record or record.day ~= intent.dayStamp or record.best ~= intent.bestBefore then
        record = {day = intent.dayStamp, best = intent.bestBefore, hits = 0, stamina = 0}
        self.bossEncounters[key] = record
    end
    record.hits = record.hits + 1
    record.stamina = record.stamina + intent.expectedStaminaCost
    self.bossConfirmSeen[identity] = true
    -- Count before checkpoint cleanup. A failed cleanup may call this again;
    -- the owned request identity prevents duplicate accounting in this load.
    local settings = self.latestBossSettings or {}
    local delay = settings.confirmationDelay or 5
    local localNow = self:BossLocalNow()
    self.bossReadyAt = settings.confirmationDelayEnabled == true
        and bossNumber(delay, 5, 120) and localNow ~= nil and localNow + delay or 0
    return true
end

function Methods:Enrich(snapshot, settings)
    local result = {}
    for key, value in pairs(snapshot) do result[key] = value end
    for _, field in ipairs(ownedProofs) do result[field] = nil end
    self.latestBossSnapshot = result
    self.latestBossSettings = type(settings) == "table" and settings.bosses or nil
    result.bossEncounterProof = self:BossEncounterProof(result)
    if self.bossCatalog then
        -- Missing city state must not suppress independent Global/Family rows.
        result = self.bossCatalog:Enrich(result, self.latestBossSettings, nil,
            self:BossExcluded(result.bossEncounterProof, self.latestBossSettings)) or result
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
        result.warRosterProof = self.warRosterQuery:Read(result)
        if result.warRosterProof and self.warProfiles then
            result.warRosterProof.profiles = self.warProfiles:Read(result) or {}
        end
        result.hitListProof = self:CurrentHitList(result, result.warRosterProof)
        if result.hitListProof and self.playerProfiles then
            result.hitListProof.profiles = self.playerProfiles:Read(result) or {}
        end
        if result.hitListProof and type(settings) == "table" and type(settings.combat) == "table"
            and settings.combat.enabled == true and type(self.frameReader) == "function"
            and self.nativeReadSource.CombatFrame == self.frameReader then
            local ok, frame = pcall(self.frameReader, self.nativeReadSource, result.native, result.hitListProof.rows)
            if ok and type(frame) == "table" then
                local bound = {}
                for key, value in pairs(frame) do bound[key] = value end
                bound.header = {serverNow = result.native.serverNow}
                for _, key in ipairs({"session", "account", "place", "release", "revision", "capturedAt"}) do
                    bound.header[key] = result[key]
                end
                bound.sourceKey = result.hitListProof.sourceKey
                result.hitListProof.nativeFrame = bound
            end
        end
    end
    if self.playerLedger and not self.closed then
        local combat = type(settings) == "table" and settings.combat
        local source = type(combat) == "table" and combat.enabled == true and combat.targetSource
        result.playerFightHistoryProof = self.playerLedger:Proof(result, source == "High value only" or source == "High value only + lookup"
            or type(combat) == "table" and combat.enabled == true and combat.preferHighValue == true)
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
    if self.familyDirectory then self.familyDirectory:Close() end
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
    local prefer = settings.preferHighValue == true
    local present, highIds = {}, {}
    for _, row in ipairs(list.rows) do present[row.userId] = true end
    local highTargets = (highOnly or prefer) and self.playerLedger:HighValueTargets(snapshot) or nil
    for _, row in ipairs(highTargets or {}) do highIds[row.userId] = true end
    local minimum = math.max(settings.minWinRate, settings.policy == "Cautious" and 90 or 0)
    local function eligible(candidates, requireSample, excludeHigh)
        local result = {}
        for _, target in ipairs(candidates or {}) do
            local stats = self.historyStats(target.history, native.serverNow)
            local count = daily.counts[tostring(target.userId)]
            local used = count ~= nil and count ~= 0
            if settings.dailyOnly == true then
                for _, row in ipairs(target.history) do if math.floor(row.at / 86400) == daily.day then used = true end end
            end
            local enemy = list.war.active == true and type(list.war.enemyTargets) == "table" and list.war.enemyTargets[tostring(target.userId)] == true
            if not present[target.userId] and not enemy and not (excludeHigh and highIds[target.userId])
                and target.userId ~= native.userId and stats and stats.samples >= math.max(requireSample and 1 or 0, settings.minSamples)
                and stats.payout >= settings.minimumPayout and (stats.samples == 0 or stats.winRate >= minimum)
                and (settings.dailyOnly ~= true or not used) then result[#result + 1] = target end
        end
        return result
    end
    local high = highTargets and self.hitListQuery:PickSavedSearch(snapshot,
        eligible(highTargets, settings.targetSource == "Saved only + lookup", false), 128, "high") or nil
    if highOnly then if high then high.lookupScope = "high" end; return high end
    local ordinary = self.hitListQuery:PickSavedSearch(snapshot, eligible(self.playerLedger:SavedTargets(snapshot), true, prefer), 32, "ordinary")
    local selected = high and (not ordinary or self.savedSearchScope ~= "high") and high or ordinary or high
    if selected then selected.lookupScope = selected == high and "high" or "ordinary" end
    return selected

end

function Methods:ReadSources(reader)
    local sources = {}
    if self.familyDirectory then
        local query = self.familyDirectory
        sources[#sources + 1] = {id = "allianceDirectory", interval = 60,
            enabled = function(settings) return not self.closed and query:Configure(settings.alliance) end,
            prepare = function(raw) return query:Prepare(raw) end,
            accept = function(raw, request, reply) return query:Accept(raw, request, reply) end,
            commit = function(staged) return query:Commit(staged) end}
    end
    if self.hitListQuery.sourceKey then
        sources[#sources + 1] = {id = "combatHitList", interval = 1,
            enabled = function(settings, _, snapshot)
                local current = snapshot or self.latestBossSnapshot
                return not self.closed and type(settings.combat) == "table" and settings.combat.enabled == true
                    and (not current or self.hitListQuery:NeedsRead(current))
            end,
            prepare = function(snapshot) return self.hitListQuery:Prepare(snapshot) end,
            accept = function(snapshot, request, reply) return self.hitListQuery:Accept(snapshot, request, reply) end,
            commit = function(staged) return self.hitListQuery:Commit(staged) end}
    end
    if self.playerPlannerReady and self.playerLedger and type(self.playerLedger.SavedTargets) == "function"
        and type(self.historyStats) == "function" then
        sources[#sources + 1] = {id = "combatSavedSearch", interval = 60,
            enabled = function(settings, _, snapshot)
                self.savedSearchSettings = type(settings.combat) == "table" and settings.combat or nil
                local configured = self.savedSearchSettings
                local run, current = self.savedSearchRun, snapshot or self.latestBossSnapshot
                local source = type(configured) == "table" and configured.targetSource
                local permitted = type(configured) == "table" and configured.enabled == true and not self.closed and not self.playerLedgerFault
                    and (source == "Saved only + lookup" or source == "Saved and new + lookup" or source == "High value only + lookup")
                if run then
                    if not permitted or not sameLookupScope(run.scope, lookupScope(current, configured)) then
                        self.hitListQuery:CancelSavedSearch(run.request)
                        self.savedSearchRun = nil
                        if not permitted then return false end
                        -- Revoke this tick; admission waits for the existing read cooldown.
                        return false
                    elseif self.hitListQuery:OwnsSavedSearch(run.request) then
                        return true -- Authorization survives the new-admission cooldown.
                    else self.savedSearchRun = nil end
                end
                if not permitted then return false end
                if source == "High value only + lookup" or configured.preferHighValue == true then
                    local status = self.playerLedger:HighValueStatus(snapshot or self.latestBossSnapshot)
                    if source == "High value only + lookup" then return status.known and status.count > 0 end
                    if status.known and status.count > 0 then return true end
                end
                return self:SavedSearchTarget(snapshot or self.latestBossSnapshot, configured) ~= nil
            end,
            prepare = function(snapshot)
                local target = self:SavedSearchTarget(snapshot, self.savedSearchSettings)
                local request, why = self.hitListQuery:PrepareSavedSearch(snapshot, target)
                if request then
                    self.savedSearchScope = target.lookupScope
                    self.savedSearchRun = {request = request, scope = lookupScope(snapshot, self.savedSearchSettings)}
                end
                return request, why
            end,
            accept = function(snapshot, request, reply) return self.hitListQuery:AcceptSavedSearch(snapshot, request, reply) end,
            commit = function(staged)
                local saved = self.hitListQuery:CommitSavedSearch(staged)
                if self.savedSearchRun then self.hitListQuery:CancelSavedSearch(self.savedSearchRun.request) end
                self.savedSearchRun = nil
                return saved
            end}
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
    if self.closed or not self.playerPlannerReady or type(raw) ~= "table" or type(i) ~= "table"
        or p.feature ~= "combat" or not self.playerProfiles then return false end
    for _, key in ipairs({"session", "account", "place", "release", "revision"}) do if p[key] ~= raw[key] then return false end end
    local proof, profiles = self:CurrentHitList(raw), self.playerProfiles:Read(raw)
    local profile = profiles and profiles[tostring(i.target)]
    if not proof or proof.sourceKey ~= i.sourceKey or type(proof.war) ~= "table"
        or type(proof.war.active) ~= "boolean"
        or proof.war.active and (proof.war.enemyFamilyId == nil or i.excludedWarFamilyId ~= proof.war.enemyFamilyId
            or i.familyId == proof.war.enemyFamilyId)
        or not proof.war.active and i.excludedWarFamilyId ~= nil
        or not profile or profile.userId ~= i.target or profile.name ~= i.targetName or profile.level ~= i.targetLevel
        or profile.familyId ~= i.familyId or profile.friend ~= false or profile.friendshipStatus ~= "reported"
        or profile.shieldUntil ~= nil and (type(profile.shieldUntil) ~= "number" or profile.shieldUntil ~= profile.shieldUntil
            or profile.shieldUntil > raw.native.serverNow) then return false end
    local target
    for _, row in ipairs(proof.rows) do if row.userId == i.target then target = row end end
    if not target or target.name ~= i.targetName or target.level ~= i.targetLevel or target.familyId ~= i.familyId
        or target.shielded ~= false or target.stamina ~= i.attackQuote or type(i.scoutMaxAge) ~= "number" or i.scoutMaxAge < 1 or i.scoutMaxAge > 1800 then return false end
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
    local stats = profile.statsHidden == false and {at = profile.observedServerNow, defense = profile.defense} or nil
    if type(profile.scout) == "table" and (not stats or profile.scout.at > stats.at) then stats = profile.scout end
    local fresh = stats and type(stats.at) == "number" and stats.at <= raw.native.serverNow
        and raw.native.serverNow - stats.at <= i.scoutMaxAge
    if i.kind == "playerScout" then
        return i.allowScout == true and profile.scoutCost == i.expectedStaminaCost
            and profile.statsHidden == true and not fresh
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
            canDispatch = descriptor.id == "combat" and self.playerPlannerReady and function(p) return self:CanDispatchPlayer(p) end or nil,
            recoverSaved = self.playerEvidence and function(data, after)
                local e = type(data) == "table" and owner(data.proposal)
                return e and e.recoverSaved(data, after) or nil
            end,
            recordOutcome = self.playerEvidence and function(data, after)
                if self.closed then return false, "Player outcome owner closed" end
                local p = type(data) == "table" and data.proposal
                if type(p) == "table" and type(p.intent) == "table" and p.intent.kind == "playerScout" then
                    if not self.playerProfiles then return false, "Owned Scout cache unavailable" end
                    return self.playerProfiles:RecordScout(data, after)
                end
                if not self.playerLedger or self.playerLedgerFault then
                    return false, self.playerLedgerFault or "Durable player history unavailable"
                end
                return self.playerLedger:Record(data, after)
            end or nil }
    end
    for index, descriptor in ipairs(self.descriptors) do
        local evidence = descriptor.evidence
        local function exact(proposal, snapshot)
            if self.closed or not self.bossCatalog or type(proposal) ~= "table"
                or type(proposal.intent) ~= "table" then return nil end
            local enriched = self.bossCatalog:Enrich(snapshot, proposal.intent, proposal.intent.stage)
            if enriched then enriched.bossEncounterProof = self:BossEncounterProof(snapshot) end
            return not self.closed and enriched or nil
        end
        local wrapped = descriptor.id == "bosses" and {
            capture = evidence.capture,
            evaluate = function(p, before, after, reply, baseline)
                local enriched = exact(p, after)
                return enriched and evidence.evaluate(p, before, enriched, reply, baseline) or "pending"
            end,
        } or evidence
        result[index + #self.blocked] = { id = descriptor.id, reader = descriptor.reader,
            planner = descriptor.planner, evidence = wrapped,
            recordOutcome = descriptor.id == "bosses" and function(data, after)
                return self:RecordBossOutcome(data, after, evidence)
            end or nil,
            recoverSaved = descriptor.id == "bosses" and function(data, after)
                local enriched = type(data) == "table" and exact(data.proposal, after)
                return enriched and evidence.recoverSaved(data, enriched) or nil
            end or evidence.recoverSaved,
            canDispatch = (descriptor.id == "globalBossAttack" or descriptor.id == "globalBossClaim") and function(proposal)
                if self.closed or not self.globalBossSource or not self.latestBossSnapshot then return false end
                local latest = self.globalBossSource:Enrich(self.latestBossSnapshot)
                return latest ~= nil and descriptor.evidence.canDispatch(proposal, latest)
            end or descriptor.id == "familyBossClaims" and function(proposal)
                return not self.closed and self.latestBossSnapshot ~= nil
                    and descriptor.evidence.canDispatch(proposal, self.latestBossSnapshot)
            end or (descriptor.id == "bosses" or descriptor.id == "bossShop") and function(proposal)
                if self.closed or not self.bossCatalog or not self.latestBossSnapshot then return false end
                local latest
                if descriptor.id == "bosses" then latest = exact(proposal, self.latestBossSnapshot)
                else latest = self.bossCatalog:Enrich(self.latestBossSnapshot) end
                return latest ~= nil and descriptor.evidence.canDispatch(proposal, latest)
            end or nil }
    end
    return result
end

return CombatTab
