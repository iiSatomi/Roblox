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

function NativeBossCatalog.new(stages, config, fingerprint, release)
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
    return setmetatable({ stages = stages,
        staminaCost = config.BOSS.staminaCost,
        catalogKey = fingerprint:lower(), release = release }, Methods)
end

function Methods:Enrich(snapshot)
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
    -- Bound work: the next stage and up to 128 earlier repeat stages.
    local last = math.min(state.best + 1, self.stages.MAX_STAGE)
    local first = math.max(1, last - 128)
    for stage = first, last do
        local ok, row = pcall(self.stages.get, stage)
        if not ok or type(row) ~= "table"
            or row.stage ~= stage
            or not integer(row.level, 1, 1000000)
            or not integer(row.hp, 1, 9007199254740991)
            or not integer(row.hitBackMax, 0, 9007199254740991) then
            return nil, "Invalid current Boss stage"
        end
        rows[#rows + 1] = { stage = stage, level = row.level,
            hp = row.hp, hitBackMax = row.hitBackMax }
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
    result.bossStageProof = { account = snapshot.account, catalogKey = self.catalogKey,
        capturedAt = snapshot.capturedAt,
        staminaCost = self.staminaCost, stages = rows }
    result.bossShopProof = { account = snapshot.account,
        capturedAt = snapshot.capturedAt,
        catalogKey = self.catalogKey, items = items }
    return result, nil
end

return NativeBossCatalog
