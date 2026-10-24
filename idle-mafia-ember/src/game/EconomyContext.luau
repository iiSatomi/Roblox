-- Read-only source-backed decree/Family/bonus quote context.
local EconomyContext = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value < math.huge and value >= minimum and value % 1 == 0
end

local function finite(value, minimum, maximum)
    return type(value) == "number" and value == value
        and value > -math.huge and value < math.huge
        and value >= minimum and value <= maximum
end

local function effective(value, default, exempt)
    if exempt and value > default then return default end
    return value
end

function EconomyContext.read(raw, context)
    if type(raw) ~= "table" or type(context) ~= "table" then
        return nil, "Missing economic state or context"
    end
    for _, field in ipairs({ "session", "account", "place", "release",
        "revision", "capturedAt" }) do
        if raw[field] ~= context[field] then
            return nil, "Economic snapshot header changed"
        end
    end
    local native, proof = raw.native, raw.economyProof
    if type(native) ~= "table" or native.fullSync ~= true
        or type(native.cityId) ~= "string" or #native.cityId == 0
        or type(proof) ~= "table"
        or proof.account ~= context.account
        or proof.capturedAt ~= context.capturedAt
        or proof.city ~= native.cityId
        or not integer(proof.revision, 0)
        or type(proof.familyId) ~= "string"
        or type(proof.rulerId) ~= "string"
        or not integer(proof.shopPct, -25) or proof.shopPct > 25
        or not integer(proof.hirePct, -25) or proof.hirePct > 25
        or not integer(proof.marketPct, 5) or proof.marketPct > 15
        or not finite(proof.territoryShopDiscount, 0, 0.25)
        or not finite(proof.globalShopSale, 0, 0.99) then
        return nil, "Current decree, Family and Shop discount proof required"
    end
    local exempt = #proof.familyId > 0
        and proof.familyId == proof.rulerId
    local shop = effective(proof.shopPct, 0, exempt)
    local hire = effective(proof.hirePct, 0, exempt)
    local market = effective(proof.marketPct, 10, exempt)
    local key = native.cityId .. ":" .. proof.revision .. ":"
        .. #proof.familyId .. ":" .. proof.familyId .. ":"
        .. #proof.rulerId .. ":" .. proof.rulerId .. ":"
        .. shop .. ":" .. hire .. ":" .. market .. ":"
        .. proof.territoryShopDiscount .. ":" .. proof.globalShopSale
    return { session = context.session, account = context.account,
        place = context.place, release = context.release,
        revision = context.revision, capturedAt = context.capturedAt,
        city = native.cityId, decreeRevision = proof.revision,
        quoteKey = key, rulingExempt = exempt,
        shopPct = shop, hirePct = hire, marketPct = market,
        territoryShopDiscount = proof.territoryShopDiscount,
        globalShopSale = proof.globalShopSale }, nil
end

function EconomyContext.shopPrice(view, base)
    if type(view) ~= "table" or not integer(base, 1)
        or not finite(view.territoryShopDiscount, 0, 0.25)
        or not finite(view.globalShopSale, 0, 0.99)
        or not integer(view.shopPct, -25) or view.shopPct > 25 then
        return nil
    end
    local value = base * (1 - view.territoryShopDiscount)
        * (1 - view.globalShopSale) * (100 + view.shopPct) / 100
    return math.max(1, math.floor(value + 0.5))
end

function EconomyContext.hireCost(view, base)
    if type(view) ~= "table" or not integer(base, 1)
        or not integer(view.hirePct, -25) or view.hirePct > 25 then
        return nil
    end
    return math.max(1, math.floor(base * (100 + view.hirePct) / 100 + 0.5))
end

function EconomyContext.marketFee(view, price, permanent)
    if type(view) ~= "table" or not integer(price, 1)
        or type(permanent) ~= "boolean"
        or not integer(view.marketPct, 5) or view.marketPct > 15 then
        return nil
    end
    local permille = view.marketPct * 10
    if permanent then permille = math.floor(permille * 0.7 + 0.5) end
    return math.max(1, math.floor(price * permille / 1000))
end

return EconomyContext
