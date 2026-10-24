-- Read-only, adapter-proof-backed effective effects from saved native rules.
local BuffContext = {}

local multipliers = { "xp", "cash", "energy", "stamina", "health",
    "ops", "mastery", "boss", "takedown", "helps" }
local amounts = { "luck", "hire" }
local daily = {
    rush_hour = { ops = 1.25 }, old_habits = { mastery = 1.5 },
    open_season = { boss = 1.25 }, muscle_memory = { takedown = 1.25 },
    open_interviews = { hire = 0.1 }, fresh_shipment = { luck = 0.05 },
    second_wind = { energy = 1.25 }, night_shift = { stamina = 1.25 },
    all_hands = { helps = 2 },
    weekend = { xp = 2, cash = 2, energy = 1.5, stamina = 1.5,
        health = 1.5, luck = 0.1 },
}

local function finite(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge
end

local function knownKey(key)
    for _, candidate in ipairs(multipliers) do
        if candidate == key then return true end
    end
    for _, candidate in ipairs(amounts) do
        if candidate == key then return true end
    end
    return false
end

local function validateEnds(ends)
    if type(ends) ~= "table" then return false end
    for key, value in pairs(ends) do
        if not knownKey(key) or not finite(value, 0) then return false end
    end
    return true
end

local function choose(entry, value, source, endsAt)
    if value > entry.value or (value == entry.value
        and (entry.endsAt == nil or endsAt > entry.endsAt)) then
        entry.value, entry.source, entry.endsAt = value, source, endsAt
    end
end

function BuffContext.read(raw, context)
    if type(raw) ~= "table" or type(context) ~= "table"
        or type(raw.native) ~= "table" or raw.native.fullSync ~= true then
        return nil, "Missing complete buff snapshot"
    end
    local proof = raw.buffProof
    local now = context.serverNow
    if type(proof) ~= "table" or proof.account ~= context.account
        or proof.capturedAt ~= context.capturedAt
        or proof.serverNow ~= now or not finite(now, 0)
        or type(proof.daily) ~= "table"
        or not daily[proof.daily.id]
        or not finite(proof.daily.startsAt, 0)
        or not finite(proof.daily.endsAt, 0)
        or proof.daily.startsAt > now or proof.daily.endsAt <= now
        or not validateEnds(proof.globalEnds)
        or not validateEnds(proof.decreeEnds)
        or type(proof.globalAmounts) ~= "table"
        or not finite(proof.personalXpEnd, 0) then
        return nil, "Current native buff proof required"
    end
    for key, value in pairs(proof.globalAmounts) do
        if (key ~= "luck" and key ~= "hire")
            or not finite(value, 0) or value > 1 then
            return nil, "Invalid global buff amount"
        end
    end

    local result = { session = context.session, account = context.account,
        revision = context.revision, capturedAt = context.capturedAt,
        serverNow = now, dailyId = proof.daily.id,
        dailyEndsAt = proof.daily.endsAt }
    local function one(key, amount)
        local entry = { value = amount and 0 or 1,
            source = "base" }
        local adminEnd = proof.globalEnds[key]
        local decreeEnd = proof.decreeEnds[key]
        if finite(adminEnd, 0) and adminEnd > now then
            local strength = amount and proof.globalAmounts[key] or 2
            if amount and not finite(strength, 0) then
                return nil, "Active global amount missing"
            end
            choose(entry, strength, "global", adminEnd)
        end
        if finite(decreeEnd, 0) and decreeEnd > now then
            local strength = amount and 0.1 or (key == "xp" and 1.25 or 2)
            choose(entry, strength, "decree", decreeEnd)
        end
        local dailyStrength = daily[proof.daily.id][key]
        if dailyStrength then
            choose(entry, dailyStrength, "daily", proof.daily.endsAt)
        end
        if key == "xp" and proof.personalXpEnd > now then
            choose(entry, 2, "personal", proof.personalXpEnd)
        end
        result[key] = entry
        return true
    end
    for _, key in ipairs(multipliers) do one(key, false) end
    for _, key in ipairs(amounts) do
        local ok, reason = one(key, true)
        if not ok then return nil, reason end
    end
    return result, nil
end

return BuffContext
