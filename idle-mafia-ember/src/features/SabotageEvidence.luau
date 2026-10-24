-- Exact personal sabotage count and Favor debit prove a selected row.
local SabotageEvidence = {}

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

local function matching(a, b)
    for _, field in ipairs({ "session", "account", "place", "release" }) do
        if not key(a[field]) or a[field] ~= b[field] then return false end
    end
    return true
end

local function used(row, countKey, legacyKey)
    if row[countKey] ~= nil then
        return integer(row[countKey], 0) and row[countKey] or nil
    end
    if row[legacyKey] == nil or row[legacyKey] == false then return 0 end
    if row[legacyKey] == true then return 1 end
    return nil
end

local function current(raw, id)
    local proof = type(raw) == "table" and raw.heistBoardProof
    local usage = type(raw) == "table" and raw.sabotageUsageProof
    local player = type(raw) == "table" and raw.localUserIdProof
    local native = type(raw) == "table" and raw.native
    local board = type(proof) == "table" and proof.board
    if type(proof) ~= "table" or type(usage) ~= "table"
        or type(player) ~= "table"
        or type(native) ~= "table" or native.fullSync ~= true
        or proof.account ~= raw.account
        or proof.capturedAt ~= raw.capturedAt
        or usage.account ~= raw.account
        or usage.capturedAt ~= raw.capturedAt
        or player.account ~= raw.account
        or player.capturedAt ~= raw.capturedAt
        or not integer(player.userId, 1)
        or proof.query ~= nil or type(board) ~= "table"
        or board.ok ~= true or type(board.rows) ~= "table"
        or not integer(board.serverNow, 0)
        or not integer(board.favorsLeft, 0)
        or not integer(usage.day, 0)
        or not integer(usage.attempts, 0)
        or usage.day ~= math.floor(board.serverNow / 86400) then
        return nil
    end
    for _, row in ipairs(board.rows) do
        if type(row) == "table" and row.id == id then
            return board, row, usage, player, native
        end
    end
    return nil
end

function SabotageEvidence.capture(proposal, before)
    local intent = type(proposal) == "table" and proposal.intent
    if type(proposal) ~= "table" or proposal.feature ~= "sabotage"
        or type(intent) ~= "table" or intent.kind ~= "heistSabotage"
        or not rowId(intent.rowId) or not key(intent.heistId)
        or not integer(intent.ownerId, 1)
        or not integer(intent.selfId, 1)
        or not integer(intent.sabosBefore, 0)
        or not integer(intent.favorsBefore, 0)
        or not integer(intent.expectedFavorCost, 0)
        or not integer(intent.expectedEnergyCost, 0)
        or not integer(intent.serverDay, 0)
        or not integer(intent.usageAttemptsBefore, 0)
        or intent.needsSequence ~= true
        or type(before) ~= "table" or not matching(proposal, before)
        or proposal.revision ~= before.revision then
        return nil, "Sabotage baseline mismatch"
    end
    local board, row, usage, player, native =
        current(before, intent.rowId)
    if not board or row.heistId ~= intent.heistId
        or row.ownerId ~= intent.ownerId
        or player.userId ~= intent.selfId
        or row.ownerId == player.userId
        or row.friend == true or row.famRel == "family"
        or used(row, "helpsUsed", "helped") ~= 0
        or used(row, "sabosUsed", "sabotaged")
            ~= intent.sabosBefore
        or not integer(board.saboMaxPerHeist, 1)
        or intent.sabosBefore >= board.saboMaxPerHeist
        or board.favorsLeft ~= intent.favorsBefore
        or board.saboFavorCost ~= intent.expectedFavorCost
        or board.saboEnergyCost ~= intent.expectedEnergyCost
        or board.favorsLeft - board.saboFavorCost < 5
        or usage.day ~= intent.serverDay
        or usage.attempts ~= intent.usageAttemptsBefore
        or usage.attempts >= 5
        or not integer(row.endsAt, board.serverNow)
        or row.endsAt <= board.serverNow
        or not integer(native.level, 1)
        or type(native.pools) ~= "table"
        or not integer(native.pools.energy, 0)
        or native.pools.energy - board.saboEnergyCost < 10 then
        return nil, "Selected sabotage row or resources changed"
    end
    local eligibleLevel
    if type(before.heistCatalog) == "table" then
        for _, entry in ipairs(before.heistCatalog) do
            if type(entry) == "table"
                and entry.id == intent.heistId then
                eligibleLevel = entry.level
                break
            end
        end
    end
    if not integer(eligibleLevel, 1)
        or eligibleLevel > native.level then
        return nil, "Sabotage catalog changed"
    end
    return { session = proposal.session, account = proposal.account,
        place = proposal.place, release = proposal.release,
        revision = proposal.revision, rowId = intent.rowId,
        heistId = intent.heistId, ownerId = intent.ownerId,
        selfId = intent.selfId, sabosBefore = intent.sabosBefore,
        favorsBefore = intent.favorsBefore,
        favorCost = intent.expectedFavorCost,
        serverDay = intent.serverDay,
        usageAttemptsBefore = intent.usageAttemptsBefore }, nil
end

function SabotageEvidence.evaluate(proposal, beforeHeader, after,
    reply, baseline)
    if type(proposal) ~= "table" or type(beforeHeader) ~= "table"
        or type(after) ~= "table" or type(reply) ~= "table"
        or type(baseline) ~= "table"
        or not matching(proposal, beforeHeader)
        or not matching(proposal, after)
        or not matching(proposal, baseline)
        or proposal.revision ~= baseline.revision
        or beforeHeader.revision ~= baseline.revision then
        return "pending"
    end
    local board, row, usage, player = current(after, baseline.rowId)
    if not board then return "pending" end
    local advanced = type(after.revision) == "number"
        and after.revision > baseline.revision
        and player.userId == baseline.selfId
        and row.ownerId == baseline.ownerId
        and row.heistId == baseline.heistId
        and used(row, "sabosUsed", "sabotaged")
            == baseline.sabosBefore + 1
        and board.favorsLeft == baseline.favorsBefore
            - baseline.favorCost
        and usage.day == baseline.serverDay
        and usage.attempts >= baseline.usageAttemptsBefore + 1
    if reply.ok == false then return advanced and "pending" or "rejected" end
    if reply.ok == true and advanced then return "confirmed" end
    return "pending"
end

return SabotageEvidence
