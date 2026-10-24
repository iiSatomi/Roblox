-- Read-only Crew and loose-border custody from one identity-matched full Sync.
local RosterState = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value < math.huge and value >= minimum and value % 1 == 0
end

local function counts(map)
    if type(map) ~= "table" then return false end
    local size = 0
    for key, value in pairs(map) do
        if type(key) ~= "string" or not integer(value, 0) then
            return false
        end
        size = size + 1
        if size > 2048 then return false end
    end
    return true
end

function RosterState.read(raw, context)
    if type(raw) ~= "table" or type(context) ~= "table" then
        return nil, "Missing Crew input"
    end
    for _, field in ipairs({ "session", "account", "place", "release",
        "revision", "capturedAt" }) do
        if raw[field] ~= context[field] then
            return nil, "Crew snapshot header changed"
        end
    end
    local native = raw.native
    local items = context.itemsById
    if type(native) ~= "table" or native.fullSync ~= true
        or type(native.crew) ~= "table"
        or type(items) ~= "table"
        or not counts(native.inventory)
        or not counts(native.inventoryBound) then
        return nil, "Current Crew and inventory proof required"
    end
    local members, wornBorders, seen = {}, {}, {}
    local size = 0
    for index, member in pairs(native.crew) do
        if not integer(index, 1) or index > 32
            or type(member) ~= "table"
            or (index > 1 and ((member.name ~= nil
                and (type(member.name) ~= "string" or #member.name == 0))
                or (member.rarity ~= nil
                    and not integer(member.rarity, 0))))
            or (member.injuredUntil ~= nil
                and not integer(member.injuredUntil, 0)) then
            return nil, "Invalid Crew member"
        end
        size = size + 1
        if size > 32 then return nil, "Too many Crew members" end
        local border = index == 1 and native.equippedBorder or member.border
        if border ~= nil and (type(border) ~= "string"
            or type(items[border]) ~= "table"
            or items[border].kind ~= "border") then
            return nil, "Unknown equipped Crew border"
        end
        if border then wornBorders[border] = (wornBorders[border] or 0) + 1 end
        members[index] = { index = index,
            name = index == 1 and "YOU" or (member.name or
                (member.rolling == true and "ROLLING" or "HENCHMAN")),
            rarity = index == 1 and nil or member.rarity,
            border = border,
            duty = member.duty ~= nil and member.duty ~= false,
            rolling = member.rolling == true,
            training = member.training ~= nil,
            injuredUntil = member.injuredUntil }
        seen[index] = true
    end
    if not seen[1] then return nil, "Player Crew slot missing" end
    local loose = {}
    for id, item in pairs(items) do
        if type(id) == "string" and type(item) == "table"
            and item.kind == "border" then
            local ordinary = native.inventory[id] or 0
            local bound = native.inventoryBound[id] or 0
            if ordinary > 0 or bound > 0 or wornBorders[id] then
                loose[id] = { id = id, ordinary = ordinary,
                    bound = bound, totalLoose = ordinary + bound,
                    worn = wornBorders[id] or 0 }
            end
        end
    end
    return { session = context.session, account = context.account,
        place = context.place, release = context.release,
        revision = context.revision, capturedAt = context.capturedAt,
        members = members, borders = loose }, nil
end

return RosterState
