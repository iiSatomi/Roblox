-- Exact personal sabotage count and Favor debit prove a selected row.
local SabotageEvidence = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge and value % 1 == 0
end

local function timestamp(value)
    return type(value) == "number" and value == value
        and value >= 0 and value < math.huge
end

local function key(value)
    return type(value) == "string" and #value > 0
end

local function rowId(value)
    return key(value) or integer(value, 1)
end

local function copy(value, seen, depth)
    local kind = type(value)
    if kind == "number" then
        local numeric = tonumber(value)
        return numeric and numeric == numeric and math.abs(numeric) <= 9007199254740991 and numeric or nil
    end
    if kind == "string" or kind == "boolean" then return value end
    if kind ~= "table" or getmetatable(value) ~= nil or (depth or 0) > 12 then return nil end
    seen = seen or {}
    if seen[value] then return nil end
    seen[value] = true
    local result = {}
    for name, child in pairs(value) do
        if type(name) ~= "string" and not integer(name, 0) then return nil end
        local cloned = copy(child, seen, (depth or 0) + 1)
        if cloned == nil then return nil end
        result[name] = cloned
    end
    seen[value] = nil
    return result
end

local function same(a, b)
    if type(a) ~= type(b) then return false end
    if type(a) ~= "table" then return a == b end
    for name, value in pairs(a) do if not same(value, b[name]) then return false end end
    for name in pairs(b) do if a[name] == nil then return false end end
    return true
end

local function exposure(proposal)
    local intent, resources = proposal.intent, proposal.resources
    if type(resources) ~= "table" or resources.energy ~= intent.expectedEnergyCost
        or resources.favors ~= intent.expectedFavorCost then return false end
    for name, value in pairs(resources) do
        if name ~= "energy" and name ~= "favors" and value ~= 0 then return false end
    end
    return true
end

local function protocol(raw, intent, allocated)
    if intent.sequence == nil then
        return intent.nativeJob == nil and intent.nativeEpoch == nil and intent.nativeSourceKey == nil
    end
    local proof = raw.heistProtocolProof
    if not integer(intent.sequence, 1) or intent.sequence > 9007199254740991
        or not key(intent.nativeJob) or not key(intent.nativeEpoch)
        or type(intent.nativeSourceKey) ~= "string" or #intent.nativeSourceKey ~= 64
        or not intent.nativeSourceKey:match("^[%x]+$") or type(proof) ~= "table"
        or not integer(proof.controllerCounter, 0) or proof.controllerCounter > 9007199254740991 then return false end
    for _, name in ipairs({"session", "account", "place", "release", "revision", "capturedAt"}) do
        if proof[name] ~= raw[name] then return false end
    end
    for _, name in ipairs({"nativeJob", "nativeEpoch", "nativeSourceKey"}) do
        if proof[name] ~= intent[name] then return false end
    end
    if allocated then return proof.controllerCounter >= intent.sequence end
    local quote = proof.quote
    if proof.controllerCounter ~= intent.sequence - 1 or type(quote) ~= "table"
        or quote.sequence ~= intent.sequence then return false end
    for _, name in ipairs({"nativeJob", "nativeEpoch", "nativeSourceKey"}) do
        if quote[name] ~= intent[name] then return false end
    end
    return true
end

local function knownResources(native)
    local result = {}
    for _, name in ipairs({"cash", "xp", "level", "banked", "respect", "skillPoints",
        "paidMedals", "prestige", "maxLevel", "xpBoostEnd"}) do
        local value = native[name]
        if value ~= nil and not timestamp(value) then return nil end
        result[name] = value
    end
    for _, name in ipairs({"pools", "stats", "inventory", "inventoryBound", "collection", "collectionBound"}) do
        if native[name] ~= nil then
            if type(native[name]) ~= "table" then return nil end
            result[name] = copy(native[name])
            if result[name] == nil then return nil end
        end
    end
    return result
end

local function boardState(board)
    local state = {}
    for name, value in pairs(board) do
        if name ~= "rows" and name ~= "serverNow" then state[name] = value end
    end
    return copy(state)
end

local function resourceEffect(baseline, native, reply, confirmed)
    if type(baseline.nativeResources) ~= "table" or not knownResources(native) then return false end
    local expected = copy(baseline.nativeResources)
    if not expected or type(expected.pools) ~= "table" then return false end
    if confirmed then
        expected.pools.energy = expected.pools.energy - baseline.energyCost
        if expected.xp ~= nil then
            if not timestamp(reply.xp) then return false end
            expected.xp = expected.xp + reply.xp
        end
    end
    for name, value in pairs(expected) do
        if not same(value, native[name]) then return false end
    end
    return true
