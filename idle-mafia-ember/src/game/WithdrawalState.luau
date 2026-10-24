-- Banked balance and an adapter-derived enabled purchase shortfall.
local WithdrawalState = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value < math.huge and value >= minimum and value % 1 == 0
end

function WithdrawalState.read(raw, context)
    if type(raw) ~= "table" or type(context) ~= "table" then
        return nil, "Missing withdrawal state or context"
    end
    for _, field in ipairs({ "session", "account", "place", "release",
        "revision", "capturedAt" }) do
        if raw[field] ~= context[field] then
            return nil, "Withdrawal snapshot header changed"
        end
    end
    local native, request = raw.native, raw.fundingRequest
    if type(native) ~= "table" or native.fullSync ~= true
        or not integer(native.cash, 0) or not integer(native.banked, 0)
        or type(request) ~= "table"
        or request.account ~= context.account
        or request.capturedAt ~= context.capturedAt
        or (request.purpose ~= "operations"
            and request.purpose ~= "safehouse")
        or type(request.purchaseKey) ~= "string"
        or #request.purchaseKey == 0
        or not integer(request.requiredCash, 1) then
        return nil, "Current enabled purchase funding request required"
    end
    return { session = context.session, account = context.account,
        place = context.place, release = context.release,
        revision = context.revision, capturedAt = context.capturedAt,
        cash = native.cash, banked = native.banked,
        purpose = request.purpose, purchaseKey = request.purchaseKey,
        requiredCash = request.requiredCash }, nil
end

return WithdrawalState
