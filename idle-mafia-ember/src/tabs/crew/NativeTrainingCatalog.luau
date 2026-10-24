-- Current Config.CREW.training quote, copied behind a reviewed source key.
local NativeTrainingCatalog = {}
local Methods = {}
Methods.__index = Methods

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value < math.huge and value >= minimum and value % 1 == 0
end

local function copyTraining(source)
    assert(type(source) == "table"
        and integer(source.minRarity, 1) and source.minRarity <= 8
        and integer(source.maxLevel, 1) and source.maxLevel <= 10
        and integer(source.maxConcurrent, 1)
        and source.maxConcurrent <= 8
        and type(source.cost) == "table"
        and type(source.minutes) == "table",
        "Invalid native Crew training limits")
    local cost, seconds = {}, {}
    for rarity = source.minRarity, 8 do
        local costs, minutes = source.cost[rarity],
            source.minutes[rarity]
        assert(type(costs) == "table" and type(minutes) == "table"
            and #costs == source.maxLevel
            and #minutes == source.maxLevel,
            "Missing native Crew training tier")
        local copiedCost, copiedSeconds = {}, {}
        for level = 1, source.maxLevel do
            assert(integer(costs[level], 1)
                and integer(minutes[level], 1)
                and minutes[level] <= 7 * 24 * 60,
                "Invalid native Crew training quote")
            copiedCost[level] = costs[level]
            copiedSeconds[level] = minutes[level] * 60
        end
        for key in pairs(costs) do
            assert(integer(key, 1) and key <= source.maxLevel,
                "Sparse native Crew training cost")
        end
        for key in pairs(minutes) do
            assert(integer(key, 1) and key <= source.maxLevel,
                "Sparse native Crew training duration")
        end
        cost[rarity], seconds[rarity] = copiedCost, copiedSeconds
    end
    return { minRarity = source.minRarity,
        maxLevel = source.maxLevel,
        maxConcurrent = source.maxConcurrent,
        cost = cost, seconds = seconds }
end

local function clone(source)
    local result = {}
    for key, value in pairs(source) do
        result[key] = type(value) == "table" and clone(value) or value
    end
    return result
end

function NativeTrainingCatalog.new(config, fingerprint, release)
    assert(type(config) == "table"
        and type(fingerprint) == "string" and #fingerprint == 64
        and fingerprint:match("^[%x]+$") ~= nil
        and type(release) == "string" and #release > 0,
        "Missing reviewed Crew training source identity")
    local crew = config.CREW
    local copied = copyTraining(type(crew) == "table"
        and crew.training)
    copied.catalogKey = string.lower(fingerprint)
    copied.release = release
    return setmetatable({ proof = copied, release = release }, Methods)
end

function Methods:Enrich(snapshot)
    if type(snapshot) ~= "table" or snapshot.release ~= self.release
        or type(snapshot.native) ~= "table"
        or snapshot.native.fullSync ~= true then
        return nil, "Crew training needs a matching full Sync"
    end
    local result = {}
    for key, value in pairs(snapshot) do result[key] = value end
    result.trainingCatalog = clone(self.proof)
    return result, nil
end

return NativeTrainingCatalog