end

-- Source-owned thresholds establish XP/level transitions without assuming
-- level-up bonuses. Unknown changes to persistent stats or skill points stay held.
local function projectXP(native, gain, thresholds)
    if not integer(native.level, 1) or not timestamp(native.xp)
        or type(thresholds) ~= "table" or not integer(gain, 0)
        or native.xp + gain > 9007199254740991 then return nil end
    local level, xp, used = native.level, native.xp + gain, {}
    for crossing = 0, 128 do
        local needed = thresholds[level]
        if not integer(needed, 1) or needed > 9007199254740991
            or crossing == 0 and native.xp >= needed then return nil end
        used[level] = needed
        if xp < needed then return {level = level, xp = xp, thresholds = used} end
        xp, level = xp - needed, level + 1
    end
    return nil
end

local function regeneratedEffect(baseline, native, reply, observed)
    local original = baseline.nativeResources
    if type(original) ~= "table" or type(original.pools) ~= "table"
        or type(observed) ~= "table" or baseline.intent.sequence == nil
        or observed.controllerCounter ~= baseline.intent.sequence
        or reply.ok ~= true or reply.code == "busy" or not knownResources(native) then return false end
    -- This fallback needs complete item/origin custody, even when older exact
    -- offline evidence intentionally omitted optional inventory fields.
    for _, name in ipairs({"inventory", "inventoryBound", "collection", "collectionBound"}) do
        if type(original[name]) ~= "table" or type(native[name]) ~= "table"
            or not same(original[name], native[name]) then return false end
    end
    local cashAward = reply.cash
    if cashAward == nil then cashAward = 0 end -- Native reward renderer uses cash or zero.
    if not timestamp(original.cash) or not timestamp(native.cash) or not timestamp(cashAward)
        or original.cash + cashAward > 9007199254740991
        or native.cash < original.cash + cashAward then return false end
    local projection = projectXP(original, reply.xp, baseline.xpThresholds)
    if not projection or native.level ~= projection.level or native.xp ~= projection.xp
        or type(observed.xpThresholds) ~= "table"
        or observed.xpThresholds[projection.level] ~= projection.thresholds[projection.level]
        or original.maxLevel ~= nil and native.maxLevel ~= math.max(original.maxLevel, projection.level) then return false end
    for level, needed in pairs(projection.thresholds) do
        if observed.xpThresholds[level] ~= nil and observed.xpThresholds[level] ~= needed then return false end
    end
    for name, value in pairs(original.pools) do
        if name == "energy" or name == "health" or name == "stamina" then
            if not timestamp(value) or not timestamp(native.pools[name]) then return false end
            local minimum = value - (name == "energy" and baseline.energyCost or 0)
            if native.pools[name] < minimum then return false end
        elseif not same(value, native.pools[name]) then return false end
    end
    for name in pairs(native.pools) do if original.pools[name] == nil then return false end end
    for name, value in pairs(original) do
        if name ~= "cash" and name ~= "xp" and name ~= "level" and name ~= "maxLevel" and name ~= "pools"
            and not same(value, native[name]) then return false end
    end
    return true
end

local function matching(a, b, restart)
    for _, field in ipairs({ "session", "account", "place", "release" }) do
        if not key(a[field]) or not key(b[field])
            or (not restart or field ~= "session") and a[field] ~= b[field] then return false end
    end
    return true
end

local function used(row, countKey, legacyKey)
    if row[countKey] ~= nil then
        return integer(row[countKey], 0) and row[countKey] or nil
    end
    if row[legacyKey] == nil or row[legacyKey] == false then return 0 end
    if row[legacyKey] == true then return 1 end
    return nil
end

