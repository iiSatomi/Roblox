-- Exact current cash quotes require an external native stock/price producer.
local ShopState = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge and value % 1 == 0
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
    if type(native) ~= "table" or native.fullSync ~= true
        or not integer(native.level, 1)
        or not integer(native.cash, 0)
        or not integer(native.serverNow, 0)
        or type(native.inventory) ~= "table"
        or type(native.shopBought) ~= "table"
        or type(native.shopRotation) ~= "table"
        or type(native.shopRotation.bought) ~= "table"
        or type(catalog) ~= "table"
        or catalog.release ~= context.release
        or type(catalog.key) ~= "string" or #catalog.key ~= 64
        or type(catalog.offers) ~= "table"
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
        or proof.slot ~= native.shopRotation.slot
        or type(proof.stock) ~= "table"
        or type(proof.quotes) ~= "table" then
        return nil, "Current native Shop stock and cash quotes required"
    end
    local offers, count = {}, 0
    for id, row in pairs(catalog.offers) do
        if type(id) ~= "string" or type(row) ~= "table"
            or not integer(row.level, 1)
            or not integer(row.rarity, 1)
            or not integer(row.base, 1)
            or not integer(row.ceiling, row.base)
            or (row.limit ~= nil and not integer(row.limit, 1))
            or type(row.kind) ~= "string"
            or not integer(native.shopBought[id] or 0, 0)
            or not integer(native.inventory[id] or 0, 0)
            or (proof.stock[id] ~= nil
                and type(proof.stock[id]) ~= "boolean")
            or (native.shopRotation.bought[id] ~= nil
                and type(native.shopRotation.bought[id]) ~= "boolean") then
            return nil, "Invalid Shop offer or custody"
        end
        if proof.stock[id] == true then
            local price = proof.quotes[id]
            if not integer(price, 1) then
                return nil, "Invalid current Shop quote"
            end
            offers[id] = { cost = price, level = row.level,
                kind = row.kind, rarity = row.rarity,
                limit = row.limit, bought = native.shopBought[id] or 0,
                owned = native.inventory[id] or 0,
                rotationBought = native.shopRotation.bought[id] == true }
        end
        count = count + 1
        if count > 512 then return nil, "Shop catalog too large" end
    end
    return { session = context.session, account = context.account,
        place = context.place, release = context.release,
        revision = context.revision, capturedAt = context.capturedAt,
        catalogKey = catalog.key, slot = proof.slot,
        level = native.level, cash = native.cash,
        autoBuy = type(native.autoBuyRules) == "table"
            and native.autoBuyRules.on == true,
        offers = offers }, nil
end

return ShopState
