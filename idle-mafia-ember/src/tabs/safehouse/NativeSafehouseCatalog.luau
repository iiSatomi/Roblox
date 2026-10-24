-- Current reviewed Config.SAFEHOUSE tiers for a matching release.
local NativeSafehouseCatalog = {}
local Methods = {}
Methods.__index = Methods

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge and value % 1 == 0
end

function NativeSafehouseCatalog.new(config, fingerprint, release)
    local source = type(config) == "table" and config.SAFEHOUSE
    assert(type(source) == "table" and #source == 18
        and type(fingerprint) == "string" and #fingerprint == 64
        and fingerprint:match("^[%x]+$")
        and type(release) == "string" and #release > 0,
        "Missing reviewed Safehouse source")
    local rows, lastCost, lastLevel = {}, -1, 0
    local count = 0
    for key in pairs(source) do
        assert(integer(key, 1) and key <= 18,
            "Sparse Safehouse source")
        count = count + 1
    end
    assert(count == 18, "Sparse Safehouse source")
    for index = 1, 18 do
        local row = source[index]
        assert(type(row) == "table" and type(row.name) == "string"
            and #row.name > 0 and integer(row.cost, 0)
            and integer(row.level, 1)
            and type(row.mult) == "number" and row.mult == row.mult
            and row.mult >= 1 and row.mult < math.huge
            and row.cost > lastCost and row.level > lastLevel
            and (index ~= 1 or (row.cost == 0 and row.level == 1)),
            "Invalid Safehouse tier")
        rows[index] = { name = row.name, cost = row.cost,
            level = row.level, mult = row.mult }
        lastCost, lastLevel = row.cost, row.level
    end
    return setmetatable({ rows = rows, key = fingerprint:lower(),
        release = release }, Methods)
end

function Methods:Enrich(snapshot)
    if type(snapshot) ~= "table" or snapshot.release ~= self.release
        or type(snapshot.native) ~= "table"
        or snapshot.native.fullSync ~= true then
        return nil, "Safehouse needs a matching full Sync"
    end
    local rows, result = {}, {}
    for index, row in ipairs(self.rows) do
        rows[index] = { name = row.name, cost = row.cost,
            level = row.level, mult = row.mult }
    end
    for key, value in pairs(snapshot) do result[key] = value end
    result.catalogKey = self.key
    result.safehouseCatalog = rows
    return result, nil
end

return NativeSafehouseCatalog
