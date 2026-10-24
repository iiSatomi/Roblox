-- Pure ordinary Operation start policy. No paid finish or transport path.
local OperationsStart = {}

local function finite(value)
    return type(value) == "number" and value == value
        and value >= 0 and value < math.huge
end

local function identity(view)
    for _, field in ipairs({ "session", "account", "place", "release" }) do
        if type(view[field]) ~= "string" or #view[field] == 0 then return false end
    end
    return true
end

function OperationsStart.propose(view, settings, reservations)
    if type(view) ~= "table" or type(settings) ~= "table"
        or type(reservations) ~= "table" then
        return nil, "Missing Operation planning input"
    end
    if settings.enabled ~= true then return nil, "Operations disabled" end
    local policy = settings.policy
    if policy ~= "Best chest" and policy ~= "Highest tier" then
        return nil, "Operation policy has no verified parameters"
    end
    if not identity(view) or not finite(view.revision)
        or view.revision % 1 ~= 0 or not finite(view.level)
        or not finite(view.respect) or not finite(view.cash)
        or not finite(view.openSlots) or view.openSlots % 1 ~= 0
        or type(view.catalogKey) ~= "string" or #view.catalogKey == 0
        or type(view.operations) ~= "table"
        or not finite(reservations.cash or 0)
        or not finite(reservations.uncertainCash or 0) then
        return nil, "Invalid Operation resource view"
    end
    if view.openSlots < 1 then return nil, "No open Operation slot" end
    local available = view.cash - (reservations.cash or 0)
        - (reservations.uncertainCash or 0)
    local best, bestScore = nil, nil
    for _, operation in ipairs(view.operations) do
        if type(operation) == "table" and type(operation.id) == "string"
            and #operation.id > 0 and finite(operation.cost)
            and finite(operation.level) and finite(operation.respect)
            and (policy == "Highest tier" or finite(operation.chestScore))
            and finite(operation.order)
            and operation.level <= view.level
            and operation.respect <= view.respect
            and operation.cost <= available then
            local score = policy == "Best chest"
                and operation.chestScore or operation.order
            if not best or score > bestScore
                or (score == bestScore and operation.id < best.id) then
                best, bestScore = operation, score
            end
        end
    end
    if not best then return nil, "No unlocked Operation within cash reserve" end
    if policy == "Best chest" and bestScore <= 0 then
        return nil, "No verified chest chance for eligible Operations"
    end
    local key = "operations:" .. #view.catalogKey .. ":" .. view.catalogKey
        .. ":" .. #best.id .. ":" .. best.id .. ":" .. view.revision
    return {
        session = view.session, account = view.account,
        place = view.place, release = view.release,
        revision = view.revision, feature = "operations", actionKey = key,
        resources = { cash = best.cost },
        intent = { kind = "operationStart", targetId = best.id,
            expectedCost = best.cost, catalogKey = view.catalogKey },
    }, nil
end

return OperationsStart
