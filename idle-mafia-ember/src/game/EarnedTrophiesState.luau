-- Ready, non-consuming trophy/cosmetic claims from a complete Sync.
local EarnedTrophiesState = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value < math.huge and value >= minimum and value % 1 == 0
end

local function nonempty(value)
    return type(value) == "string" and #value > 0
end

local function array(value, maximum)
    if type(value) ~= "table" or #value > maximum then return nil end
    local size = #value
    for key in pairs(value) do
        if not integer(key, 1) or key > size then return nil end
    end
    for index = 1, size do if value[index] == nil then return nil end end
    return size
end

local function counts(value)
    if type(value) ~= "table" then return nil end
    for id, count in pairs(value) do
        if not nonempty(id) or not integer(count, 0) then return nil end
    end
    return value
end

function EarnedTrophiesState.read(raw, context)
    if type(raw) ~= "table" or type(context) ~= "table" then
        return nil, "Missing earned Trophy state or context"
    end
    for _, field in ipairs({ "session", "account", "place", "release",
        "revision", "capturedAt" }) do
        if raw[field] ~= context[field] then
            return nil, "Trophy snapshot header changed"
        end
    end
    local native = raw.native
    if type(native) ~= "table" or native.fullSync ~= true
        or type(native.derived) ~= "table" then
        return nil, "Complete native Trophy Sync required"
    end
    local readyCount = array(native.derived.trophyReady, 256)
    local catalogCount = array(raw.trophyCatalog, 512)
    local inventory = counts(native.inventory)
    local bound = counts(native.inventoryBound or {})
    if not readyCount or not catalogCount or catalogCount == 0
        or not inventory or not bound
        or not nonempty(raw.catalogKey) then
        return nil, "Trophy readiness, catalog or ownership incomplete"
    end
    local ready, seenReady = {}, {}
    for _, id in ipairs(native.derived.trophyReady) do
        if not nonempty(id) or seenReady[id] then
            return nil, "Invalid or duplicate ready Trophy"
        end
        ready[id], seenReady[id] = true, true
    end
    local catalog, seenCatalog = {}, {}
    for _, item in ipairs(raw.trophyCatalog) do
        if type(item) ~= "table" or not nonempty(item.id)
            or seenCatalog[item.id]
            or (item.kind ~= "trophy" and item.kind ~= "border"
                and item.kind ~= "background")
            or (item.tradeIn ~= nil and type(item.tradeIn) ~= "boolean")
            or (item.requiresItems ~= nil
                and type(item.requiresItems) ~= "boolean") then
            return nil, "Invalid or duplicate Trophy catalog entry"
        end
        seenCatalog[item.id] = true
        catalog[item.id] = item.tradeIn ~= true
            and item.requiresItems ~= true
    end
    local eligible = {}
    for _, item in ipairs(raw.trophyCatalog) do
        local id = item.id
        if catalog[id] and ready[id]
            and (inventory[id] or 0) + (bound[id] or 0) == 0 then
            eligible[#eligible + 1] = id
        end
    end
    return {
        session = context.session, account = context.account,
        place = context.place, release = context.release,
        revision = context.revision, capturedAt = context.capturedAt,
        catalogKey = raw.catalogKey, eligible = eligible,
    }, nil
end

return EarnedTrophiesState
