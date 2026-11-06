-- Data for reconciliation only. Never serializes a callback, capability or replay arm.
local PendingAction = {}
local MAX = 9007199254740991
local identity = {"session", "account", "place", "release"}
local function finite(value) return type(value) == "number" and value == value and math.abs(value) <= MAX end
local function text(value) return type(value) == "string" and #value > 0 and #value <= 1000 end
local function convert(value, decode, validateOnly)
    local seen, nodes, bytes = {}, 0, 0
    local function walk(child, depth)
        nodes = nodes + 1
        if nodes > 24000 or depth > 12 then error("Recovery data exceeds node/depth limit") end
        local kind = type(child)
        if kind == "string" then
            bytes = bytes + #child
            if #child > 16384 then error("Recovery string too large") end
        elseif kind == "number" then
            if not finite(child) then error("Recovery number invalid") end
            bytes = bytes + #tostring(child)
        elseif kind ~= "boolean" and kind ~= "table" then error("Recovery value invalid") end
        if not validateOnly and bytes > 262144 then error("Recovery data exceeds byte limit") end
        if kind ~= "table" then return child end
        if seen[child] or getmetatable(child) ~= nil then error("Recovery table invalid") end
        seen[child] = true
        local source, output = child, nil
        if not validateOnly then output = {} end
        if decode then
            if type(child.entries) ~= "table" then error("Recovery encoding invalid") end
            for field in pairs(child) do if field ~= "entries" then error("Unknown recovery encoding field") end end
            source = child.entries
        end
        for key, entry in pairs(source) do
            local encoded, restored
            if decode then
                if type(key) ~= "string" or #key > 1002 then error("Invalid encoded recovery key") end
                local prefix, raw = key:sub(1, 2), key:sub(3)
                if prefix == "s:" then restored = raw
                elseif prefix == "n:" then
                    restored = tonumber(raw)
                    if not finite(restored) or restored % 1 ~= 0 or tostring(restored) ~= raw then error("Invalid numeric recovery key") end
                else error("Unknown recovery key kind") end
                encoded = key
            elseif type(key) == "string" and #key <= 1000 then encoded = "s:" .. key
            elseif finite(key) and key % 1 == 0 then encoded = "n:" .. tostring(key)
            else error("Recovery key invalid") end
            bytes = bytes + #encoded + 16 -- Includes conservative JSON wrapper overhead.
            if not validateOnly and bytes > 262144 then error("Recovery data exceeds byte limit") end
            local copied = walk(entry, depth + 1)
            if not validateOnly then output[decode and restored or encoded] = copied end
        end
        seen[child] = nil
        if validateOnly then return true end
        return decode and output or {entries = output}
    end
    local ok, result = pcall(walk, value, 0)
    return ok and result or nil
end
local function valid(data, record)
    if type(data) ~= "table" or type(data.proposal) ~= "table" or type(data.before) ~= "table"
        or type(data.baseline) ~= "table" then return false end
    for key in pairs(data) do if key ~= "proposal" and key ~= "before" and key ~= "baseline" and key ~= "reply" then return false end end
    if data.reply ~= nil and type(data.reply) ~= "table" then return false end
    local proposal, before = data.proposal, data.before
    if proposal.requestId ~= nil and (not finite(proposal.requestId)
        or proposal.requestId < 1 or proposal.requestId % 1 ~= 0) then return false end
    for _, key in ipairs(identity) do
        if not text(proposal[key]) or proposal[key] ~= before[key] then return false end
    end
    if not finite(proposal.revision) or proposal.revision < 0 or proposal.revision % 1 ~= 0
        or proposal.revision ~= before.revision or not finite(before.capturedAt) or before.capturedAt < 0
        or type(before.native) ~= "table" or before.native.fullSync ~= true
        or not text(proposal.feature) or not text(proposal.actionKey)
        or type(proposal.intent) ~= "table" or not text(proposal.intent.kind)
        or type(proposal.resources) ~= "table" then return false end
    for key, value in pairs(proposal.intent) do
        if not text(key) or (type(value) ~= "string" and type(value) ~= "boolean" and not finite(value)) then return false end
    end
    for key, amount in pairs(proposal.resources) do if not text(key) or not finite(amount) or amount < 0 then return false end end
    if record then
        if proposal.requestId ~= record.requestId then return false end
        for _, key in ipairs({"account", "place", "release", "feature", "actionKey"}) do
            if proposal[key] ~= record[key] then return false end
        end
        if type(record.resources) ~= "table" then return false end
        for key, amount in pairs(proposal.resources) do if record.resources[key] ~= amount then return false end end
        for key, amount in pairs(record.resources) do if proposal.resources[key] ~= amount then return false end end
    end
    return true
