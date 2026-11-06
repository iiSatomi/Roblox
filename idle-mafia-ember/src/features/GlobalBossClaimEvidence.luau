-- A positive reply plus exact personal claimed state confirms.
local GlobalBossClaimEvidence = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge and value % 1 == 0
end

local function timestamp(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge
end

local function key(value)
    return type(value) == "string" and #value > 0
end

local function matching(a, b)
    for _, field in ipairs({ "session", "account", "place", "release" }) do
        if not key(a[field]) or a[field] ~= b[field] then return false end
    end
    return true
end

local function current(raw)
    local proof = type(raw) == "table" and raw.globalBossProof
    local player = type(raw) == "table" and raw.localUserIdProof
    local usage = type(raw) == "table" and raw.globalClaimUsageProof
    local native = type(raw) == "table" and raw.native
    local event = type(proof) == "table" and proof.event
    if type(proof) ~= "table" or type(player) ~= "table"
        or type(usage) ~= "table" or type(native) ~= "table"
        or native.fullSync ~= true
        or proof.account ~= raw.account
        or proof.capturedAt ~= raw.capturedAt
        or player.account ~= raw.account
        or player.capturedAt ~= raw.capturedAt
        or usage.account ~= raw.account
        or usage.capturedAt ~= raw.capturedAt
        or type(event) ~= "table" or not key(event.id)
        or not integer(event.startAt, 0)
        or event.status ~= "done"
        or not integer(event.resultAt, 0)
        or not timestamp(native.serverNow, event.resultAt)
        or not integer(player.userId, 1)
        or (event.testUserId ~= nil
            and event.testUserId ~= player.userId)
        or type(native.gb) ~= "table"
        or not integer(native.gb.dmg, 1)
        or type(native.gb.claimed) ~= "boolean" then
        return nil
    end
    local runKey = event.id .. "_" .. tostring(event.startAt)
    if native.gb.run ~= runKey or usage.runKey ~= runKey
        or not integer(usage.attempts, 0)
        or native.serverNow - event.resultAt >= 604800 then
        return nil
    end
    return event, native.gb, usage, runKey
end

local function inventory(raw)
    if type(raw) ~= "table" then return nil end
    local result, size = {}, 0
    for id, amount in pairs(raw) do
        size = size + 1
        if size > 4096 or not key(id) or #id > 120 or not integer(amount, 0)
            or amount > 9007199254740991 then return nil end
        result[id] = amount
    end
    return result
end
local function winnings(rows)
    if type(rows) ~= "table" or #rows > 128 then return nil end
    local result, size = {}, 0
    for index, row in pairs(rows) do
        if not integer(index, 1) or index > #rows or type(row) ~= "table"
            or not key(row.i) or #row.i > 120 or not integer(row.n or 1, 1)
            or (row.n or 1) > 9007199254740991 then return nil end
        size = size + 1
        result[row.i] = (result[row.i] or 0) + (row.n or 1)
        if result[row.i] > 9007199254740991 then return nil end
    end
    return size == #rows and result or nil
end
local function equal(a, b)
    if type(a) ~= type(b) then return false end
    if type(a) ~= "table" then return a == b end
    for k, v in pairs(a) do if not equal(v, b[k]) then return false end end
    for k in pairs(b) do if a[k] == nil then return false end end
    return true
end
local function inventoryEffect(beforeLoose, beforeBound, native, expected)
    local loose, bound = inventory(native.inventory), inventory(native.inventoryBound)
    if not loose or not bound then return false end
    local ids = {}
    for _, map in ipairs({beforeLoose, beforeBound, loose, bound, expected}) do
        for id in pairs(map) do ids[id] = true end
    end
    for id in pairs(ids) do
        local dl = (loose[id] or 0) - (beforeLoose[id] or 0)
        local db = (bound[id] or 0) - (beforeBound[id] or 0)
        local amount = expected[id] or 0
        if id == "event_medal" then
            if dl ~= 0 or db ~= amount then return false end
        elseif not (dl == amount and db == 0 or dl == 0 and db == amount) then return false end
    end
    return true
end

function GlobalBossClaimEvidence.capture(proposal, before)
    local intent = type(proposal) == "table" and proposal.intent
    if type(proposal) ~= "table"
        or proposal.feature ~= "globalBossClaim"
        or type(intent) ~= "table"
        or intent.kind ~= "globalBossClaim"
        or not key(intent.runKey)
        or intent.attemptsBefore ~= 0
        or type(before) ~= "table" or not matching(proposal, before)
        or proposal.revision ~= before.revision then
        return nil, "Global Boss claim baseline mismatch"
    end
    local _, mine, usage, runKey = current(before)
    if not mine or runKey ~= intent.runKey
        or mine.claimed ~= false or usage.attempts ~= 0 then
        return nil, "Global Boss result or attempt changed"
    end
    local loose, bound = inventory(before.native.inventory), inventory(before.native.inventoryBound)
    if not loose or not bound or not integer(before.native.paidMedals or 0, 0) then
        return nil, "Current Global Boss award custody unavailable"
    end
    return { session = proposal.session, account = proposal.account,
        place = proposal.place, release = proposal.release,
        revision = proposal.revision, runKey = runKey,
        serverNow = before.native.serverNow, mineDamage = mine.dmg, mineHits = mine.hits or 0,
        sourceKey = before.globalBossProof.sourceKey, userId = before.localUserIdProof.userId,
        inventory = loose, inventoryBound = bound, paidMedals = before.native.paidMedals or 0 }, nil
end

local function reconcile(proposal, beforeHeader, after, reply, baseline, restart)
    if type(proposal) ~= "table" or type(beforeHeader) ~= "table" or type(after) ~= "table"
        or type(reply) ~= "table" or type(baseline) ~= "table"
        or not matching(proposal, beforeHeader) or not matching(proposal, baseline)
        or proposal.account ~= after.account or proposal.place ~= after.place or proposal.release ~= after.release
        or (not restart and not matching(proposal, after))
        or proposal.revision ~= baseline.revision or beforeHeader.revision ~= baseline.revision
        or not integer(after.revision, 0)
        or not (after.session == baseline.session and after.revision > baseline.revision
            or restart and after.session ~= baseline.session and type(after.native) == "table"
                and timestamp(after.native.serverNow, baseline.serverNow) and after.native.serverNow > baseline.serverNow)
        or reply.pending == true or reply.code == "rate_limited" or reply.code == "presence" then return "pending" end
    local _, mine, usage, runKey = current(after)
    local native = after.native
    if not mine or runKey ~= baseline.runKey or native.serverNow < baseline.serverNow
        or after.globalBossProof.sourceKey ~= baseline.sourceKey or after.localUserIdProof.userId ~= baseline.userId
        or mine.dmg ~= baseline.mineDamage or (mine.hits or 0) ~= baseline.mineHits
        or (native.paidMedals or 0) ~= baseline.paidMedals then return "pending" end
    if reply.ok == false then
        return mine.claimed == false and inventoryEffect(baseline.inventory, baseline.inventoryBound, native, {})
            and "rejected" or "pending"
    end
    if reply.ok ~= true or mine.claimed ~= true or usage.attempts ~= 1
        or not integer(reply.medals, 0) or reply.medals > 9007199254740991
        or mine.medals ~= reply.medals then return "pending" end
    local returned, observed = winnings(reply.won), winnings(mine.won)
    if not returned or not observed or not equal(returned, observed) then return "pending" end
    returned.event_medal = (returned.event_medal or 0) + reply.medals
    if returned.event_medal > 9007199254740991 then return "pending" end
    return inventoryEffect(baseline.inventory, baseline.inventoryBound, native, returned) and "confirmed" or "pending"
end
function GlobalBossClaimEvidence.evaluate(proposal, before, after, reply, baseline)
    return reconcile(proposal, before, after, reply, baseline, false)
end
function GlobalBossClaimEvidence.recoverSaved(data, after)
    if type(data) ~= "table" or type(data.reply) ~= "table" then return nil end
    local baseline = GlobalBossClaimEvidence.capture(data.proposal, data.before)
    if not baseline or not equal(baseline, data.baseline) then return nil end
    local result = reconcile(data.proposal, data.before, after, data.reply, baseline, true)
    return (result == "confirmed" or result == "rejected") and result or nil
end
function GlobalBossClaimEvidence.canDispatch(proposal, snapshot)
    if type(snapshot) ~= "table" or type(proposal) ~= "table" or type(proposal.intent) ~= "table" then return false end
    local before = {}
    for key, value in pairs(snapshot) do before[key] = value end
    before.globalClaimUsageProof = {account = proposal.account, capturedAt = snapshot.capturedAt,
        runKey = proposal.intent.runKey, attempts = proposal.intent.attemptsBefore}
    return GlobalBossClaimEvidence.capture(proposal, before) ~= nil
end
return GlobalBossClaimEvidence
