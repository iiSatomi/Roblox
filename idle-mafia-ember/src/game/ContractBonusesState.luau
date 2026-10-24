-- Earned daily/weekly completion bonuses from fully claimed native rows.
local ContractBonusesState = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value < math.huge and value >= minimum and value % 1 == 0
end

local function tiers(value)
    if type(value) ~= "table" or #value ~= 5 then return false end
    for key, tier in pairs(value) do
        if not integer(key, 1) or key > 5
            or not integer(tier, 1) or tier > 4 then return false end
    end
    for index = 1, 5 do if value[index] == nil then return false end end
    return true
end

local function claimedRows(rows, count, singleton)
    if singleton and type(rows) == "table" and rows.id ~= nil then
        rows, count = { rows }, 1
    end
    if type(rows) ~= "table" or #rows ~= count then return nil end
    local ids, seen, allClaimed = {}, {}, true
    for key in pairs(rows) do
        if not integer(key, 1) or key > count then return nil end
    end
    for index = 1, count do
        local row = rows[index]
        if type(row) ~= "table" or type(row.id) ~= "string"
            or #row.id == 0 or seen[row.id]
            or type(row.claimed) ~= "boolean" then return nil end
        seen[row.id] = true
        ids[index] = row.id
        if not row.claimed then allClaimed = false end
    end
    local signature = tostring(count) .. ":"
    for _, id in ipairs(ids) do
        signature = signature .. #id .. ":" .. id .. ";"
    end
    return signature, allClaimed
end

function ContractBonusesState.read(raw, context)
    if type(raw) ~= "table" or type(context) ~= "table" then
        return nil, "Missing Contract bonus state or context"
    end
    for _, field in ipairs({ "session", "account", "place", "release",
        "revision", "capturedAt" }) do
        if raw[field] ~= context[field] then
            return nil, "Contract bonus snapshot header changed"
        end
    end
    local native = raw.native
    if type(native) ~= "table" or native.fullSync ~= true
        or type(native.contracts) ~= "table"
        or type(native.derived) ~= "table" then
        return nil, "Complete native Contract Sync required"
    end
    local config, bonuses = raw.contractConfig, raw.contractBonusConfig
    if type(config) ~= "table" or not tiers(config.dailyTiers)
        or not tiers(config.weeklyTiers)
        or type(bonuses) ~= "table"
        or type(bonuses.daily) ~= "table"
        or not integer(bonuses.daily.seals, 0)
        or bonuses.daily.energyRefill ~= true
        or type(bonuses.weekly) ~= "table"
        or not integer(bonuses.weekly.seals, 0)
        or type(bonuses.weekly.crate) ~= "string"
        or #bonuses.weekly.crate == 0
        or type(raw.catalogKey) ~= "string" or #raw.catalogKey == 0 then
        return nil, "Current Contract bonus catalog required"
    end
    local now = context.serverNow
    local dayReset, weekReset = native.derived.contractDayReset,
        native.derived.contractWeekReset
    if not integer(now, 0) or native.serverNow ~= now
        or not integer(dayReset, 1) or not integer(weekReset, 1)
        or dayReset - now <= 5 or weekReset - now <= 5 then
        return nil, "Current Contract reset window required"
    end
    local contracts = native.contracts
    local dailyKey, dailyDone = claimedRows(contracts.daily, 5, false)
    local weeklyKey, weeklyDone = claimedRows(contracts.weekly, 5, true)
    if not dailyKey or not weeklyKey
        or (contracts.bonusClaimed ~= nil
            and type(contracts.bonusClaimed) ~= "boolean")
        or (contracts.weeklyBonusClaimed ~= nil
            and type(contracts.weeklyBonusClaimed) ~= "boolean") then
        return nil, "Contract bonus prerequisites incomplete"
    end
    local ready = {}
    if dailyDone and contracts.bonusClaimed ~= true then
        ready[#ready + 1] = { period = "daily", reset = dayReset,
            rewardKind = "energyRefill", rewardSeals = bonuses.daily.seals,
            rowKey = dailyKey }
    end
    if weeklyDone and contracts.weeklyBonusClaimed ~= true then
        ready[#ready + 1] = { period = "weekly", reset = weekReset,
            rewardKind = "crate", rewardSeals = bonuses.weekly.seals,
            rewardItem = bonuses.weekly.crate, rowKey = weeklyKey }
    end
    return { session = context.session, account = context.account,
        place = context.place, release = context.release,
        revision = context.revision, capturedAt = context.capturedAt,
        catalogKey = raw.catalogKey, ready = ready }, nil
end

return ContractBonusesState
