-- Daily/weekly entry readiness from one complete replicated Contract Sync.
local ContractEntriesState = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value < math.huge and value >= minimum and value % 1 == 0
end

local function tiers(value)
    if type(value) ~= "table" or #value ~= 5 then return false end
    for key, tier in pairs(value) do
        if not integer(key, 1) or key > 5
            or not integer(tier, 1) or tier > 4 then return false end
    end
    for index = 1, 5 do if value[index] == nil then return false end end
    return true
end

local function entries(rows, count, allowSingleton)
    if allowSingleton and type(rows) == "table" and rows.id ~= nil then
        rows = { rows }
        count = 1
    end
    if type(rows) ~= "table" or #rows ~= count then return nil end
    local result, ids = {}, {}
    for key in pairs(rows) do
        if not integer(key, 1) or key > count then return nil end
    end
    for index = 1, count do
        local row = rows[index]
        if type(row) ~= "table" or type(row.id) ~= "string"
            or #row.id == 0 or ids[row.id]
            or type(row.done) ~= "boolean"
            or type(row.claimed) ~= "boolean" then return nil end
        ids[row.id] = true
        result[index] = { id = row.id, ready = row.done and not row.claimed }
    end
    return result
end

function ContractEntriesState.read(raw, context)
    if type(raw) ~= "table" or type(context) ~= "table" then
        return nil, "Missing Contract state or context"
    end
    for _, field in ipairs({ "session", "account", "place", "release",
        "revision", "capturedAt" }) do
        if raw[field] ~= context[field] then
            return nil, "Contract snapshot header changed"
        end
    end
    local native = raw.native
    if type(native) ~= "table" or native.fullSync ~= true
        or type(native.contracts) ~= "table"
        or type(native.derived) ~= "table" then
        return nil, "Complete native Contract Sync required"
    end
    local config = raw.contractConfig
    if type(config) ~= "table" or not tiers(config.dailyTiers)
        or not tiers(config.weeklyTiers)
        or type(raw.catalogKey) ~= "string" or #raw.catalogKey == 0 then
        return nil, "Current Contract tiers required"
    end
    local now = context.serverNow
    local dayReset, weekReset = native.derived.contractDayReset,
        native.derived.contractWeekReset
    if not integer(now, 0) or native.serverNow ~= now
        or not integer(dayReset, 1) or not integer(weekReset, 1)
        or dayReset - now <= 5 or weekReset - now <= 5 then
        return nil, "Current Contract reset window required"
    end
    local daily = entries(native.contracts.daily, 5, false)
    local weekly = entries(native.contracts.weekly, 5, true)
    if not daily or not weekly then
        return nil, "Contract entry rows incomplete"
    end
    local ready = {}
    for index, row in ipairs(daily) do
        if row.ready then ready[#ready + 1] = {
            period = "daily", index = index, rowId = row.id } end
    end
    for index, row in ipairs(weekly) do
        if row.ready then ready[#ready + 1] = {
            period = "weekly", index = index, rowId = row.id } end
    end
    return {
        session = context.session, account = context.account,
        place = context.place, release = context.release,
        revision = context.revision, capturedAt = context.capturedAt,
        catalogKey = raw.catalogKey, dayReset = dayReset,
        weekReset = weekReset, ready = ready,
    }, nil
end

return ContractEntriesState
