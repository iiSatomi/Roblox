-- An unresolved-action ledger. Storage Read/Write must atomically persist decoded tables.
local Checkpoint = {}
local function familyId(value)
    return type(value) == "string" and #value > 0 and #value <= 120
        and not value:find("[%c]")
        or type(value) == "number" and value == value and value >= 1
            and value <= 9007199254740991 and value % 1 == 0
end
local Methods = {}
Methods.__index = Methods
local writers = {} -- Same loaded storage owner/scope cannot interleave commits.
local MAX = 9007199254740991
local function envelopeCopy(raw)
    local seen, nodes, bytes = {}, 0, 0
    local function walk(value, depth)
        nodes = nodes + 1
        if nodes > 800000 or depth > 40 then error("Checkpoint envelope exceeds limits") end
        local kind = type(value)
        if kind == "string" then bytes = bytes + #value
        elseif kind == "number" then
            if value ~= value or math.abs(value) > MAX then error("Invalid checkpoint number") end
        elseif kind ~= "table" and kind ~= "boolean" and kind ~= "nil" then error("Invalid checkpoint value") end
        if bytes > 2097152 then error("Checkpoint envelope too large") end
        if kind ~= "table" then return value end
        if seen[value] or getmetatable(value) ~= nil then error("Invalid checkpoint table") end
        seen[value] = true
        local result = {}
        for key, child in pairs(value) do
            if type(key) ~= "string" and type(key) ~= "number" then error("Invalid checkpoint key") end
            if type(key) == "number" and (key ~= key or math.abs(key) > MAX) then error("Invalid checkpoint key") end
            bytes = bytes + #tostring(key)
            result[key] = walk(child, depth + 1)
        end
        seen[value] = nil
        return result
    end
    local ok, value = pcall(walk, raw, 0)
    return ok and value or nil
end
local function sameEnvelope(a, b)
    if type(a) ~= type(b) then return false end
    if type(a) ~= "table" then return a == b end
    for key, value in pairs(a) do if not sameEnvelope(value, b[key]) then return false end end
    for key in pairs(b) do if a[key] == nil then return false end end
    return true
end

local function nonempty(value)
    return type(value) == "string" and #value > 0
end

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge and value % 1 == 0
end

local function timestamp(value)
    return type(value) == "number" and value == value
        and value >= 0 and value <= MAX
end

-- Preserve a run's allowance when public/private events alternate.
local function copyGlobalUsage(value, claim)
    if type(value) ~= "table" then return nil end
    local field, limit = claim and "attempts" or "hits", claim and 1 or 25
    local function row(raw)
        if type(raw) ~= "table" or not nonempty(raw.runKey) or #raw.runKey > 120
            or not integer(raw[field], 0) or raw[field] > limit
            or not claim and not timestamp(raw.lastServerNow) then return nil end
        return {runKey = raw.runKey, [field] = raw[field], lastServerNow = not claim and raw.lastServerNow or nil}
    end
    local result = row(value)
    if not result or value.history ~= nil and type(value.history) ~= "table" then return nil end
    result.history = {}
    local seen = {[result.runKey] = true}
    for index, raw in ipairs(value.history or {}) do
        local copied = row(raw)
        if index > 63 or not copied or seen[copied.runKey] then return nil end
        seen[copied.runKey], result.history[index] = true, copied
    end
    for index in pairs(value.history or {}) do
        if not integer(index, 1) or index > #result.history then return nil end
    end
    return result
end
local function globalUsageFor(value, runKey)
    if not value then return nil end
    if value.runKey == runKey then return value end
    for _, row in ipairs(value.history or {}) do if row.runKey == runKey then return row end end
    return nil
