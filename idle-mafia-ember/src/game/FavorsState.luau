-- Current board help rows plus same-day durable attempt accounting.
local FavorsState = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge and value % 1 == 0
end

local function key(value)
    return type(value) == "string" and #value > 0
end

local function rowId(value)
    return key(value) or integer(value, 1)
end

local function used(row, countKey, legacyKey)
    if row[countKey] ~= nil then
        return integer(row[countKey], 0) and row[countKey] or nil
    end
    if row[legacyKey] == nil or row[legacyKey] == false then return 0 end
    if row[legacyKey] == true then return 1 end
    return nil
end

function FavorsState.read(raw, context)
    if type(raw) ~= "table" or type(context) ~= "table" then
        return nil, "Missing Favor state or context"
    end
    for _, field in ipairs({ "session", "account", "place", "release",
        "revision", "capturedAt" }) do
        if raw[field] ~= context[field] then
            return nil, "Favor snapshot header changed"
        end
    end
    local heists = context.heists
    local proof, usage, native = raw.heistBoardProof,
        raw.favorUsageProof, raw.native
    local board = type(proof) == "table" and proof.board
    local day = type(heists) == "table" and heists.serverDay
    if type(heists) ~= "table" or not integer(day, 0)
        or type(proof) ~= "table" or proof.account ~= context.account
        or proof.capturedAt ~= context.capturedAt
        or proof.query ~= nil or type(board) ~= "table"
        or board.ok ~= true or board.serverNow ~= heists.serverNow
        or type(board.rows) ~= "table"
        or not integer(board.favorsLeft, 0)
        or not integer(board.helpFavorCost, 0)
        or not integer(board.helpEnergyCost, 0)
        or not integer(board.helpMaxPerHeist, 1)
        or (board.helpCashCap ~= nil
            and not integer(board.helpCashCap, 0))
        or type(native) ~= "table" or native.fullSync ~= true
        or not integer(native.level, 1)
        or type(native.pools) ~= "table"
        or not integer(native.pools.energy, 0)
        or type(usage) ~= "table" or usage.account ~= context.account
        or usage.capturedAt ~= context.capturedAt
        or usage.day ~= day or not integer(usage.attempts, 0)
        or type(raw.heistCatalog) ~= "table" then
        return nil, "Current Favor board and durable day proof required"
    end
    local catalog = {}
    for _, item in ipairs(raw.heistCatalog) do
        if type(item) ~= "table" or not key(item.id)
            or catalog[item.id] or not integer(item.level, 1)
            or not integer(item.helpCash, 0)
            or not integer(item.helpXp, 0) then
            return nil, "Invalid Favor catalog"
        end
        catalog[item.id] = item
    end
    local rows, seen = {}, {}
    for _, row in ipairs(board.rows) do
        if type(row) ~= "table" or not rowId(row.id)
            or seen[row.id] or not integer(row.ownerId, 1)
            or not catalog[row.heistId]
            or not integer(row.endsAt, 0)
            or (row.friend ~= nil and type(row.friend) ~= "boolean")
            or (row.famRel ~= nil and row.famRel ~= "family"
                and row.famRel ~= "war" and row.famRel ~= "other") then
            return nil, "Invalid Favor board row"
        end
        local helps = used(row, "helpsUsed", "helped")
        local sabos = used(row, "sabosUsed", "sabotaged")
        if not helps or not sabos then
            return nil, "Invalid personal Favor usage"
        end
        seen[row.id] = true
        local item = catalog[row.heistId]
        rows[#rows + 1] = { id = row.id,
            heistId = row.heistId, ownerId = row.ownerId,
            level = item.level, endsAt = row.endsAt,
            friend = row.friend == true, family = row.famRel == "family",
            atWar = row.famRel == "war", helpsUsed = helps,
            sabosUsed = sabos,
            rewardCash = math.min(item.helpCash,
                board.helpCashCap or item.helpCash),
            rewardXp = item.helpXp }
    end
    return { session = context.session, account = context.account,
        place = context.place, release = context.release,
        revision = context.revision, capturedAt = context.capturedAt,
        serverNow = heists.serverNow, serverDay = day,
        favorsLeft = board.favorsLeft,
        favorCost = board.helpFavorCost,
        energyCost = board.helpEnergyCost,
        maxHelps = board.helpMaxPerHeist,
        energy = native.pools.energy, level = native.level,
        usageAttempts = usage.attempts, rows = rows }, nil
end

return FavorsState