end
-- Explicit capture dependencies; unknown feature contracts retain the full snapshot.
local recoveryFields = {
    jobs = {catalogKey = true, jobCatalog = true, masteryRules = true},
    heists = {catalogKey = true, heistCatalog = true, heistBoardProof = true},
    heistCollect = {catalogKey = true, heistCatalog = true, heistBoardProof = true, heistControllerProof = true},
    favors = {catalogKey = true, heistCatalog = true, heistBoardProof = true, favorUsageProof = true},
    sabotage = {catalogKey = true, heistCatalog = true, heistBoardProof = true,
        sabotageUsageProof = true, localUserIdProof = true},
    combat = {hitListProof = true, playerFightProof = true, playerFightUsageProof = true, playerFightHistoryProof = true},
    warCombat = {warRosterProof = true, playerFightProof = true, playerFightUsageProof = true},
    bosses = {bossStageProof = true, bossUsageProof = true},
    bossShop = {bossShopProof = true, bossShopUsageProof = true},
    globalBossAttack = {globalBossProof = true, localUserIdProof = true, globalAttackUsageProof = true},
    globalBossClaim = {globalBossProof = true, localUserIdProof = true, globalClaimUsageProof = true},
    familyBossAttacks = {familyTakedownProof = true, familyAttackProof = true, familyAttackUsageProof = true},
    familyBossClaims = {familyTakedownProof = true, familyClaimUsageProof = true, familyClaimUsageProofs = true},
    operations = {catalogKey = true, operationCatalog = true},
    collect = {catalogKey = true, operationCatalog = true},
    playtime = {catalogKey = true, ladderCatalog = true, ladderTiers = true, weekendBuff = true},
    monthlyRewards = {catalogKey = true, monthlyConfig = true},
    groupBonus = {catalogKey = true, groupConfig = true, groupMembership = true},
    bank = {bankConfig = true, purchaseSavings = true},
    withdraw = {fundingRequest = true},
    safehouse = {catalogKey = true, safehouseCatalog = true},
    properties = {catalogKey = true, propertyCatalog = true, propertyProof = true},
    shop = {catalogKey = true, shopCatalog = true, shopQuoteProof = true},
    contracts = {catalogKey = true, contractConfig = true},
    bonuses = {catalogKey = true, contractConfig = true, contractBonusConfig = true},
    trophies = {catalogKey = true, trophyCatalog = true},
    briefcases = {catalogKey = true, caseEvent = true, briefcaseRules = true},
    skills = {catalogKey = true, skillRules = true},
    marketSell = {}, marketFlip = {}, marketManage = {},
    marketRent = {marketRentTermsProof = true, marketRentUsageProof = true},
    station = {territoryMap = true, territoryDistrict = true, stationCatalogProof = true, stationReservationProof = true},
    residency = {residencyView = true, residencyUsageProof = true},
    familyCash = {familyContributionCatalog = true, familyContributionProof = true, familyActorProof = true, familyUsageProof = true},
    familyStamina = {familyContributionCatalog = true, familyContributionProof = true, familyActorProof = true, familyUsageProof = true},
    familyGold = {familyContributionCatalog = true, familyContributionProof = true, familyActorProof = true, familyUsageProof = true},
    eventShop = {eventShopProof = true, eventShopUsageProof = true},
    crewRoll = {crewReplacementSourceKey = true, economyProof = true,
        crewReplacementUsageProof = true, crewReplacementOwnerProof = true},
    crew = {}, crewGear = {}, crewSort = {}, cosmetics = {},
    crewHeal = {healRules = true},
    crewTrain = {trainingCatalog = true},
    crewHealItems = {healItemCatalog = true},
    chests = {ownedCrateCatalog = true, crateLuckProof = true},
    restoratives = {restorativeCatalog = true},
    collectionDonate = {collectionCatalog = true, collectionProtection = true},
    prestige = {catalogKey = true, prestigeCatalog = true, prestigeUsageProof = true},
    crewHire = {catalogKey = true, contractTemplates = true, hireCatalog = true,
        economyProof = true, crewHireUsageProof = true},
}
local commonRecoveryFields = {session = true, account = true, place = true,
    release = true, revision = true, capturedAt = true, fullSync = true, native = true}

