-- Reviewed native Trophy/earned-cosmetic catalog; no trade-in is sent.
local NativeTrophyCatalog = {}
local Methods = {}
Methods.__index = Methods

local setClaim = {
    t_fb_medaldiamond = true, t_ashportcase = true,
    t_calderacase = true, t_volkovskcase = true,
    t_jadecase = true, t_sterlingcase = true,
    t_veilmontcase = true, t_vesperacase = true,
    t_exilescase = true, t_heistcase = true,
    t_keystothecity = true,
}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge and value % 1 == 0
end

-- ItemsData descriptions select the city; GameData owns membership and Config owns Gold.
local masteryCities = {t_ashportkey="city_ashport", t_calderaanchor="city_caldera",
    t_volkovskbell="city_volkovsk", t_jadeseal="city_jade", t_charterseal="city_sterling",
    t_gildedledger="city_veilmont", t_eldersignet="city_vespera", t_grudgeledger="city_exiles"}
local function dense(rows, maximum)
    if type(rows) ~= "table" or #rows == 0 or #rows > maximum then return false end
    local count = 0
    for key in pairs(rows) do
        if not integer(key,1) or key > #rows then return false end
        count = count + 1
    end
    return count == #rows
end
local function cloneGoal(goal)
    if not goal then return nil end
    local result = {kind=goal.kind,cityId=goal.cityId,goldTier=goal.goldTier,ids={}}
    for index, id in ipairs(goal.ids) do result.ids[index]=id end
    return result
end
local function masteryTargets(data, config, jobSource)
    local levels = type(config)=="table" and config.MASTERY
    if not dense(levels,20) then return {} end
    local gold, previous = nil, 0
    for index, row in ipairs(levels) do
        if type(row)~="table" or not integer(row.completions,1) or row.completions<=previous then return {} end
        previous=row.completions
        if row.name=="Gold" then if gold then return {} end;gold=index end
    end
    if not gold then return {} end
    if type(jobSource) ~= "table" or type(jobSource.CityMembership) ~= "function" then return {} end
    local mapping = jobSource.CityMembership(data)
    if not mapping then return {} end
    local groups = mapping.groups
    local result={}
    for trophy,city in pairs(masteryCities) do
        if groups[city] and #groups[city]>0 then result[trophy]={kind="mastery",cityId=city,goldTier=gold,ids=groups[city]} end
    end
    return result
end
local function propertyTargets(data)
    if not dense(data.PROPERTIES,128) then return {} end
    local known,ids={},{}
    for _, row in ipairs(data.PROPERTIES) do
        if type(row)~="table" or type(row.id)~="string" or #row.id==0 or #row.id>120 or known[row.id] then return {} end
        known[row.id]=true;ids[#ids+1]=row.id
    end
    local result={t_deedbook={kind="propertyCount",ids=ids}}
    local city=type(data.CITY_PROPERTIES)=="table" and data.CITY_PROPERTIES.city_ashport
    if dense(city,128) then
        local seen={}
        for _,id in ipairs(city) do if not known[id] or seen[id] then return result end;seen[id]=true end
        result.t_brasskeys={kind="property",cityId="city_ashport",ids=city}
    end
    return result
end

function NativeTrophyCatalog.new(gameData, fingerprint, release, config, jobSource)
    assert(type(gameData) == "table" and type(gameData.ITEMS) == "table"
        and #gameData.ITEMS > 0 and #gameData.ITEMS <= 2048
        and type(gameData.TROPHY_TRADE_INS) == "table"
        and type(fingerprint) == "string" and #fingerprint == 64
        and fingerprint:match("^[%x]+$")
        and type(release) == "string" and #release > 0,
        "Missing reviewed Trophy source")
    local goals=masteryTargets(gameData,config,jobSource)
    for id,goal in pairs(propertyTargets(gameData)) do goals[id]=goal end
    local rows, seen = {}, {}
    for key, item in pairs(gameData.ITEMS) do
        assert(integer(key, 1) and key <= #gameData.ITEMS
            and type(item) == "table", "Sparse Trophy item source")
    end
    for _, item in ipairs(gameData.ITEMS) do
        if item.kind == "trophy" or item.kind == "border"
            or item.kind == "background" then
            assert(type(item.id) == "string" and #item.id > 0
                and #item.id <= 120 and not seen[item.id],
                "Invalid Trophy item identity")
            seen[item.id] = true
            rows[#rows + 1] = { id = item.id, kind = item.kind,
                tradeIn = setClaim[item.id] == true
                    or gameData.TROPHY_TRADE_INS[item.id] ~= nil,
                requiresItems = item.requiresItems == true, goal = cloneGoal(goals[item.id]) }
        end
    end
    assert(#rows > 0 and #rows <= 512,
        "Invalid Trophy catalog size")
    return setmetatable({ rows = rows,
        key = fingerprint:lower(), release = release }, Methods)
end

function Methods:Enrich(snapshot)
    if type(snapshot) ~= "table" or snapshot.release ~= self.release
        or type(snapshot.native) ~= "table"
        or snapshot.native.fullSync ~= true then
        return nil, "Trophies need a matching full Sync"
    end
    local result, rows = {}, {}
    for key, value in pairs(snapshot) do result[key] = value end
    for index, item in ipairs(self.rows) do
        rows[index] = { id = item.id, kind = item.kind,
            tradeIn = item.tradeIn,
            requiresItems = item.requiresItems, goal = cloneGoal(item.goal) }
    end
    result.catalogKey = self.key
    result.trophyCatalog = rows
    return result, nil
end

return NativeTrophyCatalog