local function current(raw, id)
    local proof = type(raw) == "table" and raw.heistBoardProof
    local usage = type(raw) == "table" and raw.sabotageUsageProof
    local native = type(raw) == "table" and raw.native
    local player = type(raw) == "table" and raw.localUserIdProof
    local board = type(proof) == "table" and proof.board
    if type(proof) ~= "table" or type(usage) ~= "table"
        or type(native) ~= "table" or native.fullSync ~= true
        or not timestamp(native.serverNow) or not integer(native.level, 1)
        or type(native.pools) ~= "table" or not integer(native.pools.energy, 0)
        or not integer(raw.revision, 0) or not timestamp(raw.capturedAt)
        or proof.account ~= raw.account or proof.capturedAt ~= raw.capturedAt
        or usage.account ~= raw.account or usage.capturedAt ~= raw.capturedAt
        or type(player) ~= "table" or player.account ~= raw.account
        or player.capturedAt ~= raw.capturedAt or not integer(player.userId, 1)
        or proof.query ~= nil or type(board) ~= "table"
        or board.ok ~= true or type(board.rows) ~= "table"
        or not timestamp(board.serverNow) or math.abs(board.serverNow - native.serverNow) > 2
        or not integer(board.favorsLeft, 0) or not integer(usage.day, 0)
        or not integer(usage.attempts, 0)
        or usage.day ~= math.floor(board.serverNow / 86400) then return nil end
    local selected, seen, count = nil, {}, 0
    for index, row in ipairs(board.rows) do
        if type(row) ~= "table" or not rowId(row.id) or seen[row.id]
            or not key(row.heistId) or not integer(row.ownerId, 1)
            or not integer(row.endsAt, 0) then return nil end
        seen[row.id], count = true, index
        if row.id == id then selected = row end
    end
    for index in pairs(board.rows) do
        if not integer(index, 1) or index > count then return nil end
    end
    if selected then return board, selected, usage, player, native end
    return nil
end

function SabotageEvidence.capture(proposal, before)
    local intent = type(proposal) == "table" and proposal.intent
    if type(proposal) ~= "table" or proposal.feature ~= "sabotage"
        or type(intent) ~= "table" or intent.kind ~= "heistSabotage"
        or not rowId(intent.rowId) or not key(intent.heistId)
        or not integer(intent.ownerId, 1)
        or not integer(intent.selfId, 1)
        or not integer(intent.sabosBefore, 0)
        or not integer(intent.favorsBefore, 0)
        or not integer(intent.expectedFavorCost, 0)
        or not integer(intent.expectedEnergyCost, 0)
        or not integer(intent.serverDay, 0)
        or not integer(intent.usageAttemptsBefore, 0)
        or intent.needsSequence ~= true
        or type(before) ~= "table" or not matching(proposal, before)
        or proposal.revision ~= before.revision
        or not key(proposal.actionKey) or not exposure(proposal)
        or not protocol(before, intent, false) then
        return nil, "Sabotage baseline mismatch"
    end
    local board, row, usage, player, native =
        current(before, intent.rowId)
    if not board or row.heistId ~= intent.heistId
        or row.ownerId ~= intent.ownerId
        or player.userId ~= intent.selfId
        or row.ownerId == player.userId
        or row.friend == true or row.famRel == "family"
        or used(row, "helpsUsed", "helped") ~= 0
        or used(row, "sabosUsed", "sabotaged")
            ~= intent.sabosBefore
        or not integer(board.saboMaxPerHeist, 1)
        or intent.sabosBefore >= board.saboMaxPerHeist
        or board.favorsLeft ~= intent.favorsBefore
        or board.saboFavorCost ~= intent.expectedFavorCost
        or board.saboEnergyCost ~= intent.expectedEnergyCost
        or board.favorsLeft - board.saboFavorCost < 5
        or usage.day ~= intent.serverDay
        or usage.attempts ~= intent.usageAttemptsBefore
        or usage.attempts >= 5
        or not integer(row.endsAt, board.serverNow)
        or row.endsAt <= board.serverNow
        or not integer(native.level, 1)
        or type(native.pools) ~= "table"
        or not integer(native.pools.energy, 0)
        or native.pools.energy - board.saboEnergyCost < 10 then
        return nil, "Selected sabotage row or resources changed"
    end
    local eligibleLevel
    if type(before.heistCatalog) == "table" then
        for _, entry in ipairs(before.heistCatalog) do
            if type(entry) == "table"
                and entry.id == intent.heistId then
                eligibleLevel = entry.level
                break
            end
        end
    end
    if not integer(eligibleLevel, 1)
        or eligibleLevel > native.level then
        return nil, "Sabotage catalog changed"
    end
    local savedRow, savedBoard, nativeResources = copy(row), boardState(board), knownResources(native)
    if not savedRow or not savedBoard or not nativeResources then return nil, "Complete owned outcome baseline required" end
    return { session = proposal.session, account = proposal.account,
        place = proposal.place, release = proposal.release,
        revision = proposal.revision, rowId = intent.rowId,
        heistId = intent.heistId, ownerId = intent.ownerId,
        selfId = intent.selfId, sabosBefore = intent.sabosBefore,
        favorsBefore = intent.favorsBefore,
        favorCost = intent.expectedFavorCost,
        serverDay = intent.serverDay,
        usageAttemptsBefore = intent.usageAttemptsBefore,
        actionKey = proposal.actionKey, intent = copy(intent), resources = copy(proposal.resources),
        energyCost = intent.expectedEnergyCost,
        capturedAt = before.capturedAt, serverNow = board.serverNow, nativeServerNow = native.serverNow,
        row = savedRow, boardState = savedBoard, nativeResources = nativeResources,
        xpThresholds = intent.sequence ~= nil and copy(before.heistProtocolProof.xpThresholds) or nil }, nil
