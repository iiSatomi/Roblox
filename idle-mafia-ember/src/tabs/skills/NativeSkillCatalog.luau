-- Copy saved Config.LEVEL allocation costs into a matching full Sync.
local NativeSkillCatalog = {}
local Methods = {}
Methods.__index = Methods

local stats = { "energy", "stamina", "health",
    "attack", "defense", "property" }
local known = {}
for _, stat in ipairs(stats) do known[stat] = true end

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge and value % 1 == 0
end

local function clone(rows)
    local result = {}
    for stat, row in pairs(rows) do
        result[stat] = { baseCost = row.baseCost,
            costEvery = row.costEvery,
            costMultiplier = row.costMultiplier }
    end
    return result
end

function NativeSkillCatalog.new(config, fingerprint, release)
    local source = type(config) == "table" and config.LEVEL
    source = type(source) == "table" and source.allocation
    assert(type(source) == "table"
        and type(fingerprint) == "string" and #fingerprint == 64
        and fingerprint:match("^[%x]+$")
        and type(release) == "string" and #release > 0,
        "Missing reviewed Skill source")
    local rules = {}
    for stat, row in pairs(source) do
        assert(known[stat] and type(row) == "table"
            and integer(row.baseCost, 1),
            "Invalid saved Skill rule")
    end
    for _, stat in ipairs(stats) do
        local row = source[stat]
        assert(type(row) == "table", "Missing Skill stat")
        if stat == "property" then
            assert(integer(row.costMultiplier, 2),
                "Invalid Property skill multiplier")
        else
            assert(integer(row.costEvery, 1),
                "Invalid Skill cost step")
        end
        rules[stat] = { baseCost = row.baseCost,
            costEvery = stat == "property" and nil or row.costEvery,
            costMultiplier = stat == "property"
                and row.costMultiplier or nil }
    end
    return setmetatable({ rules = rules,
        key = fingerprint:lower(), release = release }, Methods)
end

function Methods:Enrich(snapshot)
    if type(snapshot) ~= "table" or snapshot.release ~= self.release
        or type(snapshot.native) ~= "table"
        or snapshot.native.fullSync ~= true then
        return nil, "Skills need a matching full Sync"
    end
    local result = {}
    for key, value in pairs(snapshot) do result[key] = value end
    result.catalogKey = self.key
    result.skillRules = clone(self.rules)
    return result, nil
end

return NativeSkillCatalog
