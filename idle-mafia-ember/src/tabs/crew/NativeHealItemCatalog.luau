-- Reviewed health consumables and Crew cooldown copied by release.
local NativeHealItemCatalog = {}
local Methods = {}
Methods.__index = Methods

local ids = { "con_bandages", "con_medkit_small",
    "con_medkit_large" }
local percents = { 25, 50, 100 }

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value < math.huge and value >= minimum and value % 1 == 0
end

function NativeHealItemCatalog.new(gameData, config, fingerprint, release)
    assert(type(gameData) == "table"
        and type(gameData.ITEMS_BY_ID) == "table"
        and type(config) == "table"
        and type(config.TERRITORY) == "table"
        and type(config.CONSUMABLES) == "table"
        and integer(config.TERRITORY.injurySeconds, 1)
        and integer(config.CONSUMABLES.henchmanCooldownSeconds, 1)
        and type(fingerprint) == "string" and #fingerprint == 64
        and fingerprint:match("^[%x]+$")
        and type(release) == "string" and #release > 0,
        "Missing reviewed Crew healing source")
    local items = {}
    for index, id in ipairs(ids) do
        local item = gameData.ITEMS_BY_ID[id]
        assert(type(item) == "table" and item.id == id
            and item.kind == "consumable"
            and type(item.restore) == "table"
            and item.restore.pool == "health"
            and item.restore.percent == percents[index],
            "Changed native Crew healing item")
        items[id] = percents[index]
    end
    return setmetatable({ release = release,
        key = fingerprint:lower(),
        injurySeconds = config.TERRITORY.injurySeconds,
        cooldownSeconds = config.CONSUMABLES.henchmanCooldownSeconds,
        items = items }, Methods)
end

function Methods:Enrich(snapshot)
    if type(snapshot) ~= "table" or snapshot.release ~= self.release
        or type(snapshot.native) ~= "table"
        or snapshot.native.fullSync ~= true then
        return nil, "Crew item healing needs a matching full Sync"
    end
    local result, items = {}, {}
    for key, value in pairs(snapshot) do result[key] = value end
    for key, value in pairs(self.items) do items[key] = value end
    result.healItemCatalog = { release = self.release,
        catalogKey = self.key, injurySeconds = self.injurySeconds,
        cooldownSeconds = self.cooldownSeconds, items = items }
    return result, nil
end

return NativeHealItemCatalog
