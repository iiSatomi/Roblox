-- Current derived Contract cash is the only actionable reward quote.
local ContractCashQuote = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge and value % 1 == 0
end

function ContractCashQuote.read(raw, context)
    if type(raw) ~= "table" or type(context) ~= "table" then
        return nil, "Missing Contract quote"
    end
    for _, field in ipairs({ "session", "account", "place", "release",
        "revision", "capturedAt" }) do
        if raw[field] ~= context[field] then
            return nil, "Contract quote snapshot changed"
        end
    end
    local native = raw.native
    local cash = type(native) == "table"
        and type(native.derived) == "table"
        and native.derived.contractCash
    if type(native) ~= "table" or native.fullSync ~= true
        or type(cash) ~= "table" or #cash ~= 4 then
        return nil, "Current derived Contract cash required"
    end
    local copied = {}
    for key, value in pairs(cash) do
        if not integer(key, 1) or key > 4
            or not integer(value, 0) then
            return nil, "Invalid derived Contract cash"
        end
        copied[key] = value
    end
    return { session = context.session, account = context.account,
        place = context.place, release = context.release,
        revision = context.revision, capturedAt = context.capturedAt,
        cashByTier = copied }, nil
end

return ContractCashQuote
