-- Snapshot adapter for shared facts. The caller labels complete native Syncs.
local Context = {}
local Methods = {}
Methods.__index = Methods

local function finite(value)
    return type(value) == "number" and value == value
        and value >= 0 and value < math.huge
end

local function entitlement(derived, key)
    if type(derived) ~= "table" then return nil end
    if derived[key] == true then return true end
    if derived[key] == false then return false end
    return nil
end

local function savedToggle(value, key, fullSync)
    if not fullSync then return "unknown" end
    if value == nil then return "inactive" end
    if type(value) ~= "table" then return "unknown" end
    if value[key] == true then return "active" end
    if value[key] == false or value[key] == nil then return "inactive" end
    return "unknown"
end

local function rolling(value, fullSync)
    if not fullSync then return "unknown" end
    if value == nil then return "inactive" end
    if type(value) ~= "table" then return "unknown" end
    local active = false
    for slot, record in pairs(value) do
        if (type(slot) ~= "string" and type(slot) ~= "number")
            or type(record) ~= "table" then return "unknown" end
        active = true
    end
    return active and "active" or "inactive"
end

local function bossActivity(stage, fullSync)
    if not fullSync then return "unknown" end
    if stage == nil then return "inactive" end
    if type(stage) ~= "table" then return "unknown" end
    local auto = stage.auto
    if auto == nil or auto == false then return "inactive" end
    if type(auto) == "number" and auto == auto and auto > 0
        and auto < math.huge and auto % 1 == 0 then return "active" end
    return "unknown"
end

local sourceCatalogs = {
    trainingCatalogKey = "trainingCatalog",
    hireCatalogKey = "hireCatalog",
    healItemCatalogKey = "healItemCatalog",
    restorativeCatalogKey = "restorativeCatalog",
    crateCatalogKey = "ownedCrateCatalog",
    collectionCatalogKey = "collectionCatalog",
}

function Context.new(contracts, economyReader, buffReader, heistReader,
    bossStageReader, globalBossReader, bossShopReader,
    takedownReader)
    assert(type(contracts) == "table" and type(contracts.validateSnapshot) == "function",
        "Context needs request contracts")
    assert(economyReader == nil or (type(economyReader) == "table"
        and type(economyReader.read) == "function"),
        "Invalid economic context reader")
    assert(buffReader == nil or (type(buffReader) == "table"
        and type(buffReader.read) == "function"),
        "Invalid buff context reader")
    assert(heistReader == nil or (type(heistReader) == "table"
        and type(heistReader.read) == "function"),
        "Invalid Heist board reader")
    assert(bossStageReader == nil or (type(bossStageReader) == "table"
        and type(bossStageReader.read) == "function"),
        "Invalid Boss stage reader")
    assert(globalBossReader == nil or (type(globalBossReader) == "table"
        and type(globalBossReader.read) == "function"),
        "Invalid Global Boss reader")
    assert(bossShopReader == nil or (type(bossShopReader) == "table"
        and type(bossShopReader.read) == "function"),
        "Invalid Boss Shop reader")
    assert(takedownReader == nil or (type(takedownReader) == "table"
        and type(takedownReader.read) == "function"),
        "Invalid Family Takedown reader")
    return setmetatable({ contracts = contracts,
        economyReader = economyReader, buffReader = buffReader,
        heistReader = heistReader,
        bossStageReader = bossStageReader,
        globalBossReader = globalBossReader,
        bossShopReader = bossShopReader,
        takedownReader = takedownReader }, Methods)
end

