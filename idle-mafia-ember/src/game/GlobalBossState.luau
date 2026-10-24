-- Read-only current event and exact personal run facts.
local GlobalBossState = {}

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

function GlobalBossState.read(raw, context)
    if type(raw) ~= "table" or type(context) ~= "table" then
        return nil, "Missing Global Boss input"
    end
    for _, field in ipairs({ "session", "account", "place", "release",
        "revision", "capturedAt" }) do
        if raw[field] ~= context[field] then
            return nil, "Global Boss snapshot header changed"
        end
    end
    local native, proof, player = raw.native,
        raw.globalBossProof, raw.localUserIdProof
    if type(native) ~= "table" or native.fullSync ~= true
        or not integer(native.serverNow, 0)
        or context.serverNow ~= native.serverNow
        or type(proof) ~= "table"
        or proof.account ~= context.account
        or proof.capturedAt ~= context.capturedAt
        or type(player) ~= "table"
        or player.account ~= context.account
        or player.capturedAt ~= context.capturedAt
        or not integer(player.userId, 1) then
        return nil, "Current Global Boss event and identity proof required"
    end
    local event = proof.event
    if event == nil then
        return { status = "known", phase = "none",
            accessible = false, canAttack = false,
            claimable = false }, nil
    end
    if type(event) ~= "table" or not key(event.id)
        or not integer(event.startAt, 0)
        or not integer(event.endAt, event.startAt + 1)
        or not integer(event.hp, 10000)
        or event.hp > 1000000000000000
        or not finite(event.dmg, 0)
        or (event.status ~= "live" and event.status ~= "settling"
            and event.status ~= "done")
        or (event.testUserId ~= nil
            and not integer(event.testUserId, 1))
        or (event.status == "done"
            and (not integer(event.resultAt, 0)
                or event.resultAt > native.serverNow)) then
        return nil, "Invalid Global Boss event"
    end
    local run = event.id .. "_" .. tostring(event.startAt)
    local mine, mineDamage, mineHits, claimed = native.gb, 0, 0, false
    if type(mine) == "table" and mine.run == run then
        if (mine.dmg ~= nil and not finite(mine.dmg, 0))
            or (mine.hits ~= nil and not integer(mine.hits, 0))
            or (mine.claimed ~= nil
                and type(mine.claimed) ~= "boolean") then
            return nil, "Invalid personal Global Boss run"
        end
        mineDamage = mine.dmg or 0
        mineHits = mine.hits or 0
        claimed = mine.claimed == true
    end
    local now = native.serverNow
    local elapsed = math.max(0, math.min(1,
        (now - event.startAt) / (event.endAt - event.startAt)))
    local remaining = math.max(0,
        event.hp - event.dmg - event.hp * elapsed)
    local accessible = event.testUserId == nil
        or event.testUserId == player.userId
    local phase = event.status
    if phase == "live" then
        if now < event.startAt then phase = "pending"
        elseif now >= event.endAt then phase = "expired"
        elseif remaining <= 0 then phase = "exhausted" end
    end
    local claimable = accessible and phase == "done"
        and mineDamage > 0 and not claimed
        and now - event.resultAt < 604800
    return { status = "known", session = context.session,
        account = context.account, place = context.place,
        release = context.release, revision = context.revision,
        capturedAt = context.capturedAt,
        id = event.id, runKey = run,
        serverNow = now, startAt = event.startAt,
        endAt = event.endAt, resultAt = event.resultAt,
        phase = phase, accessible = accessible,
        canAttack = accessible and phase == "live",
        claimable = claimable,
        maxHp = event.hp, totalDamage = event.dmg,
        remainingHp = remaining,
        mineDamage = mineDamage, mineHits = mineHits,
        claimed = claimed }, nil
end

return GlobalBossState
