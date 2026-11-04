-- Banked balance and an adapter-derived enabled purchase shortfall.
local WithdrawalState = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value < math.huge and value >= minimum and value % 1 == 0
end

local function balance(value)
    return type(value) == "number" and value == value
        and value < math.huge and value >= 0
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
        or not balance(native.cash) or not balance(native.banked)
        or type(request) ~= "table"
        or request.session ~= context.session
        or request.account ~= context.account
        or request.place ~= context.place
        or request.release ~= context.release
        or request.revision ~= context.revision
        or request.capturedAt ~= context.capturedAt
        or (request.purpose ~= "operations"
            and request.purpose ~= "safehouse"
            and request.purpose ~= "heists"
            and request.purpose ~= "properties" and request.purpose ~= "shop")
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