local function sameNative(first, second)
    local seenFirst, seenSecond, nodes = {}, {}, 0
    local function compare(a, b, depth)
        nodes = nodes + 1
        if nodes > 24000 or depth > 12 or type(a) ~= type(b) then return false end
        local kind = type(a)
        if kind ~= "table" then
            return (kind == "string" or kind == "boolean" or kind == "number" and finite(a)) and a == b
        end
        if getmetatable(a) ~= nil or getmetatable(b) ~= nil then return false end
        if rawequal(a, b) then return true end -- The retained native copy is still validated by convert.
        if seenFirst[a] or seenSecond[b] then return false end
        seenFirst[a], seenSecond[b] = true, true
        for key, value in pairs(a) do
            if not compare(value, b[key], depth + 1) then return false end
        end
        for key in pairs(b) do if a[key] == nil then return false end end
        seenFirst[a], seenSecond[b] = nil, nil
        return true
    end
    return type(first) == "table" and type(second) == "table" and compare(first, second, 0)
end
local function selectedStationCatalog(proposal, before)
    local intent, catalog = proposal.intent, before.stationCatalogProof
    local source = before.territoryDistrict
    local district = type(source) == "table" and source.district
    if proposal.feature ~= "station" or type(intent) ~= "table"
        or (intent.kind ~= "territoryStation" and intent.kind ~= "territoryRecall")
        or type(intent.districtId) ~= "string" or #intent.districtId == 0 or #intent.districtId > 120
        or type(district) ~= "table" or district.id ~= intent.districtId
        or type(catalog) ~= "table" or type(catalog.cities) ~= "table" or type(catalog.caps) ~= "table"
        or type(catalog.cities[intent.districtId]) ~= "string" then return catalog end
    -- Stationing.read/capture consult only this exact district's city/cap.
    -- Keep the source identity and full current district/map/reservation proofs.
    local saved = {}
    for key, value in pairs(catalog) do if key ~= "cities" and key ~= "caps" then saved[key] = value end end
    saved.cities = {[intent.districtId] = catalog.cities[intent.districtId]}
    saved.caps = {[intent.districtId] = catalog.caps[intent.districtId]}
    return saved