end
local function replaceGlobalUsage(value, row, claim)
    local result = {runKey = row.runKey, hits = row.hits, attempts = row.attempts,
        lastServerNow = row.lastServerNow, history = {}}
    local function keep(previous)
        if previous and previous.runKey ~= row.runKey then result.history[#result.history + 1] = previous end
    end
    keep(value)
    for _, previous in ipairs(value and value.history or {}) do keep(previous) end
    return copyGlobalUsage(result, claim)
end

local function unknownFight(records, feature)
    if feature ~= "combat" and feature ~= "warCombat" then return false end
    for _, record in ipairs(records) do
        if record.feature == feature and record.fightCharge == nil then return true end
    end
    return false
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

local function copyRecord(raw, scope, familyUsageModule, reservationModule, pendingModule, eventUsageModule, skipRecovery, rentUsageModule, hireUsageModule, fightUsageModule, chestUsageModule)
    if type(raw) ~= "table" or not nonempty(raw.feature)
        or not nonempty(raw.actionKey) or raw.account ~= scope.account
        or raw.place ~= scope.place or raw.release ~= scope.release then
        return nil
    end
    local resources = validResources(raw.resources)
    if not resources then return nil end
    local record = {
        account = scope.account, place = scope.place, release = scope.release,
        feature = raw.feature, actionKey = raw.actionKey, resources = resources,
    }
    if raw.requestId ~= nil then
        if not integer(raw.requestId, 1) or raw.requestId > MAX then return nil end
        record.requestId = raw.requestId
    end
    if raw.custody ~= nil then
        if not reservationModule then return nil end
        record.custody = reservationModule.CopyClaims(raw.custody)
        if not record.custody then return nil end
    end
    if raw.recovery ~= nil and not skipRecovery then
        if not pendingModule then return nil end
        record.recovery = pendingModule.Copy(raw.recovery, record)
        if not record.recovery then return nil end
    end
    if raw.familyCharge ~= nil then
        if not familyUsageModule then return nil end
        record.familyCharge = familyUsageModule.copyCharge(raw.familyCharge, raw.feature, resources)
        if not record.familyCharge then return nil end
    end
    if raw.eventCharge ~= nil then
        if not eventUsageModule then return nil end
        record.eventCharge = eventUsageModule.copyCharge(raw.eventCharge, raw.feature, resources)
        if not record.eventCharge then return nil end
    end
    if raw.chestCharge ~= nil then
        if not chestUsageModule then return nil end
        record.chestCharge = chestUsageModule.copyCharge(raw.chestCharge, raw.feature, resources)
        if not record.chestCharge then return nil end
        if record.recovery and not skipRecovery then
            local data = pendingModule.Decode(record.recovery, record)
            local intent = data and data.proposal.intent
            if not intent or intent.kind ~= "chests" then return nil end
            for _, key in ipairs({"itemId", "amount", "attemptedBefore", "spentBefore"}) do
                if intent[key] ~= record.chestCharge[key] then return nil end
            end
        end
    end
    if raw.rentCharge ~= nil then
        if not rentUsageModule then return nil end
        record.rentCharge = rentUsageModule.copyCharge(raw.rentCharge, raw.feature, resources)
        if not record.rentCharge then return nil end
    end
    if raw.hireCharge~=nil then
        if not hireUsageModule then return nil end
        record.hireCharge=hireUsageModule.copyCharge(raw.hireCharge,raw.feature,resources)
        if not record.hireCharge then return nil end
    end
    if raw.fightCharge ~= nil then
        if not fightUsageModule then return nil end
        record.fightCharge = fightUsageModule.copyCharge(raw.fightCharge, raw.feature, resources)
        local data = record.recovery and pendingModule and pendingModule.Decode(record.recovery, record)
        local intent = data and data.proposal.intent
        local charge = record.fightCharge
        if not charge then return nil end
        if not skipRecovery and (not intent
            or intent.kind ~= (charge.mode == "attack" and "playerAttack" or "playerScout")
            or intent.expectedStaminaCost ~= (charge.quoteCost or charge.cost)
            or (charge.quoteCost ~= nil and intent.maxStaminaExposure ~= charge.cost)
            or (charge.quoteCost == nil and intent.maxStaminaExposure ~= nil)
            or intent.attemptedBefore ~= charge.attemptedBefore or intent.spentBefore ~= charge.spentBefore) then return nil end
    end
    if raw.prestigeOrdinal ~= nil then
        if raw.feature ~= "prestige" or not integer(raw.prestigeOrdinal, 1) or raw.prestigeOrdinal > 6
            or next(resources) ~= nil then return nil end
        record.prestigeOrdinal = raw.prestigeOrdinal
        if not skipRecovery then
            local data = record.recovery and pendingModule and pendingModule.Decode(record.recovery, record)
            local intent = data and data.proposal.intent
            if not intent or intent.kind ~= "prestigeReset" or intent.allowReset ~= true
                or intent.attemptedBefore ~= record.prestigeOrdinal - 1 or not integer(intent.maxResets, record.prestigeOrdinal)
                or intent.maxResets > 6 then return nil end
        end
    end
    return record
end

local function scopeKey(account, place, release)
    return "idle-mafia-ember:checkpoint:v1:"
        .. #account .. ":" .. account .. #place .. ":" .. place
        .. #release .. ":" .. release
end

function Checkpoint.new(storage, familyUsageModule, reservationModule, pendingModule, eventUsageModule, rentUsageModule, hireUsageModule, fightUsageModule, chestUsageModule)
    assert(type(storage) == "table" and type(storage.Read) == "function"
        and type(storage.Write) == "function", "Missing checkpoint storage")
    -- A two-slot file store used for write-ahead actions must not revive an
    -- older generation when its newer slot is damaged.
    assert(storage.strictRecovery == true,
        "Checkpoint requires strict two-slot recovery")
    assert(familyUsageModule == nil or (type(familyUsageModule) == "table"
        and type(familyUsageModule.copy) == "function" and type(familyUsageModule.copyCharge) == "function"
        and type(familyUsageModule.charge) == "function" and type(familyUsageModule.holds) == "function"
        and type(familyUsageModule.rollback) == "function"), "Invalid Family budget module")
    assert(reservationModule == nil or (type(reservationModule) == "table"
        and type(reservationModule.CopyClaims) == "function"), "Invalid reservation module")
    assert(pendingModule == nil or (type(pendingModule) == "table" and type(pendingModule.Copy) == "function"
        and type(pendingModule.Capture) == "function" and type(pendingModule.Decode) == "function"
        and type(pendingModule.WithReply) == "function"), "Invalid pending action module")
    assert(eventUsageModule == nil or (type(eventUsageModule) == "table" and type(eventUsageModule.copy) == "function"
        and type(eventUsageModule.copyCharge) == "function" and type(eventUsageModule.charge) == "function"
        and type(eventUsageModule.holds) == "function" and type(eventUsageModule.rollback) == "function"), "Invalid Event Shop usage owner")
    assert(chestUsageModule == nil or type(chestUsageModule) == "table" and type(chestUsageModule.copy) == "function"
        and type(chestUsageModule.copyCharge) == "function" and type(chestUsageModule.charge) == "function"
        and type(chestUsageModule.holds) == "function" and type(chestUsageModule.rollback) == "function", "Invalid chest usage owner")
    assert(rentUsageModule == nil or (type(rentUsageModule) == "table" and type(rentUsageModule.copy) == "function"
        and type(rentUsageModule.copyCharge) == "function" and type(rentUsageModule.charge) == "function"
        and type(rentUsageModule.holds) == "function" and type(rentUsageModule.rollback) == "function"), "Invalid rental usage owner")
    assert(hireUsageModule==nil or type(hireUsageModule)=="table" and type(hireUsageModule.copy)=="function"
        and type(hireUsageModule.copyCharge)=="function" and type(hireUsageModule.charge)=="function"
        and type(hireUsageModule.holds)=="function" and type(hireUsageModule.rollback)=="function","Invalid hire usage owner")
    assert(fightUsageModule == nil or type(fightUsageModule) == "table" and type(fightUsageModule.copy) == "function"
        and type(fightUsageModule.copyCharge) == "function" and type(fightUsageModule.charge) == "function"
        and type(fightUsageModule.holds) == "function" and type(fightUsageModule.rollback) == "function"
        and type(fightUsageModule.summary) == "function" and type(fightUsageModule.reset) == "function", "Invalid player usage owner")
    return setmetatable({ storage = storage, scope = nil, key = nil,
        hireUsageModule=hireUsageModule,crewHireUsage=nil,
        fightUsageModule=fightUsageModule,playerFightUsage=nil,
        chestUsageModule = chestUsageModule, chestUsage = nil,
        rentUsageModule = rentUsageModule, marketRentUsage = nil,
        reservationModule = reservationModule,
        pendingModule = pendingModule,
        eventUsageModule = eventUsageModule, eventShopUsage = nil,
        familyUsageModule = familyUsageModule, familyContributionUsage = nil,
        records = {}, favorUsage = nil, sabotageUsage = nil,
        bossUsage = nil, globalClaimUsage = nil,
        globalAttackUsage = nil, familyClaimUsage = nil,
        familyAttackUsage = nil, bossShopUsage = nil,
        residencyAttempts = 0, stationAttempts = 0, prestigeAttempts = 0, requestHighwater = 0, fault = nil }, Methods)
end

function Methods:ScopeKey()
    return self.key
end

function Methods:Load(account, place, release)
    if self.writing then return nil, "Checkpoint write already in flight" end
    if not nonempty(account) or not nonempty(place) or not nonempty(release) then
        self.fault = "Invalid checkpoint scope"
        return nil, self.fault
    end
    self.scope = { account = account, place = place, release = release }
    self.key = scopeKey(account, place, release)
    if writers[self.key] then self.fault = "Checkpoint write already in flight"; return nil, self.fault end
    self.records = {}
    self.expectedEnvelope = nil
    self.requestHighwater = 0
    self.favorUsage = nil
    self.sabotageUsage = nil
    self.bossUsage = nil
    self.globalClaimUsage = nil
    self.globalAttackUsage = nil
    self.familyClaimUsage = nil
    self.familyAttackUsage = nil
    self.bossShopUsage = nil
    self.familyContributionUsage = self.familyUsageModule and self.familyUsageModule.copy(nil) or nil
    self.chestUsage = nil
    self.eventShopUsage = nil
    self.marketRentUsage = nil
    self.crewHireUsage=nil
    self.playerFightUsage=nil
    self.stationAttempts = 0
    self.prestigeAttempts = 0
    self.residencyAttempts = 0
    self.fault = nil
    local ok, data = pcall(self.storage.Read, self.storage, self.key)
    if not ok then self.fault = "Checkpoint read failed"; return nil, self.fault end
    if data == nil then return {}, nil end
    if type(data) ~= "table" or data.version ~= 1
        or type(data.records) ~= "table" or #data.records > 256 then
        self.fault = "Corrupt checkpoint"
        return nil, self.fault
    end
    local residencyAttempts = data.residencyAttempts
    if residencyAttempts == nil then residencyAttempts = 0 end
    if not integer(residencyAttempts, 0) or residencyAttempts > 1000 then
        self.fault = "Corrupt residency attempt count"; return nil, self.fault
    end
    local stationAttempts = data.stationAttempts
    if stationAttempts == nil then stationAttempts = 0 end
    if not integer(stationAttempts, 0) or stationAttempts > 1000 then
        self.fault = "Corrupt station attempt count"; return nil, self.fault
    end
    local prestigeAttempts = data.prestigeAttempts
    if prestigeAttempts == nil then prestigeAttempts = 0 end
    if not integer(prestigeAttempts, 0) or prestigeAttempts > 6 then
        self.fault = "Corrupt Prestige attempt count"; return nil, self.fault
    end
    local highwater = data.requestHighwater
    if highwater == nil then highwater = 0 end -- Legacy records are deliberately unnumbered.
    if not integer(highwater, 0) or highwater > MAX then
        self.fault = "Corrupt checkpoint request highwater"; return nil, self.fault
    end
    local records, seen, ids, prestigeOrdinals = {}, {}, {}, {}
    for index, raw in ipairs(data.records) do
        local record = copyRecord(raw, self.scope, self.familyUsageModule, self.reservationModule, self.pendingModule, self.eventUsageModule, nil, self.rentUsageModule,self.hireUsageModule,self.fightUsageModule,self.chestUsageModule)
        if not record or seen[record.actionKey]
            or record.prestigeOrdinal ~= nil and (record.prestigeOrdinal > prestigeAttempts or prestigeOrdinals[record.prestigeOrdinal])
            or (record.requestId ~= nil and (record.requestId > highwater or ids[record.requestId]))
            or (record.requestId ~= nil and (record.feature == "combat" or record.feature == "warCombat")
                and record.fightCharge == nil) then
            self.fault = "Corrupt checkpoint"
            return nil, self.fault
        end
        if record.feature == "chests" and record.recovery and not record.chestCharge then
            local data = self.pendingModule.Decode(record.recovery, record)
            if data and data.proposal.intent.attemptedBefore ~= nil then
                self.fault = "Missing chest allowance charge"; return nil, self.fault
            end
        end
        seen[record.actionKey] = true
        if record.requestId then ids[record.requestId] = true end
        if record.prestigeOrdinal then prestigeOrdinals[record.prestigeOrdinal] = true end
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
    local marketRentUsage
    if data.marketRentUsage ~= nil then
        marketRentUsage = self.rentUsageModule and self.rentUsageModule.copy(data.marketRentUsage)
        if not marketRentUsage then self.fault = "Missing or invalid rental usage owner"; return nil, self.fault end
    end
    for _, record in ipairs(records) do
        if record.rentCharge and not self.rentUsageModule.holds(marketRentUsage, record.rentCharge) then
            self.fault = "Missing rental allowance charge"; return nil, self.fault
        end
    end
    local crewHireUsage
    if data.crewHireUsage~=nil then
        crewHireUsage=self.hireUsageModule and self.hireUsageModule.copy(data.crewHireUsage)
        if not crewHireUsage then self.fault="Invalid hire usage owner";return nil,self.fault end
    end
    for _,record in ipairs(records) do
        if record.hireCharge and not self.hireUsageModule.holds(crewHireUsage,record.hireCharge) then
            self.fault="Missing hire allowance charge";return nil,self.fault
        end
    end
    local playerFightUsage
    if data.playerFightUsage ~= nil then
        playerFightUsage = self.fightUsageModule and self.fightUsageModule.copy(data.playerFightUsage)
        if not playerFightUsage then self.fault = "Missing or invalid player Stamina usage owner"; return nil, self.fault end
    end
    for _, record in ipairs(records) do
        if record.fightCharge and not self.fightUsageModule.holds(playerFightUsage, record.fightCharge) then
            self.fault = "Missing player Stamina allowance charge"; return nil, self.fault
        end
    end
    local chestUsage
    if data.chestUsageInitialized ~= nil and (data.chestUsageInitialized ~= true or data.chestUsage == nil) then
        self.fault = "Initialized chest usage is missing or invalid"; return nil, self.fault
    end
    if data.chestUsage ~= nil then
        chestUsage = self.chestUsageModule and self.chestUsageModule.copy(data.chestUsage)
        if not chestUsage then self.fault = "Missing or invalid chest usage owner"; return nil, self.fault end
    end
    for _, record in ipairs(records) do
        if record.feature == "chests" and not record.chestCharge then
            if not self.chestUsageModule then self.fault = "Legacy chest usage owner required"; return nil, self.fault end
            chestUsage = self.chestUsageModule.copy(chestUsage)
            if not chestUsage then self.fault = "Invalid legacy chest usage"; return nil, self.fault end
            chestUsage.unknown = true -- Exact settlement cannot establish the prior run total.
        end
        if record.chestCharge and not self.chestUsageModule.holds(chestUsage, record.chestCharge) then
            self.fault = "Chest charge missing from saved usage"; return nil, self.fault
        end
    end
    local eventShopUsage
    if data.eventShopUsage ~= nil then
        eventShopUsage = self.eventUsageModule and self.eventUsageModule.copy(data.eventShopUsage)
        if not eventShopUsage then self.fault = "Missing or invalid Event Shop usage owner"; return nil, self.fault end
    end
    for _, record in ipairs(records) do
        if record.eventCharge and not self.eventUsageModule.holds(eventShopUsage, record.eventCharge) then
            self.fault = "Event Shop charge missing from saved usage"; return nil, self.fault
        end
    end
    if data.familyContributionUsage ~= nil and not self.familyUsageModule then
        self.fault = "Family budget module required for saved usage"
        return nil, self.fault
    end
    local familyContributionUsage = self.familyUsageModule and self.familyUsageModule.copy(data.familyContributionUsage) or nil
    if self.familyUsageModule and not familyContributionUsage then
        self.fault = "Corrupt Family budget checkpoint"
        return nil, self.fault
    end
    for _, record in ipairs(records) do
        if record.familyCharge and not self.familyUsageModule.holds(familyContributionUsage, record.familyCharge) then
            self.fault = "Missing Family budget charge"
            return nil, self.fault
        end
    end
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
        or not timestamp(boss.lastServerNow)) then
        self.fault = "Corrupt checkpoint"
        return nil, self.fault
    end
    local claim = data.globalClaimUsage and copyGlobalUsage(data.globalClaimUsage, true)
    if data.globalClaimUsage ~= nil and not claim then
        self.fault = "Corrupt checkpoint"
        return nil, self.fault
    end
    local attack = data.globalAttackUsage and copyGlobalUsage(data.globalAttackUsage, false)
    if data.globalAttackUsage ~= nil and not attack then
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
        or not familyId(familyAttack.famId)
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
    self.stationAttempts = stationAttempts
    self.residencyAttempts = residencyAttempts
    self.prestigeAttempts = prestigeAttempts
    self.requestHighwater = highwater
    self.marketRentUsage = marketRentUsage
    self.crewHireUsage=crewHireUsage
    self.playerFightUsage=playerFightUsage
    self.chestUsage = chestUsage
    self.eventShopUsage = eventShopUsage
    self.familyContributionUsage = familyContributionUsage
    self.favorUsage = usage and { day = usage.day,
        attempts = usage.attempts } or nil
    self.sabotageUsage = sabotage and { day = sabotage.day,
        attempts = sabotage.attempts } or nil
    self.bossUsage = boss and { day = boss.day, hits = boss.hits,
        stamina = boss.stamina,
        lastServerNow = boss.lastServerNow } or nil
    self.globalClaimUsage = claim
    self.globalAttackUsage = attack
    self.familyClaimUsage = familyClaims
    self.familyAttackUsage = familyAttack and {
        week = familyAttack.week, famId = familyAttack.famId,
        hits = familyAttack.hits,
        lastServerNow = familyAttack.lastServerNow } or nil
    self.bossShopUsage = shop and {
        session = shop.session, attempts = shop.attempts } or nil
    self.expectedEnvelope = envelopeCopy(data)
    if not self.expectedEnvelope then self.fault = "Invalid checkpoint envelope"; return nil, self.fault end
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
    local current = globalUsageFor(self.globalClaimUsage, runKey)
    return { account = self.scope.account, runKey = runKey,
        attempts = current and current.attempts or 0,
        capturedAt = capturedAt }