end

local function reconcile(proposal, beforeHeader, after, reply, baseline, restart)
    if type(proposal) ~= "table" or type(beforeHeader) ~= "table"
        or type(after) ~= "table" or type(reply) ~= "table" or type(baseline) ~= "table"
        or not matching(proposal, beforeHeader) or not matching(proposal, baseline)
        or not matching(proposal, after, restart) or not key(proposal.actionKey)
        or baseline.actionKey ~= proposal.actionKey or not same(proposal.intent, baseline.intent)
        or not same(proposal.resources, baseline.resources)
        or proposal.revision ~= baseline.revision or beforeHeader.revision ~= baseline.revision
        or type(baseline.row) ~= "table" or type(baseline.boardState) ~= "table"
        or not timestamp(baseline.serverNow) or not timestamp(baseline.nativeServerNow)
        or not timestamp(baseline.capturedAt) or not exposure(proposal)
        or not protocol(after, proposal.intent, true)
        or reply.pending == true or reply.code == "pending"
        or reply.code == "no_pending" or reply.code == "rate_limited"
        or reply.code == "presence"
        or proposal.intent.sequence ~= nil and reply.code == "busy" then return "pending" end
    local board, row, usage, player, native = current(after, baseline.rowId)
    if not board or usage.day ~= baseline.serverDay
        or usage.attempts ~= baseline.usageAttemptsBefore + 1
        or board.serverNow < baseline.serverNow or native.serverNow < baseline.nativeServerNow then return "pending" end
    local sameSession = after.session == baseline.session
    if sameSession then
        if after.revision <= baseline.revision or after.capturedAt < baseline.capturedAt then return "pending" end
    elseif not restart or board.serverNow <= baseline.serverNow
        or native.serverNow <= baseline.nativeServerNow then return "pending" end
    if player.userId ~= baseline.selfId then return "pending" end
    if reply.ok == false then
        local unchanged = same(row, baseline.row) and same(boardState(board), baseline.boardState)
            and resourceEffect(baseline, native, reply, false)
        return unchanged and "rejected" or "pending"
    end
    local expectedBoard = copy(baseline.boardState)
    expectedBoard.favorsLeft = baseline.favorsBefore - baseline.favorCost
    local advanced = row.heistId == baseline.heistId and row.ownerId == baseline.ownerId
        and used(row, "sabosUsed", "sabotaged") == baseline.sabosBefore + 1
        and used(row, "helpsUsed", "helped") == used(baseline.row, "helpsUsed", "helped")
        and row.endsAt == baseline.row.endsAt and row.friend == baseline.row.friend
        and row.famRel == baseline.row.famRel and same(boardState(board), expectedBoard)
    if (restart or proposal.intent.sequence ~= nil)
        and not resourceEffect(baseline, native, reply, true)
        and not regeneratedEffect(baseline, native, reply, after.heistProtocolProof) then return "pending" end
    if reply.ok == true and advanced then return "confirmed" end
    return "pending"
end

function SabotageEvidence.evaluate(proposal, beforeHeader, after, reply, baseline)
    return reconcile(proposal, beforeHeader, after, reply, baseline, false)
end

function SabotageEvidence.recoverSaved(data, after)
    if type(data) ~= "table" or type(data.baseline) ~= "table" or type(data.reply) ~= "table" then return nil end
    local expected = SabotageEvidence.capture(data.proposal, data.before)
    if not expected or not same(expected, data.baseline) then return nil end
    local result = reconcile(data.proposal, data.before, after, data.reply, expected, true)
    return (result == "confirmed" or result == "rejected") and result or nil
end

return SabotageEvidence
