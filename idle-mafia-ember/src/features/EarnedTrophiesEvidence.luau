-- Selected Trophy must leave ready list and appear in owned inventory.
local EarnedTrophiesEvidence = {}


local function matching(a, b)
    for _, field in ipairs({ "session", "account", "place", "release" }) do
        if type(a[field]) ~= "string" or #a[field] == 0
            or a[field] ~= b[field] then return false end
    end
    return true
end

local function nonconsuming(raw, id)
    if type(raw.trophyCatalog) ~= "table" then return false end
    local found
    for _, item in ipairs(raw.trophyCatalog) do
        if type(item) ~= "table" then return false end
        if item.id == id then
            if found then return false end
            found = item
        end
    end
    return found ~= nil and (found.kind == "trophy"
        or found.kind == "border" or found.kind == "background")
        and found.tradeIn ~= true
        and found.requiresItems ~= true
end

local function state(raw, id)
    local native = type(raw) == "table" and raw.native
    local derived = type(native) == "table" and native.derived
    if type(native) ~= "table" or native.fullSync ~= true
        or type(derived) ~= "table" or type(derived.trophyReady) ~= "table"
        or type(native.inventory) ~= "table"
        or type(native.inventoryBound) ~= "table"
        or type(native.collection) ~= "table"
        or type(native.collectionBound) ~= "table" then return nil end
    local ready = false
    for _, value in ipairs(derived.trophyReady) do
        if type(value) ~= "string" then return nil end
        if value == id then ready = true end
    end
    local owned = 0
    for _, field in ipairs({ "inventory", "inventoryBound",
        "collection", "collectionBound" }) do
        local count = native[field][id] or 0
        if type(count) ~= "number" or count ~= count
            or count < 0 or count >= math.huge
            or count % 1 ~= 0 then return nil end
        owned = owned + count
    end
    return ready, owned
end

function EarnedTrophiesEvidence.capture(proposal, before)
    local intent = type(proposal) == "table" and proposal.intent
    if type(proposal) ~= "table" or proposal.feature ~= "trophies"
        or type(intent) ~= "table" or intent.kind ~= "earnedTrophyClaim"
        or type(intent.targetId) ~= "string"
        or #intent.targetId == 0 or #intent.targetId > 120
        or type(before) ~= "table" or not matching(proposal, before)
        or proposal.revision ~= before.revision
        or intent.catalogKey ~= before.catalogKey
        or not nonconsuming(before, intent.targetId) then
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
        and ready == false and owned == 1
    if reply.ok == false then return advanced and "pending" or "rejected" end
    if reply.ok == true and advanced then return "confirmed" end
    return "pending"
end

return EarnedTrophiesEvidence
