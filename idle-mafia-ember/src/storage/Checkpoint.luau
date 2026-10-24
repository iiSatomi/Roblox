-- An unresolved-action ledger. Storage Read/Write must atomically persist decoded tables.
local Checkpoint = {}
local Methods = {}
Methods.__index = Methods

local function nonempty(value)
    return type(value) == "string" and #value > 0
end

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge and value % 1 == 0
end

local function validResources(raw)
    if type(raw) ~= "table" then return nil end
    local copy = {}
    for name, amount in pairs(raw) do
        if not nonempty(name) or type(amount) ~= "number" or amount ~= amount
            or amount < 0 or amount == math.huge then return nil end
        copy[name] = amount
    end
    return copy
end

local function copyRecord(raw, scope)
    if type(raw) ~= "table" or not nonempty(raw.feature)
        or not nonempty(raw.actionKey) or raw.account ~= scope.account
        or raw.place ~= scope.place or raw.release ~= scope.release then
        return nil
    end
    local resources = validResources(raw.resources)
    if not resources then return nil end
    return {
        account = scope.account, place = scope.place, release = scope.release,
        feature = raw.feature, actionKey = raw.actionKey, resources = resources,
    }
end

local function scopeKey(account, place, release)
    return "idle-mafia-ember:checkpoint:v1:"
        .. #account .. ":" .. account .. #place .. ":" .. place
        .. #release .. ":" .. release
end

function Checkpoint.new(storage)
    assert(type(storage) == "table" and type(storage.Read) == "function"
        and type(storage.Write) == "function", "Missing checkpoint storage")
    -- A two-slot file store used for write-ahead actions must not revive an
    -- older generation when its newer slot is damaged.
    assert(storage.strictRecovery == true,
        "Checkpoint requires strict two-slot recovery")
    return setmetatable({ storage = storage, scope = nil, key = nil,
        records = {}, favorUsage = nil, sabotageUsage = nil,
        bossUsage = nil, globalClaimUsage = nil,
        globalAttackUsage = nil, familyClaimUsage = nil,
        familyAttackUsage = nil, bossShopUsage = nil,
        fault = nil }, Methods)
end

function Methods:ScopeKey()
    return self.key
end

