-- Exact personal row-use increment plus Favor debit proves help.
local FavorHelpEvidence = {}

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

local function personalCount(row)
    if row.helpsUsed ~= nil then
        return integer(row.helpsUsed, 0) and row.helpsUsed or nil
    end
    if row.helped == true then return 1 end
    if row.helped == nil or row.helped == false then return 0 end
    return nil
end

local function current(raw, id)
    local proof = type(raw) == "table" and raw.heistBoardProof
    local usage = type(raw) == "table" and raw.favorUsageProof
    local board = type(proof) == "table" and proof.board
    if type(proof) ~= "table" or type(usage) ~= "table"
        or proof.account ~= raw.account
        or proof.capturedAt ~= raw.capturedAt
        or usage.account ~= raw.account
        or usage.capturedAt ~= raw.capturedAt
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
            return board, row, usage
        end
    end
    return nil
end

function FavorHelpEvidence.capture(proposal, before)
    local intent = type(proposal) == "table" and proposal.intent
    if type(proposal) ~= "table" or proposal.feature ~= "favors"
        or type(intent) ~= "table" or intent.kind ~= "favorHelp"
        or not rowId(intent.rowId) or not key(intent.heistId)
        or not integer(intent.ownerId, 1)
        or not integer(intent.helpsBefore, 0)
        or not integer(intent.favorsBefore, 0)
        or not integer(intent.expectedFavorCost, 0)
        or not integer(intent.expectedEnergyCost, 0)
        or not integer(intent.serverDay, 0)
        or not integer(intent.usageAttemptsBefore, 0)
        or intent.needsSequence ~= true
        or type(before) ~= "table" or not matching(proposal, before)
        or proposal.revision ~= before.revision then
        return nil, "Favor help baseline mismatch"
    end
    local board, row, usage = current(before, intent.rowId)
    if not board or row.heistId ~= intent.heistId
        or row.ownerId ~= intent.ownerId
        or personalCount(row) ~= intent.helpsBefore
        or board.favorsLeft ~= intent.favorsBefore
        or board.helpFavorCost ~= intent.expectedFavorCost
        or board.helpEnergyCost ~= intent.expectedEnergyCost
        or usage.day ~= intent.serverDay
        or usage.attempts ~= intent.usageAttemptsBefore
        or usage.attempts >= 5
        or board.favorsLeft - board.helpFavorCost < 5
        or type(before.native) ~= "table"
        or type(before.native.pools) ~= "table"
        or not integer(before.native.pools.energy, 0)
        or before.native.pools.energy - board.helpEnergyCost < 10
        or not integer(board.helpMaxPerHeist, 1)
        or intent.helpsBefore >= board.helpMaxPerHeist
        or not integer(row.endsAt, board.serverNow)
        or row.endsAt <= board.serverNow
        or not (row.friend == true or row.famRel == "family")
        or (row.sabosUsed or (row.sabotaged and 1 or 0)) ~= 0 then
        return nil, "Selected Favor row changed"
    end
    return { session = proposal.session, account = proposal.account,
        place = proposal.place, release = proposal.release,
        revision = proposal.revision,
        rowId = intent.rowId, heistId = intent.heistId,
        ownerId = intent.ownerId,
        helpsBefore = intent.helpsBefore,
        favorsBefore = intent.favorsBefore,
        favorCost = intent.expectedFavorCost,
        serverDay = intent.serverDay,
        usageAttemptsBefore = intent.usageAttemptsBefore }, nil
end

function FavorHelpEvidence.evaluate(proposal, beforeHeader, after,
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
    local board, row, usage = current(after, baseline.rowId)
    if not board then return "pending" end
    local advanced = type(after.revision) == "number"
        and after.revision > baseline.revision
        and row.heistId == baseline.heistId
        and row.ownerId == baseline.ownerId
        and personalCount(row) == baseline.helpsBefore + 1
        and board.favorsLeft == baseline.favorsBefore
            - baseline.favorCost
        and usage.day == baseline.serverDay
        and usage.attempts >= baseline.usageAttemptsBefore + 1
    if reply.ok == false then return advanced and "pending" or "rejected" end
    if reply.ok == true and advanced then return "confirmed" end
    return "pending"
end

return FavorHelpEvidence
