-- A positive reply plus exact personal claimed state confirms.
local GlobalBossClaimEvidence = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge and value % 1 == 0
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
        or not integer(native.serverNow, event.resultAt)
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
    return { session = proposal.session, account = proposal.account,
        place = proposal.place, release = proposal.release,
        revision = proposal.revision, runKey = runKey }, nil
end

function GlobalBossClaimEvidence.evaluate(proposal, beforeHeader,
    after, reply, baseline)
    if type(proposal) ~= "table" or type(beforeHeader) ~= "table"
        or type(after) ~= "table" or type(reply) ~= "table"
        or type(baseline) ~= "table"
        or not matching(proposal, beforeHeader)
        or not matching(proposal, after)
        or not matching(proposal, baseline)
        or proposal.revision ~= baseline.revision
        or beforeHeader.revision ~= baseline.revision then
        return "pending"
    end
    local _, mine, usage, runKey = current(after)
    if not mine then return "pending" end
    local advanced = type(after.revision) == "number"
        and after.revision > baseline.revision
        and runKey == baseline.runKey
        and mine.claimed == true
        and usage.attempts >= 1
    if reply.ok == false then return advanced and "pending" or "rejected" end
    if reply.ok == true and advanced then return "confirmed" end
    return "pending"
end

return GlobalBossClaimEvidence
