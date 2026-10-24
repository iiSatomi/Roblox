-- Copy reviewed Config.CONTRACTS definitions into a matching full Sync.
local NativeContractCatalog = {}
local Methods = {}
Methods.__index = Methods

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge and value % 1 == 0
end

local function five(rows)
    if type(rows) ~= "table" or #rows ~= 5 then return false end
    for index = 1, 5 do
        if not integer(rows[index], 1) or rows[index] > 4 then
            return false
        end
    end
    for key in pairs(rows) do
        if not integer(key, 1) or key > 5 then return false end
    end
    return true
end

local function copy(rows)
    local result = {}
    for index, row in ipairs(rows) do
        result[index] = { id = row.id, key = row.key }
    end
    return result
end

local function copyTiers(rows)
    local result = {}
    for index = 1, 5 do result[index] = rows[index] end
    return result
end

function NativeContractCatalog.new(config, fingerprint, release)
    local source = type(config) == "table" and config.CONTRACTS
    assert(type(source) == "table" and five(source.DAILY_TIERS)
        and five(source.WEEKLY_TIERS)
        and type(source.TEMPLATES) == "table"
        and #source.TEMPLATES > 0 and #source.TEMPLATES <= 100
        and type(source.BONUS) == "table"
        and type(source.WEEKLY_BONUS) == "table"
        and integer(source.BONUS.seals, 0)
        and source.BONUS.energyRefill == true
        and integer(source.WEEKLY_BONUS.seals, 0)
        and type(source.WEEKLY_BONUS.crate) == "string"
        and #source.WEEKLY_BONUS.crate > 0
        and type(fingerprint) == "string" and #fingerprint == 64
        and fingerprint:match("^[%x]+$")
        and type(release) == "string" and #release > 0,
        "Missing reviewed Contract source")
    local templates, seen = {}, {}
    for index, row in ipairs(source.TEMPLATES) do
        assert(type(row) == "table" and type(row.id) == "string"
            and #row.id > 0 and not seen[row.id]
            and type(row.key) == "string" and #row.key > 0,
            "Invalid Contract template")
        seen[row.id] = true
        templates[index] = { id = row.id, key = row.key }
    end
    for key in pairs(source.TEMPLATES) do
        assert(integer(key, 1) and key <= #source.TEMPLATES,
            "Sparse Contract templates")
    end
    return setmetatable({ release = release,
        catalogKey = string.lower(fingerprint),
        templates = templates,
        dailyTiers = copyTiers(source.DAILY_TIERS),
        weeklyTiers = copyTiers(source.WEEKLY_TIERS),
        dailyBonus = { seals = source.BONUS.seals,
            energyRefill = true },
        weeklyBonus = { seals = source.WEEKLY_BONUS.seals,
            crate = source.WEEKLY_BONUS.crate } }, Methods)
end

function Methods:Enrich(snapshot)
    if type(snapshot) ~= "table" or snapshot.release ~= self.release
        or type(snapshot.native) ~= "table"
        or snapshot.native.fullSync ~= true then
        return nil, "Contracts need a matching full Sync"
    end
    local result = {}
    for key, value in pairs(snapshot) do result[key] = value end
    result.catalogKey = self.catalogKey
    result.contractTemplates = copy(self.templates)
    result.contractConfig = { dailyTiers = copyTiers(self.dailyTiers),
        weeklyTiers = copyTiers(self.weeklyTiers) }
    result.contractBonusConfig = { daily = {
        seals = self.dailyBonus.seals, energyRefill = true },
        weekly = { seals = self.weeklyBonus.seals,
            crate = self.weeklyBonus.crate } }
    return result, nil
end

return NativeContractCatalog
