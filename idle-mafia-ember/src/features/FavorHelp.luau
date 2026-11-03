-- Separately enabled ordinary help, capped by durable send attempts.
local FavorHelp = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge and value % 1 == 0
end

local function timestamp(value)
    return type(value) == "number" and value == value
        and value >= 0 and value < math.huge
end

local function rowId(value)
    return (type(value) == "string" and #value > 0)
        or integer(value, 1)
end

local function better(row, best, policy, score, bestScore)
    if not best then return true end
    if policy == "Best reward" then
        if row.rewardCash ~= best.rewardCash then
            return row.rewardCash > best.rewardCash end
        if row.rewardXp ~= best.rewardXp then
            return row.rewardXp > best.rewardXp end
    elseif score ~= bestScore then return score > bestScore end
    if row.endsAt ~= best.endsAt then return row.endsAt < best.endsAt end
    if policy == "Best reward" then
        return (type(row.id) .. tostring(row.id))
            < (type(best.id) .. tostring(best.id))
    end
    -- Equal textual IDs keep the first row without changing native identity.
    return tostring(row.id) < tostring(best.id)
end

function FavorHelp.propose(view, settings, reservations)
    if type(view) ~= "table" or type(settings) ~= "table"
        or type(reservations) ~= "table" then
        return nil, "Missing Favor planning input"
    end
    if settings.enabled ~= true then return nil, "Favor help disabled" end
    local policy = settings.policy
    if policy ~= "Best reward" and policy ~= "Highest tier"
        and policy ~= "Balanced" and policy ~= "Cash reward"
        and policy ~= "XP reward" and policy ~= "Ending soon" then
        return nil, "Invalid Favor policy"
    end
    local floor = settings.energyReserve or 0
    if not integer(floor, 0) or floor > 1000000000000 then return nil, "Invalid shared energy reserve" end
    local custom = type(settings.custom) == "table"
        and settings.custom or settings
    local minRewardCash, minRewardXp = custom.minRewardCash, custom.minRewardXp
    if minRewardCash == nil then minRewardCash = 0 end
    if minRewardXp == nil then minRewardXp = 0 end
    if not timestamp(minRewardCash) or minRewardCash > 1000000000000000
        or not timestamp(minRewardXp) or minRewardXp > 1000000000000000
        or not integer(custom.maxDailyAttempts, 1)
        or custom.maxDailyAttempts > 100
        or not integer(custom.minFavorReserve, 0)
        or custom.minFavorReserve > 1000000
        or not integer(custom.minEnergyReserve, 0)
        or custom.minEnergyReserve > 1000000
        or (custom.relations ~= "Friends or Family"
            and custom.relations ~= "Friends only"
            and custom.relations ~= "Family only") then
        return nil, "Favor policy limits required"
    end
    if not timestamp(view.serverNow)
        or not integer(view.serverDay, 0)
        or not integer(view.usageAttempts, 0)
        or not integer(view.favorsLeft, 0)
        or not integer(view.favorCost, 0)
        or not integer(view.energyCost, 0)
        or not integer(view.maxHelps, 1)
        or not integer(view.energy, 0)
        or not integer(view.level, 1)
        or type(view.rows) ~= "table"
        or not integer(reservations.favors or 0, 0)
        or not integer(reservations.uncertainFavors or 0, 0)
        or not integer(reservations.energy or 0, 0)
        or not integer(reservations.uncertainEnergy or 0, 0) then
        return nil, "Current Favor capacity and resource proof required"
    end
    if view.usageAttempts >= custom.maxDailyAttempts then
        return nil, "Daily Favor attempt cap reached"
    end
    if view.favorsLeft - view.favorCost
        - (reservations.favors or 0)
        - (reservations.uncertainFavors or 0)
            < custom.minFavorReserve
        or view.energy - view.energyCost
        - (reservations.energy or 0)
        - (reservations.uncertainEnergy or 0)
            < math.max(custom.minEnergyReserve, floor) then
        return nil, "Favor or energy reserve blocks help"
    end
    local candidates, maxCash, maxXp, maxLevel = {}, 0, 0, 0
    for _, row in ipairs(view.rows) do
        if type(row) == "table" and rowId(row.id)
            and integer(row.ownerId, 1)
            and integer(row.level, 1)
            and integer(row.endsAt, 0)
            and integer(row.helpsUsed, 0)
            and integer(row.sabosUsed, 0)
            and integer(row.rewardCash, 0)
            and integer(row.rewardXp, 0)
            and row.rewardCash >= minRewardCash
            and row.rewardXp >= minRewardXp
            and ((custom.relations == "Friends or Family"
                    and (row.friend == true or row.family == true))
                or (custom.relations == "Friends only"
                    and row.friend == true)
                or (custom.relations == "Family only"
                    and row.family == true))
            and row.level <= view.level
            and row.endsAt > view.serverNow
            and row.sabosUsed == 0
            and row.helpsUsed < view.maxHelps then
            candidates[#candidates + 1] = row
            maxCash = math.max(maxCash, row.rewardCash)
            maxXp = math.max(maxXp, row.rewardXp)
            maxLevel = math.max(maxLevel, row.level)
        end
    end
    local best, bestScore
    for _, row in ipairs(candidates) do
        local score = 0
        if policy == "Cash reward" then score = row.rewardCash
        elseif policy == "XP reward" then score = row.rewardXp
        elseif policy == "Ending soon" then score = -row.endsAt
        elseif policy == "Highest tier" then score = row.level
        elseif policy == "Balanced" then
            score = (maxCash > 0 and row.rewardCash / maxCash or 0)
                + (maxXp > 0 and row.rewardXp / maxXp or 0)
                + (maxLevel > 0 and row.level / maxLevel or 0)
        end
        if better(row, best, policy, score, bestScore) then
            best, bestScore = row, score
        end
    end
    if not best then return nil, "No eligible Favor help" end
    return { session = view.session, account = view.account,
        place = view.place, release = view.release,
        revision = view.revision, feature = "favors",
        actionKey = "favors:" .. view.serverDay .. ":"
            .. type(best.id) .. ":" .. tostring(best.id)
            .. ":" .. best.helpsUsed,
        resources = { favors = view.favorCost,
            energy = view.energyCost },
        intent = { kind = "favorHelp", rowId = best.id,
            heistId = best.heistId, ownerId = best.ownerId,
            helpsBefore = best.helpsUsed,
            favorsBefore = view.favorsLeft,
            expectedFavorCost = view.favorCost,
            expectedEnergyCost = view.energyCost,
            rewardCash = best.rewardCash,
            rewardXp = best.rewardXp,
            serverDay = view.serverDay,
            usageAttemptsBefore = view.usageAttempts,
            maxDailyAttempts = custom.maxDailyAttempts,
            minFavorReserve = custom.minFavorReserve,
            minEnergyReserve = math.max(custom.minEnergyReserve, floor),
            relations = custom.relations,
            needsSequence = true } }, nil
end

return FavorHelp
