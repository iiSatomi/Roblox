-- Cash-only Shop definitions from a reviewed GameData release.
local NativeShopCatalog = {}
local Methods = {}
Methods.__index = Methods

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge and value % 1 == 0
end

function NativeShopCatalog.new(gameData, fingerprint, release)
    assert(type(gameData) == "table" and type(gameData.SHOP) == "table"
        and type(gameData.ITEMS_BY_ID) == "table"
        and type(fingerprint) == "string" and #fingerprint == 64
        and fingerprint:match("^[%x]+$")
        and type(release) == "string" and #release > 0,
        "Missing reviewed Shop source")
    local items, count = {}, 0
    for _, offer in ipairs(gameData.SHOP) do
        assert(type(offer) == "table" and type(offer.item) == "string"
            and #offer.item > 0
            and type(gameData.ITEMS_BY_ID[offer.item]) == "table",
            "Invalid Shop offer")
        if offer.goldPrice == nil
            and not (gameData.ITEMS_BY_ID[offer.item].kind == "crate"
                and gameData.ITEMS_BY_ID[offer.item].paid == true) then
            local item = gameData.ITEMS_BY_ID[offer.item]
            assert(not items[offer.item]
                and integer(offer.price, 1)
                and (offer.priceMax == nil
                    or integer(offer.priceMax, offer.price))
                and (offer.level == nil or integer(offer.level, 1))
                and (offer.limit == nil or integer(offer.limit, 1))
                and type(item.kind) == "string"
                and integer(item.rarity, 1),
                "Invalid cash Shop offer")
            items[offer.item] = { kind = item.kind,
                rarity = item.rarity, level = offer.level or 1,
                limit = offer.limit, base = offer.price,
                ceiling = offer.priceMax or offer.price }
            count = count + 1
        end
    end
    assert(count > 0 and count <= 512, "Invalid cash Shop size")
    return setmetatable({ items = items, key = fingerprint:lower(),
        release = release }, Methods)
end

function Methods:Enrich(snapshot)
    if type(snapshot) ~= "table" or snapshot.release ~= self.release
        or type(snapshot.native) ~= "table"
        or snapshot.native.fullSync ~= true then
        return nil, "Shop needs a matching full Sync"
    end
    local result, offers = {}, {}
    for key, value in pairs(snapshot) do result[key] = value end
    for id, item in pairs(self.items) do
        offers[id] = { kind = item.kind, rarity = item.rarity,
            level = item.level, limit = item.limit,
            base = item.base, ceiling = item.ceiling }
    end
    result.shopCatalog = { key = self.key,
        release = self.release, offers = offers }
    return result, nil
end

return NativeShopCatalog
