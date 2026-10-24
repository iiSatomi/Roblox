-- Separately enabled ordinary help, capped by durable send attempts.
local FavorHelp = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge and value % 1 == 0
end

local function rowId(value)
    return (type(value) == "string" and #value > 0)
        or integer(value, 1)
end

local function better(row, best, policy)
    if not best then return true end
    if policy == "Highest tier" then
        if row.level ~= best.level then return row.level > best.level end
    else
        if row.rewardCash ~= best.rewardCash then
            return row.rewardCash > best.rewardCash end
        if row.rewardXp ~= best.rewardXp then
            return row.rewardXp > best.rewardXp end
    end
    if row.endsAt ~= best.endsAt then return row.endsAt < best.endsAt end
    return (type(row.id) .. tostring(row.id))
        < (type(best.id) .. tostring(best.id))
end

function FavorHelp.propose(view, settings, reservations)
    if type(view) ~= "table" or type(settings) ~= "table"
        or type(reservations) ~= "table" then
        return nil, "Missing Favor planning input"
    end
    if settings.enabled ~= true then return nil, "Favor help disabled" end
    local policy = settings.policy
    if policy ~= "Best reward" and policy ~= "Highest tier" then
        return nil, "Invalid Favor policy"
    end
    if not integer(view.serverNow, 0)
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
    -- Legacy defaults until the simplified Favors controls are mapped.
    if view.usageAttempts >= 5 then
        return nil, "Daily Favor attempt cap reached"
    end
    if view.favorsLeft - view.favorCost
        - (reservations.favors or 0)
        - (reservations.uncertainFavors or 0) < 5
        or view.energy - view.energyCost
        - (reservations.energy or 0)
        - (reservations.uncertainEnergy or 0) < 10 then
        return nil, "Favor or energy reserve blocks help"
    end
    local best
    for _, row in ipairs(view.rows) do
        if type(row) == "table" and rowId(row.id)
            and integer(row.ownerId, 1)
            and integer(row.level, 1)
            and integer(row.endsAt, 0)
            and integer(row.helpsUsed, 0)
            and integer(row.sabosUsed, 0)
            and integer(row.rewardCash, 0)
            and integer(row.rewardXp, 0)
            and (row.friend == true or row.family == true)
            and row.level <= view.level
            and row.endsAt > view.serverNow
            and row.sabosUsed == 0
            and row.helpsUsed < view.maxHelps
            and better(row, best, policy) then best = row end
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
            needsSequence = true } }, nil
end

return FavorHelp
