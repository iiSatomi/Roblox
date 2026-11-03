-- Only exact reply run identity plus newer board can confirm a start.
local HeistStartEvidence = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge and value % 1 == 0
end

local function balance(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge
end

local function key(value)
    return type(value) == "string" and #value > 0
end

local function matching(a, b)
    for _, field in ipairs({ "session", "account", "place", "release" }) do
        if not key(a[field]) or a[field] ~= b[field] then return false end
    end
    return true
end

local function board(raw)
    local proof = type(raw) == "table" and raw.heistBoardProof
    local native = type(raw) == "table" and raw.native
    if type(proof) ~= "table" or type(proof.board) ~= "table"
        or type(native) ~= "table" or native.fullSync ~= true
        or proof.account ~= raw.account
        or proof.capturedAt ~= raw.capturedAt
        or proof.query ~= nil or proof.board.ok ~= true then
        return nil
    end
    return proof.board
end

function HeistStartEvidence.capture(proposal, before)
    local intent = type(proposal) == "table" and proposal.intent
    if type(proposal) ~= "table" or proposal.feature ~= "heists"
        or type(intent) ~= "table" or intent.kind ~= "heistStart"
        or not key(intent.heistId)
        or not integer(intent.expectedStake, 0)
        or not integer(intent.expectedEnergy, 0)
        or not integer(intent.startsBefore, 1)
        or not integer(intent.serverDay, 0)
        or not key(intent.catalogKey)
        or intent.needsSequence ~= true
        or type(before) ~= "table" or not matching(proposal, before)
        or proposal.revision ~= before.revision
        or before.catalogKey ~= intent.catalogKey then
        return nil, "Heist start baseline mismatch"
    end
    local current = board(before)
    local native = before.native
    if not current or current.mine ~= nil or current.result ~= nil
        or current.startsLeft ~= intent.startsBefore
        or current.bustWait ~= 0
        or not balance(current.serverNow, 0)
        or math.floor(current.serverNow / 86400) ~= intent.serverDay
        or not integer(native.level, 1)
        or not balance(native.cash, intent.expectedStake)
        or type(native.pools) ~= "table"
        or not integer(native.pools.energy, intent.expectedEnergy) then
        return nil, "Heist board or resources changed"
    end
    local found
    if type(before.heistCatalog) == "table" then
        for _, row in ipairs(before.heistCatalog) do
            if type(row) == "table" and row.id == intent.heistId then
                found = row
                break
            end
        end
    end
    if type(found) ~= "table" or found.stake ~= intent.expectedStake
        or found.energy ~= intent.expectedEnergy
        or not integer(found.level, 1)
        or found.level > native.level then
        return nil, "Selected Heist quote changed"
    end
    return { session = proposal.session, account = proposal.account,
        place = proposal.place, release = proposal.release,
        revision = proposal.revision, heistId = intent.heistId,
        startsBefore = intent.startsBefore,
        serverDay = intent.serverDay, catalogKey = before.catalogKey,
        cash = native.cash, energy = native.pools.energy, level = native.level,
        capturedAt = before.capturedAt, serverNow = current.serverNow,
        nativeServerNow = native.serverNow }, nil
end

function HeistStartEvidence.evaluate(proposal, beforeHeader, after,
    reply, baseline)
    if type(proposal) ~= "table" or type(beforeHeader) ~= "table"
        or type(after) ~= "table" or type(reply) ~= "table"
        or type(baseline) ~= "table"
        or not matching(proposal, beforeHeader)
        or not matching(proposal, after)
        or not matching(proposal, baseline)
        or proposal.revision ~= baseline.revision
        or beforeHeader.revision ~= baseline.revision
        or reply.pending == true or reply.code == "pending"
        or reply.code == "no_pending" or reply.code == "rate_limited"
        or reply.code == "presence" then
        return "pending"
    end
    local current = board(after)
    if not current then return "pending" end
    local mine = current.mine
    local advanced = type(after.revision) == "number"
        and after.revision > baseline.revision
        and current.startsLeft == baseline.startsBefore - 1
        and type(mine) == "table" and key(mine.id)
        and mine.heistId == baseline.heistId
        and key(reply.runId) and reply.runId == mine.id
    if reply.ok == false then
        local native = after.native
        -- An unmatched run is not proof of failure: partial state, a different
        -- run, or any resource change leaves the sent action unresolved.
        local unchanged = integer(baseline.revision, 0)
            and integer(after.revision, 0) and after.revision > baseline.revision
            and balance(baseline.capturedAt, 0) and balance(after.capturedAt, 0)
            and after.capturedAt >= baseline.capturedAt
            and balance(baseline.serverNow, 0) and balance(current.serverNow, 0)
            and current.serverNow >= baseline.serverNow
            and math.floor(current.serverNow / 86400) == baseline.serverDay
            and balance(baseline.nativeServerNow, 0) and balance(native.serverNow, 0)
            and native.serverNow >= baseline.nativeServerNow
            and math.abs(current.serverNow - native.serverNow) <= 2
            and key(baseline.catalogKey) and after.catalogKey == baseline.catalogKey
            and current.mine == nil and current.result == nil
            and current.startsLeft == baseline.startsBefore and current.bustWait == 0
            and balance(baseline.cash, 0) and native.cash == baseline.cash
            and integer(baseline.energy, 0) and type(native.pools) == "table"
            and native.pools.energy == baseline.energy
            and integer(baseline.level, 1) and native.level == baseline.level
        return unchanged and "rejected" or "pending"
    end
    if reply.ok == true and advanced then return "confirmed" end
    return "pending"
end

return HeistStartEvidence
