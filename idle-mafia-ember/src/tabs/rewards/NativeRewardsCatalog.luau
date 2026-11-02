-- Saved ladder, group and monthly settings for a matching full Sync.
local NativeRewardsCatalog = {}
local Methods = {}
Methods.__index = Methods

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value <= 9007199254740991 and value % 1 == 0
end

local function copyReward(row)
    return { kind = row.kind, flat = row.flat,
        minutes = row.minutes, amount = row.amount,
        crate = row.crate, bound = row.bound, item = row.item, count = row.count }
end

local function copyLadder(rows)
    local result = {}
    for index, row in ipairs(rows) do
        local item = copyReward(row)
        item.seconds = row.seconds
        if row.weekend then item.weekend = copyReward(row.weekend) end
        if row.tiers then
            item.tiers = {}
            for tier, reward in pairs(row.tiers) do
                item.tiers[tier] = copyReward(reward)
            end
        end
        result[index] = item
    end
    return result
end

function NativeRewardsCatalog.new(config, fingerprint, release)
    assert(type(config) == "table"
        and type(config.LADDER) == "table"
        and #config.LADDER == 7
        and type(config.LADDER_TIERS) == "table"
        and #config.LADDER_TIERS == 4
        and type(config.GROUP) == "table"
        and integer(config.GROUP.id, 1)
        and type(config.MONTHLY_CALENDAR) == "table"
        and type(config.MONTHLY_CALENDAR.enabled) == "boolean"
        and type(fingerprint) == "string" and #fingerprint == 64
        and fingerprint:match("^[%x]+$")
        and type(release) == "string" and #release > 0,
        "Missing reviewed Rewards source")
    for key in pairs(config.LADDER) do
        assert(integer(key, 1) and key <= 7,
            "Sparse ladder source")
    end
    for key in pairs(config.LADDER_TIERS) do
        assert(integer(key, 1) and key <= 4,
            "Sparse ladder thresholds")
    end
    local ladder, tiers = copyLadder(config.LADDER), {}
    local previous = 0
    for index, row in ipairs(ladder) do
        assert(integer(row.seconds, 1) and row.seconds > previous
            and type(row.kind) == "string" and #row.kind > 0,
            "Invalid saved ladder rung")
        previous = row.seconds
        for tier, reward in pairs(row.tiers or {}) do
            assert(integer(tier, 2) and tier <= 4
                and type(reward.kind) == "string",
                "Invalid ladder tier override")
        end
        if row.weekend then
            assert(type(row.weekend.kind) == "string",
                "Invalid weekend reward")
        end
    end
    previous = 0
    for index = 1, 4 do
        local threshold = config.LADDER_TIERS[index]
        assert(integer(threshold, 1) and threshold > previous,
            "Invalid ladder tier threshold")
        tiers[index], previous = threshold, threshold
    end
    local groupIncome = config.GROUP.incomeBonus
    assert(groupIncome == nil or (type(groupIncome) == "number" and groupIncome == groupIncome
        and groupIncome >= 0 and groupIncome <= 1), "Invalid Group income modifier")
    local monthlyDays = {}
    assert(config.MONTHLY_CALENDAR.days == nil or type(config.MONTHLY_CALENDAR.days) == "table",
        "Invalid monthly reward definitions")
    assert(config.MONTHLY_CALENDAR.default == nil or type(config.MONTHLY_CALENDAR.default) == "table",
        "Invalid monthly reward default")
    for day, reward in pairs(config.MONTHLY_CALENDAR.days or {}) do
        assert(integer(day, 1) and day <= 30 and type(reward) == "table", "Invalid monthly reward day")
        monthlyDays[day] = copyReward(reward)
    end
    local mystery = {}
    local definition = config.LADDER_MYSTERY
    assert(definition == nil or type(definition) == "table", "Invalid mystery reward definition")
    if type(definition) == "table" then
        assert(definition.robux == nil or type(definition.robux) == "table", "Invalid mystery premium pool")
        for poolIndex, pool in ipairs({definition.pool or {}, type(definition.robux) == "table" and definition.robux.crates or {}}) do
            assert(type(pool) == "table" and #pool <= 64, "Invalid mystery reward pool")
            local count = 0
            for key in pairs(pool) do
                assert(integer(key, 1) and key <= #pool, "Sparse mystery reward pool")
                count = count + 1
            end
            assert(count == #pool, "Sparse mystery reward pool")
            for _, row in ipairs(pool) do
                assert(type(row) == "table" and type(row.item) == "string" and #row.item <= 120
                    and row.item:match("^[%w_]+$") and type(row.weight) == "number"
                    and row.weight > 0 and row.weight < math.huge
                    and (row.minLevel == nil or integer(row.minLevel, 0))
                    and (row.maxLevel == nil or integer(row.maxLevel, 0)), "Invalid mystery reward")
                mystery[#mystery + 1] = {item = row.item, minLevel = row.minLevel,
                    maxLevel = row.maxLevel, premium = poolIndex == 2}
            end
        end
    end
    return setmetatable({ release = release,
        key = fingerprint:lower(), ladder = ladder,
        tiers = tiers, groupId = config.GROUP.id, groupIncomeBonus = groupIncome,
        monthlyEnabled = config.MONTHLY_CALENDAR.enabled, monthlyDays = monthlyDays,
        monthlyDefault = type(config.MONTHLY_CALENDAR.default) == "table"
            and copyReward(config.MONTHLY_CALENDAR.default) or nil, mystery = mystery }, Methods)
end

function Methods:Enrich(snapshot)
    if type(snapshot) ~= "table" or snapshot.release ~= self.release
        or type(snapshot.native) ~= "table"
        or snapshot.native.fullSync ~= true then
        return nil, "Rewards need a matching full Sync"
    end
    local result, tiers = {}, {}
    for key, value in pairs(snapshot) do result[key] = value end
    for index = 1, 4 do tiers[index] = self.tiers[index] end
    result.catalogKey = self.key
    result.ladderCatalog = copyLadder(self.ladder)
    result.ladderTiers = tiers
    result.groupConfig = { id = self.groupId, incomeBonus = self.groupIncomeBonus,
        sourceKey = self.key, release = self.release }
    result.monthlyConfig = { enabled = self.monthlyEnabled }
    return result, nil
end

-- PropsTab uses this flag to multiply property income; no immediate Cash grant is implied.
function Methods:GroupEffect(snapshot)
    local native = type(snapshot) == "table" and snapshot.native
    local group = type(snapshot) == "table" and snapshot.groupConfig
    if type(snapshot) ~= "table" or self.groupIncomeBonus == nil or snapshot.release ~= self.release
        or type(native) ~= "table" or native.fullSync ~= true
        or type(native.groupBonus) ~= "boolean" or snapshot.catalogKey ~= self.key
        or type(group) ~= "table" or group.id ~= self.groupId
        or group.sourceKey ~= self.key or group.release ~= self.release
        or group.incomeBonus ~= self.groupIncomeBonus then
        return nil, "Current source-backed Group income effect unavailable"
    end
    return { kind = "propertyIncome", groupId = self.groupId, incomeBonus = self.groupIncomeBonus,
        multiplier = native.groupBonus and 1 + self.groupIncomeBonus or 1,
        active = native.groupBonus, sourceKey = self.key, release = self.release }, nil
end

function Methods:RewardSpec(snapshot, lane, slot)
    local native = type(snapshot) == "table" and snapshot.native
    if type(native) ~= "table" or native.fullSync ~= true or snapshot.release ~= self.release
        or snapshot.catalogKey ~= self.key or type(native.serverNow) ~= "number"
        or native.serverNow ~= native.serverNow or native.serverNow < 0 or native.serverNow >= math.huge then
        return nil, "Matching Rewards source and full Sync required"
    end
    local row, tier
    if lane == "playtime" then
        if not integer(slot, 1) or slot > 7 or not integer(native.level, 1)
            or (native.maxLevel ~= nil and not integer(native.maxLevel, 0)) then
            return nil, "Current ladder index and highest level required"
        end
        local highest = math.max(native.level, native.maxLevel or 0)
        tier = 1
        for index, threshold in ipairs(self.tiers) do if highest >= threshold then tier = index end end
        row = self.ladder[slot]
        if row.tiers then
            for index = tier, 2, -1 do if row.tiers[index] then row = row.tiers[index]; break end end
        end
        local weekend = snapshot.weekendBuff
        local ok, day = pcall(os.date, "!%Y%j", math.floor(native.serverNow))
        if not ok or type(weekend) ~= "table" or type(weekend.active) ~= "boolean"
            or weekend.day ~= tonumber(day) then return nil, "Current weekend proof required" end
        if weekend.active and self.ladder[slot].weekend then row = self.ladder[slot].weekend end
    elseif lane == "monthlyRewards" then
        if not self.monthlyEnabled or not integer(slot, 1) or slot > 30 then
            return nil, "Native monthly calendar is disabled or day invalid"
        end
        row = self.monthlyDays[slot] or self.monthlyDefault
    else return nil, "Unknown reward lane" end
    if type(row) ~= "table" then return nil, "Native reward definition missing" end
    local spec = {sourceKey = self.key, release = self.release, slot = slot,
        lane = lane, tier = tier, rewardKind = row.kind}
    if row.kind == "gold" or row.kind == "seals" or row.kind == "item" or row.kind == "crate" then
        spec.kind = "item"
        spec.itemId = row.kind == "gold" and "gold_bar" or row.kind == "seals" and "contract_seal"
            or row.kind == "crate" and row.crate or row.item
        spec.amount = row.kind == "crate" and 1 or row.amount or row.count or 1
        spec.bound = row.bound
        if type(spec.itemId) ~= "string" or #spec.itemId > 120 or not spec.itemId:match("^[%w_]+$")
            or not integer(spec.amount, 1) or (spec.bound ~= nil and type(spec.bound) ~= "boolean") then
            return nil, "Invalid native item reward"
        end
    elseif row.kind == "cash" and integer(row.flat, 1) then
        spec.kind, spec.amount = "cash", row.flat
    elseif row.kind == "energy" or row.kind == "stamina" then
        spec.kind, spec.pool = "refill", row.kind
    elseif row.kind == "xpboost" and integer(row.minutes, 1) then
        spec.kind, spec.seconds = "xpboost", row.minutes * 60
        if not integer(spec.seconds, 1) then return nil, "Invalid boost duration" end
    elseif row.kind == "mystery" then
        spec.kind, spec.items = "mystery", {}
        if not integer(native.level, 1) or (native.maxLevel ~= nil and not integer(native.maxLevel, 0)) then
            return nil, "Mystery highest level unavailable"
        end
        local highest = math.max(native.level or 0, native.maxLevel or 0)
        local regular = false
        for _, entry in ipairs(self.mystery) do
            if entry.premium or ((entry.minLevel == nil or highest >= entry.minLevel)
                and (entry.maxLevel == nil or highest <= entry.maxLevel)) then
                spec.items[entry.item] = true
                if not entry.premium then regular = true end
            end
        end
        if next(spec.items) == nil then return nil, "Mystery reward catalog unavailable" end
        if not regular then spec.items.crate_boss = true end
    else return nil, "Reward amount or application rule is not established: " .. tostring(row.kind) end
    return spec, nil
end

return NativeRewardsCatalog