end

function Methods:GlobalAttackUsage(runKey, capturedAt)
    if not self.scope or self.fault or not nonempty(runKey)
        or #runKey > 120
        or type(capturedAt) ~= "number" or capturedAt ~= capturedAt
        or capturedAt < 0 or capturedAt == math.huge then return nil end
    local current = globalUsageFor(self.globalAttackUsage, runKey)
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
        or not integer(week, 1) or not familyId(famId)
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

function Methods:Records(includeRecovery)
    local copy = {}
    for index, record in ipairs(self.records) do
        copy[index] = copyRecord(record, self.scope, self.familyUsageModule, self.reservationModule, self.pendingModule, self.eventUsageModule,
            includeRecovery ~= true, self.rentUsageModule,self.hireUsageModule,self.fightUsageModule,self.chestUsageModule)
    end
    return copy
end

function Methods:FamilyContributionUsage(snapshot)
    if self.fault or not self.scope or not self.familyUsageModule or self.familyContributionUsage == nil or type(snapshot) ~= "table"
        or not nonempty(snapshot.session) or not integer(snapshot.revision, 0)
        or type(snapshot.capturedAt) ~= "number" or snapshot.capturedAt ~= snapshot.capturedAt
        or snapshot.capturedAt < 0 or snapshot.capturedAt == math.huge then return nil, "Family budget owner unavailable" end
    for _, field in ipairs({"account", "place", "release"}) do
        if snapshot[field] ~= self.scope[field] then return nil, "Family budget scope changed" end
    end
    local usage = self.familyUsageModule.copy(self.familyContributionUsage)
    if not usage then return nil, "Family budget state unavailable" end
    local proof = {usage = usage.lanes}
    for _, field in ipairs({"session", "account", "place", "release", "revision", "capturedAt"}) do
        proof[field] = snapshot[field]
    end
    return proof, nil