end
local function recoveryBefore(proposal, before)
    -- NativeSnapshotReader exposes one Sync through both names. Store its full
    -- native evidence once; decoded historical copies may have lost the alias.
    if type(before) == "table" and getmetatable(before) == nil and before.data ~= nil then
        if not sameNative(before.data, before.native) then return nil, "Duplicate native recovery data differs" end
        local saved = {}
        for key, value in pairs(before) do if key ~= "data" then saved[key] = value end end
        before = saved
    end
    local fields = recoveryFields[proposal.feature]
    if fields and type(before) == "table" and getmetatable(before) == nil then
        -- Projection may discard selection data, never a malformed graph. The
        -- retained action payload still obeys the original byte limit below.
        if not convert(before, false, true) then return nil, "Recovery snapshot graph invalid" end
        local saved = {}
        for key, value in pairs(before) do
            if commonRecoveryFields[key] or fields[key] then saved[key] = value end
        end
        before = saved
        if proposal.feature == "station" then before.stationCatalogProof = selectedStationCatalog(proposal, before) end
    end
    -- Target catalogs are selection data, not durable outcome evidence. Keep only
    -- this action's high-only membership; current full history stays in the live owner.
    local ledger = type(before) == "table" and before.playerFightHistoryProof
    if type(ledger) ~= "table" or ledger.highValue == nil or getmetatable(before) ~= nil or getmetatable(ledger) ~= nil then return before end
    local saved, history = {}, {}
    for key, value in pairs(before) do saved[key] = value end
    for key, value in pairs(ledger) do if key ~= "highValue" then history[key] = value end end
    saved.playerFightHistoryProof = history
    local intent, high = proposal.intent, ledger.highValue
    if proposal.feature == "combat" and type(intent) == "table" and intent.highValueOnly == true
        and (intent.kind == "playerAttack" or intent.kind == "playerScout")
        and finite(intent.target) and intent.target >= 1 and intent.target % 1 == 0 then
        local targets = type(high) == "table" and high.targets
        local target = type(targets) == "table" and targets[tostring(intent.target)]
        history.highValue = {known = type(high) == "table" and high.known == true, targets = {}}
        if type(target) == "table" then history.highValue.targets[tostring(intent.target)] = {userId = target.userId} end
    end
    return saved
end
function PendingAction.Capture(proposal, before, baseline, reply)
    if type(proposal) ~= "table" then return nil, "Recovery proposal required" end
    local request = {}
    for _, key in ipairs({"session", "account", "place", "release", "revision", "feature", "actionKey", "resources", "intent", "requestId"}) do
        request[key] = proposal[key]
    end
    local savedBefore, reason = recoveryBefore(request, before)
    if savedBefore == nil then return nil, reason or "Complete recovery intent and baseline required" end
    local data = {proposal = request, before = savedBefore, baseline = baseline, reply = reply}
    if not valid(data) then return nil, "Complete recovery intent and baseline required" end
    local encoded = convert(data, false)
    if not encoded then return nil, "Recovery data invalid or exceeds bounded storage" end
    return {version = 1, payload = encoded}, nil
end
function PendingAction.Decode(raw, record)
    if type(raw) ~= "table" or raw.version ~= 1 then return nil end
    for key in pairs(raw) do if key ~= "version" and key ~= "payload" then return nil end end
    local data = convert(raw.payload, true)
    if not data or not valid(data, record) then return nil end
    return data
end
function PendingAction.Copy(raw, record)
    local data = PendingAction.Decode(raw, record)
    if not data then return nil end
    return PendingAction.Capture(data.proposal, data.before, data.baseline, data.reply)
end
local function equal(a, b)
    if type(a) ~= type(b) then return false end
    if type(a) ~= "table" then return a == b end
    for key, value in pairs(a) do if not equal(value, b[key]) then return false end end
    for key in pairs(b) do if a[key] == nil then return false end end
    return true
end
function PendingAction.WithReply(raw, record, reply)
    local data = PendingAction.Decode(raw, record)
    if not data or type(reply) ~= "table" then return nil, "Original pending data and table result required" end
    -- Validate/copy before comparison so cycles and capabilities cannot enter it.
    local encoded, reason = PendingAction.Capture(data.proposal, data.before, data.baseline, reply)
    if not encoded then return nil, reason end
    local candidate = PendingAction.Decode(encoded, record)
    if not candidate then return nil, "Returned result could not be decoded" end
    if data.reply ~= nil and not equal(data.reply, candidate.reply) then return nil, "A different result is already recorded" end
    return encoded, nil
end
function PendingAction.Same(first, second, record)
    local a, b = PendingAction.Decode(first, record), PendingAction.Decode(second, record)
    return a ~= nil and b ~= nil and equal(a, b)
end
return PendingAction
