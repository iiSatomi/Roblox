-- Read-only native Auto Roll status. Starting remains blocked.
local CrewRollState = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value < math.huge and value >= minimum and value % 1 == 0
end

local function same(a, b)
    if type(a) ~= "table" or type(b) ~= "table" then return false end
    for _, field in ipairs({ "session", "account", "place", "release" }) do
        if type(a[field]) ~= "string" or #a[field] == 0
            or a[field] ~= b[field] then return false end
    end
    return true
end

function CrewRollState.read(raw, context)
    if not same(raw, context) or raw.revision ~= context.revision
        or raw.capturedAt ~= context.capturedAt then
        return nil, "Crew Auto Roll snapshot changed"
    end
    local native = raw.native
    local crew = type(native) == "table" and native.crew
    if type(native) ~= "table" or native.fullSync ~= true
        or type(crew) ~= "table" or #crew < 2
        or #crew > 46 or not integer(native.cash, 0)
        or type(native.derived) ~= "table"
        or type(native.derived.autoRoll) ~= "boolean" then
        return nil, "Current native Crew Auto Roll state required"
    end
    local active, available, count = {}, {}, 0
    for slot, member in pairs(crew) do
        if not integer(slot, 1) or slot > #crew
            or type(member) ~= "table" then
            return nil, "Invalid Crew Auto Roll roster"
        end
        count = count + 1
        if slot > 1 then
            if member.rolling == true then
                active[#active + 1] = slot
            elseif member.rarity == nil and member.duty == nil then
                available[#available + 1] = slot
            end
        end
    end
    if count ~= #crew then return nil, "Sparse Crew Auto Roll roster" end
    table.sort(active)
    table.sort(available)
    return { session = context.session, account = context.account,
        place = context.place, release = context.release,
        revision = context.revision, capturedAt = context.capturedAt,
        passDerived = native.derived.autoRoll,
        activeSlots = active, emptySlots = available,
        cash = native.cash }, nil
end

function CrewRollState.propose(_view, _settings)
    return nil, "Native autoroll spends after start; stop-on-disable and server validation unverified"
end

function CrewRollState.capture()
    return nil, "Crew Auto Roll start is blocked"
end

function CrewRollState.evaluate()
    return "pending"
end

return CrewRollState
