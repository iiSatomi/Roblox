-- Nine reviewed player consumables copied behind a release/source key.
local NativeRestorativeCatalog = {}
local Methods = {}
Methods.__index = Methods

local expected = {
    { "con_bandages", "health", 25 },
    { "con_medkit_small", "health", 50 },
    { "con_medkit_large", "health", 100 },
    { "con_energy_small", "energy", 25 },
    { "con_energy", "energy", 50 },
    { "con_energy_pack", "energy", 100 },
    { "con_peanuts", "stamina", 25 },
    { "con_sandwich", "stamina", 50 },
    { "con_lunchbox", "stamina", 100 },
}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value < math.huge and value >= minimum and value % 1 == 0
end

function NativeRestorativeCatalog.new(gameData, config,
    fingerprint, release)
    assert(type(gameData) == "table"
        and type(gameData.ITEMS_BY_ID) == "table"
        and type(config) == "table"
        and type(config.CONSUMABLES) == "table"
        and integer(config.CONSUMABLES.cooldownSeconds, 1)
        and type(fingerprint) == "string" and #fingerprint == 64
        and fingerprint:match("^[%x]+$")
        and type(release) == "string" and #release > 0,
        "Missing reviewed Inventory restorative source")
    local items = {}
    for _, spec in ipairs(expected) do
        local id, pool, percent = spec[1], spec[2], spec[3]
        local item = gameData.ITEMS_BY_ID[id]
        assert(type(item) == "table" and item.id == id
            and item.kind == "consumable"
            and type(item.restore) == "table"
            and item.restore.pool == pool
            and item.restore.percent == percent,
            "Changed native restorative item")
        items[#items + 1] = { id = id, pool = pool,
            percent = percent }
    end
    return setmetatable({ release = release,
        key = fingerprint:lower(), items = items,
        cooldown = config.CONSUMABLES.cooldownSeconds }, Methods)
end

function Methods:Enrich(snapshot)
    if type(snapshot) ~= "table" or snapshot.release ~= self.release
        or type(snapshot.native) ~= "table"
        or snapshot.native.fullSync ~= true then
        return nil, "Restoratives need a matching full Sync"
    end
    local result, items = {}, {}
    for key, value in pairs(snapshot) do result[key] = value end
    for index, row in ipairs(self.items) do
        items[index] = { id = row.id, pool = row.pool,
            percent = row.percent }
    end
    result.restorativeCatalog = { release = self.release,
        catalogKey = self.key, cooldown = self.cooldown,
        items = items }
    return result, nil
end

return NativeRestorativeCatalog
