-- Fresh cash/bank view with explicit same-snapshot purchase savings.
local BankState = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value < math.huge and value >= minimum and value % 1 == 0
end

function BankState.read(raw, context)
    if type(raw) ~= "table" or type(context) ~= "table" then
        return nil, "Missing Bank state or context"
    end
    for _, field in ipairs({ "session", "account", "place", "release",
        "revision", "capturedAt" }) do
        if raw[field] ~= context[field] then
            return nil, "Bank snapshot header changed"
        end
    end
    local native, config, savings = raw.native, raw.bankConfig,
        raw.purchaseSavings
    if type(native) ~= "table" or native.fullSync ~= true
        or not integer(native.cash, 0) or not integer(native.banked, 0)
        or type(native.derived) ~= "table"
        or type(native.derived.noBankFees) ~= "boolean"
        or type(config) ~= "table"
        or type(config.depositFee) ~= "number"
        or config.depositFee ~= config.depositFee
        or config.depositFee < 0 or config.depositFee > 1
        or type(savings) ~= "table"
        or savings.account ~= context.account
        or savings.session ~= context.session
        or savings.place ~= context.place
        or savings.release ~= context.release
        or savings.revision ~= context.revision
        or savings.capturedAt ~= context.capturedAt
        or not integer(savings.amount, 0) then
        return nil, "Complete Bank balances, fee and savings required"
    end
    return { session = context.session, account = context.account,
        place = context.place, release = context.release,
        revision = context.revision, capturedAt = context.capturedAt,
        cash = native.cash, banked = native.banked,
        savings = savings.amount,
        feeRate = native.derived.noBankFees and 0 or config.depositFee,
        noFee = native.derived.noBankFees }, nil
end

return BankState
