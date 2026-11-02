-- A newer exact owned count proves one selected ordinary build.
local PropertiesEvidence = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge and value % 1 == 0
end

local function balance(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge
end

local function matching(a, b, restart)
    for _, field in ipairs({ "session", "account", "place", "release" }) do
        if type(a[field]) ~= "string" or #a[field] == 0
            or type(b[field]) ~= "string" or #b[field] == 0
            or (not restart or field ~= "session") and a[field] ~= b[field] then return false end
    end
    return true
end

local function owned(raw, id, key)
    local native = type(raw) == "table" and raw.native
    if type(native) ~= "table" or native.fullSync ~= true
        or raw.catalogKey ~= key
        or type(native.properties) ~= "table" then return nil end
    local record = native.properties[id]
    if record ~= nil and type(record) ~= "table" then return nil end
    if record ~= nil and record.owned == nil then return nil end
    local count = record and record.owned or 0
    return integer(count, 0) and count or nil
end

function PropertiesEvidence.capture(proposal, before)
    local intent = type(proposal) == "table" and proposal.intent
    if type(proposal) ~= "table" or proposal.feature ~= "properties"
        or type(intent) ~= "table" or intent.kind ~= "propertyBuild"
        or type(intent.propId) ~= "string" or #intent.propId == 0
        or not integer(intent.beforeOwned, 0)
        or not integer(intent.expectedCost, 1)
        or type(proposal.resources) ~= "table"
        or proposal.resources.cash ~= intent.expectedCost
        or not integer(intent.cashReserve, 0)
        or intent.optionalSlot ~= nil
        or type(intent.catalogKey) ~= "string" or #intent.catalogKey == 0
        or type(before) ~= "table" or not matching(proposal, before)
        or proposal.revision ~= before.revision then
        return nil, "Property build baseline mismatch"
    end
    local count = owned(before, intent.propId, intent.catalogKey)
    if count ~= intent.beforeOwned then
        return nil, "Selected Property count changed"
    end
    local catalog = before.propertyCatalog
    local found, otherOwned, seen = nil, {}, {}
    if type(catalog) == "table" then
        for _, row in ipairs(catalog) do
            if type(row) ~= "table" or type(row.id) ~= "string"
                or #row.id == 0 or seen[row.id] then
                return nil, "Incomplete Property catalog"
            end
            seen[row.id] = true
            local rowOwned = owned(before, row.id, intent.catalogKey)
            if rowOwned == nil then return nil, "Incomplete Property ownership" end
            if row.id == intent.propId then found = row
            else otherOwned[row.id] = rowOwned end
        end
    end
    for id in pairs(before.native.properties) do
        if not seen[id] then return nil, "Unknown owned Property" end
    end
    local proof = before.propertyProof
    if type(found) ~= "table" or type(proof) ~= "table"
        or not integer(found.baseCost, 1)
        or not integer(found.level, 1)
        or not integer(before.native.level, found.level)
        or proof.account ~= proposal.account
        or proof.capturedAt ~= before.capturedAt
        or type(proof.buildDiscount) ~= "number"
        or proof.buildDiscount ~= proof.buildDiscount
        or proof.buildDiscount < 0 or proof.buildDiscount > 0.25
        or not integer(proof.occupied, 0)
        or not integer(proof.capacity, 1)
        or proof.occupied >= proof.capacity
        or not balance(before.native.cash,
            intent.expectedCost + intent.cashReserve) then
        return nil, "Selected Property is no longer buildable"
    end
    local base = math.floor(found.baseCost * 1.18 ^ count + 0.5)
    local quoted = proof.buildDiscount == 0 and base
        or math.max(1, math.floor(base * (1 - proof.buildDiscount) + 0.5))
    if quoted ~= intent.expectedCost then
        return nil, "Selected Property quote changed"
    end
    return { session = proposal.session, account = proposal.account,
        place = proposal.place, release = proposal.release,
        revision = proposal.revision, propId = intent.propId,
        beforeOwned = count, beforeCash = before.native.cash,
        expectedCost = intent.expectedCost, otherOwned = otherOwned,
        catalogKey = intent.catalogKey }, nil
end

local function reconcile(proposal, beforeHeader, after,
    reply, baseline, restart)
    if type(proposal) ~= "table" or type(beforeHeader) ~= "table"
        or type(after) ~= "table" or type(reply) ~= "table"
        or type(baseline) ~= "table"
        or not matching(proposal, beforeHeader)
        or not matching(proposal, after, restart)
        or not matching(proposal, baseline)
        or proposal.revision ~= baseline.revision
        or beforeHeader.revision ~= baseline.revision then
        return "pending"
    end
    local count = owned(after, baseline.propId, baseline.catalogKey)
    if count == nil then return "pending" end
    local native = after.native
    if type(native) ~= "table" or not balance(native.cash, 0)
        or type(native.properties) ~= "table"
        or type(baseline.otherOwned) ~= "table"
        or not balance(baseline.beforeCash, baseline.expectedCost)
        or not integer(baseline.expectedCost, 1) then return "pending" end
    local unchanged = true
    for id, prior in pairs(baseline.otherOwned) do
        if owned(after, id, baseline.catalogKey) ~= prior then
            unchanged = false
            break
        end
    end
    if unchanged then
        for id in pairs(native.properties) do
            if id ~= baseline.propId
                and baseline.otherOwned[id] == nil then
                unchanged = false
                break
            end
        end
    end
    if restart and (type(beforeHeader.native) ~= "table"
        or not balance(beforeHeader.native.serverNow, 0) or not balance(native.serverNow, 0)
        or native.serverNow < beforeHeader.native.serverNow) then return "pending" end
    local advanced = (restart or type(after.revision) == "number"
        and after.revision > baseline.revision)
        and count == baseline.beforeOwned + 1
        and native.cash == baseline.beforeCash - baseline.expectedCost
        and unchanged
    if reply.ok == false then return advanced and "pending" or "rejected" end
    if reply.ok == true and advanced then return "confirmed" end
    return "pending"
end

function PropertiesEvidence.evaluate(proposal, beforeHeader, after, reply, baseline)
    return reconcile(proposal, beforeHeader, after, reply, baseline, false)
end
local function same(a, b)
    if type(a) ~= type(b) then return false end
    if type(a) ~= "table" then return a == b end
    for key, value in pairs(a) do if not same(value, b[key]) then return false end end
    for key in pairs(b) do if a[key] == nil then return false end end
    return true
end
function PropertiesEvidence.recoverSaved(data, after)
    if type(data) ~= "table" or type(data.baseline) ~= "table" then return nil end
    local expected = PropertiesEvidence.capture(data.proposal, data.before)
    if not expected or not same(expected, data.baseline) then return nil end
    for key, value in pairs(data.proposal.resources) do
        if key ~= "cash" and value ~= 0 then return nil end
    end
    local result = reconcile(data.proposal, data.before, after, data.reply, expected, true)
    return (result == "confirmed" or result == "rejected") and result or nil
end

return PropertiesEvidence
