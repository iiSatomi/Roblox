-- Only exact reply run identity plus newer board can confirm a start.
local HeistStartEvidence = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge and value % 1 == 0
end

local function balance(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge
end

local function key(value)
    return type(value) == "string" and #value > 0
end

local function matching(a, b, restart)
    for _, field in ipairs({ "session", "account", "place", "release" }) do
        if not key(a[field]) or not key(b[field]) or (not restart or field ~= "session") and a[field] ~= b[field] then return false end
    end
    return true
end

local function board(raw)
    local proof = type(raw) == "table" and raw.heistBoardProof
    local native = type(raw) == "table" and raw.native
    if type(proof) ~= "table" or type(proof.board) ~= "table"
        or type(native) ~= "table" or native.fullSync ~= true
        or proof.account ~= raw.account
        or proof.capturedAt ~= raw.capturedAt
        or proof.query ~= nil or proof.board.ok ~= true then
        return nil
    end
    return proof.board
end

local function equal(a, b)
    if type(a) ~= type(b) then return false end
    if type(a) ~= "table" then return a == b end
    for k, v in pairs(a) do if not equal(v, b[k]) then return false end end
    for k in pairs(b) do if a[k] == nil then return false end end
    return true
end
local function protocol(raw, intent, sent)
    if intent.sequence == nil then return true end
    local proof = raw.heistProtocolProof
    if not integer(intent.sequence, 1) or type(proof) ~= "table" then return false end
    for _, field in ipairs({"session", "account", "place", "release", "revision", "capturedAt"}) do
        if proof[field] ~= raw[field] then return false end
    end
    for _, field in ipairs({"nativeJob", "nativeEpoch", "nativeSourceKey"}) do
        if not key(intent[field]) or proof[field] ~= intent[field] then return false end
    end
    if not integer(proof.controllerCounter, 0) then return false end
    if sent then return proof.controllerCounter >= intent.sequence end
    local quote = proof.quote
    if proof.controllerCounter ~= intent.sequence - 1 or type(quote) ~= "table" or quote.sequence ~= intent.sequence then return false end
    for _, field in ipairs({"nativeJob", "nativeEpoch", "nativeSourceKey"}) do if quote[field] ~= intent[field] then return false end end
    return true
end

function HeistStartEvidence.capture(proposal, before)
    local intent = type(proposal) == "table" and proposal.intent
    if type(proposal) ~= "table" or proposal.feature ~= "heists"
        or type(intent) ~= "table" or intent.kind ~= "heistStart"
        or not key(intent.heistId)
        or not integer(intent.expectedStake, 0)
        or not integer(intent.expectedEnergy, 0)
        or not integer(intent.startsBefore, 1)
        or not integer(intent.serverDay, 0)
        or not key(intent.catalogKey)
        or intent.needsSequence ~= true
        or type(before) ~= "table" or not matching(proposal, before)
        or proposal.revision ~= before.revision
        or before.catalogKey ~= intent.catalogKey or not protocol(before, intent, false)
        or type(proposal.resources) ~= "table" or proposal.resources.cash ~= intent.expectedStake
        or proposal.resources.energy ~= intent.expectedEnergy then
        return nil, "Heist start baseline mismatch"
    end
    local current = board(before)
    local native = before.native
    if not current or current.mine ~= nil or current.result ~= nil
        or current.startsLeft ~= intent.startsBefore
        or current.bustWait ~= 0
        or not balance(current.serverNow, 0)
        or math.floor(current.serverNow / 86400) ~= intent.serverDay
        or not integer(native.level, 1)
        or not balance(native.cash, intent.expectedStake)
        or type(native.pools) ~= "table"
        or not integer(native.pools.energy, intent.expectedEnergy) then
        return nil, "Heist board or resources changed"
    end
    local found
    if type(before.heistCatalog) == "table" then
        for _, row in ipairs(before.heistCatalog) do
            if type(row) == "table" and row.id == intent.heistId then
                found = row
                break
            end
        end
    end
    if type(found) ~= "table" or found.stake ~= intent.expectedStake
        or found.energy ~= intent.expectedEnergy
        or not integer(found.level, 1)
        or found.level > native.level then
        return nil, "Selected Heist quote changed"
    end
    return { session = proposal.session, account = proposal.account,
        place = proposal.place, release = proposal.release,
        revision = proposal.revision, heistId = intent.heistId,
        startsBefore = intent.startsBefore,
        serverDay = intent.serverDay, catalogKey = before.catalogKey,
        cash = native.cash, energy = native.pools.energy, level = native.level,
        capturedAt = before.capturedAt, serverNow = current.serverNow,
        nativeServerNow = native.serverNow, expectedStake = intent.expectedStake,
        expectedEnergy = intent.expectedEnergy, sequence = intent.sequence,
        nativeJob = intent.nativeJob, nativeEpoch = intent.nativeEpoch,
        nativeSourceKey = intent.nativeSourceKey }, nil
end

local function reconcile(proposal, beforeHeader, after, reply, baseline, restart)
    if type(proposal) ~= "table" or type(beforeHeader) ~= "table"
        or type(after) ~= "table" or type(reply) ~= "table"
        or type(baseline) ~= "table"
        or not matching(proposal, beforeHeader)
        or not matching(proposal, after, restart)
        or not matching(proposal, baseline)
        or proposal.revision ~= baseline.revision
        or beforeHeader.revision ~= baseline.revision
        or reply.pending == true or reply.code == "pending"
        or reply.code == "no_pending" or reply.code == "rate_limited"
        or reply.code == "presence" then
        return "pending"
    end
    local current = board(after)
    if not current then return "pending" end
    local intent, native = proposal.intent, after.native
    if type(intent) ~= "table" or not protocol(after, intent, true) then return "pending" end
    local newer = after.session == baseline.session and integer(after.revision, 0) and after.revision > baseline.revision
        and balance(after.capturedAt, baseline.capturedAt)
        or restart and after.session ~= baseline.session and balance(current.serverNow, 0)
            and current.serverNow > baseline.serverNow and balance(native.serverNow, 0)
            and native.serverNow > baseline.nativeServerNow
    local mine = current.mine
    local exactRun = type(mine) == "table" and key(reply.runId) and reply.runId == mine.id
    local ownedRun = intent.sequence ~= nil and reply.runId == nil and type(after.heistProtocolProof) == "table"
        and after.heistProtocolProof.controllerCounter == intent.sequence
        and balance(native.cash, 0) and type(native.pools) == "table" and integer(native.pools.energy, 0)
        and integer(native.level, 1) and balance(current.serverNow, baseline.serverNow)
        and balance(native.serverNow, baseline.nativeServerNow)
        and math.abs(current.serverNow - native.serverNow) <= 2
    -- The native reply contains only ok/msg. Under the unchanged exclusive
    -- sequence, idle -> this newly created run and exactly one native start
    -- debit identify the action. Passive income/regeneration are independent
    -- of that transition and cannot be used as exact spend counters.
    local advanced = newer
        and current.startsLeft == baseline.startsBefore - 1
        and type(mine) == "table" and key(mine.id)
        and mine.heistId == baseline.heistId
        and (exactRun or ownedRun)
    if reply.ok == false then
        -- An unmatched run is not proof of failure: partial state, a different
        -- run, or any resource change leaves the sent action unresolved.
        local unchanged = integer(baseline.revision, 0) and newer
            and balance(baseline.capturedAt, 0) and balance(after.capturedAt, 0)
            and after.capturedAt >= baseline.capturedAt
            and balance(baseline.serverNow, 0) and balance(current.serverNow, 0)
            and current.serverNow >= baseline.serverNow
            and math.floor(current.serverNow / 86400) == baseline.serverDay
            and balance(baseline.nativeServerNow, 0) and balance(native.serverNow, 0)
            and native.serverNow >= baseline.nativeServerNow
            and math.abs(current.serverNow - native.serverNow) <= 2
            and key(baseline.catalogKey) and after.catalogKey == baseline.catalogKey
            and current.mine == nil and current.result == nil
            and current.startsLeft == baseline.startsBefore and current.bustWait == 0
            and balance(baseline.cash, 0) and native.cash == baseline.cash
            and integer(baseline.energy, 0) and type(native.pools) == "table"
            and native.pools.energy == baseline.energy
            and integer(baseline.level, 1) and native.level == baseline.level
        return unchanged and "rejected" or "pending"
    end
    if reply.ok == true and advanced then return "confirmed" end
    return "pending"
end

function HeistStartEvidence.evaluate(proposal, beforeHeader, after, reply, baseline)
    return reconcile(proposal, beforeHeader, after, reply, baseline, false)
end
function HeistStartEvidence.recoverSaved(data, after)
    if type(data) ~= "table" or type(data.reply) ~= "table" then return nil end
    local baseline = HeistStartEvidence.capture(data.proposal, data.before)
    if not baseline or not equal(baseline, data.baseline) then return nil end
    local status = reconcile(data.proposal, data.before, after, data.reply, baseline, true)
    return (status == "confirmed" or status == "rejected") and status or nil
end
return HeistStartEvidence
