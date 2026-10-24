-- Read-only personal Heist board. Mutation sequence ownership is separate.
local HeistBoardState = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge and value % 1 == 0
end

local function key(value)
    return type(value) == "string" and #value > 0
end

function HeistBoardState.read(raw, context)
    if type(raw) ~= "table" or type(context) ~= "table" then
        return nil, "Missing Heist board or context"
    end
    for _, field in ipairs({ "session", "account", "place", "release",
        "revision", "capturedAt" }) do
        if raw[field] ~= context[field] then
            return nil, "Heist board snapshot header changed"
        end
    end
    local native, proof = raw.native, raw.heistBoardProof
    local board = type(proof) == "table" and proof.board
    if type(native) ~= "table" or native.fullSync ~= true
        or not integer(native.serverNow, 0)
        or type(proof) ~= "table"
        or proof.account ~= context.account
        or proof.capturedAt ~= context.capturedAt
        or proof.query ~= nil
        or type(board) ~= "table" or board.ok ~= true
        or (board.serverNow ~= nil and
            (not integer(board.serverNow, 0)
                or math.abs(board.serverNow - native.serverNow) > 2))
        or type(board.rows) ~= "table"
        or (board.startsLeft ~= nil
            and not integer(board.startsLeft, 0))
        or (board.bustWait ~= nil
            and not integer(board.bustWait, 0))
        or (board.favorsLeft ~= nil
            and not integer(board.favorsLeft, 0))
        or type(raw.heistCatalog) ~= "table"
        or #raw.heistCatalog == 0 then
        return nil, "Current unqueried personal Heist board required"
    end
    local known, options = {}, {}
    for _, row in ipairs(raw.heistCatalog) do
        if type(row) ~= "table" or not key(row.id)
            or known[row.id] or not integer(row.level, 1)
            or not integer(row.stake, 0)
            or not integer(row.energy, 0) then
            return nil, "Invalid Heist catalog"
        end
        known[row.id] = true
        options[#options + 1] = { id = row.id, level = row.level,
            stake = row.stake, energy = row.energy,
            crateCount = row.crateCount }
    end
    local mine, result = board.mine, board.result
    if mine ~= nil and result ~= nil then
        return nil, "Ambiguous personal Heist board"
    end
    local state = "idle"
    local mineId, heistId, endsAt, resultHeistId, resultSummary
    if mine ~= nil then
        if type(mine) ~= "table" or not key(mine.id)
            or not known[mine.heistId]
            or not integer(mine.endsAt, 0)
            or (mine.settling ~= nil
                and type(mine.settling) ~= "boolean") then
            return nil, "Incomplete personal Heist run"
        end
        state = mine.settling == true and "settling" or "active"
        mineId, heistId, endsAt = mine.id, mine.heistId, mine.endsAt
    elseif result ~= nil then
        if type(result) ~= "table" or not known[result.heistId]
            or type(result.ok) ~= "boolean" then
            return nil, "Incomplete personal Heist result"
        end
        for _, field in ipairs({ "cash", "xp", "gold", "crates",
            "bonusCrates" }) do
            if result[field] ~= nil and not integer(result[field], 0) then
                return nil, "Invalid personal Heist reward"
            end
        end
        if (result.crates or 0) > 0 and not key(result.crateId) then
            return nil, "Missing personal Heist crate identity"
        end
        if (result.bonusCrates or 0) > 0
            and not key(result.bonusCrateId) then
            return nil, "Missing personal Heist bonus crate identity"
        end
        state, resultHeistId = "result", result.heistId
        resultSummary = { ok = result.ok,
            cash = result.cash or 0, xp = result.xp or 0,
            gold = result.gold or 0, crates = result.crates or 0,
            bonusCrates = result.bonusCrates or 0,
            crateId = result.crateId,
            bonusCrateId = result.bonusCrateId }
    end
    return { session = context.session, account = context.account,
        place = context.place, release = context.release,
        revision = context.revision, capturedAt = context.capturedAt,
        serverNow = board.serverNow, clockKnown = board.serverNow ~= nil,
        state = state,
        startsLeft = board.startsLeft, bustWait = board.bustWait,
        favorsLeft = board.favorsLeft,
        catalogKey = raw.catalogKey, options = options,
        level = native.level, cash = native.cash,
        energy = type(native.pools) == "table" and native.pools.energy,
        serverDay = board.serverNow
            and math.floor(board.serverNow / 86400),
        mineId = mineId, heistId = heistId, endsAt = endsAt,
        resultHeistId = resultHeistId,
        resultSummary = resultSummary,
        resultAddressable = false }, nil
end

return HeistBoardState
