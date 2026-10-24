-- Only exact staged HP/clear changes after a positive reply confirm a hit.
local BossesEvidence = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge and value % 1 == 0
end

local function finite(value, minimum)
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

local function current(raw, stage)
    local native = type(raw) == "table" and raw.native
    local proof = type(raw) == "table" and raw.bossStageProof
    local usage = type(raw) == "table" and raw.bossUsageProof
    local state = type(native) == "table" and native.bossStage
    if type(native) ~= "table" or native.fullSync ~= true
        or not integer(native.serverNow, 0)
        or type(state) ~= "table" or not integer(state.best, 0)
        or not integer(state.day, 0)
        or type(proof) ~= "table" or proof.account ~= raw.account
        or proof.capturedAt ~= raw.capturedAt
        or type(proof.stages) ~= "table"
        or type(usage) ~= "table" or usage.account ~= raw.account
        or usage.capturedAt ~= raw.capturedAt
        or not integer(usage.day, 0)
        or not integer(usage.hits, 0)
        or not integer(usage.stamina, 0)
        or not integer(usage.lastServerNow, 0)
        or usage.day ~= tonumber(os.date("!%Y%j", native.serverNow)) then
        return nil
    end
    local selected
    for _, row in ipairs(proof.stages) do
        if type(row) == "table" and row.stage == stage then
            selected = row
            break
        end
    end
    if not selected then return nil end
    local stageKey = tostring(stage)
    local hp = type(state.hp) == "table" and state.hp[stageKey]
    if not integer(hp, 1) or hp > selected.hp then hp = selected.hp end
    local done = state.day == usage.day
        and type(state.done) == "table"
        and state.done[stageKey] == true or false
    return native, state, proof, usage, selected, hp, done
end

function BossesEvidence.capture(proposal, before)
    local intent = type(proposal) == "table" and proposal.intent
    if type(proposal) ~= "table" or proposal.feature ~= "bosses"
        or type(intent) ~= "table" or intent.kind ~= "bossStageAttack"
        or not integer(intent.stage, 1)
        or not integer(intent.dayStamp, 0)
        or not integer(intent.serverNow, 0)
        or not integer(intent.bestBefore, 0)
        or not integer(intent.remainingHpBefore, 1)
        or not integer(intent.maxHp, 1)
        or not integer(intent.hitBackMax, 0)
        or not integer(intent.expectedStaminaCost, 1)
        or not integer(intent.hitsBefore, 0)
        or not integer(intent.staminaBefore, 0)
        or not integer(intent.lastServerNowBefore, 0)
        or type(before) ~= "table" or not matching(proposal, before)
        or proposal.revision ~= before.revision then
        return nil, "Boss attack baseline mismatch"
    end
    local native, state, proof, usage, row, hp, done =
        current(before, intent.stage)
    if not native or native.serverNow ~= intent.serverNow
        or usage.day ~= intent.dayStamp
        or usage.hits ~= intent.hitsBefore
        or usage.stamina ~= intent.staminaBefore
        or usage.lastServerNow ~= intent.lastServerNowBefore
        or usage.hits >= 100
        or usage.stamina + intent.expectedStaminaCost > 100
        or (usage.hits > 0
            and native.serverNow < usage.lastServerNow + 5)
        or state.best ~= intent.bestBefore
        or intent.stage > state.best + 1 or done
        or row.hp ~= intent.maxHp
        or row.hitBackMax ~= intent.hitBackMax
        or row.level > native.level
        or hp ~= intent.remainingHpBefore
        or proof.staminaCost ~= intent.expectedStaminaCost
        or (state.auto ~= nil and state.auto ~= false)
        or type(native.stats) ~= "table"
        or not integer(native.stats.maxHealth, 1)
        or type(native.pools) ~= "table"
        or not finite(native.pools.health, 0)
        or math.floor(native.pools.health) - row.hitBackMax
            < native.stats.maxHealth * 0.5
        or not finite(native.pools.stamina,
            intent.expectedStaminaCost + 1) then
        return nil, "Selected Boss stage or resources changed"
    end
    return { session = proposal.session, account = proposal.account,
        place = proposal.place, release = proposal.release,
        revision = proposal.revision, stage = intent.stage,
        dayStamp = intent.dayStamp, bestBefore = intent.bestBefore,
        hpBefore = hp, maxHp = row.hp,
        hitsBefore = usage.hits }, nil
end

function BossesEvidence.evaluate(proposal, beforeHeader, after,
    reply, baseline)
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
    local native, state, _, usage, row, hp, done =
        current(after, baseline.stage)
    if not native then return "pending" end
    local advanced = type(after.revision) == "number"
        and after.revision > baseline.revision
        and usage.day == baseline.dayStamp
        and usage.hits >= baseline.hitsBefore + 1
        and row.hp == baseline.maxHp
        and state.best >= baseline.bestBefore
        and (hp < baseline.hpBefore or done == true)
    if reply.ok == false then return advanced and "pending" or "rejected" end
    if reply.ok == true and advanced then return "confirmed" end
    return "pending"
end

return BossesEvidence
