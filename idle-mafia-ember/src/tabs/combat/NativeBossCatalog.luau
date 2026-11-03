-- Read-only current BossStages quotes bound to one complete native Sync.
local NativeBossCatalog = {}
local Methods = {}
Methods.__index = Methods

local function integer(value, minimum, maximum)
    return type(value) == "number" and value == value
        and value % 1 == 0 and value >= minimum
        and value <= maximum
end

local function validShop(rows)
    if type(rows) ~= "table" or #rows < 1 or #rows > 32 then
        return false
    end
    for _, row in ipairs(rows) do
        if type(row) ~= "table"
            or type(row.item) ~= "string"
            or #row.item < 1 or #row.item > 120
            or not integer(row.price, 1, 1000000000) then
            return false
        end
    end
    return true
end

-- Build 653's reviewed get formula (docs/native-source/2026-11-03).
-- This is a build/function-lifetime contract, not a runtime source decompile.
local CONTRACT = "boss-get-653-v1"
local function equal(a, b)
    if type(a) ~= type(b) then return false end
    if type(a) ~= "table" then return a == b end
    for key, value in pairs(a) do if not equal(value, b[key]) then return false end end
    for key in pairs(b) do if a[key] == nil then return false end end
    return true
end
local function constants(stages)
    local mw, base = stages.MOST_WANTED, stages.MW_BASE
    return type(mw) == "table" and type(base) == "table"
        and stages.MAX_STAGE == 100000 and stages.CITY_STAGES == 32
        and stages.CITY_XP_MULT == 1 and stages.MW_TIER_XP_STEP == .07
        and mw.DON_CRATE == "crate_boss" and mw.DON_HP_MULT == 12
        and mw.HP_MULT == 8 and mw.DEF_GROWTH == 1.04 and mw.LINEAR_GROWTH == .02
        and base.hitBackMin == 32 and base.hitBackMax == 47 and base.xp == 66177.8125
end
local cityFields = {"level", "hp", "def", "hitBackMax", "cash", "xp", "crate", "firstKillCrate"}
local function citySource(data)
    if type(data) ~= "table" or type(data.BOSSES) ~= "table" or #data.BOSSES ~= 32
        or type(data.ITEMS_BY_ID) ~= "table" then return nil end
    local rows, rarities = {}, {}
    local function rarity(id)
        if id == nil then return true end
        if type(id) ~= "string" or #id < 1 or #id > 120 then return false end
        local item = data.ITEMS_BY_ID[id]
        if type(item) ~= "table" or not integer(item.rarity, 0, 1000000) then return false end
        rarities[id] = item.rarity
        return true
    end
    if not rarity("crate_boss") then return nil end
    for i = 1, 32 do
        local row = data.BOSSES[i]
        if type(row) ~= "table" or not integer(row.level, 1, 1000000)
            or not integer(row.hp, 1, 9007199254740991)
            or not integer(row.def, 0, 9007199254740991)
            or not integer(row.hitBackMax, 0, 9007199254740991)
            or not integer(row.cash, 0, 9007199254740991)
            or not integer(row.xp, 0, 9007199254740991)
            or not rarity(row.crate) or not rarity(row.firstKillCrate) then return nil end
        rows[i] = {}
        for _, field in ipairs(cityFields) do rows[i][field] = row[field] end
    end
    return {rows = rows, rarities = rarities}
end
local function reviewed(stages, data, game)
    if game == nil or game.PlaceId ~= 73897506680154 or game.PlaceVersion ~= 653
        or not constants(stages) then return nil end
    return citySource(data)
end
local function expected(source, stage)
    local row = source.rows[stage <= 32 and stage or (stage - 33) % 32 + 1]
    if stage <= 32 then
        return {stage = stage, level = row.level, hp = row.hp, hitBackMax = row.hitBackMax,
            cash = row.cash, xp = math.floor(row.xp + .5), crate = row.crate,
            firstClearCrate = row.firstKillCrate, mostWanted = false}
    end
    local n, last = stage - 32, source.rows[32]
    return {stage = stage, level = last.level,
        hp = math.floor(last.def * 1.04 ^ n + .5) * (row.firstKillCrate and 12 or 8),
        hitBackMax = math.floor(47 * (1 + .02 * n) + .5),
        cash = math.floor(last.cash * 1.04 ^ n + .5),
        xp = math.floor(66177.8125 * (1 + .07 * (1 + (n - 1) / 32)) + .5),
        firstClearCrate = row.firstKillCrate and "crate_boss" or nil, mostWanted = true}
