-- Reviewed Config.CREW.hireTiers, copied for a matching full Sync.
local NativeHireCatalog = {}
local Methods = {}
Methods.__index = Methods

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value < math.huge and value >= minimum and value % 1 == 0
end

function NativeHireCatalog.new(config, fingerprint, release)
    assert(type(config) == "table" and type(config.CREW) == "table"
        and type(config.CREW.hireTiers) == "table"
        and type(fingerprint) == "string" and #fingerprint == 64
        and fingerprint:match("^[%x]+$")
        and type(release) == "string" and #release > 0,
        "Missing reviewed Crew hire source")
    local tiers, count = {}, 0
    for index, row in pairs(config.CREW.hireTiers) do
        assert(integer(index, 1) and index <= 8
            and type(row) == "table" and type(row.id) == "string"
            and row.id:match("^[a-z]+$") and not tiers[row.id]
            and integer(row.cost, 1), "Invalid native Crew hire tier")
        tiers[row.id] = row.cost
        count = count + 1
    end
    assert(count >= 1 and count == #config.CREW.hireTiers,
        "Sparse native Crew hire tiers")
    return setmetatable({ release = release, key = fingerprint:lower(),
        tiers = tiers }, Methods)
end

function Methods:Enrich(snapshot)
    if type(snapshot) ~= "table" or snapshot.release ~= self.release
        or type(snapshot.native) ~= "table"
        or snapshot.native.fullSync ~= true then
        return nil, "Crew hire needs a matching full Sync"
    end
    local result, tiers = {}, {}
    for key, value in pairs(snapshot) do result[key] = value end
    for key, value in pairs(self.tiers) do tiers[key] = value end
    result.hireCatalog = { release = self.release,
        catalogKey = self.key, tiers = tiers }
    return result, nil
end

return NativeHireCatalog
