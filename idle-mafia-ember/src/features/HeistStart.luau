-- Offline ordinary personal Heist start selection; transport owns sequence.
local HeistStart = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge and value % 1 == 0
end

local function better(candidate, chosen, policy)
    if not chosen then return true end
    if policy == "Best chest"
        and candidate.crateCount ~= chosen.crateCount then
        return candidate.crateCount > chosen.crateCount
    end
    if candidate.level ~= chosen.level then
        return candidate.level > chosen.level
    end
    if candidate.stake ~= chosen.stake then
        return candidate.stake < chosen.stake
    end
    return candidate.id < chosen.id
end

function HeistStart.propose(view, settings, reservations)
    if type(view) ~= "table" or type(settings) ~= "table"
        or type(reservations) ~= "table" then
        return nil, "Missing Heist planning input"
    end
    if settings.enabled ~= true then return nil, "Heist starts disabled" end
    local policy = settings.policy
    if policy ~= "Best chest" and policy ~= "Highest tier"
        and policy ~= "Custom" then
        return nil, "Invalid Heist selection policy"
    end
    if view.state ~= "idle" then return nil, "Personal Heist board busy" end
    if not integer(view.startsLeft, 1)
        or not integer(view.bustWait, 0) or view.bustWait > 0
        or not integer(view.serverDay, 0)
        or not integer(view.level, 1)
        or not integer(view.cash, 0)
        or not integer(view.energy, 0)
        or type(view.options) ~= "table"
        or type(view.catalogKey) ~= "string" or #view.catalogKey == 0
        or not integer(reservations.cash or 0, 0)
        or not integer(reservations.energy or 0, 0)
        or not integer(reservations.uncertainCash or 0, 0)
        or not integer(reservations.uncertainEnergy or 0, 0) then
        return nil, "Current Heist capacity and resource proof required"
    end
    local cash = view.cash - (reservations.cash or 0)
        - (reservations.uncertainCash or 0)
    local energy = view.energy - (reservations.energy or 0)
        - (reservations.uncertainEnergy or 0)
    local chosen
    for _, row in ipairs(view.options) do
        if type(row) == "table" and type(row.id) == "string"
            and #row.id > 0 and integer(row.level, 1)
            and integer(row.stake, 0) and integer(row.energy, 0)
            and integer(row.crateCount, 0)
            and row.level <= view.level
            and row.stake <= cash and row.energy <= energy
            and better(row, chosen, policy) then chosen = row end
    end
    if not chosen then return nil, "No eligible personal Heist" end
    return { session = view.session, account = view.account,
        place = view.place, release = view.release,
        revision = view.revision, feature = "heists",
        actionKey = "heists:" .. view.serverDay .. ":"
            .. view.startsLeft .. ":" .. #view.catalogKey .. ":"
            .. view.catalogKey .. ":" .. chosen.id,
        resources = { cash = chosen.stake, energy = chosen.energy },
        intent = { kind = "heistStart", heistId = chosen.id,
            expectedStake = chosen.stake,
            expectedEnergy = chosen.energy,
            startsBefore = view.startsLeft,
            serverDay = view.serverDay,
            catalogKey = view.catalogKey,
            needsSequence = true } }, nil
end

return HeistStart
