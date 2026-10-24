-- Explicitly opted-in ordinary sabotage of eligible public Heists.
local Sabotage = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge and value % 1 == 0
end

local function rowId(value)
    return (type(value) == "string" and #value > 0)
        or integer(value, 1)
end

function Sabotage.propose(view, settings, reservations)
    if type(view) ~= "table" or type(settings) ~= "table"
        or type(reservations) ~= "table" then
        return nil, "Missing sabotage planning input"
    end
    if settings.enabled ~= true then return nil, "Sabotage disabled" end
    if not integer(view.serverNow, 0)
        or not integer(view.serverDay, 0)
        or not integer(view.selfId, 1)
        or not integer(view.level, 1)
        or not integer(view.energy, 0)
        or not integer(view.favorsLeft, 0)
        or not integer(view.favorCost, 0)
        or not integer(view.energyCost, 0)
        or not integer(view.maxSabos, 1)
        or not integer(view.usageAttempts, 0)
        or type(view.rows) ~= "table"
        or not integer(reservations.energy or 0, 0)
        or not integer(reservations.uncertainEnergy or 0, 0)
        or not integer(reservations.favors or 0, 0)
        or not integer(reservations.uncertainFavors or 0, 0) then
        return nil, "Current sabotage capacity and resources required"
    end
    if view.usageAttempts >= 5 then
        return nil, "Daily sabotage attempt cap reached"
    end
    if view.favorsLeft - view.favorCost
        - (reservations.favors or 0)
        - (reservations.uncertainFavors or 0) < 5
        or view.energy - view.energyCost
        - (reservations.energy or 0)
        - (reservations.uncertainEnergy or 0) < 10 then
        return nil, "Sabotage resource reserve"
    end
    local chosen
    for _, row in ipairs(view.rows) do
        if type(row) == "table" and rowId(row.id)
            and integer(row.ownerId, 1)
            and row.ownerId ~= view.selfId
            and integer(row.level, 1) and row.level <= view.level
            and integer(row.endsAt, 0)
            and row.endsAt > view.serverNow
            and row.friend == false and row.family == false
            and row.helpsUsed == 0
            and integer(row.sabosUsed, 0)
            and row.sabosUsed < view.maxSabos
            and (not chosen or row.endsAt < chosen.endsAt
                or row.endsAt == chosen.endsAt
                and type(row.id) .. tostring(row.id)
                    < type(chosen.id) .. tostring(chosen.id)) then
            chosen = row
        end
    end
    if not chosen then return nil, "No eligible sabotage row" end
    return { session = view.session, account = view.account,
        place = view.place, release = view.release,
        revision = view.revision, feature = "sabotage",
        actionKey = "sabotage:" .. view.serverDay .. ":"
            .. type(chosen.id) .. ":" .. tostring(chosen.id)
            .. ":" .. chosen.sabosUsed,
        resources = { favors = view.favorCost,
            energy = view.energyCost },
        intent = { kind = "heistSabotage", rowId = chosen.id,
            heistId = chosen.heistId, ownerId = chosen.ownerId,
            selfId = view.selfId, sabosBefore = chosen.sabosUsed,
            favorsBefore = view.favorsLeft,
            expectedFavorCost = view.favorCost,
            expectedEnergyCost = view.energyCost,
            serverDay = view.serverDay,
            usageAttemptsBefore = view.usageAttempts,
            needsSequence = true } }, nil
end

return Sabotage
