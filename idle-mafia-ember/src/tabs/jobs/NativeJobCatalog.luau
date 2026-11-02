-- Jobs-tab constants from a reviewed GameData/Config pair. No game calls.
local NativeJobCatalog = {}
local Methods = {}
Methods.__index = Methods

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge
        and value % 1 == 0
end

local function nonnegative(value)
    return type(value) == "number" and value == value
        and value >= 0 and value < math.huge
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
    if count ~= length then return nil end
    return length
end

local function clone(rows)
    local result = {}
    for index, row in ipairs(rows) do
        local item = {}
        for key, value in pairs(row) do item[key] = value end
        result[index] = item
    end
    return result
end

-- Shared with Trophy targets: immutable native tier ranges establish membership.
function NativeJobCatalog.CityMembership(data)
    if type(data) ~= "table" or not dense(data.CITIES, 32) or not dense(data.JOBS, 256) then
        return nil, "Native Job city membership unavailable"
    end
    local result = { groups = {}, byJob = {}, ids = {} }
    local seen, previous = {}, 0
    for index, city in ipairs(data.CITIES) do
        if type(city) ~= "table" or type(city.id) ~= "string" or #city.id == 0 or #city.id > 120
            or seen[city.id] or not integer(city.firstTier, previous + 1) then return nil, "Ambiguous native Job city boundaries" end
        seen[city.id], previous = true, city.firstTier
        result.groups[city.id], result.ids[index] = {}, city.id
    end
    seen = {}
    for _, job in ipairs(data.JOBS) do
        if type(job) ~= "table" or type(job.id) ~= "string" or #job.id == 0 or #job.id > 120
            or seen[job.id] or not integer(job.tier, 1) or job.tier > 100 then return nil, "Invalid native Job city member" end
        local selected
        for _, city in ipairs(data.CITIES) do if job.tier >= city.firstTier then selected = city.id end end
        if not selected then return nil, "Job precedes native city ranges" end
        seen[job.id], result.byJob[job.id] = true, selected
        local ids = result.groups[selected]; ids[#ids + 1] = job.id
    end
    return result, nil
end

function NativeJobCatalog.new(gameData, config, fingerprint, release)
    assert(type(gameData) == "table" and type(config) == "table"
        and type(fingerprint) == "string" and #fingerprint == 64
        and fingerprint:match("^[%x]+$") ~= nil
        and type(release) == "string" and #release > 0,
        "Missing reviewed Jobs source identity")
    local jobCount = dense(gameData.JOBS, 256)
    local masteryCount = dense(config.MASTERY, 20)
    assert(jobCount and masteryCount, "Invalid Jobs source arrays")
    local membership = NativeJobCatalog.CityMembership(gameData)
    local jobs, seen = {}, {}
    for index, row in ipairs(gameData.JOBS) do
        assert(type(row) == "table" and type(row.id) == "string"
            and #row.id > 0 and #row.id <= 120 and not seen[row.id]
            and integer(row.level, 1) and integer(row.energy, 1)
            and nonnegative(row.cash) and nonnegative(row.xp),
            "Invalid saved Job definition")
        seen[row.id] = true
        jobs[index] = { id = row.id, level = row.level,
            energy = row.energy, cash = row.cash, xp = row.xp,
            cityId = membership and membership.byJob[row.id] or nil,
            tier = integer(row.tier, 1) and row.tier <= 100 and row.tier or nil }
    end
    local mastery = {}
    for index, row in ipairs(config.MASTERY) do
        assert(type(row) == "table"
            and integer(row.completions, 1)
            and nonnegative(row.energyDiscount)
            and row.energyDiscount < 1
            and (index == 1
                or row.completions > mastery[index - 1].completions),
            "Invalid saved Mastery definition")
        mastery[index] = { name = type(row.name) == "string" and #row.name > 0 and #row.name <= 80 and row.name or nil,
            completions = row.completions,
            energyDiscount = row.energyDiscount }
    end
    return setmetatable({ jobs = jobs, mastery = mastery, cityIds = membership and membership.ids or nil,
        catalogKey = string.lower(fingerprint), release = release }, Methods)
end

function Methods:Enrich(snapshot)
    if type(snapshot) ~= "table" or snapshot.release ~= self.release
        or type(snapshot.native) ~= "table"
        or snapshot.native.fullSync ~= true then
        return nil, "Jobs need a matching full Sync"
    end
    local result = {}
    for key, value in pairs(snapshot) do result[key] = value end
    result.catalogKey = self.catalogKey
    result.jobCatalog = clone(self.jobs)
    result.masteryRules = clone(self.mastery)
    result.jobCities = nil
    if self.cityIds then
        result.jobCities = {}
        for index, id in ipairs(self.cityIds) do result.jobCities[index] = id end
    end
    return result, nil
end

return NativeJobCatalog
