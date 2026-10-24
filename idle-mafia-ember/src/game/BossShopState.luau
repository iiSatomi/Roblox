-- Read-only Boss Token Shop quotes and item custody.
local BossShopState = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge and value % 1 == 0
end

local function count(map, id)
    if type(map) ~= "table" then return nil end
    local amount = map[id]
    if amount == nil then return 0 end
    if integer(amount, 0) then return amount end
    return nil
end

function BossShopState.read(raw, context)
    if type(raw) ~= "table" or type(context) ~= "table" then
        return nil, "Missing Boss Shop state or context"
    end
    for _, field in ipairs({ "session", "account", "place", "release",
        "revision", "capturedAt" }) do
        if raw[field] ~= context[field] then
            return nil, "Boss Shop snapshot changed"
        end
    end
    local native, proof = raw.native, raw.bossShopProof
    if type(native) ~= "table" or native.fullSync ~= true
        or type(native.inventory) ~= "table"
        or type(native.inventoryBound) ~= "table"
        or type(proof) ~= "table"
        or proof.account ~= context.account
        or proof.capturedAt ~= context.capturedAt
        or type(proof.catalogKey) ~= "string"
        or #proof.catalogKey == 0 or #proof.catalogKey > 120
        or type(proof.items) ~= "table"
        or #proof.items == 0 or #proof.items > 32 then
        return nil, "Current Boss Shop catalog and inventory required"
    end
    local loose = count(native.inventory, "boss_token")
    local bound = count(native.inventoryBound, "boss_token")
    if not loose or not bound then
        return nil, "Invalid Boss Token count"
    end
    local items, seen = {}, {}
    for _, row in ipairs(proof.items) do
        if type(row) ~= "table"
            or type(row.item) ~= "string" or #row.item == 0
            or #row.item > 120 or seen[row.item]
            or (row.kind ~= "gear" and row.kind ~= "crate")
            or not integer(row.price, 1)
            or type(row.unlocked) ~= "boolean" then
            return nil, "Invalid Boss Shop quote"
        end
        local ownedLoose = count(native.inventory, row.item)
        local ownedBound = count(native.inventoryBound, row.item)
        if not ownedLoose or not ownedBound then
            return nil, "Invalid Boss Shop item count"
        end
        seen[row.item] = true
        items[#items + 1] = { item = row.item,
            kind = row.kind, price = row.price,
            unlocked = row.unlocked,
            owned = ownedLoose + ownedBound }
    end
    for key in pairs(proof.items) do
        if type(key) ~= "number" or key % 1 ~= 0
            or key < 1 or key > #items then
            return nil, "Invalid Boss Shop catalog shape"
        end
    end
    return { status = "known", session = context.session,
        account = context.account, place = context.place,
        release = context.release, revision = context.revision,
        capturedAt = context.capturedAt,
        catalogKey = proof.catalogKey,
        tokens = loose + bound, looseTokens = loose,
        boundTokens = bound, items = items }, nil
end

return BossShopState
