-- Separate sabotage board with explicit local identity and sent attempts.
local SabotageState = {}

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

function SabotageState.read(raw, context)
    if type(raw) ~= "table" or type(context) ~= "table" then
        return nil, "Missing sabotage input"
    end
    for _, field in ipairs({ "session", "account", "place", "release",
        "revision", "capturedAt" }) do
        if raw[field] ~= context[field] then
            return nil, "Sabotage snapshot header changed"
        end
    end
    local heists = context.heists
    local proof, usage, player = raw.heistBoardProof,
        raw.sabotageUsageProof, raw.localUserIdProof
    local board = type(proof) == "table" and proof.board
    local native = raw.native
    if type(heists) ~= "table"
        or not integer(heists.serverDay, 0)
        or not integer(heists.serverNow, 0)
        or type(proof) ~= "table" or proof.account ~= context.account
        or proof.capturedAt ~= context.capturedAt
        or proof.query ~= nil or type(board) ~= "table"
        or board.ok ~= true or board.serverNow ~= heists.serverNow
        or type(board.rows) ~= "table"
        or not integer(board.favorsLeft, 0)
        or not integer(board.saboFavorCost, 0)
        or not integer(board.saboEnergyCost, 0)
        or not integer(board.saboMaxPerHeist, 1)
        or type(native) ~= "table" or native.fullSync ~= true
        or not integer(native.level, 1)
        or type(native.pools) ~= "table"
        or not integer(native.pools.energy, 0)
        or type(usage) ~= "table" or usage.account ~= context.account
        or usage.capturedAt ~= context.capturedAt
        or usage.day ~= heists.serverDay
        or not integer(usage.attempts, 0)
        or type(player) ~= "table"
        or player.account ~= context.account
        or player.capturedAt ~= context.capturedAt
        or not integer(player.userId, 1)
        or type(raw.heistCatalog) ~= "table" then
        return nil, "Current sabotage board, identity and usage proof required"
    end
    local catalog = {}
    for _, item in ipairs(raw.heistCatalog) do
        if type(item) ~= "table" or not key(item.id)
            or catalog[item.id] or not integer(item.level, 1) then
            return nil, "Invalid sabotage catalog"
        end
        catalog[item.id] = item.level
    end
    local rows, seen = {}, {}
    for _, row in ipairs(board.rows) do
        if type(row) ~= "table" or not rowId(row.id)
            or seen[row.id] or not integer(row.ownerId, 1)
            or not catalog[row.heistId]
            or not integer(row.endsAt, 0)
            or (row.friend ~= nil and type(row.friend) ~= "boolean")
            or (row.famRel ~= nil and type(row.famRel) ~= "string") then
            return nil, "Invalid sabotage row"
        end
        local helps = used(row, "helpsUsed", "helped")
        local sabos = used(row, "sabosUsed", "sabotaged")
        if not helps or not sabos then
            return nil, "Invalid personal sabotage usage"
        end
        seen[row.id] = true
        rows[#rows + 1] = { id = row.id,
            heistId = row.heistId, ownerId = row.ownerId,
            level = catalog[row.heistId], endsAt = row.endsAt,
            friend = row.friend == true,
            family = row.famRel == "family",
            helpsUsed = helps, sabosUsed = sabos }
    end
    return { session = context.session, account = context.account,
        place = context.place, release = context.release,
        revision = context.revision,
        serverNow = heists.serverNow,
        serverDay = heists.serverDay,
        selfId = player.userId, level = native.level,
        energy = native.pools.energy,
        favorsLeft = board.favorsLeft,
        favorCost = board.saboFavorCost,
        energyCost = board.saboEnergyCost,
        maxSabos = board.saboMaxPerHeist,
        usageAttempts = usage.attempts, rows = rows }, nil
end

return SabotageState