end
local function selectionSettings(settings)
    settings = type(settings) == "table" and settings or {}
    local floor = settings.healthFloor
    if floor == nil then floor = 50 end
    local low, high, enabled = settings.minLevel, settings.maxLevel, settings.limitsEnabled
    if low == nil then low = 1 end
    if high == nil then high = 10000 end
    if enabled == nil then enabled = false end
    if type(floor) ~= "number" or floor ~= floor or floor < 1 or floor > 100
        or type(enabled) ~= "boolean" or not integer(low, 1, 1000000)
        or not integer(high, 1, 1000000) or (enabled and low > high) then return nil end
    local mode = settings.selection or "Current progression"
    local modes = {["Current progression"] = true, Smart = true, ["First undefeated"] = true,
        ["Highest level"] = true, ["Best chest"] = true, ["Cash reward"] = true, ["XP reward"] = true}
    if not modes[mode] then return nil end
    local confirmedEnabled = settings.confirmedLimitsEnabled
    if confirmedEnabled == nil then confirmedEnabled = false end
    local hits, stamina = settings.maxConfirmedHits or 100, settings.maxConfirmedStamina or 100
    if type(confirmedEnabled) ~= "boolean" or type(hits) ~= "number" or hits ~= hits or hits < 1 or hits > 100000
        or type(stamina) ~= "number" or stamina ~= stamina or stamina < 1 or stamina > 100000 then return nil end
    return {confirmedLimitsEnabled = confirmedEnabled, maxConfirmedHits = hits, maxConfirmedStamina = stamina, healthFloor = floor, minLevel = low, maxLevel = high, limitsEnabled = enabled, selection = mode}
