-- Saved AutoEquipCrew() contract with exact newer-Sync equipment evidence.
local AutoEquipCrew = {}
local slots = { "weapon", "armor", "vehicle" }

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

local function equipment(raw)
    local native = type(raw) == "table" and raw.native
    local crew = type(native) == "table" and native.crew
    if type(native) ~= "table" or native.fullSync ~= true
        or type(crew) ~= "table" then return nil end
    local result, count = {}, 0
    for index, member in pairs(crew) do
        if not integer(index, 1) or index > 32
            or type(member) ~= "table" then return nil end
        if member.name ~= nil and (type(member.name) ~= "string"
            or #member.name > 64) then return nil end
        count = count + 1
        if count > 32 then return nil end
        local row = { index = index,
            name = member.name, rarity = member.rarity,
            duty = member.duty ~= nil, rolling = member.rolling == true }
        for _, slot in ipairs(slots) do
            local id = member[slot]
            if id ~= nil and (type(id) ~= "string" or #id == 0
                or #id > 128) then
                return nil
            end
            row[slot] = id
        end
        result[index] = row
    end
    if not result[1] then return nil end
    return result
end

local function identitiesEqual(a, b)
    local total = 0
    for index, before in pairs(a) do
        local after = b[index]
        if not after or before.name ~= after.name
            or before.rarity ~= after.rarity
            or before.duty ~= after.duty
            or before.rolling ~= after.rolling then return false end
        total = total + 1
    end
    local afterTotal = 0
    for _ in pairs(b) do afterTotal = afterTotal + 1 end
    return total == afterTotal
end

local function gearChanged(a, b)
    for index, before in pairs(a) do
        local after = b[index]
        for _, slot in ipairs(slots) do
            if before[slot] ~= after[slot] then return true end
        end
    end
    return false
end

local function fingerprint(raw, gear)
    local native = raw.native
    local hash = 17
    local function add(value)
        local token = tostring(value)
        token = #token .. ":" .. token
        for index = 1, #token do
            hash = (hash * 131 + string.byte(token, index)) % 2147483647
        end
    end
    for index = 1, 32 do
        local member = gear[index]
        if member then
            add(index)
            add(member.name or "")
            add(member.rarity or "")
            add(member.duty)
            add(member.rolling)
            for _, slot in ipairs(slots) do add(member[slot] or "") end
        end
    end
    for _, field in ipairs({ "inventory", "inventoryBound" }) do
        local map = native[field]
        if type(map) ~= "table" then return nil end
        local ids = {}
        for id, count in pairs(map) do
            if type(id) ~= "string" or #id > 128
                or not integer(count, 0) then return nil end
            ids[#ids + 1] = id
            if #ids > 2048 then return nil end
        end
        table.sort(ids)
        add(field)
        for _, id in ipairs(ids) do add(id); add(map[id]) end
    end
    return tostring(hash)
end

function AutoEquipCrew.read(raw, context)
    if not same(raw, context) or raw.revision ~= context.revision
        or raw.capturedAt ~= context.capturedAt then
        return nil, "Crew Auto Equip snapshot changed"
    end
    local gear = equipment(raw)
    if not gear then return nil, "Current Crew equipment required" end
    local key = fingerprint(raw, gear)
    if not key then return nil, "Current Crew inventory required" end
    return { session = context.session, account = context.account,
        place = context.place, release = context.release,
        revision = context.revision, capturedAt = context.capturedAt,
        equipment = gear, fingerprint = key }, nil
end

function AutoEquipCrew.propose(view, settings)
    if type(view) ~= "table" or type(settings) ~= "table" then
        return nil, "Missing Crew Auto Equip input"
    end
    if settings.enabled ~= true then return nil, "Crew Auto Equip disabled" end
    if type(view.equipment) ~= "table" or not view.equipment[1]
        or not integer(view.revision, 0)
        or type(view.fingerprint) ~= "string"
        or not same(view, view) then
        return nil, "Invalid Crew Auto Equip view"
    end
    return { session = view.session, account = view.account,
        place = view.place, release = view.release,
        revision = view.revision, feature = "crew",
        actionKey = "crewAutoEquip:" .. view.fingerprint,
        resources = {}, intent = { kind = "crewAutoEquip",
            remote = "AutoEquipCrew", args = {} } }, nil
end

function AutoEquipCrew.capture(proposal, before)
    if type(proposal) ~= "table" or proposal.feature ~= "crew"
        or type(proposal.intent) ~= "table"
        or proposal.intent.kind ~= "crewAutoEquip"
        or not same(proposal, before)
        or proposal.revision ~= before.revision then
        return nil, "Crew Auto Equip baseline changed"
    end
    local gear = equipment(before)
    if not gear then return nil, "Crew Auto Equip baseline unavailable" end
    return { session = proposal.session, account = proposal.account,
        place = proposal.place, release = proposal.release,
        revision = proposal.revision, equipment = gear }, nil
end

function AutoEquipCrew.evaluate(proposal, before, after, reply, baseline)
    if type(proposal) ~= "table" or type(reply) ~= "table"
        or not same(proposal, before) or not same(proposal, after)
        or not same(proposal, baseline)
        or proposal.revision ~= baseline.revision
        or before.revision ~= baseline.revision
        or not integer(after.revision, baseline.revision + 1) then
        return "pending"
    end
    local current = equipment(after)
    if not current or not identitiesEqual(baseline.equipment, current) then
        return "pending"
    end
    if reply.ok == false then return "rejected" end
    if reply.ok ~= true or type(reply.changed) ~= "boolean" then
        return "pending"
    end
    local changed = gearChanged(baseline.equipment, current)
    if changed == reply.changed then return "confirmed" end
    return "pending"
end

return AutoEquipCrew
