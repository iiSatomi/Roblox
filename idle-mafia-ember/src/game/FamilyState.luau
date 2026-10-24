-- Read-only resource and membership facts; no shared spending authority.
local FamilyState = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge and value % 1 == 0
end

function FamilyState.read(raw, context)
    if type(raw) ~= "table" or type(context) ~= "table" then
        return nil, "Missing Family state"
    end
    for _, field in ipairs({ "session", "account", "place", "release",
        "revision", "capturedAt" }) do
        if raw[field] ~= context[field] then
            return nil, "Family snapshot changed"
        end
    end
    local native, info = raw.native, raw.familyInfo
    if type(native) ~= "table" or native.fullSync ~= true
        or type(native.family) ~= "table"
        or not (type(native.family.id) == "string"
            and #native.family.id > 0
            or integer(native.family.id, 1))
        or not integer(native.cash, 0)
        or type(native.pools) ~= "table"
        or not integer(native.pools.stamina, 0)
        or type(native.inventory) ~= "table"
        or not integer(native.inventory.gold_bar or 0, 0)
        or type(info) ~= "table"
        or info.id ~= native.family.id
        or type(info.perks) ~= "table" then
        return nil, "Current Family identity and resources required"
    end
    return { session = context.session, account = context.account,
        place = context.place, release = context.release,
        revision = context.revision, capturedAt = context.capturedAt,
        familyId = info.id, cash = native.cash,
        stamina = native.pools.stamina,
        gold = native.inventory.gold_bar or 0,
        perks = info.perks }, nil
end

return FamilyState
