-- A newer personal hit and free-charge debit confirm a Takedown attack.
local FamilyBossAttacksEvidence = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge and value % 1 == 0
end

local function matching(a, b)
    for _, field in ipairs({ "session", "account", "place", "release" }) do
        if type(a[field]) ~= "string" or #a[field] == 0
            or a[field] ~= b[field] then return false end
    end
    return true
end

local function current(raw, needAttack)
    local native = type(raw) == "table" and raw.native
    local proof = type(raw) == "table" and raw.familyTakedownProof
    local state = type(proof) == "table" and proof.state
    local attack = type(raw) == "table" and raw.familyAttackProof
    local usage = type(raw) == "table"
        and raw.familyAttackUsageProof
    if type(native) ~= "table" or native.fullSync ~= true
        or not integer(native.serverNow, 0)
        or type(proof) ~= "table"
        or proof.account ~= raw.account
        or proof.capturedAt ~= raw.capturedAt
        or type(state) ~= "table"
        or not integer(state.week, 1)
        or not integer(state.famId, 1)
        or not integer(state.stage, 1)
        or not integer(state.resetAt, native.serverNow + 1)
        or state.inFamily ~= true
        or not integer(state.freeMax, 1)
        or not integer(state.freeUsed, 0)
        or state.freeUsed > state.freeMax
        or not integer(state.freeRegen, 1)
        or (state.nextFreeAt ~= nil
            and not integer(state.nextFreeAt, 0))
        or not integer(state.tickets, 0)
        or not integer(state.myDmg, 0)
        or type(usage) ~= "table"
        or usage.account ~= raw.account
        or usage.capturedAt ~= raw.capturedAt
        or usage.week ~= state.week
        or usage.famId ~= state.famId
        or not integer(usage.hits, 0)
        or not integer(usage.lastServerNow, 0) then
        return nil
    end
    if needAttack and (type(attack) ~= "table"
        or attack.account ~= raw.account
        or attack.capturedAt ~= raw.capturedAt
        or attack.week ~= state.week
        or attack.famId ~= state.famId
        or attack.stage ~= state.stage
        or not integer(attack.staminaCost, 1)
        or not integer(attack.hitBackMax, 1)) then
        return nil
    end
    return native, state, attack, usage
end

local function freeNow(state, now)
    local free = math.max(0, state.freeMax - state.freeUsed)
    local nextAt = free < state.freeMax
        and state.nextFreeAt or nil
    if nextAt and nextAt <= now then
        local gained = math.floor((now - nextAt)
            / state.freeRegen) + 1
        free = math.min(state.freeMax, free + gained)
    end
    return free
end

function FamilyBossAttacksEvidence.capture(proposal, before)
    local intent = type(proposal) == "table" and proposal.intent
    if type(proposal) ~= "table"
        or proposal.feature ~= "familyBossAttacks"
        or type(intent) ~= "table"
        or intent.kind ~= "familyBossAttack"
        or not integer(intent.week, 1)
        or not integer(intent.famId, 1)
        or not integer(intent.stage, 1) or intent.stage > 5
        or not integer(intent.serverNow, 0)
        or not integer(intent.hitsBefore, 0)
        or not integer(intent.lastServerNowBefore, 0)
        or not integer(intent.mineDamageBefore, 0)
        or not integer(intent.freeUsedBefore, 0)
        or not integer(intent.expectedStaminaCost, 1)
        or not integer(intent.expectedHitBackMax, 1)
        or type(before) ~= "table"
        or not matching(proposal, before)
        or proposal.revision ~= before.revision then
        return nil, "Family attack baseline mismatch"
    end
    local native, state, attack, usage = current(before, true)
    local pools = native and native.pools
    local stats = native and native.stats
    if not native or state.week ~= intent.week
        or state.famId ~= intent.famId
        or state.stage ~= intent.stage
        or state.tickets ~= 0
        or native.serverNow ~= intent.serverNow
        or freeNow(state, native.serverNow) < 1
        or usage.hits ~= intent.hitsBefore
        or usage.lastServerNow ~= intent.lastServerNowBefore
        or usage.hits >= 25
        or (usage.hits > 0
            and native.serverNow < usage.lastServerNow + 5)
        or state.myDmg ~= intent.mineDamageBefore
        or state.freeUsed ~= intent.freeUsedBefore
        or attack.staminaCost ~= intent.expectedStaminaCost
        or attack.hitBackMax ~= intent.expectedHitBackMax
        or type(pools) ~= "table"
        or type(stats) ~= "table"
        or not integer(stats.maxHealth, 1)
        or not integer(pools.health, 0)
        or pools.health > stats.maxHealth
        or not integer(pools.stamina,
            attack.staminaCost + 1)
        or pools.health - attack.hitBackMax
            < math.max(20, stats.maxHealth * 0.5) then
        return nil, "Family free attack or resources changed"
    end
    return { session = proposal.session, account = proposal.account,
        place = proposal.place, release = proposal.release,
        revision = proposal.revision,
        week = state.week, famId = state.famId,
        stage = state.stage,
        mineDamageBefore = state.myDmg,
        freeUsedBefore = state.freeUsed,
        usageHitsBefore = usage.hits }, nil
end

function FamilyBossAttacksEvidence.evaluate(proposal, beforeHeader,
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
    local native, state, _, usage = current(after, false)
    if not native then return "pending" end
    local advanced = type(after.revision) == "number"
        and after.revision > baseline.revision
        and state.week == baseline.week
        and state.famId == baseline.famId
        and state.tickets == 0
        and usage.hits >= baseline.usageHitsBefore + 1
        and integer(reply.dmg, 1)
        and integer(reply.freeLeft, 0)
        and reply.tickets == 0
        and state.myDmg >= baseline.mineDamageBefore
            + reply.dmg
        and state.freeUsed >= baseline.freeUsedBefore + 1
    if reply.ok == false then
        return advanced and "pending" or "rejected"
    end
    if reply.ok == true and advanced then return "confirmed" end
    return "pending"
end

return FamilyBossAttacksEvidence
