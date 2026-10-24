-- A newer exact owned count proves one selected ordinary build.
local PropertiesEvidence = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge and value % 1 == 0
end

local function matching(a, b)
    for _, field in ipairs({ "session", "account", "place", "release" }) do
        if type(a[field]) ~= "string" or #a[field] == 0
            or a[field] ~= b[field] then return false end
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
    local found
    if type(catalog) == "table" then
        for _, row in ipairs(catalog) do
            if type(row) == "table" and row.id == intent.propId then
                found = row
                break
            end
        end
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
        or not integer(before.native.cash,
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
        beforeOwned = count, catalogKey = intent.catalogKey }, nil
end

function PropertiesEvidence.evaluate(proposal, beforeHeader, after,
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
    local count = owned(after, baseline.propId, baseline.catalogKey)
    if count == nil then return "pending" end
    local advanced = type(after.revision) == "number"
        and after.revision > baseline.revision
        and count == baseline.beforeOwned + 1
    if reply.ok == false then return advanced and "pending" or "rejected" end
    if reply.ok == true and advanced then return "confirmed" end
    return "pending"
end

return PropertiesEvidence