function Methods:Read(raw, expectedSession, now, maxAge)
    local header, reason = self.contracts.validateSnapshot(raw, expectedSession)
    if not header then return nil, reason end
    local age = type(maxAge) == "number" and maxAge or 2
    if not finite(now) or not finite(age) or age == 0 then
        return nil, "Invalid context clock or freshness limit"
    end
    if header.capturedAt > now or now - header.capturedAt > age then
        return nil, "Native snapshot is stale"
    end
    local native = raw.native
    if type(native) ~= "table" then return nil, "Native state missing" end

    local derived = native.derived
    local fullSync = native.fullSync == true
    local activity = "unknown"
    if fullSync and type(native.autoJob) == "table" then
        activity = "active"
    elseif fullSync and native.autoJob == nil then
        -- A complete Sync can establish that the saved autoJob run is absent.
        activity = "inactive"
    end
    local resources = {}
    if type(native.pools) == "table" and finite(native.pools.energy) then
        resources.energy = native.pools.energy
    end
    if type(native.pools) == "table" and finite(native.pools.stamina) then
        resources.stamina = native.pools.stamina
    end
    if finite(native.cash) then resources.cash = native.cash end
    if finite(native.skillPoints) then resources.skillPoints = native.skillPoints end
    local serverNow = finite(native.serverNow) and native.serverNow or nil
    local view = {
        session = header.session, account = header.account, place = header.place,
        release = header.release, revision = header.revision,
        capturedAt = header.capturedAt, maxAge = age,
        serverNow = serverNow, resources = resources,
        owners = {
            jobs = { entitled = entitlement(derived, "autoJobs"), activity = activity },
            shop = { entitled = entitlement(derived, "autoBuy"),
                activity = savedToggle(native.autoBuyRules, "on", fullSync) },
            crewRoll = { entitled = entitlement(derived, "autoRoll"),
                activity = rolling(native.autoRolls, fullSync) },
            bosses = { entitled = entitlement(derived, "autoBoss"),
                activity = bossActivity(native.bossStage, fullSync) },
        },
        economy = { status = "unknown" }, buffs = { status = "unknown" },
        heists = { status = "unknown" },
        bossStages = { status = "unknown" },
        globalBoss = { status = "unknown" },
        bossShop = { status = "unknown" },
        takedown = { status = "unknown" },
    }
    if fullSync then
        for field, source in pairs(sourceCatalogs) do
            local catalog = raw[source]
            if type(catalog) == "table"
                and catalog.release == header.release
                and type(catalog.catalogKey) == "string"
                and #catalog.catalogKey > 0 then
                view[field] = catalog.catalogKey
            end
        end
        for _, field in ipairs({ "gearSourceKey",
            "cosmeticSourceKey" }) do
            if type(raw[field]) == "string"
                and #raw[field] > 0 then
                view[field] = raw[field]
            end
        end
    end
    if self.economyReader then
        local ok, economy, economyReason = pcall(self.economyReader.read, raw, view)
        if ok and economy then view.economy = economy
        else view.economy = { status = "unknown",
            reason = ok and economyReason or "Economic reader failed" } end
    end
    if self.buffReader then
        local ok, buffs, buffReason = pcall(self.buffReader.read, raw, view)
        if ok and buffs then view.buffs = buffs
        else view.buffs = { status = "unknown",
            reason = ok and buffReason or "Buff reader failed" } end
    end
    if self.heistReader then
        local ok, heists, heistReason = pcall(self.heistReader.read, raw, view)
        if ok and heists then
            view.heists = heists
            if finite(heists.favorsLeft) then
                view.resources.favors = heists.favorsLeft
            end
        else view.heists = { status = "unknown",
            reason = ok and heistReason or "Heist reader failed" } end
    end
    if self.bossStageReader then
        local ok, stages, stageReason = pcall(
            self.bossStageReader.read, raw, view)
        if ok and stages then view.bossStages = stages
        else view.bossStages = { status = "unknown",
            reason = ok and stageReason or "Boss stage reader failed" } end
    end
    if self.globalBossReader then
        local ok, boss, bossReason = pcall(
            self.globalBossReader.read, raw, view)
        if ok and boss then view.globalBoss = boss
        else view.globalBoss = { status = "unknown",
            reason = ok and bossReason or "Global Boss reader failed" } end
    end
    if self.bossShopReader then
        local ok, shop, shopReason = pcall(
            self.bossShopReader.read, raw, view)
        if ok and shop then
            view.bossShop = shop
            view.resources.bossTokens = shop.tokens
        else view.bossShop = { status = "unknown",
            reason = ok and shopReason or "Boss Shop reader failed" } end
    end
    if self.takedownReader then
        local ok, state, stateReason = pcall(
            self.takedownReader.read, raw, view)
        if ok and state then view.takedown = state
        else view.takedown = { status = "unknown",
            reason = ok and stateReason
                or "Family Takedown reader failed" } end
    end
    return view, nil
end

return Context
