-- Reviewed saved Heist quotes; no sequence allocation or game calls.
local NativeHeistCatalog = {}
local Methods = {}
Methods.__index = Methods

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge and value % 1 == 0
end

local function dense(value)
    if type(value) ~= "table" then return false end
    local length, count = #value, 0
    if length < 1 or length > 32 then return false end
    for key in pairs(value) do
        if not integer(key, 1) or key > length then return false end
        count = count + 1
    end
    return count == length
end

local function copy(rows)
    local result = {}
    for index, row in ipairs(rows) do
        result[index] = { id = row.id, level = row.level,
            stake = row.stake, energy = row.energy,
            crateCount = row.crateCount }
    end
    return result
end

function NativeHeistCatalog.new(gameData, fingerprint, release)
    assert(type(gameData) == "table" and dense(gameData.HEISTS)
        and type(fingerprint) == "string" and #fingerprint == 64
        and fingerprint:match("^[%x]+$") ~= nil
        and type(release) == "string" and #release > 0,
        "Missing reviewed Heist source identity")
    local seen, rows = {}, {}
    for index, row in ipairs(gameData.HEISTS) do
        assert(type(row) == "table" and type(row.id) == "string"
            and #row.id > 0 and #row.id <= 120 and not seen[row.id]
            and integer(row.level, 1) and integer(row.stake, 0)
            and integer(row.energy, 0) and integer(row.crateCount, 0),
            "Invalid saved Heist definition")
        seen[row.id] = true
        rows[index] = { id = row.id, level = row.level,
            stake = row.stake, energy = row.energy,
            crateCount = row.crateCount }
    end
    return setmetatable({ rows = rows,
        catalogKey = string.lower(fingerprint), release = release }, Methods)
end

function Methods:Enrich(snapshot)
    if type(snapshot) ~= "table" or snapshot.release ~= self.release
        or type(snapshot.native) ~= "table"
        or snapshot.native.fullSync ~= true then
        return nil, "Heists need a matching full Sync"
    end
    local result = {}
    for key, value in pairs(snapshot) do result[key] = value end
    result.catalogKey = self.catalogKey
    result.heistCatalog = copy(self.rows)
    return result, nil
end

return NativeHeistCatalog