end
local function candidates(native, state, day, settings, excluded)
    if type(native.pools) ~= "table" or type(native.pools.health) ~= "number"
        or native.pools.health ~= native.pools.health or native.pools.health < 0
        or type(native.stats) ~= "table" or not integer(native.stats.maxHealth, 1, 9007199254740991)
        or native.pools.health > native.stats.maxHealth then return nil end
    local selected, seen = {}, {}
    local function add(stage)
        if stage and not seen[stage] then selected[#selected + 1] = stage; seen[stage] = true end
    end
    local last = math.min(state.best + 1, 100000)
    for stage = 1, math.min(last, 32) do add(stage) end
    add(last)
    -- Every MW repeat has the same level and no repeat Cash/crate. Its
    -- hit-back and XP are monotone under the reviewed positive constants.
    local lo, hi, limit = 33, state.best, 32
    while lo <= hi do
        local middle = math.floor((lo + hi) / 2)
        local hitBack = math.floor(47 * (1 + .02 * (middle - 32)) + .5)
        if native.pools.health >= hitBack + native.stats.maxHealth * settings.healthFloor / 100 then
            limit = middle; lo = middle + 1
        else hi = middle - 1 end
    end
    local done = state.day == day and type(state.done) == "table" and state.done or {}
    local function available(first, lastStage, step)
        -- At most 100000 primitive flags; no native quotes or row allocations.
        for stage = first, lastStage, step do if done[tostring(stage)] ~= true and not (excluded and excluded[tostring(stage)]) then return stage end end
        return nil
    end
    if limit >= 33 then
        add(available(33, limit, 1))
        local highest = available(limit, 33, -1)
        add(highest)
        if highest then
            local function xp(stage) return math.floor(66177.8125 * (1 + .07 * (1 + (stage - 33) / 32)) + .5) end
            local target = xp(highest)
            lo, hi = 33, highest
            while lo < hi do
                local middle = math.floor((lo + hi) / 2)
                if xp(middle) >= target then hi = middle else lo = middle + 1 end
            end
            add(available(lo, highest, 1))
        end
    end
    table.sort(selected)
    return selected
end

local function winner(source, indexes, native, state, day, settings, excluded)
    if not indexes or not integer(native.level, 1, 9007199254740991) then return nil end
    local chosen, top = nil, math.min(state.best + 1, 100000)
    local done = state.day == day and type(state.done) == "table" and state.done or {}
    local mode = settings.selection
    local function rank(row)
        if mode == "Highest level" then return row.level end
        if mode == "XP reward" then return row.xp end
        if mode == "Cash reward" then return row.stage > state.best and row.cash or 0 end
        return math.max(not row.mostWanted and (source.rarities[row.crate] or 0) or 0,
            row.stage > state.best and (source.rarities[row.firstClearCrate] or 0) or 0)
    end
    local function consider(stage)
        local row = expected(source, stage)
        if row.level > native.level or done[tostring(stage)] == true
            or excluded and excluded[tostring(stage)] == true
            or settings.limitsEnabled and (row.level < settings.minLevel or row.level > settings.maxLevel)
            or native.pools.health < row.hitBackMax + native.stats.maxHealth * settings.healthFloor / 100 then return end
        if mode == "Smart" or mode == "First undefeated" or mode == "Current progression" then
            if not chosen then chosen = row end
        elseif not chosen or rank(row) > rank(chosen)
            or rank(row) == rank(chosen) and mode == "Highest level" and row.stage > chosen.stage then
            chosen = row
        end
    end
    -- Legacy order is top first, then ascending repeats. Only the winning
    -- quote must be representable; irrelevant huge frontier HP cannot block it.
    consider(top)
    for _, stage in ipairs(indexes) do if stage ~= top then consider(stage) end end
    return chosen and chosen.stage or nil
end

local function sameReferences(self)
    if not self.contract then return true end
    if self.data.BOSSES ~= self.cityRows or self.data.ITEMS_BY_ID ~= self.itemRows then return false end
    for index, row in ipairs(self.rowRefs) do if self.cityRows[index] ~= row then return false end end
    for id, item in pairs(self.itemRefs) do if self.itemRows[id] ~= item then return false end end
    return true
end

function NativeBossCatalog.new(stages, config, fingerprint, release, data, game)
    assert(type(stages) == "table"
        and type(stages.get) == "function"
        and type(stages.crateUnlocked) == "function"
        and integer(stages.MAX_STAGE, 1, 100000)
        and type(stages.SHOP) == "table"
        and validShop(stages.SHOP.gear)
        and validShop(stages.SHOP.crates)
        and type(config) == "table"
        and type(config.BOSS) == "table"
        and integer(config.BOSS.staminaCost, 1, 10000)
        and type(fingerprint) == "string"
        and #fingerprint == 64
        and fingerprint:match("^[%x]+$")
        and type(release) == "string" and #release > 0,
        "Missing current Boss catalog source")
    local contract = reviewed(stages, data, game)
    local rowRefs, itemRefs = {}, {}
    if contract then
        for index = 1, 32 do rowRefs[index] = data.BOSSES[index] end
        for id in pairs(contract.rarities) do itemRefs[id] = data.ITEMS_BY_ID[id] end
    end
    return setmetatable({ stages = stages, game = game, data = data, contract = contract,
        rowRefs = rowRefs, itemRefs = itemRefs,
        get = stages.get, mw = stages.MOST_WANTED, base = stages.MW_BASE,
        cityRows = type(data) == "table" and data.BOSSES,
        itemRows = type(data) == "table" and data.ITEMS_BY_ID,
        staminaCost = config.BOSS.staminaCost,
        catalogKey = fingerprint:lower(), release = release }, Methods)
end

function Methods:Enrich(snapshot, settings, exactStage, excludedStages)
    local native = type(snapshot) == "table" and snapshot.native
    local state = type(native) == "table" and native.bossStage
    if type(snapshot) ~= "table"
        or snapshot.release ~= self.release
        or type(snapshot.account) ~= "string"
        or type(snapshot.capturedAt) ~= "number"
        or type(native) ~= "table" or native.fullSync ~= true
        or type(state) ~= "table"
        or not integer(state.best, 0, self.stages.MAX_STAGE) then
        return nil, "Boss catalog needs a matching full Sync"
    end
    local result, rows, items = {}, {}, {}
    for key, value in pairs(snapshot) do result[key] = value end
    if type(native.serverNow) ~= "number"
        or native.serverNow ~= native.serverNow
        or native.serverNow < 0 or native.serverNow == math.huge then
        return nil, "Current Boss server time unavailable"
    end
    local okDay, dayText = pcall(os.date, "!%Y%j",
        math.floor(native.serverNow))
    local day = okDay and tonumber(dayText)
    if not integer(day, 0, 9999999) then
        return nil, "Current Boss day unavailable"
    end
    local selection, indexes, cityReason, selectionAvailable, selectionReason
    if self.contract then
        local current = reviewed(self.stages, self.data, self.game)
        if self.retired or self.stages.get ~= self.get
            or self.stages.MOST_WANTED ~= self.mw or self.stages.MW_BASE ~= self.base
            or not sameReferences(self)
            or not current or not equal(current, self.contract) then
            self.retired = true
            cityReason = "Reviewed Boss formula source changed"
        end
        selection = selectionSettings(settings)
        if selection and selection.confirmedLimitsEnabled and type(excludedStages) ~= "table" and exactStage == nil then selection = nil end
        if cityReason then indexes = {}
        elseif exactStage ~= nil then
            if not integer(exactStage, 1, self.stages.MAX_STAGE) then return nil, "Invalid saved Boss stage" end
            indexes = {exactStage}
        else
            local frontier = selection and candidates(native, state, day, selection, excludedStages)
            selectionAvailable = frontier ~= nil and integer(native.level, 1, 9007199254740991)
            local selected = frontier and winner(self.contract, frontier, native, state, day, selection, excludedStages)
            if selectionAvailable and not selected and type(excludedStages) == "table" and next(excludedStages) ~= nil then
                local unfiltered = candidates(native, state, day, selection)
                if winner(self.contract, unfiltered, native, state, day, selection) then
                    selectionReason = "Eligible Boss stages reached confirmed encounter caps"
                end
            end
            indexes = selected and {selected} or {}
        end
    else
        indexes = {}
        if exactStage ~= nil then
            if not integer(exactStage, 1, self.stages.MAX_STAGE) then return nil, "Invalid saved Boss stage" end
            indexes[1] = exactStage
        else
            local last = math.min(state.best + 1, self.stages.MAX_STAGE)
            for stage = math.max(1, last - 128), last do indexes[#indexes + 1] = stage end
        end
    end
    for _, stage in ipairs(indexes) do
        local ok, row = pcall(self.stages.get, stage)
        if not ok or type(row) ~= "table" or row.stage ~= stage
            or not integer(row.level, 1, 1000000)
            or not integer(row.hp, 1, 9007199254740991)
            or not integer(row.hitBackMax, 0, 9007199254740991) then
            cityReason = "Invalid current Boss stage"
            rows = {}
            break
        end
        local quote = {stage = stage, level = row.level, hp = row.hp, hitBackMax = row.hitBackMax}
        if self.contract then
            local predicted = expected(self.contract, stage)
            for _, field in ipairs({"stage", "level", "hp", "hitBackMax", "cash", "xp", "crate", "firstClearCrate", "mostWanted"}) do
                if predicted[field] ~= row[field] then
                    self.retired = true
                    cityReason = "Native Boss quote differs from reviewed formula"
                    break
                end
            end
            if cityReason then rows = {}; break end
            if not integer(row.cash, 0, 9007199254740991) or not integer(row.xp, 0, 9007199254740991) then
                cityReason = "Boss reward quote exceeds supported numeric domain"
                rows = {}
                break
            end
            for key, value in pairs(predicted) do quote[key] = value end
            quote.crateRarity = self.contract.rarities[row.crate] or 0
            quote.firstClearRarity = self.contract.rarities[row.firstClearCrate] or 0
        end
        rows[#rows + 1] = quote
    end
    for _, kind in ipairs({ "gear", "crates" }) do
        for _, row in ipairs(self.stages.SHOP[kind]) do
            local unlocked = kind == "gear"
            if kind == "crates" then
                local ok, allowed = pcall(self.stages.crateUnlocked,
                    native, row.item, day)
                if not ok or type(allowed) ~= "boolean" then
                    return nil, "Boss crate unlock unavailable"
                end
                unlocked = allowed
            end
            items[#items + 1] = { item = row.item,
                kind = kind == "crates" and "crate" or "gear",
                price = row.price, unlocked = unlocked }
        end
    end
    if self.contract and (self.retired or self.stages.get ~= self.get or self.stages.MOST_WANTED ~= self.mw
        or self.stages.MW_BASE ~= self.base or not sameReferences(self)
        or not equal(reviewed(self.stages, self.data, self.game), self.contract)) then
        self.retired = true
        cityReason = "Reviewed Boss source changed while quoting"
        rows = {}
    end
    result.bossStageProof = { account = snapshot.account, catalogKey = self.catalogKey,
        capturedAt = snapshot.capturedAt,
        staminaCost = self.staminaCost, stages = rows,
        selectionContract = self.contract and CONTRACT or nil,
        selectionComplete = selectionAvailable == true, selectionReason = selectionReason,
        selectionSettings = selection }
    if (#rows == 0 and not selectionAvailable) or cityReason then result.bossStageProof = nil end
    result.bossShopProof = { account = snapshot.account,
        capturedAt = snapshot.capturedAt,
        catalogKey = self.catalogKey, items = items }
    return result, nil
end

return NativeBossCatalog
