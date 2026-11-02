-- Read-only resource and membership facts; no shared spending authority.
local FamilyState = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge and value % 1 == 0
end

local function balance(value)
    return type(value) == "number" and value == value
        and value >= 0 and value < math.huge
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
        or not balance(native.cash)
        or type(native.pools) ~= "table"
        or not integer(native.pools.stamina, 0)
        or type(native.inventory) ~= "table"
        or not integer(native.inventory.gold_bar or 0, 0)
        or type(info) ~= "table"
        or info.id ~= native.family.id
        or not integer(info.level, 1)
        or type(info.perks) ~= "table" then
        return nil, "Current Family identity and resources required"
    end
    local count = 0
    for id, level in pairs(info.perks) do
        if type(id) ~= "string" or #id == 0
            or not integer(level, 0) or level > 25 then
            return nil, "Invalid Family perk info"
        end
        count = count + 1
        if count > 64 then return nil, "Family perk list too large" end
    end
    return { session = context.session, account = context.account,
        place = context.place, release = context.release,
        revision = context.revision, capturedAt = context.capturedAt,
        familyId = info.id, familyLevel = info.level, cash = native.cash,
        stamina = native.pools.stamina,
        gold = native.inventory.gold_bar or 0,
        perks = info.perks }, nil
end

return FamilyState
