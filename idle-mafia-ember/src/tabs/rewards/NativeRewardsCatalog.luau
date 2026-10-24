-- Saved ladder, group and monthly settings for a matching full Sync.
local NativeRewardsCatalog = {}
local Methods = {}
Methods.__index = Methods

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge and value % 1 == 0
end

local function copyReward(row)
    return { kind = row.kind, flat = row.flat,
        minutes = row.minutes, amount = row.amount,
        crate = row.crate, bound = row.bound }
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
    return setmetatable({ release = release,
        key = fingerprint:lower(), ladder = ladder,
        tiers = tiers, groupId = config.GROUP.id,
        monthlyEnabled = config.MONTHLY_CALENDAR.enabled }, Methods)
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
    result.groupConfig = { id = self.groupId }
    result.monthlyConfig = { enabled = self.monthlyEnabled }
    return result, nil
end

return NativeRewardsCatalog
