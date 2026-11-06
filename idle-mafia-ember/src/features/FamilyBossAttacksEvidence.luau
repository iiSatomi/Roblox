-- A newer personal hit and free-charge debit confirm a Takedown attack.
local FamilyBossAttacksEvidence = {}
local function familyId(value)
    return type(value) == "string" and #value > 0 and #value <= 120
        and not value:find("[%c]")
        or type(value) == "number" and value == value and value >= 1
            and value <= 9007199254740991 and value % 1 == 0
end

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge and value % 1 == 0
end

local function timestamp(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge
end

local function matching(a, b, restart)
    for _, field in ipairs({ "session", "account", "place", "release" }) do
        if type(a[field]) ~= "string" or #a[field] == 0
            or (a[field] ~= b[field] and not (restart and field == "session")) then return false end
    end
    return true
end

local function unknownProof(attack, raw)
    if type(attack) ~= "table" or attack.hitBackKnown ~= false or attack.hitBackMax ~= nil
        or attack.nativePreflight ~= true or attack.controllersClear ~= true
        or not integer(attack.hospitalHealth, 1) or type(attack.sourceKey) ~= "string"
        or #attack.sourceKey ~= 64 or not attack.sourceKey:match("^[%x]+$")
        or type(attack.header) ~= "table" then return false end
    for _, field in ipairs({"session", "account", "place", "release", "revision", "capturedAt"}) do
        if attack.header[field] ~= raw[field] then return false end
    end
    return true
end
local function current(raw, needAttack, skipUsage)
    local native = type(raw) == "table" and raw.native
    local proof = type(raw) == "table" and raw.familyTakedownProof
    local state = type(proof) == "table" and proof.state
    local attack = type(raw) == "table" and raw.familyAttackProof
    local usage = type(raw) == "table"
        and raw.familyAttackUsageProof
    if type(native) ~= "table" or native.fullSync ~= true
        or not timestamp(native.serverNow, 0)
        or type(proof) ~= "table"
        or proof.account ~= raw.account
        or proof.capturedAt ~= raw.capturedAt
        or type(state) ~= "table"
        or not integer(state.week, 1)
        or not familyId(state.famId)
        or not integer(state.stage, 1)
        or not timestamp(state.resetAt, native.serverNow + 1)
        or state.inFamily ~= true
        or not integer(state.freeMax, 1)
        or not integer(state.freeUsed, 0)
        or state.freeUsed > state.freeMax
        or not integer(state.freeRegen, 1)
        or (state.nextFreeAt ~= nil
            and not timestamp(state.nextFreeAt, 0))
        or not integer(state.tickets, 0)
        or not integer(state.myDmg, 0)
        or not skipUsage and (type(usage) ~= "table"
        or usage.account ~= raw.account
        or usage.capturedAt ~= raw.capturedAt
        or usage.week ~= state.week
        or usage.famId ~= state.famId
        or not integer(usage.hits, 0)
        or not timestamp(usage.lastServerNow, 0)) then
        return nil
    end
    if needAttack and (type(attack) ~= "table"
        or attack.account ~= raw.account
        or attack.capturedAt ~= raw.capturedAt
        or attack.week ~= state.week
        or attack.famId ~= state.famId
        or attack.stage ~= state.stage
        or not integer(attack.staminaCost, 1)
        or (attack.hitBackKnown == false and not unknownProof(attack, raw)
            or attack.hitBackKnown ~= false and not integer(attack.hitBackMax, 1))) then
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
    local unknown = type(intent) == "table" and intent.uncalculatedHitBack == true
    if type(proposal) ~= "table"
        or proposal.feature ~= "familyBossAttacks"
        or type(intent) ~= "table"
        or intent.kind ~= "familyBossAttack"
        or not integer(intent.week, 1)
        or not familyId(intent.famId)
        or not integer(intent.stage, 1) or intent.stage > 6
        or not timestamp(intent.serverNow, 0)
        or not integer(intent.hitsBefore, 0)
        or not timestamp(intent.lastServerNowBefore, 0)
        or not integer(intent.mineDamageBefore, 0)
        or not integer(intent.freeUsedBefore, 0)
        or not integer(intent.expectedStaminaCost, 1)
        or (unknown and (intent.allowUncalculatedHitBack ~= true or intent.hitsBefore ~= 0
                or intent.expectedHitBackMax ~= nil or type(intent.attackSourceKey) ~= "string")
            or not unknown and (intent.uncalculatedHitBack ~= nil or not integer(intent.expectedHitBackMax, 1)))
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
        or (unknown and (not unknownProof(attack, before) or attack.sourceKey ~= intent.attackSourceKey)
            or not unknown and (attack.hitBackKnown == false or attack.hitBackMax ~= intent.expectedHitBackMax))
        or type(pools) ~= "table"
        or type(stats) ~= "table"
        or not integer(stats.maxHealth, 1)
        or not timestamp(pools.health, 0)
        or pools.health > stats.maxHealth
        or not timestamp(pools.stamina,
            attack.staminaCost + 1)
        or (unknown and (pools.health ~= stats.maxHealth or pools.health < attack.hospitalHealth)
            or not unknown and pools.health - attack.hitBackMax < math.max(20, stats.maxHealth * 0.5)) then
        return nil, "Family free attack or resources changed"
    end
    return { session = proposal.session, account = proposal.account,
        place = proposal.place, release = proposal.release,
        revision = proposal.revision,
        week = state.week, famId = state.famId,
        stage = state.stage,
        mineDamageBefore = state.myDmg,
        freeUsedBefore = state.freeUsed,
        usageHitsBefore = usage.hits, uncalculatedHitBack = unknown or nil }, nil
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
        or type(proposal.intent) ~= "table"
        or (proposal.intent.uncalculatedHitBack == true) ~= (baseline.uncalculatedHitBack == true)
        or reply.pending == true or reply.code == "rate_limited" or reply.code == "busy" or reply.code == "presence" then
        return "pending"
    end
    local native, state, _, usage = current(after, false)
    if not native then return "pending" end
    local newer = type(after.revision) == "number" and after.revision > baseline.revision
    if restart and after.session ~= baseline.session then
        newer = integer(after.revision, 0) and native.serverNow > proposal.intent.serverNow
    end
    local advanced = newer
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

function FamilyBossAttacksEvidence.evaluate(proposal, beforeHeader, after, reply, baseline)
    return reconcile(proposal, beforeHeader, after, reply, baseline, false)
end

function FamilyBossAttacksEvidence.canDispatch(proposal, raw)
    local intent = type(proposal) == "table" and proposal.intent
    if type(intent) ~= "table" or not matching(proposal, raw) or proposal.revision ~= raw.revision then return false end
    local native, state, attack = current(raw, true, true)
    if not native or intent.week ~= state.week or intent.famId ~= state.famId or intent.stage ~= state.stage
        or intent.freeUsedBefore ~= state.freeUsed or intent.mineDamageBefore ~= state.myDmg or state.tickets ~= 0
        or freeNow(state, native.serverNow) < 1 or intent.expectedStaminaCost ~= attack.staminaCost
        or type(native.pools) ~= "table" or type(native.stats) ~= "table"
        or not timestamp(native.pools.stamina, attack.staminaCost + 1) or not integer(native.stats.maxHealth, 1)
        or not timestamp(native.pools.health, 0) then return false end
    if intent.uncalculatedHitBack == true then
        return intent.allowUncalculatedHitBack == true and intent.hitsBefore == 0 and unknownProof(attack, raw)
            and intent.attackSourceKey == attack.sourceKey and native.pools.health == native.stats.maxHealth
            and native.pools.health >= attack.hospitalHealth
    end
    return attack.hitBackKnown ~= false and attack.hitBackMax == intent.expectedHitBackMax
        and native.pools.health - attack.hitBackMax >= math.max(20, native.stats.maxHealth * 0.5)
end

local function equal(a, b)
    if type(a) ~= type(b) then return false end
    if type(a) ~= "table" then return a == b end
    for key, value in pairs(a) do if not equal(value, b[key]) then return false end end
    for key in pairs(b) do if a[key] == nil then return false end end
    return true
end
function FamilyBossAttacksEvidence.recoverSaved(data, after)
    if type(data) ~= "table" then return nil end
    local baseline = FamilyBossAttacksEvidence.capture(data.proposal, data.before)
    if not baseline or not equal(baseline, data.baseline) then return nil end
    local result = reconcile(data.proposal, data.before, after, data.reply, baseline, true)
    return (result == "confirmed" or result == "rejected") and result or nil
end

return FamilyBossAttacksEvidence