end

function Methods:Commit(records, favorUsage, bossUsage,
    sabotageUsage, globalClaimUsage, globalAttackUsage,
    familyClaimUsage, familyAttackUsage, bossShopUsage, familyContributionUsage, eventShopUsage, requestHighwater, marketRentUsage, crewHireUsage, stationAttempts, residencyAttempts, playerFightUsage, prestigeAttempts, chestUsage)
    if self.fault then return false, self.fault end
    if not self.key then return false, "Checkpoint not loaded" end
    if writers[self.key] then return false, "Checkpoint write already in flight" end
    local writeKey = self.key
    local nextHighwater = requestHighwater or self.requestHighwater
    local nextResidencyAttempts = residencyAttempts or self.residencyAttempts
    local nextPrestigeAttempts = prestigeAttempts or self.prestigeAttempts
    local nextStationAttempts = stationAttempts or self.stationAttempts
    local nextHireUsage=crewHireUsage or self.crewHireUsage
    local nextFightUsage=playerFightUsage or self.playerFightUsage
    local nextChestUsage = chestUsage or self.chestUsage
    local nextRentUsage = marketRentUsage or self.marketRentUsage
    writers[writeKey], self.writing = self, writeKey
    local nextEnvelope = { chestUsageInitialized = nextChestUsage ~= nil and true or nil, chestUsage = nextChestUsage, prestigeAttempts = nextPrestigeAttempts, playerFightUsage = nextFightUsage, residencyAttempts = nextResidencyAttempts, stationAttempts = nextStationAttempts, crewHireUsage=nextHireUsage,version = 1, records = records, requestHighwater = nextHighwater, marketRentUsage = nextRentUsage,
            favorUsage = favorUsage, bossUsage = bossUsage,
            sabotageUsage = sabotageUsage,
            globalClaimUsage = globalClaimUsage,
            globalAttackUsage = globalAttackUsage,
            familyClaimUsage = { weeks = familyClaimUsage or {} },
            familyAttackUsage = familyAttackUsage,
            bossShopUsage = bossShopUsage, familyContributionUsage = familyContributionUsage, eventShopUsage = eventShopUsage }
    local expectedNext, attempted = envelopeCopy(nextEnvelope), false
    local ok, result = pcall(function()
        if not expectedNext then return false end
        local raw = self.storage:Read(writeKey)
        local current = raw ~= nil and envelopeCopy(raw) or nil
        if (raw ~= nil and current == nil) or not sameEnvelope(current, self.expectedEnvelope) then return false end
        attempted = true -- A rejected stale save cannot mint another owner's unsent fact.
        return self.storage:Write(writeKey, nextEnvelope)
    end)
    if writers[writeKey] == self then writers[writeKey] = nil end
    self.writing = nil
    if not ok or result == false then
        self.fault = "Checkpoint write failed"
        if requestHighwater and attempted then return false, self.fault, requestHighwater end
        return false, self.fault
    end
    self.records = records
    self.expectedEnvelope = expectedNext
    self.residencyAttempts = nextResidencyAttempts
    self.prestigeAttempts = nextPrestigeAttempts
    self.stationAttempts = nextStationAttempts
    self.requestHighwater = nextHighwater
    self.chestUsage = nextChestUsage
    self.marketRentUsage = nextRentUsage
    self.crewHireUsage=nextHireUsage
    self.playerFightUsage=nextFightUsage
    self.favorUsage = favorUsage
    self.sabotageUsage = sabotageUsage
    self.bossUsage = bossUsage
    self.globalClaimUsage = globalClaimUsage
    self.globalAttackUsage = globalAttackUsage
    self.familyClaimUsage = familyClaimUsage
    self.familyAttackUsage = familyAttackUsage
    self.bossShopUsage = bossShopUsage
    self.familyContributionUsage = familyContributionUsage
    self.eventShopUsage = eventShopUsage
    if requestHighwater then return true, nil, requestHighwater end
    return true, nil
end

function Methods:Recovery(actionKey)
    if self.fault or not self.pendingModule then return nil, "Recovery owner unavailable" end
    for _, record in ipairs(self.records) do
        if record.actionKey == actionKey then
            local data = record.recovery and self.pendingModule.Decode(record.recovery, record)
            return data, not data and "Legacy or invalid pending action has no full baseline" or nil
        end
    end
    return nil, "Action not in checkpoint"
end

function Methods:UnsentKey(requestId)
    if not self.key or not integer(requestId, 1) or requestId > MAX
        or type(self.storage.hash) ~= "function" then return nil end
    local ok, digest = pcall(self.storage.hash, self.key)
    if not ok or type(digest) ~= "string" or #digest ~= 64 or not digest:match("^[%x]+$") then return nil end
    return "idle-mafia-ember:adapter-unsent:v1:" .. digest:lower() .. ":" .. string.format("%.0f", requestId)
end

-- Only Broker's definite no-invocation paths append this fact. Even a stopped
-- owner may append it, but it never writes or clears the main checkpoint.
function Methods:RecordUnsent(proposal, before, baseline)
    local id = type(proposal) == "table" and proposal.checkpointRequestId
    local key = self:UnsentKey(id)
    if not key or not self.scope or not self.pendingModule or type(self.pendingModule.Same) ~= "function" then
        return false, "Numbered unsent evidence unavailable"
    end
    local request = {}
    for name, value in pairs(proposal) do request[name] = value end
    request.requestId = id
    local envelope, reason = self.pendingModule.Capture(request, before, baseline)
    local record = copyRecord(request, self.scope, self.familyUsageModule, self.reservationModule, nil, self.eventUsageModule, true, self.rentUsageModule,self.hireUsageModule,self.fightUsageModule,self.chestUsageModule)
    if not envelope or not record then return false, reason or "Unsent evidence scope changed" end
    local fact = {version = 1, account = self.scope.account, place = self.scope.place,
        release = self.scope.release, requestId = id, recovery = envelope}
    if writers[key] then return false, "Unsent evidence write already in flight" end
    writers[key] = self
    local ok, saved = pcall(function()
        -- Failed/ambiguous Save IDs may be reused only when no main record was
        -- committed. Never let a side fact make such a reusable ID authoritative.
        local main = self.storage:Read(self.key)
        if type(main) ~= "table" or main.version ~= 1 or type(main.records) ~= "table"
            or not integer(main.requestHighwater, id) or main.requestHighwater > MAX then return false end
        local committed = false
        for _, entry in ipairs(main.records) do
            if entry.requestId == id and entry.actionKey == record.actionKey and entry.feature == record.feature
                and self.pendingModule.Same(entry.recovery, envelope, record) then committed = true; break end
        end
        if not committed then return false end
        local old = self.storage:Read(key)
        if old ~= nil then
            return type(old) == "table" and old.version == 1 and old.requestId == id
                and old.account == fact.account and old.place == fact.place and old.release == fact.release
                and self.pendingModule.Same(old.recovery, envelope, record)
        end
        return self.storage:Write(key, fact) == true
    end)
    if writers[key] == self then writers[key] = nil end
    if not ok or saved ~= true then return false, "Unsent evidence save failed or conflicts" end
    return true, nil
