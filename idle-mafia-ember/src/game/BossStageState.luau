-- Read-only staged city Boss state from a verified native catalog adapter.
local BossStageState = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge and value % 1 == 0
end

local function finite(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge
end

function BossStageState.read(raw, context)
    if type(raw) ~= "table" or type(context) ~= "table" then
        return nil, "Missing Boss state or context"
    end
    for _, field in ipairs({ "session", "account", "place", "release",
        "revision", "capturedAt" }) do
        if raw[field] ~= context[field] then
            return nil, "Boss snapshot header changed"
        end
    end
    local native, proof = raw.native, raw.bossStageProof
    local state = type(native) == "table" and native.bossStage
    local day
    if type(native) == "table" and finite(native.serverNow, 0) then
        local ok, value = pcall(os.date, "!%Y%j",
            math.floor(native.serverNow))
        if ok then day = tonumber(value) end
    end
    if type(native) ~= "table" or native.fullSync ~= true
        or not finite(native.serverNow, 0)
        or context.serverNow ~= native.serverNow
        or not integer(day, 0)
        or not integer(native.level, 1)
        or type(native.stats) ~= "table"
        or not integer(native.stats.maxHealth, 1)
        or type(native.pools) ~= "table"
        or not finite(native.pools.health, 0)
        or native.pools.health > native.stats.maxHealth
        or not finite(native.pools.stamina, 0)
        or type(state) ~= "table"
        or not integer(state.best, 0) or state.best > 100000
        or not integer(state.day, 0)
        or (state.done ~= nil and type(state.done) ~= "table")
        or (state.hp ~= nil and type(state.hp) ~= "table")
        or type(proof) ~= "table" or proof.account ~= context.account
        or proof.capturedAt ~= context.capturedAt
        or not integer(proof.staminaCost, 1)
        or type(proof.stages) ~= "table" then
        return nil, "Current staged Boss proof required"
    end
    local selection = proof.selectionSettings
    if proof.selectionComplete == true and (proof.selectionContract ~= "boss-get-653-v1"
        or type(selection) ~= "table" or not finite(selection.healthFloor, 1)
        or selection.healthFloor > 100 or type(selection.limitsEnabled) ~= "boolean"
        or not integer(selection.minLevel, 1) or selection.minLevel > 1000000
        or not integer(selection.maxLevel, 1) or selection.maxLevel > 1000000
        or (selection.limitsEnabled and selection.minLevel > selection.maxLevel)) then
        return nil, "Invalid complete Boss selection proof"
    end
    local stages, seen = {}, {}
    for _, row in ipairs(proof.stages) do
        if type(row) ~= "table"
            or not integer(row.stage, 1) or row.stage > 100000
            or seen[row.stage]
            or not integer(row.level, 1)
            or not integer(row.hp, 1)
            or not integer(row.hitBackMax, 0) then
            return nil, "Invalid Boss stage catalog"
        end
        if proof.selectionContract ~= nil and (not integer(row.cash, 0)
            or not integer(row.xp, 0) or not integer(row.crateRarity, 0)
            or not integer(row.firstClearRarity, 0) or type(row.mostWanted) ~= "boolean") then
            return nil, "Invalid Boss selection reward quote"
        end
        seen[row.stage] = true
        local key = tostring(row.stage)
        local doneToday = state.day == day
            and type(state.done) == "table"
            and state.done[key] == true or false
        local remaining = type(state.hp) == "table" and state.hp[key]
        if not integer(remaining, 1) or remaining > row.hp then
            remaining = row.hp
        end
        stages[#stages + 1] = {
            stage = row.stage, level = row.level, maxHp = row.hp,
            hitBackMax = row.hitBackMax, remainingHp = remaining,
            cash = row.cash, xp = row.xp, crate = row.crate, firstClearCrate = row.firstClearCrate,
            crateRarity = row.crateRarity, firstClearRarity = row.firstClearRarity, mostWanted = row.mostWanted,
            doneToday = doneToday,
            unlocked = row.stage <= state.best + 1
                and row.level <= native.level and not doneToday,
        }
    end
    if #stages == 0 and proof.selectionComplete ~= true then return nil, "Empty Boss stage catalog" end
    return { status = "known", session = context.session,
        account = context.account, place = context.place,
        release = context.release, revision = context.revision,
        capturedAt = context.capturedAt, serverNow = native.serverNow,
        dayStamp = day, best = state.best, level = native.level,
        health = native.pools.health,
        maxHealth = native.stats.maxHealth,
        stamina = native.pools.stamina,
        staminaCost = proof.staminaCost, stages = stages,
        selectionContract = proof.selectionContract, selectionComplete = proof.selectionComplete,
        selectionReason = proof.selectionReason, selectionSettings = selection }, nil
end

return BossStageState