function Methods:Load(account, place, release)
    if not nonempty(account) or not nonempty(place) or not nonempty(release) then
        self.fault = "Invalid checkpoint scope"
        return nil, self.fault
    end
    self.scope = { account = account, place = place, release = release }
    self.key = scopeKey(account, place, release)
    self.records = {}
    self.favorUsage = nil
    self.sabotageUsage = nil
    self.bossUsage = nil
    self.globalClaimUsage = nil
    self.globalAttackUsage = nil
    self.familyClaimUsage = nil
    self.familyAttackUsage = nil
    self.bossShopUsage = nil
    self.fault = nil
    local ok, data = pcall(self.storage.Read, self.storage, self.key)
    if not ok then self.fault = "Checkpoint read failed"; return nil, self.fault end
    if data == nil then return {}, nil end
    if type(data) ~= "table" or data.version ~= 1
        or type(data.records) ~= "table" or #data.records > 256 then
        self.fault = "Corrupt checkpoint"
        return nil, self.fault
    end
    local records, seen = {}, {}
    for index, raw in ipairs(data.records) do
        local record = copyRecord(raw, self.scope)
        if not record or seen[record.actionKey] then
            self.fault = "Corrupt checkpoint"
            return nil, self.fault
        end
        seen[record.actionKey] = true
        records[index] = record
    end
    for key in pairs(data.records) do
        if type(key) ~= "number" or key < 1 or key > #records
            or key % 1 ~= 0 then
            self.fault = "Corrupt checkpoint"
            return nil, self.fault
        end
    end
    local usage = data.favorUsage
    if usage ~= nil and (type(usage) ~= "table"
        or not integer(usage.day, 0)
        or not integer(usage.attempts, 0) or usage.attempts > 5) then
        self.fault = "Corrupt checkpoint"
        return nil, self.fault
    end
    local sabotage = data.sabotageUsage
    if sabotage ~= nil and (type(sabotage) ~= "table"
        or not integer(sabotage.day, 0)
        or not integer(sabotage.attempts, 0)
        or sabotage.attempts > 5) then
        self.fault = "Corrupt checkpoint"
        return nil, self.fault
    end
    local boss = data.bossUsage
    if boss ~= nil and (type(boss) ~= "table"
        or not integer(boss.day, 0)
        or not integer(boss.hits, 0) or boss.hits > 100
        or not integer(boss.stamina, 0) or boss.stamina > 100
        or not integer(boss.lastServerNow, 0)) then
        self.fault = "Corrupt checkpoint"
        return nil, self.fault
    end
    local claim = data.globalClaimUsage
    if claim ~= nil and (type(claim) ~= "table"
        or not nonempty(claim.runKey)
        or #claim.runKey > 120
        or not integer(claim.attempts, 0)
        or claim.attempts > 1) then
        self.fault = "Corrupt checkpoint"
        return nil, self.fault
    end
    local attack = data.globalAttackUsage
    if attack ~= nil and (type(attack) ~= "table"
        or not nonempty(attack.runKey)
        or #attack.runKey > 120
        or not integer(attack.hits, 0) or attack.hits > 25
        or not integer(attack.lastServerNow, 0)) then
        self.fault = "Corrupt checkpoint"
        return nil, self.fault
    end
    local familyClaim = data.familyClaimUsage
    local familyClaims, familyWeeks = {}, {}
    if familyClaim ~= nil then
        if type(familyClaim) ~= "table" then
            self.fault = "Corrupt checkpoint"
            return nil, self.fault
        end
        local source = familyClaim.weeks or { familyClaim }
        if type(source) ~= "table" or #source > 64 then
            self.fault = "Corrupt checkpoint"
            return nil, self.fault
        end
        for _, weekUsage in ipairs(source) do
            if type(weekUsage) ~= "table"
                or not integer(weekUsage.week, 1)
                or familyWeeks[weekUsage.week]
                or type(weekUsage.stages) ~= "table"
                or #weekUsage.stages > 32 then
                self.fault = "Corrupt checkpoint"
                return nil, self.fault
            end
            local stages, stageSeen = {}, {}
            for _, stage in ipairs(weekUsage.stages) do
                if not integer(stage, 0) or stage > 100 or stageSeen[stage] then
                    self.fault = "Corrupt checkpoint"
                    return nil, self.fault
                end
                stageSeen[stage] = true
                stages[#stages + 1] = stage
            end
            for key in pairs(weekUsage.stages) do
                if not integer(key, 1) or key > #stages then
                    self.fault = "Corrupt checkpoint"
                    return nil, self.fault
                end
            end
            familyWeeks[weekUsage.week] = true
            familyClaims[#familyClaims + 1] = {
                week = weekUsage.week, stages = stages }
        end
        for key in pairs(source) do
            if not integer(key, 1) or key > #familyClaims then
                self.fault = "Corrupt checkpoint"
                return nil, self.fault
            end
        end
    end
    local familyAttack = data.familyAttackUsage
    if familyAttack ~= nil and (type(familyAttack) ~= "table"
        or not integer(familyAttack.week, 1)
        or not integer(familyAttack.famId, 1)
        or not integer(familyAttack.hits, 0)
        or familyAttack.hits > 25
        or not integer(familyAttack.lastServerNow, 0)) then
        self.fault = "Corrupt checkpoint"
        return nil, self.fault
    end
    local shop = data.bossShopUsage
    if shop ~= nil and (type(shop) ~= "table"
        or not nonempty(shop.session) or #shop.session > 120
        or not integer(shop.attempts, 0)
        or shop.attempts > 20) then
        self.fault = "Corrupt checkpoint"
        return nil, self.fault
    end
    self.records = records
    self.favorUsage = usage and { day = usage.day,
        attempts = usage.attempts } or nil
    self.sabotageUsage = sabotage and { day = sabotage.day,
        attempts = sabotage.attempts } or nil
    self.bossUsage = boss and { day = boss.day, hits = boss.hits,
        stamina = boss.stamina,
        lastServerNow = boss.lastServerNow } or nil
    self.globalClaimUsage = claim and {
        runKey = claim.runKey, attempts = claim.attempts } or nil
    self.globalAttackUsage = attack and {
        runKey = attack.runKey, hits = attack.hits,
        lastServerNow = attack.lastServerNow } or nil
    self.familyClaimUsage = familyClaims
    self.familyAttackUsage = familyAttack and {
        week = familyAttack.week, famId = familyAttack.famId,
        hits = familyAttack.hits,
        lastServerNow = familyAttack.lastServerNow } or nil
    self.bossShopUsage = shop and {
        session = shop.session, attempts = shop.attempts } or nil
    return self:Records(), nil
end

function Methods:FavorUsage(day, capturedAt)
    if not self.scope or self.fault or not integer(day, 0)
        or type(capturedAt) ~= "number" or capturedAt ~= capturedAt
        or capturedAt < 0 or capturedAt == math.huge then return nil end
    local usage = self.favorUsage
    if usage and day < usage.day then return nil end
    return { account = self.scope.account, day = day,
        attempts = usage and usage.day == day and usage.attempts or 0,
        capturedAt = capturedAt }
end

function Methods:SabotageUsage(day, capturedAt)
    if not self.scope or self.fault or not integer(day, 0)
        or type(capturedAt) ~= "number" or capturedAt ~= capturedAt
        or capturedAt < 0 or capturedAt == math.huge then return nil end
    local usage = self.sabotageUsage
    if usage and day < usage.day then return nil end
    return { account = self.scope.account, day = day,
        attempts = usage and usage.day == day and usage.attempts or 0,
        capturedAt = capturedAt }
end

function Methods:BossUsage(day, capturedAt)
    if not self.scope or self.fault or not integer(day, 0)
        or type(capturedAt) ~= "number" or capturedAt ~= capturedAt
        or capturedAt < 0 or capturedAt == math.huge then return nil end
    local usage = self.bossUsage
    if usage and day < usage.day then return nil end
    local current = usage and day == usage.day and usage or nil
    return { account = self.scope.account, day = day,
        hits = current and current.hits or 0,
        stamina = current and current.stamina or 0,
        lastServerNow = current and current.lastServerNow or 0,
        capturedAt = capturedAt }
end

function Methods:GlobalClaimUsage(runKey, capturedAt)
    if not self.scope or self.fault or not nonempty(runKey)
        or #runKey > 120
        or type(capturedAt) ~= "number" or capturedAt ~= capturedAt
        or capturedAt < 0 or capturedAt == math.huge then return nil end
    local current = self.globalClaimUsage
    return { account = self.scope.account, runKey = runKey,
        attempts = current and current.runKey == runKey
            and current.attempts or 0,
        capturedAt = capturedAt }
end

function Methods:GlobalAttackUsage(runKey, capturedAt)
    if not self.scope or self.fault or not nonempty(runKey)
        or #runKey > 120
        or type(capturedAt) ~= "number" or capturedAt ~= capturedAt
        or capturedAt < 0 or capturedAt == math.huge then return nil end
    local current = self.globalAttackUsage
    if current and current.runKey ~= runKey then current = nil end
    return { account = self.scope.account, runKey = runKey,
        hits = current and current.hits or 0,
        lastServerNow = current and current.lastServerNow or 0,
        capturedAt = capturedAt }
end

function Methods:FamilyClaimUsage(week, capturedAt)
    if not self.scope or self.fault or not integer(week, 1)
        or type(capturedAt) ~= "number" or capturedAt ~= capturedAt
        or capturedAt < 0 or capturedAt == math.huge then return nil end
    local stages = {}
    for _, current in ipairs(self.familyClaimUsage or {}) do
        if current.week == week then
            for index, stage in ipairs(current.stages) do
                stages[index] = stage
            end
            break
        end
    end
    return { account = self.scope.account, week = week,
        stages = stages, capturedAt = capturedAt }
end

function Methods:FamilyAttackUsage(week, famId, capturedAt)
    if not self.scope or self.fault
        or not integer(week, 1) or not integer(famId, 1)
        or type(capturedAt) ~= "number" or capturedAt ~= capturedAt
        or capturedAt < 0 or capturedAt == math.huge then return nil end
    local current = self.familyAttackUsage
    if current and (week < current.week
        or (week == current.week
            and famId ~= current.famId)) then return nil end
    if current and week ~= current.week then current = nil end
    return { account = self.scope.account, week = week,
        famId = famId, hits = current and current.hits or 0,
        lastServerNow = current and current.lastServerNow or 0,
        capturedAt = capturedAt }
end

function Methods:BossShopUsage(session, capturedAt)
    if not self.scope or self.fault or not nonempty(session)
        or #session > 120
        or type(capturedAt) ~= "number" or capturedAt ~= capturedAt
        or capturedAt < 0 or capturedAt == math.huge then return nil end
    local usage = self.bossShopUsage
    return { account = self.scope.account, session = session,
        attempts = usage and usage.session == session
            and usage.attempts or 0,
        capturedAt = capturedAt }
end

function Methods:Records()
    local copy = {}
    for index, record in ipairs(self.records) do
        copy[index] = copyRecord(record, self.scope)
    end
    return copy
end

function Methods:Commit(records, favorUsage, bossUsage,
    sabotageUsage, globalClaimUsage, globalAttackUsage,
    familyClaimUsage, familyAttackUsage, bossShopUsage)
    if self.fault then return false, self.fault end
    local ok, result = pcall(self.storage.Write, self.storage, self.key,
        { version = 1, records = records,
            favorUsage = favorUsage, bossUsage = bossUsage,
            sabotageUsage = sabotageUsage,
            globalClaimUsage = globalClaimUsage,
            globalAttackUsage = globalAttackUsage,
            familyClaimUsage = { weeks = familyClaimUsage or {} },
            familyAttackUsage = familyAttackUsage,
            bossShopUsage = bossShopUsage })
    if not ok or result == false then
        self.fault = "Checkpoint write failed"
        return false, self.fault
    end
    self.records = records
    self.favorUsage = favorUsage
    self.sabotageUsage = sabotageUsage
    self.bossUsage = bossUsage
    self.globalClaimUsage = globalClaimUsage
    self.globalAttackUsage = globalAttackUsage
    self.familyClaimUsage = familyClaimUsage
    self.familyAttackUsage = familyAttackUsage
    self.bossShopUsage = bossShopUsage
    return true, nil
end

function Methods:Save(raw)
    if not self.scope or self.fault then return false, self.fault or "Checkpoint not loaded" end
    local record = copyRecord(raw, self.scope)
    if not record then return false, "Invalid checkpoint record" end
    local records = self:Records()
    if #records >= 256 then return false, "Checkpoint capacity reached" end
    for _, current in ipairs(records) do
        if current.actionKey == record.actionKey then
            return false, "Action already unresolved"
        end
    end
    local usage = self.favorUsage
    local bossUsage = self.bossUsage
    local sabotageUsage = self.sabotageUsage
    local globalClaimUsage = self.globalClaimUsage
    local globalAttackUsage = self.globalAttackUsage
    local familyClaimUsage = self.familyClaimUsage
    local familyAttackUsage = self.familyAttackUsage
    local bossShopUsage = self.bossShopUsage
    if record.feature == "bossShop" then
        local intent = type(raw) == "table" and raw.intent
        local count = type(intent) == "table"
            and intent.attemptsBefore
        local limit = type(intent) == "table" and intent.maxSends
        local session = type(intent) == "table" and raw.session
        if type(intent) ~= "table" or intent.kind ~= "bossShopBuy"
            or not nonempty(session) or #session > 120
            or not integer(count, 0)
            or not integer(limit, 1) or limit > 20 then
            return false, "Invalid Boss Shop attempt"
        end
        local current = bossShopUsage
            and bossShopUsage.session == session
            and bossShopUsage.attempts or 0
        if count ~= current or current >= limit then
            return false, "Boss Shop send cap or proof changed"
        end
        bossShopUsage = { session = session,
            attempts = current + 1 }
    end
    if record.feature == "favors" then
        local intent = type(raw) == "table" and raw.intent
        local day = type(intent) == "table" and intent.serverDay
        local count = type(intent) == "table" and intent.usageAttemptsBefore
        if type(intent) ~= "table" or intent.kind ~= "favorHelp"
            or not integer(day, 0) or not integer(count, 0)
            or (usage and day < usage.day) then
            return false, "Invalid Favor attempt"
        end
        local current = usage and usage.day == day and usage.attempts or 0
        if count ~= current or current >= 5 then
            return false, "Favor attempt cap or proof changed"
        end
        usage = { day = day, attempts = current + 1 }
    end
    if record.feature == "sabotage" then
        local intent = type(raw) == "table" and raw.intent
        local day = type(intent) == "table" and intent.serverDay
        local count = type(intent) == "table" and intent.usageAttemptsBefore
        if type(intent) ~= "table" or intent.kind ~= "heistSabotage"
            or not integer(day, 0) or not integer(count, 0)
            or (sabotageUsage and day < sabotageUsage.day) then
            return false, "Invalid sabotage attempt"
        end
        local current = sabotageUsage and sabotageUsage.day == day
            and sabotageUsage.attempts or 0
        if count ~= current or current >= 5 then
            return false, "Sabotage attempt cap or proof changed"
        end
        sabotageUsage = { day = day, attempts = current + 1 }
    end
    if record.feature == "bosses" then
        local intent = type(raw) == "table" and raw.intent
        local day = type(intent) == "table" and intent.dayStamp
        local hits = type(intent) == "table" and intent.hitsBefore
        local spent = type(intent) == "table" and intent.staminaBefore
        local last = type(intent) == "table" and intent.lastServerNowBefore
        local now = type(intent) == "table" and intent.serverNow
        local cost = type(intent) == "table" and intent.expectedStaminaCost
        if type(intent) ~= "table" or intent.kind ~= "bossStageAttack"
            or not integer(day, 0) or not integer(hits, 0)
            or not integer(spent, 0) or not integer(last, 0)
            or not integer(now, 0) or not integer(cost, 1)
            or (bossUsage and day < bossUsage.day) then
            return false, "Invalid Boss attempt"
        end
        local current = bossUsage and bossUsage.day == day
            and bossUsage or { hits = 0, stamina = 0,
                lastServerNow = 0 }
        if hits ~= current.hits or spent ~= current.stamina
            or last ~= current.lastServerNow
            or current.hits >= 100
            or current.stamina + cost > 100
            or (current.hits > 0 and now < current.lastServerNow + 5) then
            return false, "Boss attempt cap or proof changed"
        end
        bossUsage = { day = day, hits = hits + 1,
            stamina = spent + cost, lastServerNow = now }
    end
    if record.feature == "globalBossClaim" then
        local intent = type(raw) == "table" and raw.intent
        local runKey = type(intent) == "table" and intent.runKey
        local count = type(intent) == "table" and intent.attemptsBefore
        if type(intent) ~= "table" or intent.kind ~= "globalBossClaim"
            or not nonempty(runKey) or #runKey > 120
            or not integer(count, 0) then
            return false, "Invalid Global Boss claim attempt"
        end
        local current = globalClaimUsage
            and globalClaimUsage.runKey == runKey
            and globalClaimUsage.attempts or 0
        if count ~= current or current >= 1 then
            return false, "Global Boss claim attempt cap or proof changed"
        end
        globalClaimUsage = { runKey = runKey, attempts = 1 }
    end
    if record.feature == "globalBossAttack" then
        local intent = type(raw) == "table" and raw.intent
        local runKey = type(intent) == "table" and intent.runKey
        local hits = type(intent) == "table" and intent.hitsBefore
        local last = type(intent) == "table" and intent.lastServerNowBefore
        local now = type(intent) == "table" and intent.serverNow
        if type(intent) ~= "table" or intent.kind ~= "globalBossAttack"
            or not nonempty(runKey) or #runKey > 120
            or not integer(hits, 0) or not integer(last, 0)
            or not integer(now, 0) then
            return false, "Invalid Global Boss attack attempt"
        end
        local current = globalAttackUsage
            and globalAttackUsage.runKey == runKey
            and globalAttackUsage or { hits = 0, lastServerNow = 0 }
        if hits ~= current.hits or last ~= current.lastServerNow
            or current.hits >= 25
            or (current.hits > 0
                and now < current.lastServerNow + 5) then
            return false, "Global Boss attack cap or proof changed"
        end
        globalAttackUsage = { runKey = runKey,
            hits = hits + 1, lastServerNow = now }
    end
    if record.feature == "familyBossClaims" then
        local intent = type(raw) == "table" and raw.intent
        local week = type(intent) == "table" and intent.week
        local stage = type(intent) == "table" and intent.stage
        local count = type(intent) == "table"
            and intent.attemptsBefore
        if type(intent) ~= "table"
            or intent.kind ~= "familyBossClaim"
            or not integer(week, 1)
            or not integer(intent.famId, 1)
            or not integer(stage, 0) or stage > 100
            or not integer(intent.expiresAt, 0)
            or not integer(count, 0)
            or not integer(intent.currentWeek, week) then
            return false, "Invalid Family claim attempt"
        end
        local usages, found = {}, false
        local current = {}
        for index, weekUsage in ipairs(familyClaimUsage or {}) do
            local stages = {}
            for stageIndex, value in ipairs(weekUsage.stages) do
                stages[stageIndex] = value
            end
            usages[index] = { week = weekUsage.week, stages = stages }
            if weekUsage.week == week then
                current = stages
                found = true
            end
        end
        if count ~= #current or #current >= 32 then
            return false, "Family claim attempt cap or proof changed"
        end
        for _, value in ipairs(current) do
            if value == stage then
                return false, "Family stage already attempted"
            end
        end
        current[#current + 1] = stage
        if not found then
            if #usages >= 64 then
                return false, "Family claim week ledger capacity reached"
            end
            usages[#usages + 1] = { week = week, stages = current }
        else
            for _, weekUsage in ipairs(usages) do
                if weekUsage.week == week then
                    weekUsage.stages = current
                end
            end
        end
        familyClaimUsage = usages
    end
    if record.feature == "familyBossAttacks" then
        local intent = type(raw) == "table" and raw.intent
        local week = type(intent) == "table" and intent.week
        local famId = type(intent) == "table" and intent.famId
        local hits = type(intent) == "table"
            and intent.hitsBefore
        local last = type(intent) == "table"
            and intent.lastServerNowBefore
        local now = type(intent) == "table"
            and intent.serverNow
        if type(intent) ~= "table"
            or intent.kind ~= "familyBossAttack"
            or not integer(week, 1)
            or not integer(famId, 1)
            or not integer(intent.stage, 1)
            or intent.stage > 5
            or not integer(hits, 0)
            or not integer(last, 0)
            or not integer(now, 0)
            or not integer(intent.expectedStaminaCost, 1)
            or (familyAttackUsage
                and (week < familyAttackUsage.week
                    or (week == familyAttackUsage.week
                        and famId ~= familyAttackUsage.famId))) then
            return false, "Invalid Family attack attempt"
        end
        local current = familyAttackUsage
            and familyAttackUsage.week == week
            and familyAttackUsage or {
                hits = 0, lastServerNow = 0 }
        if hits ~= current.hits
            or last ~= current.lastServerNow
            or hits >= 25
            or (hits > 0 and now < last + 5) then
            return false, "Family attack cap or proof changed"
        end
        familyAttackUsage = { week = week, famId = famId,
            hits = hits + 1, lastServerNow = now }
    end
    records[#records + 1] = record
    return self:Commit(records, usage, bossUsage,
        sabotageUsage, globalClaimUsage, globalAttackUsage,
        familyClaimUsage, familyAttackUsage, bossShopUsage)
end

function Methods:Resolve(actionKey)
    if not self.scope or self.fault then return false, self.fault or "Checkpoint not loaded" end
    local records, found = {}, false
    for _, record in ipairs(self.records) do
        if record.actionKey == actionKey then
            found = true
        else
            records[#records + 1] = copyRecord(record, self.scope)
        end
    end
    if not found then return false, "Action not in checkpoint" end
    return self:Commit(records, self.favorUsage,
        self.bossUsage, self.sabotageUsage,
        self.globalClaimUsage, self.globalAttackUsage,
        self.familyClaimUsage, self.familyAttackUsage,
        self.bossShopUsage)
end

return Checkpoint
