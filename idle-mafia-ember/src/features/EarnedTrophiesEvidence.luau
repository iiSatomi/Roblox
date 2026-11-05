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
    local ready, seen, entries = false, {}, 0
    local size = #derived.trophyReady
    if size > 256 then return nil end
    for key, value in pairs(derived.trophyReady) do
        if type(key) ~= "number" or key % 1 ~= 0 or key < 1 or key > size
            or type(value) ~= "string" or #value == 0 or seen[value] then return nil end
        seen[value], entries = true, entries + 1
        if value == id then ready = true end
    end
    if entries ~= size then return nil end
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

local function equal(a, b)
    if type(a) ~= type(b) then return false end
    if type(a) ~= "table" then return a == b end
    for key, value in pairs(a) do if not equal(value, b[key]) then return false end end
    for key in pairs(b) do if a[key] == nil then return false end end
    return true
end
local function number(value)
    return type(value) == "number" and value == value and value >= 0
        and value <= 9007199254740991
end
local function custody(before, after, target)
    local gain = 0
    for _, field in ipairs({"inventory", "inventoryBound", "collection", "collectionBound"}) do
        local prior, current = before[field], after[field]
        if type(prior) ~= "table" or type(current) ~= "table" then return false end
        local ids = {}
        for _, map in ipairs({prior, current}) do
            for id, count in pairs(map) do
                if type(id) ~= "string" or #id == 0 or not number(count)
                    or count % 1 ~= 0 then return false end
                ids[id] = true
            end
        end
        for id in pairs(ids) do
            local delta = (current[id] or 0) - (prior[id] or 0)
            if id == target then
                if delta < 0 then return false end
                gain = gain + delta
            elseif delta ~= 0 then return false end
        end
    end
    return gain == 1
end

-- Reconstruct only the original saved positive receipt. Observation never
-- invokes another claim or adopts an award with changed item custody.
function EarnedTrophiesEvidence.recoverSaved(data, after)
    if type(data) ~= "table" or type(data.reply) ~= "table"
        or data.reply.ok ~= true or data.reply.pending == true
        or data.reply.code == "pending" or data.reply.code == "no_pending"
        or data.reply.code == "rate_limited" or data.reply.code == "presence"
        or data.reply.code == "busy" or type(after) ~= "table" then return nil end
    local baseline = EarnedTrophiesEvidence.capture(data.proposal, data.before)
    if not baseline or not equal(baseline, data.baseline) then return nil end
    local proposal, before = data.proposal, data.before
    if type(proposal.resources) ~= "table"
        or proposal.actionKey ~= "earnedTrophy:" .. #baseline.catalogKey .. ":"
            .. baseline.catalogKey .. ":" .. baseline.targetId then return nil end
    for _, amount in pairs(proposal.resources) do if amount ~= 0 then return nil end end
    for _, field in ipairs({"account", "place", "release"}) do
        if after[field] ~= proposal[field] then return nil end
    end
    local native, prior = after.native, before.native
    if type(after.session) ~= "string" or #after.session == 0
        or type(native) ~= "table" or type(prior) ~= "table"
        or not number(prior.serverNow) or not number(native.serverNow)
        or native.serverNow < prior.serverNow
        or after.catalogKey ~= baseline.catalogKey
        or not nonconsuming(after, baseline.targetId) then return nil end
    if after.session == baseline.session then
        if not number(after.revision) or after.revision % 1 ~= 0
            or after.revision <= baseline.revision
            or not number(before.capturedAt) or not number(after.capturedAt)
            or after.capturedAt < before.capturedAt then return nil end
    elseif native.serverNow <= prior.serverNow then return nil end
    local ready, owned = state(after, baseline.targetId)
    if ready ~= false or owned ~= 1 or not custody(prior, native, baseline.targetId) then return nil end
    return "confirmed"
end

return EarnedTrophiesEvidence
