-- Operations-tab quotes and crate odds from reviewed GameData. No calls.
local NativeOperationsCatalog = {}
local Methods = {}
Methods.__index = Methods

local function number(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge
end

local function integer(value, minimum)
    return number(value, minimum) and value % 1 == 0
end

local function dense(value, maximum)
    if type(value) ~= "table" then return nil end
    local length = #value
    if length < 1 or length > maximum then return nil end
    local count = 0
    for key in pairs(value) do
        if not integer(key, 1) or key > length then return nil end
        count = count + 1
    end
    return count == length and length or nil
end

local function copiedCatalog(source, crates)
    local operations, crateCatalog = {}, {}
    local seen = {}
    assert(dense(source, 256), "Invalid Operations source array")
    for index, row in ipairs(source) do
        assert(type(row) == "table" and type(row.id) == "string"
            and #row.id > 0 and #row.id <= 120 and not seen[row.id]
            and integer(row.level or 1, 1)
            and integer(row.respect or 0, 0)
            and number(row.duration, 1)
            and number(row.cost, 0) and number(row.cash, 0)
            and number(row.xp, 0), "Invalid saved Operation")
        seen[row.id] = true
        local item = { id = row.id, level = row.level,
            respect = row.respect, duration = row.duration,
            cost = row.cost, cash = row.cash, xp = row.xp }
        for _, fields in ipairs({ { "crate", "crateChance" },
            { "bonusCrate", "bonusCrateChance" } }) do
            local name, chance = fields[1], fields[2]
            local crateId, probability = row[name], row[chance]
            if crateId ~= nil or probability ~= nil then
                assert(type(crateId) == "string" and #crateId > 0
                    and number(probability, 0) and probability <= 1,
                    "Invalid Operation crate chance")
                local crate = type(crates) == "table" and crates[crateId]
                assert(type(crate) == "table"
                    and dense(crate.buckets, 32),
                    "Missing Operation crate odds")
                if not crateCatalog[crateId] then
                    local buckets = {}
                    for bucketIndex, bucket in ipairs(crate.buckets) do
                        assert(type(bucket) == "table"
                            and number(bucket.weight, 0)
                            and bucket.weight > 0
                            and integer(bucket.rarity, 1),
                            "Invalid Operation crate odds")
                        buckets[bucketIndex] = { weight = bucket.weight,
                            rarity = bucket.rarity }
                    end
                    crateCatalog[crateId] = { buckets = buckets }
                end
                item[name], item[chance] = crateId, probability
            end
        end
        operations[index] = item
    end
    return operations, crateCatalog
end

local function clone(source)
    local result = {}
    for key, value in pairs(source) do
        if type(value) == "table" then result[key] = clone(value)
        else result[key] = value end
    end
    return result
end

function NativeOperationsCatalog.new(gameData, fingerprint, release)
    assert(type(gameData) == "table"
        and type(fingerprint) == "string" and #fingerprint == 64
        and fingerprint:match("^[%x]+$") ~= nil
        and type(release) == "string" and #release > 0,
        "Missing reviewed Operations source identity")
    local operations, crates = copiedCatalog(gameData.OPERATIONS,
        gameData.CRATES)
    return setmetatable({ operations = operations, crates = crates,
        catalogKey = string.lower(fingerprint), release = release }, Methods)
end

function Methods:Enrich(snapshot)
    if type(snapshot) ~= "table" or snapshot.release ~= self.release
        or type(snapshot.native) ~= "table"
        or snapshot.native.fullSync ~= true then
        return nil, "Operations need a matching full Sync"
    end
    local result = {}
    for key, value in pairs(snapshot) do result[key] = value end
    result.catalogKey = self.catalogKey
    result.operationCatalog = clone(self.operations)
    result.crateCatalog = clone(self.crates)
    return result, nil
end

return NativeOperationsCatalog