end

function Methods:KnownUnsent(record)
    if self.fault or type(record) ~= "table" or not self.pendingModule
        or type(self.pendingModule.Same) ~= "function" then return false end
    local current
    for _, candidate in ipairs(self.records) do
        if candidate.actionKey == record.actionKey and candidate.requestId == record.requestId
            and candidate.feature == record.feature then current = candidate; break end
    end
    if not current then return false end
    local key = self:UnsentKey(current.requestId)
    local data = current.recovery and self.pendingModule.Decode(current.recovery, current)
    if not key or not data or data.reply ~= nil then return false end
    local ok, fact = pcall(self.storage.Read, self.storage, key)
    return ok and type(fact) == "table" and fact.version == 1
        and fact.account == current.account and fact.place == current.place and fact.release == current.release
        and fact.requestId == current.requestId and self.pendingModule.Same(fact.recovery, current.recovery, current)
end

function Methods:RecordReply(actionKey, reply)
    if self.fault or not self.pendingModule then return false, self.fault or "Recovery owner unavailable" end
    local records, found = self:Records(true), false
    for _, record in ipairs(records) do
        if record.actionKey == actionKey then
            local encoded, reason = self.pendingModule.WithReply(record.recovery, record, reply)
            if not encoded then return false, reason end
            record.recovery, found = encoded, true
        end
    end
    if not found then return false, "Action not in checkpoint" end
    return self:Commit(records, self.favorUsage, self.bossUsage, self.sabotageUsage,
        self.globalClaimUsage, self.globalAttackUsage, self.familyClaimUsage,
        self.familyAttackUsage, self.bossShopUsage, self.familyContributionUsage, self.eventShopUsage)
end

function Methods:Save(raw, before, baseline)
    if type(raw) == "table" then raw.checkpointRequestId = nil end
    if not self.scope or self.fault then return false, self.fault or "Checkpoint not loaded" end
    if self.writing or writers[self.key] then return false, "Checkpoint write already in flight" end
    if self.requestHighwater >= MAX then return false, "Checkpoint request identities exhausted" end
    local original, requestId = raw, self.requestHighwater + 1
    if type(raw) ~= "table" then return false, "Invalid checkpoint record" end
    local numbered = {}
    for key, value in pairs(raw) do numbered[key] = value end
    numbered.requestId = requestId -- Trusted local ID, never a caller-chosen native sequence.
    numbered.chestCharge = nil -- Only this checkpoint charges crate exposure.
    numbered.prestigeOrdinal = nil -- Only this checkpoint may assign a reset attempt.
    raw = numbered
    if self.pendingModule then
        local recovery, reason = self.pendingModule.Capture(raw, before, baseline)
        if not recovery then return false, reason end
        local request = {}
        for key, value in pairs(raw) do request[key] = value end
        request.recovery = recovery -- Never promote caller-provided recovery data.
        raw = request
    end
    local record = copyRecord(raw, self.scope, self.familyUsageModule, self.reservationModule, self.pendingModule, self.eventUsageModule, nil, self.rentUsageModule,self.hireUsageModule,self.fightUsageModule,self.chestUsageModule)
    if not record then return false, "Invalid checkpoint record" end
    local records = self:Records(true)
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
    local familyContributionUsage = self.familyContributionUsage
    local chestUsage = self.chestUsage
    local eventShopUsage = self.eventShopUsage
    local crewHireUsage=self.crewHireUsage
    local playerFightUsage=self.playerFightUsage
    local stationAttempts = self.stationAttempts
    local residencyAttempts = self.residencyAttempts
    local prestigeAttempts = self.prestigeAttempts
    local marketRentUsage = self.marketRentUsage
    if record.feature == "combat" or record.feature == "warCombat" then
        if unknownFight(self.records, record.feature) then return false, "Legacy player Stamina usage is unknown" end
        if not self.fightUsageModule then return false, "Player Stamina usage owner unavailable" end
        local usage, charge, why = self.fightUsageModule.charge(playerFightUsage, raw)
        if not usage then return false, why end
        playerFightUsage, record.fightCharge = usage, charge
    end
    if record.feature == "prestige" then
        for _, held in ipairs(self.records) do
            if held.feature == "prestige" and held.prestigeOrdinal == nil then return false, "Legacy Prestige usage is unknown" end
        end
        local intent = raw.intent
        if not record.recovery or not intent or intent.kind ~= "prestigeReset" or intent.allowReset ~= true
            or next(record.resources) ~= nil or intent.attemptedBefore ~= prestigeAttempts
            or not integer(intent.maxResets, 1) or intent.maxResets > 6 or prestigeAttempts >= intent.maxResets
            or not integer(intent.rankBefore, 0) or intent.rankBefore > 5 or intent.nextRank ~= intent.rankBefore + 1
            or not integer(intent.targetRank, intent.nextRank) or intent.targetRank > 6 then
            return false, "Prestige attempt cap, consent or proof changed"
        end
        prestigeAttempts = prestigeAttempts + 1
        record.prestigeOrdinal = prestigeAttempts
    end
    if record.feature == "residency" then
        local intent = raw.intent
        if not intent or intent.kind ~= "residencyRequest" or intent.attemptedBefore ~= residencyAttempts
            or not integer(intent.maxAttempts, 1) or intent.maxAttempts > 1000 or residencyAttempts >= intent.maxAttempts then
            return false, "Residency attempt cap or proof changed"
        end
        residencyAttempts = residencyAttempts + 1
    end
    if record.feature == "station" and raw.intent and raw.intent.kind == "territoryStation" then
        local intent = raw.intent
        if intent.attemptedBefore ~= stationAttempts or not integer(intent.maxAttempts, 1)
            or intent.maxAttempts > 1000 or stationAttempts >= intent.maxAttempts then
            return false, "Station attempt cap or proof changed"
        end
        stationAttempts = stationAttempts + 1
    end
    if record.feature=="crewHire" then
        if not self.hireUsageModule then return false,"Hire usage owner unavailable" end
        local usage,charge,why=self.hireUsageModule.charge(crewHireUsage,raw)
        if not usage then return false,why end
        crewHireUsage,record.hireCharge=usage,charge
    end
    if record.feature == "marketRent" then
        if not self.rentUsageModule then return false, "Rental usage owner unavailable" end
        local usage, charge, reason = self.rentUsageModule.charge(marketRentUsage, raw)
        if not usage then return false, reason end
        marketRentUsage, record.rentCharge = usage, charge
    end
    if record.feature == "chests" and (self.chestUsageModule or raw.intent and raw.intent.attemptedBefore ~= nil) then
        if not self.chestUsageModule then return false, "Chest usage owner unavailable" end
        local usage, charge, reason = self.chestUsageModule.charge(chestUsage, raw)
        if not usage then return false, reason end
        chestUsage, record.chestCharge = usage, charge
    end
    if record.feature == "eventShop" then
        if not self.eventUsageModule then return false, "Event Shop usage owner unavailable" end
        local usage, charge, reason = self.eventUsageModule.charge(eventShopUsage, raw)
        if not usage then return false, reason end
        eventShopUsage, record.eventCharge = usage, charge
    end
    if record.feature == "familyCash" or record.feature == "familyGold" or record.feature == "familyStamina" then
        if not self.familyUsageModule then return false, "Family budget owner unavailable" end
        local usage, charge, reason = self.familyUsageModule.charge(familyContributionUsage, raw)
        if not usage then return false, reason end
        familyContributionUsage, record.familyCharge = usage, charge
    end
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
            or not integer(spent, 0) or not timestamp(last)
            or not timestamp(now) or not integer(cost, 1)
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
        local counted = globalUsageFor(globalClaimUsage, runKey)
        local current = counted and counted.attempts or 0
        if count ~= current or current >= 1 then
            return false, "Global Boss claim attempt cap or proof changed"
        end
        globalClaimUsage = replaceGlobalUsage(globalClaimUsage, {runKey = runKey, attempts = 1}, true)
        if not globalClaimUsage then return false, "Global Boss claim ledger capacity reached" end
    end
    if record.feature == "globalBossAttack" then
        local intent = type(raw) == "table" and raw.intent
        local runKey = type(intent) == "table" and intent.runKey
        local hits = type(intent) == "table" and intent.hitsBefore
        local last = type(intent) == "table" and intent.lastServerNowBefore
        local now = type(intent) == "table" and intent.serverNow
        if type(intent) ~= "table" or intent.kind ~= "globalBossAttack"
            or not nonempty(runKey) or #runKey > 120
            or not integer(hits, 0) or not timestamp(last)
            or not timestamp(now) then
            return false, "Invalid Global Boss attack attempt"
        end
        local delay, cooldown, effective = intent.minimumDelay, intent.nativeAttackCooldown, intent.effectiveDelay
        if delay==nil and cooldown==nil and effective==nil then effective=5
        else
            local proof=type(before)=="table" and before.globalBossProof
            if not timestamp(delay) or delay<2 or delay>120 or not timestamp(effective) or effective<2 or effective>120
                or cooldown~=nil and (not timestamp(cooldown) or cooldown<=0 or cooldown>120)
                or delay<5 and cooldown==nil or effective~=math.max(delay,cooldown or 5)
                or type(proof)~="table" or proof.attackCooldown~=cooldown then
                return false,"Global Boss captured cooldown changed"
            end
        end
        local current = globalUsageFor(globalAttackUsage, runKey) or { hits = 0, lastServerNow = 0 }
        if hits ~= current.hits or last ~= current.lastServerNow
            or current.hits >= 25
            or (current.hits > 0
                and now < current.lastServerNow + effective) then
            return false, "Global Boss attack cap or proof changed"
        end
        globalAttackUsage = replaceGlobalUsage(globalAttackUsage, {runKey = runKey,
            hits = hits + 1, lastServerNow = now})
        if not globalAttackUsage then return false, "Global Boss run ledger capacity reached" end
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
            or not familyId(intent.famId)
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
            or not familyId(famId)
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
    local saved, reason, attemptedId = self:Commit(records, usage, bossUsage,
        sabotageUsage, globalClaimUsage, globalAttackUsage,
        familyClaimUsage, familyAttackUsage, bossShopUsage, familyContributionUsage, eventShopUsage, requestId, marketRentUsage,crewHireUsage,stationAttempts,residencyAttempts,playerFightUsage,prestigeAttempts,chestUsage)
    original.checkpointRequestId = attemptedId
    return saved, reason
