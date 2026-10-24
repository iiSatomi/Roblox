-- Reply damage must match a newer personal hit on the exact run.
local GlobalBossAttackEvidence = {}

local function finite(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge
end

local function integer(value, minimum)
    return finite(value, minimum) and value % 1 == 0
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
    local usage = type(raw) == "table" and raw.globalAttackUsageProof
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
        or not integer(event.endAt, event.startAt + 1)
        or not finite(event.hp, 10000)
        or not finite(event.dmg, 0)
        or not integer(native.serverNow, 0)
        or not integer(player.userId, 1)
        or (event.testUserId ~= nil
            and event.testUserId ~= player.userId)
        or not integer(usage.hits, 0)
        or not integer(usage.lastServerNow, 0) then
        return nil
    end
    local run = event.id .. "_" .. tostring(event.startAt)
    if usage.runKey ~= run then return nil end
    local mine = native.gb
    local hits, damage = 0, 0
    if type(mine) == "table" and mine.run == run then
        if not integer(mine.hits, 0)
            or not finite(mine.dmg, 0) then return nil end
        hits, damage = mine.hits, mine.dmg
    end
    return event, native, usage, run, hits, damage
end

function GlobalBossAttackEvidence.capture(proposal, before)
    local intent = type(proposal) == "table" and proposal.intent
    if type(proposal) ~= "table"
        or proposal.feature ~= "globalBossAttack"
        or type(intent) ~= "table"
        or intent.kind ~= "globalBossAttack"
        or not key(intent.runKey)
        or not integer(intent.serverNow, 0)
        or not integer(intent.hitsBefore, 0)
        or not integer(intent.lastServerNowBefore, 0)
        or not integer(intent.mineHitsBefore, 0)
        or not finite(intent.mineDamageBefore, 0)
        or intent.expectedStaminaCost ~= 1
        or type(before) ~= "table" or not matching(proposal, before)
        or proposal.revision ~= before.revision then
        return nil, "Global Boss attack baseline mismatch"
    end
    local event, native, usage, run, hits, damage = current(before)
    if not event or run ~= intent.runKey
        or event.status ~= "live"
        or native.serverNow ~= intent.serverNow
        or native.serverNow < event.startAt
        or native.serverNow >= event.endAt
        or usage.hits ~= intent.hitsBefore
        or usage.lastServerNow ~= intent.lastServerNowBefore
        or usage.hits >= 25
        or (usage.hits > 0
            and native.serverNow < usage.lastServerNow + 5)
        or hits ~= intent.mineHitsBefore
        or damage ~= intent.mineDamageBefore
        or type(native.stats) ~= "table"
        or not finite(native.stats.maxHealth, 1)
        or type(native.pools) ~= "table"
        or not finite(native.pools.health, 0)
        or math.floor(native.pools.health)
            < native.stats.maxHealth * 0.75
        or not finite(native.pools.stamina, 2) then
        return nil, "Global Boss run or resources changed"
    end
    local elapsed = math.max(0, math.min(1,
        (native.serverNow - event.startAt)
            / (event.endAt - event.startAt)))
    if event.hp - event.dmg - event.hp * elapsed <= 0 then
        return nil, "Global Boss no longer live"
    end
    return { session = proposal.session, account = proposal.account,
        place = proposal.place, release = proposal.release,
        revision = proposal.revision, runKey = run,
        mineHitsBefore = hits,
        mineDamageBefore = damage,
        usageHitsBefore = usage.hits }, nil
end

function GlobalBossAttackEvidence.evaluate(proposal, beforeHeader,
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
    local event, _, usage, run, hits, damage = current(after)
    if not event then return "pending" end
    local advanced = type(after.revision) == "number"
        and after.revision > baseline.revision
        and run == baseline.runKey
        and usage.hits >= baseline.usageHitsBefore + 1
        and integer(reply.dmg, 1)
        and hits == baseline.mineHitsBefore + 1
        and damage >= baseline.mineDamageBefore + reply.dmg
    if reply.ok == false then return advanced and "pending" or "rejected" end
    if reply.ok == true and advanced then return "confirmed" end
    return "pending"
end

return GlobalBossAttackEvidence
