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

function NativeTrophyCatalog.new(gameData, fingerprint, release)
    assert(type(gameData) == "table" and type(gameData.ITEMS) == "table"
        and #gameData.ITEMS > 0 and #gameData.ITEMS <= 2048
        and type(gameData.TROPHY_TRADE_INS) == "table"
        and type(fingerprint) == "string" and #fingerprint == 64
        and fingerprint:match("^[%x]+$")
        and type(release) == "string" and #release > 0,
        "Missing reviewed Trophy source")
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
                requiresItems = item.requiresItems == true }
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
            requiresItems = item.requiresItems }
    end
    result.catalogKey = self.key
    result.trophyCatalog = rows
    return result, nil
end

return NativeTrophyCatalog
