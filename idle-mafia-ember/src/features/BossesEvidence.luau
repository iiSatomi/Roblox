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

local function dayStamp(value)
    if not finite(value, 0) then return nil end
    local ok, result = pcall(os.date, "!%Y%j", math.floor(value))
    return ok and tonumber(result) or nil
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
        or not finite(native.serverNow, 0)
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
        or not finite(usage.lastServerNow, 0)
        or usage.day ~= dayStamp(native.serverNow) then
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

local rewardFields = {"cash", "xp", "crate", "firstClearCrate", "crateRarity", "firstClearRarity", "mostWanted"}
local function selectionOf(intent)
    if type(intent) ~= "table" then return nil end
    local result = {contract = intent.selectionContract, mode = intent.selectionMode,
        cash = intent.selectedCash, xp = intent.selectedXp, crate = intent.selectedCrate,
        firstClearCrate = intent.selectedFirstClearCrate, crateRarity = intent.selectedCrateRarity,
        firstClearRarity = intent.selectedFirstClearRarity, mostWanted = intent.selectedMostWanted}
    return next(result) ~= nil and result or nil
end
local function sameReward(selection, row, proof)
    if type(selection) ~= "table" or selection.contract ~= "boss-get-653-v1"
        or proof.selectionContract ~= selection.contract then return false end
    local modes = {["Current progression"] = true, Smart = true, ["First undefeated"] = true,
        ["Highest level"] = true, ["Best chest"] = true, ["Cash reward"] = true, ["XP reward"] = true}
    if not modes[selection.mode] then return false end
    for _, field in ipairs(rewardFields) do if selection[field] ~= row[field] then return false end end
    return integer(selection.cash, 0) and integer(selection.xp, 0)
        and integer(selection.crateRarity, 0) and integer(selection.firstClearRarity, 0)
        and type(selection.mostWanted) == "boolean"
end

local encounterFields = {"confirmedLimitsEnabled", "maxConfirmedHits", "maxConfirmedStamina",
    "confirmationDelayEnabled", "confirmationDelay", "confirmedHitsBefore", "confirmedStaminaBefore", "confirmationReadyAt"}
local function validEncounter(intent, before)
    local has = false
    for _, field in ipairs(encounterFields) do if intent[field] ~= nil then has = true end end
    if not has then return true end
    if type(intent.confirmedLimitsEnabled) ~= "boolean" or type(intent.confirmationDelayEnabled) ~= "boolean"
        or not finite(intent.maxConfirmedHits, 1) or intent.maxConfirmedHits > 100000
        or not finite(intent.maxConfirmedStamina, 1) or intent.maxConfirmedStamina > 100000
        or not finite(intent.confirmationDelay, 5) or intent.confirmationDelay > 120
        or not integer(intent.confirmedHitsBefore, 0) or not integer(intent.confirmedStaminaBefore, 0)
        or not finite(intent.confirmationReadyAt, 0) then return false end
    local proof = before.bossEncounterProof
    if type(proof) ~= "table" or proof.account ~= before.account or proof.session ~= before.session
        or proof.capturedAt ~= before.capturedAt or proof.day ~= intent.dayStamp or proof.best ~= intent.bestBefore
        or proof.readyAt ~= intent.confirmationReadyAt or type(proof.counts) ~= "table" then return false end
    local row = proof.counts[tostring(intent.stage)]
    local hits, stamina = 0, 0
    if row ~= nil then
        if type(row) ~= "table" or not integer(row.hits, 0) or not integer(row.stamina, 0) then return false end
        hits, stamina = row.hits, row.stamina
    end
    return hits == intent.confirmedHitsBefore and stamina == intent.confirmedStaminaBefore
        and (not intent.confirmedLimitsEnabled or hits < intent.maxConfirmedHits
            and stamina + intent.expectedStaminaCost <= intent.maxConfirmedStamina)
        and (not intent.confirmationDelayEnabled or finite(proof.now, 0) and proof.now >= proof.readyAt)
