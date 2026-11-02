-- Server-derived active holder sources, as displayed by TerritoryBonusDisplay.
local TerritoryBonuses = {}
local caps = { recruitmentLuck = 0.25, crateLuck = 0.25, shopDiscount = 0.25 }
local function number(value, low, high)
    return type(value) == "number" and value == value and value >= low and value <= high
end
local function ids(rows, maximum, seen, total)
    if type(rows) ~= "table" or #rows > maximum then return nil end
    local result, count = {}, 0
    for index, id in pairs(rows) do
        count = count + 1
        total.count = total.count + 1
        if total.count > 200 or type(index) ~= "number" or index % 1 ~= 0
            or index < 1 or index > #rows or type(id) ~= "string"
            or #id == 0 or #id > 120 or seen[id] then return nil end
        seen[id] = true
        result[index] = id
    end
    if count ~= #rows then return nil end
    return result
end
function TerritoryBonuses.read(raw, context)
    if type(raw) ~= "table" or type(context) ~= "table" then return nil, "Current holder bonus snapshot required" end
    for _, field in ipairs({ "session", "account", "place", "release", "revision", "capturedAt" }) do
        if raw[field] ~= context[field] then return nil, "Holder bonus snapshot changed" end
    end
    local native = raw.native
    local source = type(native) == "table" and type(native.derived) == "table"
        and native.derived.territoryBonusSources
    if type(native) ~= "table" or native.fullSync ~= true or type(native.family) ~= "table"
        or native.family.id == nil or type(source) ~= "table" or source.known ~= true
        or source.familyId ~= native.family.id or type(source.kinds) ~= "table" then
        return nil, "Current Family holder bonuses are loading"
    end
    local kinds, count, seen, total = {}, 0, {}, { count = 0 }
    for kind, row in pairs(source.kinds) do
        count = count + 1
        if count > 64 or type(kind) ~= "string" or #kind == 0 or #kind > 80
            or not kind:match("^[%w_]+$")
            or type(row) ~= "table" or not number(row.total, 0, caps[kind] or 10) then
            return nil, "Invalid effective Territory bonus"
        end
        local active = ids(row.active, 2, seen, total)
        local inactive = ids(row.inactive, 200, seen, total)
        if not active or not inactive then return nil, "Invalid active Territory bonus sources" end
        kinds[kind] = { total = row.total, totalPct = row.total * 100,
            active = active, inactive = inactive }
    end
    return { familyId = source.familyId, kinds = kinds, count = count,
        maxActivePerKind = 2, readOnly = true }, nil
end
function TerritoryBonuses.summary(view)
    if type(view) ~= "table" or type(view.kinds) ~= "table" then return "Holder bonuses unavailable" end
    local keys, parts = {}, {}
    for kind in pairs(view.kinds) do keys[#keys + 1] = kind end
    table.sort(keys)
    for index = 1, math.min(#keys, 3) do
        local kind, row = keys[index], view.kinds[keys[index]]
        local percent = string.format("%.2f", row.totalPct):gsub("0+$", ""):gsub("%.$", "")
        parts[#parts + 1] = kind .. " +" .. percent .. "% (" .. #row.active .. "/2 active)"
    end
    if #keys > 3 then parts[#parts + 1] = tostring(#keys - 3) .. " other bonus kinds" end
    return #parts == 0 and "No active Family territory bonuses" or table.concat(parts, "; ")
end
return TerritoryBonuses
