-- Reviewed Collection tiers and eligible gear/cosmetics by release.
local NativeCollectionCatalog = {}
local Methods = {}
Methods.__index = Methods

local eligible = { weapon = true, armor = true,
    vehicle = true, background = true, border = true }

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value < math.huge and value >= minimum and value % 1 == 0
end

function NativeCollectionCatalog.new(gameData, config,
    fingerprint, release)
    assert(type(gameData) == "table"
        and type(gameData.ITEMS_BY_ID) == "table"
        and type(config) == "table"
        and type(config.COLLECTION) == "table"
        and type(config.COLLECTION.bonusByRarity) == "table"
        and type(config.COLLECTION.tiers) == "table"
        and type(fingerprint) == "string" and #fingerprint == 64
        and fingerprint:match("^[%x]+$")
        and type(release) == "string" and #release > 0,
        "Missing reviewed Collection source")
    local rarity, tiers, items = {}, {}, {}
    for index, value in ipairs(config.COLLECTION.bonusByRarity) do
        assert(integer(value, 1), "Invalid Collection rarity bonus")
        rarity[index] = value
    end
    assert(#rarity >= 1 and #rarity <= 12,
        "Invalid Collection rarity count")
    local lastCount, lastMult = 0, 0
    for index, row in ipairs(config.COLLECTION.tiers) do
        assert(type(row) == "table"
            and integer(row.count, lastCount + 1)
            and integer(row.mult, lastMult + 1),
            "Invalid Collection tier")
        tiers[index] = { count = row.count, mult = row.mult }
        lastCount, lastMult = row.count, row.mult
    end
    assert(#tiers > 0 and #tiers <= 32,
        "Invalid Collection tier count")
    for id, row in pairs(gameData.ITEMS_BY_ID) do
        if type(id) == "string" and type(row) == "table"
            and row.id == id and eligible[row.kind]
            and row.rankOnly ~= true
            and integer(row.rarity, 1)
            and row.rarity <= #rarity
            and type(row.atk) == "number"
            and type(row.def) == "number"
            and not id:find("@", 1, true) then
            items[id] = { kind = row.kind, rarity = row.rarity }
        end
    end
    return setmetatable({ release = release,
        key = fingerprint:lower(), items = items,
        rarity = rarity, tiers = tiers }, Methods)
end

function Methods:Enrich(snapshot)
    if type(snapshot) ~= "table" or snapshot.release ~= self.release
        or type(snapshot.native) ~= "table"
        or snapshot.native.fullSync ~= true then
        return nil, "Collection needs a matching full Sync"
    end
    local result, items, rarity, tiers = {}, {}, {}, {}
    for key, value in pairs(snapshot) do result[key] = value end
    for id, row in pairs(self.items) do
        items[id] = { kind = row.kind, rarity = row.rarity }
    end
    for index, value in ipairs(self.rarity) do rarity[index] = value end
    for index, row in ipairs(self.tiers) do
        tiers[index] = { count = row.count, mult = row.mult }
    end
    result.collectionCatalog = { release = self.release,
        catalogKey = self.key, items = items,
        rarity = rarity, tiers = tiers }
    return result, nil
end

return NativeCollectionCatalog
