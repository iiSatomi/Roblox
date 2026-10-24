-- Reviewed owned-crate IDs and native batch limit, copied by release.
local NativeCrateCatalog = {}
local Methods = {}
Methods.__index = Methods

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value < math.huge and value >= minimum and value % 1 == 0
end

function NativeCrateCatalog.new(gameData, config,
    fingerprint, release)
    assert(type(gameData) == "table"
        and type(gameData.ITEMS_BY_ID) == "table"
        and type(config) == "table"
        and integer(config.CRATE_BATCH_MAX, 1)
        and config.CRATE_BATCH_MAX <= 100
        and type(fingerprint) == "string" and #fingerprint == 64
        and fingerprint:match("^[%x]+$")
        and type(release) == "string" and #release > 0,
        "Missing reviewed Inventory crate source")
    local crates, size = {}, 0
    for id, item in pairs(gameData.ITEMS_BY_ID) do
        if type(id) == "string" and type(item) == "table"
            and item.id == id and item.kind == "crate" then
            crates[id] = true
            size = size + 1
        end
    end
    assert(size > 0 and size <= 500, "Invalid native crate catalog")
    return setmetatable({ release = release,
        key = fingerprint:lower(),
        batchMax = config.CRATE_BATCH_MAX,
        crates = crates }, Methods)
end

function Methods:Enrich(snapshot)
    if type(snapshot) ~= "table" or snapshot.release ~= self.release
        or type(snapshot.native) ~= "table"
        or snapshot.native.fullSync ~= true then
        return nil, "Crates need a matching full Sync"
    end
    local result, crates = {}, {}
    for key, value in pairs(snapshot) do result[key] = value end
    for id in pairs(self.crates) do crates[id] = true end
    result.ownedCrateCatalog = { release = self.release,
        catalogKey = self.key, batchMax = self.batchMax,
        crates = crates }
    return result, nil
end

return NativeCrateCatalog
