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
        or not finite(native.serverNow, 0)
        or not integer(player.userId, 1)
        or (event.testUserId ~= nil
            and event.testUserId ~= player.userId)
        or not integer(usage.hits, 0)
        or not finite(usage.lastServerNow, 0) then
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
    local staminaReserve = type(intent) == "table" and intent.staminaReserve
    if staminaReserve == nil then staminaReserve = 1 end
    if type(before)=="table" and type(before.globalBossProof)=="table"
        and before.globalBossProof.attackCooldownUnavailable==true then return nil,"Current native cooldown unavailable" end
    local floor = type(intent)=="table" and intent.healthFloor
    local buffer = type(intent)=="table" and intent.hitBufferPct
    if floor == nil and buffer == nil then floor,buffer=50,25 end
    local delay = type(intent)=="table" and intent.minimumDelay
    local cooldown = type(intent)=="table" and intent.nativeAttackCooldown
    local effective = type(intent)=="table" and intent.effectiveDelay
    if delay == nil and cooldown == nil and effective == nil then delay,effective=5,5
    elseif not finite(delay,2) or delay>120 or not finite(effective,2) or effective>120
        or cooldown~=nil and (not finite(cooldown,0) or cooldown<=0 or cooldown>120)
        or delay<5 and cooldown==nil or effective~=math.max(delay,cooldown or 5)
        or type(before)~="table" or type(before.globalBossProof)~="table"
        or before.globalBossProof.attackCooldown~=cooldown then return nil,"Global Boss cooldown proof changed" end
    if not finite(floor,1) or floor>100 or not finite(buffer,0) or buffer>75 then return nil,"Invalid Global health preferences" end
    if type(proposal) ~= "table"
        or proposal.feature ~= "globalBossAttack"
        or type(intent) ~= "table"
        or not finite(staminaReserve, 0) or staminaReserve > 1e12
        or intent.kind ~= "globalBossAttack"
        or not key(intent.runKey)
        or not finite(intent.serverNow, 0)
        or not integer(intent.hitsBefore, 0)
        or not finite(intent.lastServerNowBefore, 0)
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
            and native.serverNow < usage.lastServerNow + effective)
        or hits ~= intent.mineHitsBefore
        or damage ~= intent.mineDamageBefore
        or type(native.stats) ~= "table"
        or not finite(native.stats.maxHealth, 1)
        or type(native.pools) ~= "table"
        or not finite(native.pools.health, 0)
        or native.pools.health
            < native.stats.maxHealth * (floor + buffer) / 100
        or not finite(native.pools.stamina, 1 + staminaReserve) then
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
        usageHitsBefore = usage.hits, serverNow = native.serverNow,
        staminaBefore = native.pools.stamina, sourceKey = before.globalBossProof.sourceKey,
        userId = before.localUserIdProof.userId }, nil
end

local function reconcile(proposal, beforeHeader,
    after, reply, baseline, restart)
    if type(proposal) ~= "table" or type(beforeHeader) ~= "table"
        or type(after) ~= "table" or type(reply) ~= "table"
        or type(baseline) ~= "table"
        or not matching(proposal, beforeHeader)
        or proposal.account ~= after.account or proposal.place ~= after.place or proposal.release ~= after.release
        or (not restart and not matching(proposal, after))
        or not matching(proposal, baseline)
        or proposal.revision ~= baseline.revision
        or beforeHeader.revision ~= baseline.revision
        or not integer(after.revision, 0)
        or not (after.session == baseline.session and after.revision > baseline.revision
            or restart and after.session ~= baseline.session and type(after.native) == "table"
                and finite(after.native.serverNow, 0) and finite(baseline.serverNow, 0)
                and after.native.serverNow > baseline.serverNow)
        or reply.pending == true or reply.code == "rate_limited" or reply.code == "presence" then
        return "pending"
    end
    local event, native, usage, run, hits, damage = current(after)
    if not event or run ~= baseline.runKey or not finite(baseline.serverNow, 0)
        or native.serverNow < baseline.serverNow or after.globalBossProof.sourceKey ~= baseline.sourceKey
        or after.localUserIdProof.userId ~= baseline.userId then return "pending" end
    local advanced = run == baseline.runKey
        and usage.hits == baseline.usageHitsBefore + 1
        and integer(reply.dmg, 1)
        and hits == baseline.mineHitsBefore + 1
        and damage == baseline.mineDamageBefore + reply.dmg
    if reply.ok == false then
        return hits == baseline.mineHitsBefore and damage == baseline.mineDamageBefore
            and type(native.pools) == "table" and native.pools.stamina == baseline.staminaBefore
            and "rejected" or "pending"
    end
    if reply.ok == true and advanced then return "confirmed" end
    return "pending"
end

function GlobalBossAttackEvidence.evaluate(proposal, before, after, reply, baseline)
    return reconcile(proposal, before, after, reply, baseline, false)
end
local function equal(a, b)
    if type(a) ~= type(b) then return false end
    if type(a) ~= "table" then return a == b end
    for k, v in pairs(a) do if not equal(v, b[k]) then return false end end
    for k in pairs(b) do if a[k] == nil then return false end end
    return true
end
function GlobalBossAttackEvidence.recoverSaved(data, after)
    if type(data) ~= "table" or type(data.reply) ~= "table" then return nil end
    local baseline = GlobalBossAttackEvidence.capture(data.proposal, data.before)
    if not baseline or not equal(baseline, data.baseline) then return nil end
    local result = reconcile(data.proposal, data.before, after, data.reply, baseline, true)
    return (result == "confirmed" or result == "rejected") and result or nil
end
function GlobalBossAttackEvidence.canDispatch(proposal, snapshot)
    local intent = type(proposal) == "table" and proposal.intent
    if type(snapshot) ~= "table" or type(intent) ~= "table" then return false end
    local before = {}
    for key, value in pairs(snapshot) do before[key] = value end
    before.globalAttackUsageProof = { account = proposal.account, capturedAt = snapshot.capturedAt,
        runKey = intent.runKey, hits = intent.hitsBefore, lastServerNow = intent.lastServerNowBefore }
    return GlobalBossAttackEvidence.capture(proposal, before) ~= nil
end
return GlobalBossAttackEvidence
