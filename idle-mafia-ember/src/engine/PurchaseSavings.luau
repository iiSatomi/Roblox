-- Reserve current cash for enabled purchases before considering a deposit.
local PurchaseSavings = {}

local cashSpenders = {
    heists = true, operations = true, properties = true,
    safehouse = true, shop = true, crewTrain = true,
    crewHire = true,
}

local function integer(value)
    return type(value) == "number" and value == value
        and value >= 0 and value < math.huge and value % 1 == 0
end

local function proof(context, amount)
    return { session = context.session, account = context.account,
        place = context.place, release = context.release,
        revision = context.revision,
        capturedAt = context.capturedAt, amount = amount }
end

function PurchaseSavings.derive(raw, context, settings, features, reserves)
    local native = type(raw) == "table" and raw.native
    if type(context) ~= "table" or type(settings) ~= "table"
        or type(features) ~= "table" or type(reserves) ~= "table"
        or type(native) ~= "table" or native.fullSync ~= true
        or not integer(native.cash)
        or raw.account ~= context.account
        or raw.revision ~= context.revision
        or raw.capturedAt ~= context.capturedAt then
        return nil, "Fresh purchase savings input required"
    end
    local totalCost, maxReserve = 0, 0
    for id in pairs(cashSpenders) do
        local config = settings[id]
        if type(config) == "table" and config.enabled == true then
            local spec = features[id]
            if type(spec) ~= "table" or type(spec.reader) ~= "table"
                or type(spec.planner) ~= "table" then
                return proof(context, native.cash), nil
            end
            local readOk, view = pcall(spec.reader.read, raw, context)
            if not readOk or type(view) ~= "table" then
                return proof(context, native.cash), nil
            end
            local planOk, proposal = pcall(spec.planner.propose,
                view, config, reserves)
            local cost = planOk and type(proposal) == "table"
                and type(proposal.resources) == "table"
                and proposal.resources.cash
            if not integer(cost) or cost == 0 then
                return proof(context, native.cash), nil
            end
            local custom = type(config.custom) == "table"
                and config.custom or config
            local reserve = custom.cashReserve or 0
            if not integer(reserve) or not integer(cost + reserve) then
                return proof(context, native.cash), nil
            end
            totalCost = math.min(native.cash, totalCost + cost)
            maxReserve = math.max(maxReserve, reserve)
        end
    end
    return proof(context, math.min(native.cash,
        totalCost + maxReserve)), nil
end

return PurchaseSavings
