-- Selected Trophy must leave ready list and appear in owned inventory.
local EarnedTrophiesEvidence = {}

local allowed = { t_eldersignet = true, t_grudgeledger = true }

local function matching(a, b)
    for _, field in ipairs({ "session", "account", "place", "release" }) do
        if type(a[field]) ~= "string" or #a[field] == 0
            or a[field] ~= b[field] then return false end
    end
    return true
end

local function state(raw, id)
    local native = type(raw) == "table" and raw.native
    local derived = type(native) == "table" and native.derived
    if type(native) ~= "table" or native.fullSync ~= true
        or type(derived) ~= "table" or type(derived.trophyReady) ~= "table"
        or type(native.inventory) ~= "table"
        or (native.inventoryBound ~= nil
            and type(native.inventoryBound) ~= "table") then return nil end
    local ready = false
    for _, value in ipairs(derived.trophyReady) do
        if type(value) ~= "string" then return nil end
        if value == id then ready = true end
    end
    local loose, bound = native.inventory[id] or 0,
        (native.inventoryBound or {})[id] or 0
    if type(loose) ~= "number" or type(bound) ~= "number"
        or loose < 0 or bound < 0 or loose % 1 ~= 0
        or bound % 1 ~= 0 then return nil end
    return ready, loose + bound
end

function EarnedTrophiesEvidence.capture(proposal, before)
    local intent = type(proposal) == "table" and proposal.intent
    if type(proposal) ~= "table" or proposal.feature ~= "trophies"
        or type(intent) ~= "table" or intent.kind ~= "earnedTrophyClaim"
        or not allowed[intent.targetId]
        or type(before) ~= "table" or not matching(proposal, before)
        or proposal.revision ~= before.revision
        or intent.catalogKey ~= before.catalogKey then
        return nil, "Earned Trophy baseline mismatch"
    end
    local ready, owned = state(before, intent.targetId)
    if ready ~= true or owned ~= 0 then
        return nil, "Selected earned Trophy is not ready and unowned"
    end
    return { session = proposal.session, account = proposal.account,
        place = proposal.place, release = proposal.release,
        revision = proposal.revision, targetId = intent.targetId,
        catalogKey = intent.catalogKey }, nil
end

function EarnedTrophiesEvidence.evaluate(proposal, beforeHeader, after,
    reply, baseline)
    if type(proposal) ~= "table" or type(beforeHeader) ~= "table"
        or type(after) ~= "table" or type(reply) ~= "table"
        or type(baseline) ~= "table"
        or not matching(proposal, beforeHeader)
        or not matching(proposal, after)
        or not matching(proposal, baseline)
        or proposal.revision ~= baseline.revision
        or beforeHeader.revision ~= baseline.revision
        or type(proposal.intent) ~= "table"
        or proposal.intent.targetId ~= baseline.targetId
        or proposal.intent.catalogKey ~= baseline.catalogKey
        or after.catalogKey ~= baseline.catalogKey then return "pending" end
    local ready, owned = state(after, baseline.targetId)
    if ready == nil then return "pending" end
    local advanced = type(after.revision) == "number"
        and after.revision > baseline.revision
        and ready == false and owned > 0
    if reply.ok == false then return advanced and "pending" or "rejected" end
    if reply.ok == true and advanced then return "confirmed" end
    return "pending"
end

return EarnedTrophiesEvidence