end

function BossesEvidence.capture(proposal, before)
    local intent = type(proposal) == "table" and proposal.intent
    local selection = selectionOf(intent)
    -- Older saved attacks predate level preferences. Preserve their original
    -- baseline shape; new bounded intents must carry the entire quoted range.
    local hasLevels = type(intent) == "table" and (intent.minLevel ~= nil
        or intent.maxLevel ~= nil or intent.selectedLevel ~= nil
        or intent.limitsEnabled ~= nil)
    if hasLevels and (type(intent.limitsEnabled) ~= "boolean"
        or not integer(intent.minLevel, 1) or intent.minLevel > 1000000
        or not integer(intent.maxLevel, 1) or intent.maxLevel > 1000000
        or not integer(intent.selectedLevel, 1) or intent.selectedLevel > 1000000
        or (intent.limitsEnabled and (intent.minLevel > intent.maxLevel
            or intent.selectedLevel < intent.minLevel
            or intent.selectedLevel > intent.maxLevel))) then
        return nil, "Invalid Boss level range"
    end
    local staminaReserve = type(intent) == "table" and intent.staminaReserve
    if staminaReserve == nil then staminaReserve = 1 end
    local healthFloor = type(intent) == "table" and intent.healthFloor
    if healthFloor == nil then healthFloor = 50 end
    if type(proposal) ~= "table" or proposal.feature ~= "bosses"
        or type(intent) ~= "table"
        or not finite(staminaReserve, 0) or staminaReserve > 1e12
        or not finite(healthFloor, 1) or healthFloor > 100
        or intent.kind ~= "bossStageAttack"
        or not integer(intent.stage, 1)
        or not integer(intent.dayStamp, 0)
        or not finite(intent.serverNow, 0)
        or not integer(intent.bestBefore, 0)
        or not integer(intent.remainingHpBefore, 1)
        or not integer(intent.maxHp, 1)
        or not integer(intent.hitBackMax, 0)
        or not integer(intent.expectedStaminaCost, 1)
        or not integer(intent.hitsBefore, 0)
        or not integer(intent.staminaBefore, 0)
        or not finite(intent.lastServerNowBefore, 0)
        or type(before) ~= "table" or not matching(proposal, before)
        or proposal.revision ~= before.revision then
        return nil, "Boss attack baseline mismatch"
    end
    local native, state, proof, usage, row, hp, done =
        current(before, intent.stage)
    if not validEncounter(intent, before) then return nil, "Boss encounter counters or delay changed" end
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
        or (hasLevels and row.level ~= intent.selectedLevel)
        or (selection ~= nil and not sameReward(selection, row, proof))
        or hp ~= intent.remainingHpBefore
        or proof.staminaCost ~= intent.expectedStaminaCost
        or (state.auto ~= nil and state.auto ~= false)
        or type(native.stats) ~= "table"
        or not integer(native.stats.maxHealth, 1)
        or type(native.pools) ~= "table"
        or not finite(native.pools.health, 0)
        or native.pools.health < row.hitBackMax + native.stats.maxHealth * healthFloor / 100
        or not finite(native.pools.stamina,
            intent.expectedStaminaCost + staminaReserve) then
        return nil, "Selected Boss stage or resources changed"
    end
    return { session = proposal.session, account = proposal.account,
        place = proposal.place, release = proposal.release,
        revision = proposal.revision, stage = intent.stage,
        selectedLevel = hasLevels and intent.selectedLevel or nil,
        selection = selection,
        dayStamp = intent.dayStamp, bestBefore = intent.bestBefore,
        hpBefore = hp, maxHp = row.hp, hitBackMax = row.hitBackMax, catalogKey = proof.catalogKey,
        hitsBefore = usage.hits, staminaBefore = usage.stamina,
        staminaCost = intent.expectedStaminaCost,poolBefore=native.pools.stamina,doneBefore=done,serverNow=native.serverNow }, nil
end

