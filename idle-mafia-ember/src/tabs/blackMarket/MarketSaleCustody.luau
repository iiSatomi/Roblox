-- Non-sending custody calculation for owned Black Market listings.
local MarketSaleCustody = {}

local function integer(value, low, high)
    return type(value) == "number" and value == value
        and value >= low and value <= high and value % 1 == 0
end

local function text(value)
    return type(value) == "string" and #value > 0
        and #value <= 160
end

local function same(a, b)
    if type(a) ~= "table" or type(b) ~= "table" then return false end
    for _, field in ipairs({ "session", "account", "place", "release",
        "revision", "capturedAt" }) do
        if a[field] ~= b[field] then return false end
    end
    return text(a.session) and text(a.account)
        and text(a.place) and text(a.release)
        and integer(a.revision, 0, 9007199254740991)
        and type(a.capturedAt) == "number"
        and a.capturedAt == a.capturedAt
        and a.capturedAt >= 0 and a.capturedAt < math.huge
end

local function count(map, id)
    if type(map) ~= "table" then return nil end
    local value = map[id]
    if value == nil then value = 0 end
    if not integer(value, 0, 1000000000) then return nil end
    return value
end

local function collectionTotal(native, id)
    local total, rows = 0, 0
    for _, field in ipairs({ "collection", "collectionBound" }) do
        local map = native[field]
        if type(map) ~= "table" then return nil end
        for key, amount in pairs(map) do
            rows = rows + 1
            if rows > 10000 or type(key) ~= "string"
                or not integer(amount, 0, 1000000000) then
                return nil
            end
            if key == id or key:sub(1, #id + 1) == id .. "@" then
                total = total + amount
                if total > 1000000000 then return nil end
            end
        end
    end
    return total
end

local function worn(native, id)
    local crew = native.crew
    if type(crew) ~= "table" or #crew < 1 or #crew > 46 then
        return nil
    end
    local used, rows = 0, 0
    for slot, row in pairs(crew) do
        if not integer(slot, 1, #crew) or type(row) ~= "table" then
            return nil
        end
        rows = rows + 1
        for _, kind in ipairs({ "weapon", "armor", "vehicle" }) do
            if row[kind] ~= nil and type(row[kind]) ~= "string" then
                return nil
            end
            if row[kind] == id then used = used + 1 end
        end
        local border = slot == 1 and native.equippedBorder or row.border
        if border ~= nil and type(border) ~= "string" then return nil end
        if border == id then used = used + 1 end
    end
    if rows ~= #crew then return nil end
    if native.equippedBackground ~= nil
        and type(native.equippedBackground) ~= "string" then
        return nil
    end
    if native.equippedBackground == id then used = used + 1 end
    return used
end

local function checkpoint(tiers, total)
    if type(tiers) ~= "table" or #tiers < 1
        or #tiers > 20 then return nil end
    local previous, result, rows = 0, 0, 0
    for index, tier in ipairs(tiers) do
        if type(tier) ~= "table"
            or not integer(tier.count, previous + 1, 1000000000) then
            return nil
        end
        rows = index
        previous = tier.count
        if total >= previous then result = previous end
    end
    if rows ~= #tiers then return nil end
    for key in pairs(tiers) do
        if not integer(key, 1, rows) then return nil end
    end
    return result
end

function MarketSaleCustody.assess(raw, context, id, item,
    settings, tiers)
    local native = type(raw) == "table" and raw.native
    local proof = type(context) == "table"
        and context.collectionProtection
    if not same(raw, context) or type(native) ~= "table"
        or native.fullSync ~= true or not text(id)
        or id:find("@", 1, true)
        or type(item) ~= "table" or item.id ~= id
        or item.tradable ~= true or not text(item.kind)
        or item.kind == "gold"
        or not integer(item.rarity, 1, 20)
        or type(settings) ~= "table"
        or not integer(settings.keepLoose, 0, 999)
        or not integer(settings.maxQuantity, 1, 999)
        or type(settings.fromCollection) ~= "boolean"
        or type(settings.blockedItems) ~= "table"
        or type(settings.blockedKinds) ~= "table"
        or type(settings.blockedRarities) ~= "table"
        or not same(raw, proof)
        or type(proof.covers) ~= "table"
        or proof.covers.gear ~= true
        or proof.covers.cosmetics ~= true
        or type(proof.protected) ~= "table" then
        return nil, "Current Market sale custody required"
    end
    if settings.blockedItems[id] == true
        or settings.blockedKinds[item.kind] == true
        or settings.blockedRarities[item.rarity] == true
        or settings.blockedRarities[tostring(item.rarity)] == true then
        return nil, "Item excluded from Market sale"
    end
    local loose = count(native.inventory, id)
    local bound = count(native.inventoryBound, id)
    local collected = count(native.collection, id)
    local collectedBound = count(native.collectionBound, id)
    local allCollected = collectionTotal(native, id)
    local protected = proof.protected[id] or 0
    local wornCount = worn(native, id)
    if loose == nil or bound == nil
        or collected == nil or collectedBound == nil
        or allCollected == nil
        or not integer(protected, 0, 1000000000)
        or wornCount == nil then
        return nil, "Market sale inventory or protection invalid"
    end
    if proof.reserved ~= nil and type(proof.reserved) ~= "table" then
        return nil, "Market transaction reservations invalid"
    end
    local held = proof.reserved and proof.reserved[id]
    if held == nil then held = 0 end
    if not integer(held, 0, 1000000000) then
        return nil, "Market transaction reservations invalid"
    end
    -- Future consumption holds are additional to retained equipment/spares.
    local reserved = math.max(settings.keepLoose, wornCount, protected) + held
    local looseSurplus = math.max(0, loose - reserved)
    local floor, collectionSurplus = 0, 0
    if settings.fromCollection then
        floor = checkpoint(tiers, allCollected)
        if floor == nil then
            return nil, "Collection checkpoints unavailable"
        end
        collectionSurplus = math.min(collected,
            math.max(0, allCollected - floor))
    end
    local quantity = math.min(settings.maxQuantity, 999,
        looseSurplus + collectionSurplus)
    if quantity < 1 then return nil, "No unbound Market sale surplus" end
    return { session = raw.session, account = raw.account,
        place = raw.place, release = raw.release,
        revision = raw.revision, capturedAt = raw.capturedAt,
        itemId = id, kind = item.kind, rarity = item.rarity,
        loose = loose, bound = bound,
        collected = collected, collectedBound = collectedBound,
        collectedTotal = allCollected,
        worn = wornCount, reservedLoose = reserved,
        checkpointFloor = floor, collectionSurplus = collectionSurplus,
        quantity = quantity,
        withdraw = math.max(0, quantity - looseSurplus) }, nil
end

return MarketSaleCustody