end

function Methods:Resolve(actionKey, outcome)
    if not self.scope or self.fault then return false, self.fault or "Checkpoint not loaded" end
    local records, found = {}, false
    local bossUsage = self.bossUsage
    local bossShopUsage = self.bossShopUsage
    local familyClaimUsage = self.familyClaimUsage
    local globalAttackUsage = self.globalAttackUsage
    local globalClaimUsage = self.globalClaimUsage
    local familyContributionUsage = self.familyContributionUsage
    local chestUsage = self.chestUsage
    local eventShopUsage = self.eventShopUsage
    local crewHireUsage=self.crewHireUsage
    local playerFightUsage=self.playerFightUsage
    local stationAttempts = self.stationAttempts
    local residencyAttempts = self.residencyAttempts
    local prestigeAttempts = self.prestigeAttempts
    local marketRentUsage = self.marketRentUsage
    for _, record in ipairs(self.records) do
        if record.actionKey == actionKey then
            found = true
            if outcome == "schedule_failed" and record.feature == "globalBossClaim" and record.recovery then
                local data = self.pendingModule and self.pendingModule.Decode(record.recovery, record)
                local intent = data and data.proposal.intent
                if not intent or intent.kind ~= "globalBossClaim" or data.reply ~= nil
                    or intent.attemptsBefore ~= 0 or not globalClaimUsage
                    or globalClaimUsage.runKey ~= intent.runKey or globalClaimUsage.attempts ~= 1 then
                    return false, "Global Boss unsent claim changed"
                end
                globalClaimUsage = replaceGlobalUsage(globalClaimUsage, {runKey = intent.runKey, attempts = 0}, true)
                if not globalClaimUsage then return false, "Global Boss unsent claim history unavailable" end
            end
            if outcome == "schedule_failed" and record.feature == "globalBossAttack" and record.recovery then
                local data = self.pendingModule and self.pendingModule.Decode(record.recovery, record)
                local intent = data and data.proposal.intent
                if not intent or intent.kind ~= "globalBossAttack" or data.reply ~= nil
                    or not integer(intent.hitsBefore, 0) or not timestamp(intent.lastServerNowBefore)
                    or not globalAttackUsage or globalAttackUsage.runKey ~= intent.runKey
                    or globalAttackUsage.hits ~= intent.hitsBefore + 1
                    or globalAttackUsage.lastServerNow ~= intent.serverNow then
                    return false, "Global Boss unsent attempt changed"
                end
                globalAttackUsage = replaceGlobalUsage(globalAttackUsage, {runKey = intent.runKey, hits = intent.hitsBefore,
                    lastServerNow = intent.lastServerNowBefore})
                if not globalAttackUsage then return false, "Global Boss unsent history unavailable" end
            end
            if outcome == "schedule_failed" and record.feature == "familyBossClaims" and record.recovery then
                local data = self.pendingModule and self.pendingModule.Decode(record.recovery, record)
                local intent = data and data.proposal.intent
                if not intent or intent.kind ~= "familyBossClaim" or data.reply ~= nil
                    or not integer(intent.week, 1) or not integer(intent.stage, 0)
                    or not integer(intent.attemptsBefore, 0) then return false, "Family unsent claim unavailable" end
                local restored, exact = {}, false
                for _, counted in ipairs(familyClaimUsage or {}) do
                    local stages = {}
                    for index, stage in ipairs(counted.stages) do stages[index] = stage end
                    if counted.week == intent.week then
                        if #stages ~= intent.attemptsBefore + 1 or stages[#stages] ~= intent.stage then
                            return false, "Family unsent claim attempt changed"
                        end
                        stages[#stages], exact = nil, true
                    end
                    if #stages > 0 then restored[#restored + 1] = {week = counted.week, stages = stages} end
                end
                if not exact then return false, "Family unsent claim week missing" end
                familyClaimUsage = restored
            end
            if outcome == "schedule_failed" and record.feature == "bossShop" and record.recovery then
                local data = self.pendingModule and self.pendingModule.Decode(record.recovery, record)
                local intent = data and data.proposal.intent
                if not intent or intent.kind ~= "bossShopBuy" or data.reply ~= nil
                    or not integer(intent.attemptsBefore, 0) or not bossShopUsage
                    or bossShopUsage.session ~= data.proposal.session
                    or bossShopUsage.attempts ~= intent.attemptsBefore + 1 then
                    return false, "Boss Shop unsent attempt proof changed"
                end
                bossShopUsage = { session = data.proposal.session, attempts = intent.attemptsBefore }
            end
            if outcome == "schedule_failed" and record.feature == "bosses" and record.recovery then
                local data = self.pendingModule and self.pendingModule.Decode(record.recovery, record)
                local intent = data and data.proposal.intent
                if not intent or intent.kind ~= "bossStageAttack" or data.reply ~= nil
                    or not integer(intent.hitsBefore, 0) or not integer(intent.staminaBefore, 0)
                    or not integer(intent.expectedStaminaCost, 1) or not timestamp(intent.lastServerNowBefore)
                    or not bossUsage or bossUsage.day ~= intent.dayStamp
                    or bossUsage.hits ~= intent.hitsBefore + 1
                    or bossUsage.stamina ~= intent.staminaBefore + intent.expectedStaminaCost
                    or bossUsage.lastServerNow ~= intent.serverNow then
                    return false, "Boss unsent attempt proof changed"
                end
                bossUsage = { day = intent.dayStamp, hits = intent.hitsBefore,
                    stamina = intent.staminaBefore, lastServerNow = intent.lastServerNowBefore }
            end
            if outcome == "schedule_failed" and record.feature == "prestige" then
                local data = record.recovery and self.pendingModule and self.pendingModule.Decode(record.recovery, record)
                local intent = data and data.proposal.intent
                if not intent or intent.kind ~= "prestigeReset" or data.reply ~= nil
                    or record.prestigeOrdinal ~= prestigeAttempts or not integer(intent.attemptedBefore, 0)
                    or prestigeAttempts ~= intent.attemptedBefore + 1 then
                    return false, "Prestige unsent attempt proof changed"
                end
                prestigeAttempts = intent.attemptedBefore
            end
            if outcome == "schedule_failed" and record.feature == "residency" and record.recovery then
                local data = self.pendingModule and self.pendingModule.Decode(record.recovery, record)
                local intent = data and data.proposal.intent
                if not intent or intent.kind ~= "residencyRequest" or data.reply ~= nil
                    or not integer(intent.attemptedBefore, 0) or residencyAttempts ~= intent.attemptedBefore + 1 then
                    return false, "Residency unsent attempt proof changed"
                end
                residencyAttempts = intent.attemptedBefore
            end
            if outcome == "schedule_failed" and record.feature == "station" and record.recovery then
                local data = self.pendingModule and self.pendingModule.Decode(record.recovery, record)
                local intent = data and data.proposal.intent
                if not intent or intent.kind ~= "territoryStation" or data.reply ~= nil
                    or not integer(intent.attemptedBefore, 0) or stationAttempts ~= intent.attemptedBefore + 1 then
                    return false, "Station unsent attempt proof changed"
                end
                stationAttempts = intent.attemptedBefore
            end
            if outcome == "schedule_failed" and record.familyCharge then
                familyContributionUsage = self.familyUsageModule.rollback(familyContributionUsage, record.familyCharge)
                if not familyContributionUsage then return false, "Family unsent charge changed" end
            end
            if outcome == "schedule_failed" and record.chestCharge then
                chestUsage = self.chestUsageModule.rollback(chestUsage, record.chestCharge)
                if not chestUsage then return false, "Chest unsent charge changed" end
            end
            if outcome == "schedule_failed" and record.eventCharge then
                eventShopUsage = self.eventUsageModule.rollback(eventShopUsage, record.eventCharge)
                if not eventShopUsage then return false, "Event Shop unsent charge changed" end
            end
            if outcome=="schedule_failed" and record.hireCharge then
                crewHireUsage=self.hireUsageModule.rollback(crewHireUsage,record.hireCharge)
                if not crewHireUsage then return false,"Hire unsent allowance changed" end
            end
            if outcome == "schedule_failed" and record.fightCharge then
                local data = record.recovery and self.pendingModule
                    and self.pendingModule.Decode(record.recovery, record)
                if not data or data.reply ~= nil then
                    return false, "Player unsent attempt proof unavailable"
                end
                playerFightUsage = self.fightUsageModule.rollback(playerFightUsage, record.fightCharge)
                if not playerFightUsage then return false, "Player unsent Stamina allowance changed" end
            end
            if outcome == "schedule_failed" and record.rentCharge then
                marketRentUsage = self.rentUsageModule.rollback(marketRentUsage, record.rentCharge)
                if not marketRentUsage then return false, "Rental unsent charge changed" end
            end
        else
            records[#records + 1] = copyRecord(record, self.scope, self.familyUsageModule, self.reservationModule, self.pendingModule, self.eventUsageModule, nil, self.rentUsageModule,self.hireUsageModule,self.fightUsageModule,self.chestUsageModule)
        end
    end
    if not found then return false, "Action not in checkpoint" end
    return self:Commit(records, self.favorUsage,
        bossUsage, self.sabotageUsage,
        globalClaimUsage, globalAttackUsage,
        familyClaimUsage, self.familyAttackUsage,
        bossShopUsage, familyContributionUsage, eventShopUsage, nil, marketRentUsage,crewHireUsage,stationAttempts,residencyAttempts,playerFightUsage,prestigeAttempts,chestUsage)
end

function Methods:ResidencyUsage(snapshot)
    if self.fault or not self.scope or type(snapshot) ~= "table" then return nil end
    for _, field in ipairs({"account", "place", "release"}) do
        if snapshot[field] ~= self.scope[field] then return nil end
    end
    return self.residencyAttempts
end

function Methods:StationUsage(snapshot)
    if self.fault or not self.scope or type(snapshot) ~= "table" then return nil end
    for _, field in ipairs({"account", "place", "release"}) do
        if snapshot[field] ~= self.scope[field] then return nil end
    end
    return self.stationAttempts
end

function Methods:CrewHireUsage(snapshot)
    if self.fault or not self.scope or not self.hireUsageModule or type(snapshot)~="table" then return nil,"Hire usage unavailable" end
    for _,key in ipairs({"account","place","release"}) do if snapshot[key]~=self.scope[key] then return nil,"Hire usage scope changed" end end
    if not nonempty(snapshot.session) or not integer(snapshot.revision,0) or type(snapshot.capturedAt)~="number"
        or snapshot.capturedAt~=snapshot.capturedAt or snapshot.capturedAt<0 or snapshot.capturedAt==math.huge then return nil,"Hire snapshot unavailable" end
    for _,record in ipairs(self.records) do if record.feature=="crewHire" and not record.hireCharge then return nil,"Legacy hire needs review" end end
    local u=self.hireUsageModule.copy(self.crewHireUsage)
    if not u then return nil,"Hire usage invalid" end
    local proof={attempted=u.attempted,spent=u.spent}
    for _,key in ipairs({"session","account","place","release","revision","capturedAt"}) do proof[key]=snapshot[key] end
    return proof,nil
end

function Methods:MarketRentUsage(snapshot)
    if self.fault or not self.scope or not self.rentUsageModule or type(snapshot) ~= "table"
        or not nonempty(snapshot.session) or not integer(snapshot.revision, 0)
        or type(snapshot.capturedAt) ~= "number" or snapshot.capturedAt ~= snapshot.capturedAt
        or snapshot.capturedAt < 0 or snapshot.capturedAt == math.huge then return nil, "Rental usage unavailable" end
    for _, key in ipairs({"account", "place", "release"}) do if snapshot[key] ~= self.scope[key] then return nil, "Rental usage scope changed" end end
    local usage = self.rentUsageModule.copy(self.marketRentUsage)
    if not usage then return nil, "Rental usage invalid" end
    local proof = {attempted = usage.attempted, spent = usage.spent}
    for _, key in ipairs({"session", "account", "place", "release", "revision", "capturedAt"}) do proof[key] = snapshot[key] end
    return proof, nil
end

function Methods:ChestUsage(snapshot)
    if self.fault or not self.scope or not self.chestUsageModule or type(snapshot) ~= "table"
        or not nonempty(snapshot.session) or not integer(snapshot.revision, 0)
        or type(snapshot.capturedAt) ~= "number" or snapshot.capturedAt ~= snapshot.capturedAt
        or snapshot.capturedAt < 0 or snapshot.capturedAt == math.huge then return nil, "Chest usage unavailable" end
    for _, key in ipairs({"account", "place", "release"}) do if snapshot[key] ~= self.scope[key] then return nil, "Chest usage scope changed" end end
    for _, record in ipairs(self.records) do
        if record.feature == "chests" and not record.chestCharge then return nil, "Legacy chest usage is unknown" end
    end
    local usage = self.chestUsageModule.copy(self.chestUsage)
    if not usage then return nil, "Chest usage invalid" end
    if usage.unknown == true then return nil, "Previous chest use is unknown; pause and review its allowance" end
    local proof = {attempted = usage.attempted, spent = usage.spent}
    for _, key in ipairs({"session", "account", "place", "release", "revision", "capturedAt"}) do proof[key] = snapshot[key] end
    return proof, nil
end

function Methods:EventShopUsage(snapshot)
    if self.fault or not self.scope or not self.eventUsageModule or type(snapshot) ~= "table"
        or not nonempty(snapshot.session) or not integer(snapshot.revision, 0)
        or type(snapshot.capturedAt) ~= "number" or snapshot.capturedAt ~= snapshot.capturedAt
        or snapshot.capturedAt < 0 or snapshot.capturedAt == math.huge then return nil, "Event Shop usage unavailable" end
    for _, key in ipairs({"account", "place", "release"}) do if snapshot[key] ~= self.scope[key] then return nil, "Event Shop usage scope changed" end end
    local usage = self.eventUsageModule.copy(self.eventShopUsage)
    if not usage then return nil, "Event Shop usage invalid" end
    local proof = {attempted = usage.attempted, spent = usage.spent}
    for _, key in ipairs({"session", "account", "place", "release", "revision", "capturedAt"}) do proof[key] = snapshot[key] end
    return proof, nil
end

function Methods:PrestigeUsage(snapshot)
    if self.fault or not self.scope or type(snapshot) ~= "table" or not nonempty(snapshot.session)
        or not integer(snapshot.revision, 0) or not timestamp(snapshot.capturedAt)
        or not integer(self.prestigeAttempts, 0) or self.prestigeAttempts > 6 then return nil, "Prestige usage unavailable" end
    for _, key in ipairs({"account", "place", "release"}) do
        if snapshot[key] ~= self.scope[key] then return nil, "Prestige usage scope changed" end
    end
    for _, record in ipairs(self.records) do
        if record.feature == "prestige" and record.prestigeOrdinal == nil then return nil, "Legacy Prestige usage is unknown" end
    end
    local proof = {attempted = self.prestigeAttempts}
    for _, key in ipairs({"session", "account", "place", "release", "revision", "capturedAt"}) do proof[key] = snapshot[key] end
    return proof, nil
end

function Methods:PlayerFightUsage(snapshot)
    if self.fault or not self.scope or not self.fightUsageModule or type(snapshot) ~= "table" then
        return nil, "Player Stamina usage unavailable"
    end
    for _, key in ipairs({"account", "place", "release"}) do
        if snapshot[key] ~= self.scope[key] then return nil, "Player Stamina scope changed" end
    end
    local usage = self.fightUsageModule.copy(self.playerFightUsage)
    if not usage then return nil, "Player Stamina usage corrupt" end
    -- Legacy custody has no trustworthy attempt count; absence is not zero.
    for _, feature in ipairs({"combat", "warCombat"}) do
        if unknownFight(self.records, feature) then usage.lanes[feature] = nil end
    end
    return {account = snapshot.account, capturedAt = snapshot.capturedAt, usage = usage}, nil
end

function Methods:Allowance(feature)
    if self.fault or not self.scope then return nil, self.fault or "Allowance storage unavailable" end
    local row
    if feature == "residency" then
        row = {attempted = self.residencyAttempts, spent = 0}
    elseif feature == "station" then
        row = {attempted = self.stationAttempts, spent = 0}
    elseif (feature == "combat" or feature == "warCombat") and self.fightUsageModule then
        if unknownFight(self.records, feature) then return nil, "Legacy player Stamina usage is unknown" end
        row = self.fightUsageModule.summary(self.playerFightUsage, feature)
    elseif feature=="crewHire" and self.hireUsageModule then
        row=self.hireUsageModule.copy(self.crewHireUsage)
    elseif feature == "chests" and self.chestUsageModule then
        for _, record in ipairs(self.records) do
            if record.feature == "chests" and not record.chestCharge then return nil, "Legacy chest usage is unknown" end
        end
        row = self.chestUsageModule.copy(self.chestUsage)
    elseif feature == "eventShop" and self.eventUsageModule then
        row = self.eventUsageModule.copy(self.eventShopUsage)
    elseif feature == "marketRent" and self.rentUsageModule then
        row = self.rentUsageModule.copy(self.marketRentUsage)
    elseif (feature == "familyCash" or feature == "familyGold" or feature == "familyStamina") and self.familyUsageModule then
        local usage = self.familyUsageModule.copy(self.familyContributionUsage)
        row = usage and usage.lanes[feature]
    end
    if not row then return nil, "That allowance is unavailable in this runtime" end
    return {feature = feature, account = self.scope.account, place = self.scope.place, release = self.scope.release,
        unknown = row.unknown, attempted = row.attempted, spent = row.spent, attackAttempted = row.attackAttempted, attackSpent = row.attackSpent,
        scoutAttempted = row.scoutAttempted, scoutSpent = row.scoutSpent}, nil
end

function Methods:ResetAllowance(expected)
    if type(expected) ~= "table" or not self.scope or self.fault or self.writing or #self.records ~= 0 then
        return false, self.fault or "Pending actions or storage work prevent allowance reset"
    end
    local current, reason = self:Allowance(expected.feature)
    if not current then return false, reason end
    for _, key in ipairs({"account", "place", "release", "feature", "unknown", "attempted", "spent", "attackAttempted", "attackSpent", "scoutAttempted", "scoutSpent"}) do
        if expected[key] ~= current[key] then return false, "Allowance changed; preview it again" end
    end
    if current.unknown ~= true and current.attempted == 0 and current.spent == 0 then return true, "Allowance already clear" end
    local chest = self.chestUsage
    local hire=self.crewHireUsage
    local fight=self.playerFightUsage
    local station = self.stationAttempts
    local residency = self.residencyAttempts
    local family, event, rent = self.familyContributionUsage, self.eventShopUsage, self.marketRentUsage
    if expected.feature == "combat" or expected.feature == "warCombat" then
        fight = self.fightUsageModule.reset(fight, expected.feature)
        if not fight then return false, "Player Stamina allowance unavailable" end
    elseif expected.feature == "residency" then
        residency = 0
    elseif expected.feature == "station" then
        station = 0
    elseif expected.feature=="crewHire" then
        hire=self.hireUsageModule.copy(nil)
    elseif expected.feature == "chests" then
        chest = self.chestUsageModule.copy(nil)
    elseif expected.feature == "eventShop" then
        event = self.eventUsageModule.copy(nil)
    elseif expected.feature == "marketRent" then
        rent = self.rentUsageModule.copy(nil)
    else
        family = self.familyUsageModule.copy(family)
        if not family then return false, "Family allowance unavailable" end
        family.lanes[expected.feature] = {attempted = 0, spent = 0}
    end
    return self:Commit({}, self.favorUsage, self.bossUsage, self.sabotageUsage,
        self.globalClaimUsage, self.globalAttackUsage, self.familyClaimUsage,
        self.familyAttackUsage, self.bossShopUsage, family, event, nil, rent,hire,station,residency,fight,nil,chest)
end

return Checkpoint