local function reconcile(proposal, beforeHeader, after,
    reply, baseline, restart)
    if type(proposal) ~= "table" or type(beforeHeader) ~= "table"
        or type(after) ~= "table" or type(reply) ~= "table"
        or type(baseline) ~= "table"
        or not matching(proposal, beforeHeader)
        or proposal.account ~= after.account or proposal.place ~= after.place
        or proposal.release ~= after.release
        or (not restart and not matching(proposal, after))
        or not matching(proposal, baseline)
        or proposal.revision ~= baseline.revision
        or beforeHeader.revision ~= baseline.revision
        or not integer(after.revision, 0)
        or not (after.session == baseline.session and after.revision > baseline.revision
            or restart and after.session ~= baseline.session and type(after.native) == "table"
                and finite(baseline.serverNow, 0) and finite(after.native.serverNow, 0)
                and after.native.serverNow > baseline.serverNow)
        or reply.pending==true or reply.code=="pending" or reply.code=="busy"
        or reply.code=="rate_limited" or reply.code=="presence" then
        return "pending"
    end
    local native, state, proof, usage, row, hp, done =
        current(after, baseline.stage)
    if not native or not finite(baseline.serverNow, 0) or native.serverNow < baseline.serverNow
        or (baseline.selectedLevel ~= nil and row.level ~= baseline.selectedLevel)
        or (baseline.selection ~= nil and not sameReward(baseline.selection, row, proof))
        or row.hitBackMax ~= baseline.hitBackMax or proof.staminaCost ~= baseline.staminaCost
        or proof.catalogKey ~= baseline.catalogKey then return "pending" end
    local advanced = usage.day == baseline.dayStamp
        and usage.hits == baseline.hitsBefore + 1
        and usage.stamina == baseline.staminaBefore
            + baseline.staminaCost
        and row.hp == baseline.maxHp
        and state.best >= baseline.bestBefore
        and (hp < baseline.hpBefore or done == true)
    if reply.ok==false then
        local pool=type(native.pools)=="table" and native.pools.stamina
        return not advanced and usage.day==baseline.dayStamp and hp==baseline.hpBefore and done==baseline.doneBefore
            and row.hp==baseline.maxHp and state.best==baseline.bestBefore and pool==baseline.poolBefore
            and native.serverNow>=baseline.serverNow and "rejected" or "pending"
    end
    if reply.ok == true and advanced then return "confirmed" end
    return "pending"
end

function BossesEvidence.evaluate(proposal, before, after, reply, baseline)
    return reconcile(proposal, before, after, reply, baseline, false)
end

local function equal(a, b)
    if type(a) ~= type(b) then return false end
    if type(a) ~= "table" then return a == b end
    for k, v in pairs(a) do if not equal(v, b[k]) then return false end end
    for k in pairs(b) do if a[k] == nil then return false end end
    return true
end

function BossesEvidence.recoverSaved(data, after)
    if type(data) ~= "table" or type(data.reply) ~= "table" then return nil end
    local baseline = BossesEvidence.capture(data.proposal, data.before)
    if not baseline or not equal(baseline, data.baseline) then return nil end
    local result = reconcile(data.proposal, data.before, after, data.reply, baseline, true)
    return (result == "confirmed" or result == "rejected") and result or nil
end

function BossesEvidence.canDispatch(proposal, snapshot)
    local intent = type(proposal) == "table" and proposal.intent
    if type(snapshot) ~= "table" or type(intent) ~= "table" then return false end
    local before = {}
    for key, value in pairs(snapshot) do before[key] = value end
    -- Original counters were admitted and persisted by Checkpoint.Save. They
    -- are used only to recheck the current native controller/resources/quote.
    before.bossUsageProof = { account = proposal.account, capturedAt = snapshot.capturedAt,
        day = intent.dayStamp, hits = intent.hitsBefore, stamina = intent.staminaBefore,
        lastServerNow = intent.lastServerNowBefore }
    return BossesEvidence.capture(proposal, before) ~= nil
end

return BossesEvidence
