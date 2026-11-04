-- Exact current cash quotes require an external native stock/price producer.
local ShopState = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge and value % 1 == 0
end

local function nonnegative(value)
    return type(value) == "number" and value == value
        and value >= 0 and value < math.huge
end

function ShopState.read(raw, context)
    if type(raw) ~= "table" or type(context) ~= "table" then
        return nil, "Missing Shop state"
    end
    for _, field in ipairs({ "session", "account", "place", "release",
        "revision", "capturedAt" }) do
        if raw[field] ~= context[field] then
            return nil, "Shop snapshot changed"
        end
    end
    local native, catalog, proof = raw.native, raw.shopCatalog,
        raw.shopQuoteProof
    local rotation
    if type(native) == "table" then rotation = native.shopRotation end
    if type(native) ~= "table" or native.fullSync ~= true
        or not integer(native.level, 1)
        or not nonnegative(native.cash)
        or not nonnegative(native.serverNow)
        or type(native.inventory) ~= "table"
        or (native.shopBought ~= nil
            and type(native.shopBought) ~= "table")
        or rotation ~= nil and (type(rotation) ~= "table"
            or not integer(rotation.slot, 0)
            or rotation.slot > math.floor(native.serverNow / 300)
            or rotation.bought ~= nil and type(rotation.bought) ~= "table")
        or type(catalog) ~= "table"
        or catalog.release ~= context.release
        or type(catalog.key) ~= "string" or #catalog.key ~= 64
        or type(catalog.offers) ~= "table"
        or catalog.unlockLevel ~= nil and not integer(catalog.unlockLevel, 0)
        or type(proof) ~= "table"
        or proof.session ~= context.session
        or proof.account ~= context.account
        or proof.place ~= context.place
        or proof.release ~= context.release
        or proof.revision ~= context.revision
        or proof.capturedAt ~= context.capturedAt
        or proof.catalogKey ~= catalog.key
        or not integer(proof.slot, 0)
        or proof.slot ~= math.floor(native.serverNow / 300)
        or native.serverNow % 300 > 295
        or type(proof.stock) ~= "table"
        or type(proof.quotes) ~= "table" then
        return nil, "Current native Shop stock and cash quotes required"
    end
    local rotationBought = rotation and rotation.bought or {}
    local offers, count = {}, 0
    local known, order = {}, nil
    for id in pairs(catalog.offers) do known[id] = true end
    if catalog.knownIds ~= nil then
        if type(catalog.knownIds) ~= "table" then return nil, "Invalid Shop identities" end
        for id, present in pairs(catalog.knownIds) do
            if type(id) ~= "string" or present ~= true then return nil, "Invalid Shop identities" end
            known[id] = true
        end
    end
    if catalog.order ~= nil then
        if type(catalog.order) ~= "table" or #catalog.order > 512 then return nil, "Invalid native Shop order" end
        local seen, size = {}, 0
        order = {}
        for index, id in ipairs(catalog.order) do
            if type(id) ~= "string" or seen[id] or catalog.offers[id] == nil then return nil, "Invalid native Shop order" end
            seen[id], order[index] = true, id
        end
        for index in pairs(catalog.order) do
            if not integer(index, 1) or index > #order then return nil, "Invalid native Shop order" end
            size = size + 1
        end
        for id in pairs(catalog.offers) do if not seen[id] then return nil, "Incomplete native Shop order" end end
        if size ~= #order then return nil, "Invalid native Shop order" end
    end
    for id, row in pairs(catalog.offers) do
        if type(id) ~= "string" or type(row) ~= "table"
            or not integer(row.level, 1)
            or not integer(row.rarity, 1)
            or not integer(row.base, 1)
            or not integer(row.ceiling, row.base)
            or (row.limit ~= nil and not integer(row.limit, 1))
            or type(row.kind) ~= "string"
            or not integer(type(native.shopBought) == "table"
                and (native.shopBought[id] or 0) or 0, 0)
            or not integer(native.inventory[id] or 0, 0)
            or (proof.stock[id] ~= nil
                and type(proof.stock[id]) ~= "boolean")
            or (rotationBought[id] ~= nil
                and type(rotationBought[id]) ~= "boolean") then
            return nil, "Invalid Shop offer or custody"
        end
        if proof.stock[id] == true then
            local price = proof.quotes[id]
            if not integer(price, 1) or price > row.ceiling then
                return nil, "Invalid current Shop quote"
            end
            local total = native.inventory[id] or 0
            for _, origin in ipairs({"inventoryBound", "collection", "collectionBound"}) do
                if type(native[origin]) ~= "table" then total = nil; break end
                local owned = native[origin][id] or 0
                if not integer(owned, 0) then return nil, "Invalid Shop item origin" end
                total = total + owned
            end
            offers[id] = { cost = price, level = row.level, totalOwned = total,
                kind = row.kind, rarity = row.rarity,
                limit = row.limit,
                bought = type(native.shopBought) == "table"
                    and (native.shopBought[id] or 0) or 0,
                owned = native.inventory[id] or 0,
                rotationBought = rotation ~= nil and rotation.slot == proof.slot
                    and rotationBought[id] == true }
        end
        count = count + 1
        if count > 512 then return nil, "Shop catalog too large" end
    end
    local usage
    if raw.shopUsageProof ~= nil then
        local p = raw.shopUsageProof
        if type(p) ~= "table" or not integer(p.attempted, 0) or not integer(p.spent, 0)
            or p.spent > 9007199254740991 or p.attempted > p.spent or p.unknown ~= nil then
            return nil, "Invalid Shop Cash allowance"
        end
        for _, field in ipairs({"session", "account", "place", "release", "revision", "capturedAt"}) do
            if p[field] ~= context[field] then return nil, "Shop Cash allowance changed" end
        end
        usage = {version = 1, attempted = p.attempted, spent = p.spent}
    end
    return { session = context.session, account = context.account,
        place = context.place, release = context.release,
        revision = context.revision, capturedAt = context.capturedAt,
        catalogKey = catalog.key, slot = proof.slot, serverNow = native.serverNow,
        level = native.level, unlockLevel = catalog.unlockLevel or 1, cash = native.cash,
        autoBuy = type(native.autoBuyRules) == "table"
            and native.autoBuyRules.on == true,
        offers = offers, order = order, knownIds = known, usage = usage }, nil
end

return ShopState
