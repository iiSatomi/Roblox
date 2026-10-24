-- Read-only native Trophy goal status; no cross-tab action is enabled.
local TrophyFocusState = {}

local routes = {}
local function group(kind, ids)
    for id in ids:gmatch("%S+") do routes[id] = kind end
end
group("mastery", "t_ashportkey t_calderaanchor t_volkovskbell t_jadeseal t_charterseal t_gildedledger t_eldersignet t_grudgeledger")
group("level", "t_streetname t_madering t_capocane t_underboss t_donportrait t_chancellormedal t_summitmedal")
group("property", "t_brasskeys t_deedbook")
group("operations", "t_manifest")
group("banking", "t_vaultdial")
group("combat", "t_knucklecast t_brokenblade t_doorpanel t_respectplaque")
group("family", "t_warbanner t_cornerstone t_citycrest")
group("heist", "t_firstscore t_mastermind t_accomplice t_wrench t_cleangetaway")
group("favor", "t_accomplice")
group("takedownLoot", "t_fb_spyglass t_fb_orrery t_fb_weathervane t_fb_islanddeed t_fb_horn t_fb_crest")
group("bundle", "t_pocketwatch t_founderwatch")
group("shopGold", "t_goldenrat")

local function integer(value)
    return type(value) == "number" and value == value
        and value >= 0 and value < math.huge and value % 1 == 0
end

local function owned(counts, id)
    if type(counts) ~= "table" then return nil end
    local value = counts[id] or 0
    if not integer(value) then return nil end
    return value
end

function TrophyFocusState.read(raw, context)
    if type(raw) ~= "table" or type(context) ~= "table" then
        return nil, "Missing Trophy goal state"
    end
    for _, field in ipairs({ "session", "account", "place", "release",
        "revision", "capturedAt" }) do
        if raw[field] ~= context[field] then
            return nil, "Trophy goal snapshot changed"
        end
    end
    local native = raw.native
    local catalog = raw.trophyCatalog
    if type(native) ~= "table" or native.fullSync ~= true
        or type(native.derived) ~= "table"
        or type(native.derived.trophyReady) ~= "table"
        or #native.derived.trophyReady > 256
        or type(catalog) ~= "table" or #catalog == 0
        or #catalog > 512
        or type(raw.catalogKey) ~= "string"
        or #raw.catalogKey == 0 then
        return nil, "Current Trophy goal catalog required"
    end
    for _, key in ipairs({ "inventory", "inventoryBound",
        "collection", "collectionBound" }) do
        if type(native[key]) ~= "table" then
            return nil, "Trophy ownership custody incomplete"
        end
    end
    local ready = {}
    for key in pairs(native.derived.trophyReady) do
        if not integer(key) or key < 1
            or key > #native.derived.trophyReady then
            return nil, "Sparse ready Trophy list"
        end
    end
    for _, id in ipairs(native.derived.trophyReady) do
        if type(id) ~= "string" or #id == 0 or ready[id] then
            return nil, "Invalid ready Trophy"
        end
        ready[id] = true
    end
    local result = {}
    for key in pairs(catalog) do
        if not integer(key) or key < 1 or key > #catalog then
            return nil, "Sparse Trophy goal catalog"
        end
    end
    for _, item in ipairs(catalog) do
        if type(item) ~= "table" or type(item.id) ~= "string"
            or #item.id == 0 or result[item.id]
            or (item.kind ~= "trophy" and item.kind ~= "border"
                and item.kind ~= "background") then
            return nil, "Invalid Trophy goal catalog"
        end
        local count = 0
        for _, key in ipairs({ "inventory", "inventoryBound",
            "collection", "collectionBound" }) do
            local value = owned(native[key], item.id)
            if not integer(value) then
                return nil, "Invalid Trophy ownership"
            end
            count = count + value
        end
        local status = count > 0 and "owned"
            or item.tradeIn == true and "manualTradeIn"
            or ready[item.id] and "ready" or "notReady"
        result[item.id] = { id = item.id, kind = item.kind,
            route = routes[item.id] or "unsupported",
            status = status }
    end
    return { session = context.session, account = context.account,
        place = context.place, release = context.release,
        revision = context.revision, capturedAt = context.capturedAt,
        catalogKey = raw.catalogKey, byId = result }, nil
end

return TrophyFocusState
